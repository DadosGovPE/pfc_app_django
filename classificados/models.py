from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def validate_image_size(image):
    if image.size > 10 * 1024 * 1024:
        raise ValidationError("Cada foto pode ter no máximo 10 MB.")


class Product(models.Model):
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="classificados_products", verbose_name="anunciante",
    )
    title = models.CharField("título", max_length=160)
    description = models.TextField("descrição")
    price = models.DecimalField(
        "preço", max_digits=12, decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    created_at = models.DateTimeField("publicado em", default=timezone.now, editable=False)
    expires_at = models.DateTimeField("expira em", editable=False)
    is_enabled = models.BooleanField("ativo pelo anunciante", default=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "produto"
        verbose_name_plural = "produtos"
        indexes = [models.Index(fields=["expires_at"], name="classificados_expires_idx")]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.expires_at = self.created_at + relativedelta(months=2)
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        return self.is_enabled and self.expires_at > timezone.now()

    @classmethod
    def active(cls):
        return cls.objects.filter(is_enabled=True, expires_at__gt=timezone.now())


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(
        "foto", upload_to="classificados/products/%Y/%m/",
        validators=[validate_image_size, FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
    )
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["product", "position"], name="classificados_unique_image_position"),
            models.CheckConstraint(check=models.Q(position__lte=2), name="classificados_image_position_lte_2"),
        ]

    def clean(self):
        if self.position > 2:
            raise ValidationError({"position": "O produto pode ter no máximo 3 fotos."})


class Like(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="classificados_likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["product", "user"], name="classificados_unique_like")]


class Comment(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="classificados_comments")
    text = models.TextField("comentário", max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField("lido pelo anunciante em", null=True, blank=True, editable=False)

    class Meta:
        ordering = ["created_at", "pk"]

    def __str__(self):
        return self.text[:80]
