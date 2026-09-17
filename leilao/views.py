from datetime import timedelta
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import (
    BooleanField,
    Case,
    Count,
    DateTimeField,
    Max,
    Prefetch,
    Q,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import ProductForm
from .models import Bid, Product, ProductImage
from .services import place_next_bid


def _catalog_queryset():
    now = timezone.now()
    hot_since = now - timedelta(
        hours=getattr(settings, "LEILAO_HOT_BID_WINDOW_HOURS", 24)
    )
    hot_threshold = getattr(settings, "LEILAO_HOT_BID_THRESHOLD", 5)
    return (
        Product.objects.select_related("auction", "creator")
        .prefetch_related(
            "images",
            Prefetch("bids", queryset=Bid.objects.select_related("bidder")),
        )
        .filter(auction__is_published=True)
        .annotate(
            recent_bid_count=Count(
                "bids", filter=Q(bids__created_at__gte=hot_since)
            ),
            last_bid_at=Max("bids__created_at"),
        )
        .annotate(
            last_activity_at=Coalesce(
                "last_bid_at", "created_at", output_field=DateTimeField()
            ),
            has_bids=Case(
                When(last_bid_at__isnull=False, then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            ),
            is_hot=Case(
                When(
                    recent_bid_count__gte=hot_threshold,
                    starts_at__lte=now,
                    ends_at__gt=now,
                    auction__starts_at__lte=now,
                    auction__ends_at__gt=now,
                    then=Value(True),
                ),
                default=Value(False),
                output_field=BooleanField(),
            ),
        )
        .order_by("-is_hot", "-last_activity_at", "-has_bids", "-created_at", "-pk")
    )


@login_required(login_url="login")
def catalog(request):
    products = _catalog_queryset()
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "all")
    now = timezone.now()
    if query:
        products = products.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(auction__name__icontains=query)
        )
    active_filter = Q(
        starts_at__lte=now,
        ends_at__gt=now,
        auction__starts_at__lte=now,
        auction__ends_at__gt=now,
    )
    if status == "active":
        products = products.filter(active_filter)
    elif status == "ending":
        products = products.filter(
            active_filter,
            ends_at__lte=now + timedelta(hours=6),
        )
    elif status == "ended":
        products = products.filter(
            Q(ends_at__lte=now) | Q(auction__ends_at__lte=now)
        )
    elif status != "all":
        status = "all"

    active_count = _catalog_queryset().filter(active_filter).count()
    context = {
        "products": products,
        "query": query,
        "status": status,
        "now": now,
        "active_count": active_count,
    }
    if request.headers.get("HX-Request") == "true":
        return render(request, "leilao/partials/product_grid.html", context)
    return render(request, "leilao/catalog.html", context)


@login_required(login_url="login")
def product_create(request):
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.creator = request.user
            product.save()
            for position, image in enumerate(form.cleaned_data["photos"]):
                ProductImage.objects.create(
                    product=product, image=image, position=position
                )
            messages.success(
                request, "Produto publicado. A contagem do leilão já começou."
            )
            return redirect("leilao:catalog")
    else:
        form = ProductForm()
    return render(request, "leilao/product_form.html", {"form": form})


@login_required(login_url="login")
@require_POST
def place_bid(request, pk):
    bid_error = None
    bid_success = None
    try:
        bid = place_next_bid(product_id=pk, bidder=request.user)
        bid_success = f"Lance de R$ {bid.amount:,.2f} confirmado."
        bid_success = bid_success.replace(",", "X").replace(".", ",").replace("X", ".")
    except Product.DoesNotExist:
        return HttpResponse("Produto não encontrado.", status=404)
    except ValidationError as exc:
        bid_error = exc.messages[0]

    products = _catalog_queryset()
    product = products.get(pk=pk)
    response = render(
        request,
        "leilao/partials/bid_update.html",
        {
            "product": product,
            "highlight_product_id": pk,
            "bid_error": bid_error,
            "bid_success": bid_success,
            "now": timezone.now(),
        },
    )
    response["HX-Trigger-After-Settle"] = json.dumps(
        {
            "catalogReordered": {
                "order": list(products.values_list("pk", flat=True))
            }
        }
    )
    return response


@login_required(login_url="login")
def my_products(request):
    products = _catalog_queryset().filter(creator=request.user)
    return render(
        request,
        "leilao/my_products.html",
        {"products": products, "now": timezone.now()},
    )
