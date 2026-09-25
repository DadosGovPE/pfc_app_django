from django.contrib import admin

from .models import Comment, Like, Product, ProductImage


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("title", "creator", "price", "created_at", "is_active")
    search_fields = ("title", "description", "creator__nome")
    readonly_fields = ("creator", "title", "description", "price", "created_at")

    def has_add_permission(self, request):
        return False


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("product", "position")
    readonly_fields = ("product", "image", "position")

    def has_add_permission(self, request):
        return False


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("product", "author", "created_at")
    search_fields = ("text", "product__title", "author__nome")
    readonly_fields = ("product", "author", "text", "created_at")

    def has_add_permission(self, request):
        return False


admin.site.register(Like)
