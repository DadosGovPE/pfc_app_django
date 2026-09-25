import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.http import HttpResponseForbidden
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import CommentForm, EditProductForm, ProductForm
from .context_processors import unread_comments_count
from .models import Comment, Like, Product, ProductImage

logger = logging.getLogger(__name__)


def _can_publish(user):
    return (user.origem or "").strip().upper() == "SEPLAG"


def _visible_products(user, include_owned_inactive=False):
    products = Product.objects.all() if include_owned_inactive else Product.active()
    if include_owned_inactive:
        products = products.filter(
            Q(is_enabled=True, expires_at__gt=timezone.now()) | Q(creator=user)
        )
    return (
        products
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
def unread_count(request):
    response = JsonResponse({"count": unread_comments_count(request.user)})
    response["Cache-Control"] = "no-store"
    return response


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
def my_products(request):
    products = (
        Product.objects.filter(creator=request.user)
        .prefetch_related("images")
        .annotate(
            like_count=Count("likes", distinct=True),
            comment_count=Count("comments", distinct=True),
            unread_count=Count(
                "comments",
                filter=Q(comments__read_at__isnull=True) & ~Q(comments__author=request.user),
                distinct=True,
            ),
        )
        .order_by("-created_at", "-pk")
    )
    page = Paginator(products, 12).get_page(request.GET.get("page"))
    return render(request, "classificados/my_products.html", {
        "page": page, "can_publish": _can_publish(request.user), "now": timezone.now(),
    })


def _delete_image_files(images):
    for storage, name in images:
        try:
            storage.delete(name)
        except Exception:
            logger.exception("Falha ao excluir foto do classificado: %s", name)


@login_required(login_url="login")
def product_edit(request, pk):
    product = get_object_or_404(Product.objects.filter(creator=request.user).prefetch_related("images"), pk=pk)
    form = EditProductForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
            new_photos = form.cleaned_data["photos"]
            if new_photos:
                old_files = [(photo.image.storage, photo.image.name) for photo in product.images.all()]
                product.images.all().delete()
                ProductImage.objects.bulk_create([
                    ProductImage(product=product, image=image, position=position)
                    for position, image in enumerate(new_photos)
                ])
                transaction.on_commit(lambda files=old_files: _delete_image_files(files))
        messages.success(request, "Produto atualizado.")
        return redirect("classificados:my_products")
    return render(request, "classificados/product_form.html", {
        "form": form, "product": product, "editing": True,
    })


@login_required(login_url="login")
@require_POST
def toggle_active(request, pk):
    with transaction.atomic():
        product = get_object_or_404(
            Product.objects.select_for_update().filter(creator=request.user), pk=pk
        )
        if product.is_enabled:
            product.is_enabled = False
            messages.success(request, "Anúncio desativado.")
        elif product.expires_at > timezone.now():
            product.is_enabled = True
            messages.success(request, "Anúncio reativado.")
        else:
            messages.error(request, "O prazo de dois meses terminou. Este anúncio não pode ser reativado.")
            return redirect("classificados:my_products")
        product.save(update_fields=["is_enabled"])
    return redirect("classificados:my_products")


@login_required(login_url="login")
def product_delete(request, pk):
    product = get_object_or_404(Product.objects.filter(creator=request.user).prefetch_related("images"), pk=pk)
    if request.method == "POST":
        with transaction.atomic():
            image_files = [(photo.image.storage, photo.image.name) for photo in product.images.all()]
            product.delete()
            transaction.on_commit(lambda files=image_files: _delete_image_files(files))
        messages.success(request, "Publicação excluída.")
        return redirect("classificados:my_products")
    return render(request, "classificados/product_confirm_delete.html", {"product": product})


@login_required(login_url="login")
def product_detail(request, pk):
    product = get_object_or_404(_visible_products(request.user, include_owned_inactive=True), pk=pk)
    if product.creator_id == request.user.pk:
        Comment.objects.filter(product=product, read_at__isnull=True).exclude(
            author=request.user
        ).update(read_at=timezone.now())
    comments = product.comments.select_related("author").all()
    return render(request, "classificados/product_detail.html", {
        "product": product,
        "comments": comments,
        "form": CommentForm(),
        "hot_likes": getattr(settings, "CLASSIFICADOS_HOT_LIKES", 5),
        "is_owner": product.creator_id == request.user.pk,
        "can_interact": product.is_active,
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
        "is_owner": detail.creator_id == request.user.pk,
        "can_interact": True,
    }, status=400)
