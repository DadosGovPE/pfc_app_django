from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import CommentForm, ProductForm
from .models import Like, Product, ProductImage


def _can_publish(user):
    return (user.origem or "").strip().upper() == "SEPLAG"


def _visible_products(user):
    return (
        Product.active()
        .select_related("creator")
        .prefetch_related("images")
        .annotate(
            like_count=Count("likes", distinct=True),
            comment_count=Count("comments", distinct=True),
            liked_by_me=Exists(Like.objects.filter(product_id=OuterRef("pk"), user=user)),
        )
    )


@login_required(login_url="login")
def catalog(request):
    query = request.GET.get("q", "").strip()
    products = _visible_products(request.user)
    if query:
        products = products.filter(Q(title__icontains=query) | Q(description__icontains=query))
    products = products.order_by("-like_count", "-created_at", "-pk")
    page = Paginator(products, 12).get_page(request.GET.get("page"))
    return render(request, "classificados/catalog.html", {
        "page": page,
        "query": query,
        "can_publish": _can_publish(request.user),
        "hot_likes": getattr(settings, "CLASSIFICADOS_HOT_LIKES", 5),
    })


@login_required(login_url="login")
def product_create(request):
    if not _can_publish(request.user):
        return HttpResponseForbidden("Apenas usuários com origem SEPLAG podem anunciar produtos.")
    form = ProductForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            product = form.save(commit=False)
            product.creator = request.user
            product.save()
            ProductImage.objects.bulk_create([
                ProductImage(product=product, image=image, position=position)
                for position, image in enumerate(form.cleaned_data["photos"])
            ])
        messages.success(request, "Produto publicado por dois meses.")
        return redirect("classificados:product_detail", pk=product.pk)
    return render(request, "classificados/product_form.html", {"form": form})


@login_required(login_url="login")
def product_detail(request, pk):
    product = get_object_or_404(_visible_products(request.user), pk=pk)
    comments = product.comments.select_related("author").all()
    return render(request, "classificados/product_detail.html", {
        "product": product,
        "comments": comments,
        "form": CommentForm(),
        "hot_likes": getattr(settings, "CLASSIFICADOS_HOT_LIKES", 5),
    })


@login_required(login_url="login")
@require_POST
def toggle_like(request, pk):
    product = get_object_or_404(Product.active(), pk=pk)
    like, created = Like.objects.get_or_create(product=product, user=request.user)
    if not created:
        like.delete()
    return redirect("classificados:product_detail", pk=pk)


@login_required(login_url="login")
@require_POST
def add_comment(request, pk):
    product = get_object_or_404(Product.active(), pk=pk)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.product = product
        comment.author = request.user
        comment.save()
        return redirect("classificados:product_detail", pk=pk)
    detail = get_object_or_404(_visible_products(request.user), pk=pk)
    return render(request, "classificados/product_detail.html", {
        "product": detail,
        "comments": detail.comments.select_related("author").all(),
        "form": form,
        "hot_likes": getattr(settings, "CLASSIFICADOS_HOT_LIKES", 5),
    }, status=400)
