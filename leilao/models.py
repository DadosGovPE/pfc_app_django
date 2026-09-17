from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.utils import timezone


TEN_MEGABYTES = 10 * 1024 * 1024


def validate_image_size(image):
    if image.size > TEN_MEGABYTES:
        raise ValidationError("Cada foto pode ter no máximo 10 MB.")


class Auction(models.Model):
    class Origin(models.TextChoices):
        SEPLAG = "seplag", "SEPLAG"
        EXTERNAL = "external", "Externo"

    name = models.CharField("nome", max_length=160)
    slug = models.SlugField(unique=True)
    description = models.TextField("descrição", blank=True)
    origin = models.CharField(
        "origem", max_length=20, choices=Origin.choices, default=Origin.SEPLAG
    )
    starts_at = models.DateTimeField("início")
    ends_at = models.DateTimeField("fim")
    is_published = models.BooleanField("publicado", default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="leilao_auctions_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "leilão"
        verbose_name_plural = "leilões"

    def __str__(self):
        return self.name

    def clean(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "O fim deve ser posterior ao início."})


class Product(models.Model):
    class IncrementType(models.TextChoices):
        FIXED = "fixed", "Valor fixo"
        PERCENTAGE = "percentage", "Percentual"

    auction = models.ForeignKey(
        Auction,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name="leilão",
    )
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="leilao_products",
        verbose_name="criador",
    )
    title = models.CharField("título", max_length=160)
    description = models.TextField("descrição", blank=True)
    initial_price = models.DecimalField(
        "preço inicial",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    reserve_price = models.DecimalField(
        "preço mínimo para venda",
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    increment_type = models.CharField(
        "tipo de incremento",
        max_length=20,
        choices=IncrementType.choices,
        default=IncrementType.FIXED,
    )
    increment_value = models.DecimalField(
        "incremento",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    starts_at = models.DateTimeField("início", default=timezone.now)
    ends_at = models.DateTimeField("fim")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    creator_notified_at = models.DateTimeField(null=True, blank=True, editable=False)
    winner_notified_at = models.DateTimeField(null=True, blank=True, editable=False)
    notification_error = models.TextField(blank=True, editable=False)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["ends_at"]),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        errors = {}
        if self.ends_at and self.starts_at and self.ends_at <= self.starts_at:
            errors["ends_at"] = "O fim deve ser posterior ao início."
        if self.reserve_price and self.reserve_price < self.initial_price:
            errors["reserve_price"] = (
                "O preço mínimo não pode ser menor que o preço inicial."
            )
        if (
            self.increment_type == self.IncrementType.PERCENTAGE
            and self.increment_value > 100
        ):
            errors["increment_value"] = (
                "O incremento percentual deve ser de no máximo 100%."
            )
        if errors:
            raise ValidationError(errors)

    @property
    def is_active(self):
        now = timezone.now()
        return (
            self.auction.is_published
            and self.auction.starts_at <= now < self.auction.ends_at
            and self.starts_at <= now < self.ends_at
        )

    @property
    def highest_bid(self):
        prefetched = getattr(self, "_prefetched_objects_cache", {}).get("bids")
        if prefetched is not None:
            return max(
                prefetched,
                key=lambda bid: (bid.amount, -bid.pk),
                default=None,
            )
        return self.bids.order_by("-amount", "created_at").first()

    @property
    def current_price(self):
        highest = self.highest_bid
        return highest.amount if highest else self.initial_price

    def calculate_next_bid(self, current=None):
        current = Decimal(current if current is not None else self.current_price)
        if self.increment_type == self.IncrementType.PERCENTAGE:
            increase = (
                current * self.increment_value / Decimal("100")
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            increase = max(increase, Decimal("0.01"))
        else:
            increase = self.increment_value
        return (current + increase).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @property
    def next_bid_amount(self):
        highest = self.highest_bid
        return self.calculate_next_bid(highest.amount) if highest else self.initial_price

    @property
    def winner(self):
        effective_end = min(self.ends_at, self.auction.ends_at)
        if timezone.now() < effective_end:
            return None
        highest = self.highest_bid
        if not highest or (self.reserve_price and highest.amount < self.reserve_price):
            return None
        return highest.bidder


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(
        "foto",
        upload_to="leilao/products/%Y/%m/",
        validators=[
            validate_image_size,
            FileExtensionValidator(["jpg", "jpeg", "png", "webp"]),
        ],
    )
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]


class Bid(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="bids"
    )
    bidder = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="leilao_bids",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-amount", "created_at"]
        indexes = [models.Index(fields=["product", "-amount"])]

    def __str__(self):
        return f"{self.product} — {self.amount}"
