from django.contrib import admin

from .models import Auction, Bid, Product, ProductImage


@admin.register(Auction)
class AuctionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "origin",
        "starts_at",
        "ends_at",
        "is_published",
        "created_by",
    )
    list_filter = ("origin", "is_published")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    max_num = 3


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "auction",
        "creator",
        "initial_price",
        "ends_at",
        "created_at",
    )
    list_filter = ("auction", "increment_type")
    search_fields = ("title", "description", "creator__nome", "creator__email")
    readonly_fields = (
        "creator_notified_at",
        "winner_notified_at",
        "notification_error",
    )
    inlines = [ProductImageInline]


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ("product", "bidder", "amount", "created_at")
    search_fields = ("product__title", "bidder__nome", "bidder__email")
    readonly_fields = ("product", "bidder", "amount", "created_at")

    def has_add_permission(self, request):
        return False
