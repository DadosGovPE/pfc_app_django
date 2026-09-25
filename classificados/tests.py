from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from tempfile import TemporaryDirectory

from dateutil.relativedelta import relativedelta
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from pfc_app.models import User

from .models import Comment, Like, Product, ProductImage


def photo(name="foto.png"):
    data = BytesIO()
    Image.new("RGB", (4, 4), "blue").save(data, format="PNG")
    return SimpleUploadedFile(name, data.getvalue(), content_type="image/png")


class ClassifiedsTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_dir = TemporaryDirectory()
        cls.media_settings = override_settings(MEDIA_ROOT=cls.media_dir.name)
        cls.media_settings.enable()

    @classmethod
    def tearDownClass(cls):
        cls.media_settings.disable()
        cls.media_dir.cleanup()
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(
            username="classified_seller", cpf="00000000041", nome="Ana",
            email="classified_seller@example.com", password="test", origem="SEPLAG",
        )
        cls.viewer = User.objects.create_user(
            username="classified_viewer", cpf="00000000042", nome="Bruno",
            email="classified_viewer@example.com", password="test", origem="EXTERNO",
        )

    def make_product(self, title="Produto", created_at=None):
        product = Product.objects.create(
            creator=self.seller, title=title, description="Descrição",
            price=Decimal("42.00"), created_at=created_at or timezone.now(),
        )
        ProductImage.objects.create(product=product, image=photo(), position=0)
        return product

    def test_only_seplag_can_publish_and_photo_range_is_enforced(self):
        self.client.force_login(self.viewer)
        url = reverse("classificados:product_create")
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {
            "title": "Mesa", "description": "Nova", "price": "42.00",
            "photos": photo(),
        }).status_code, 403)

        self.client.force_login(self.seller)
        self.assertEqual(self.client.post(url, {
            "title": "Mesa", "description": "Nova", "price": "42.00",
        }).status_code, 200)
        self.assertEqual(Product.objects.count(), 0)
        self.assertEqual(self.client.post(url, {
            "title": "Mesa", "description": "Nova", "price": "42.00",
            "photos": [photo(f"{n}.png") for n in range(4)],
        }).status_code, 200)
        self.assertEqual(Product.objects.count(), 0)
        response = self.client.post(url, {
            "title": "Mesa", "description": "Nova", "price": "42.00",
            "photos": [photo(f"{n}.png") for n in range(3)],
        })
        self.assertEqual(response.status_code, 302)
        product = Product.objects.get()
        self.assertEqual(product.images.count(), 3)
        self.assertEqual(product.expires_at, product.created_at + relativedelta(months=2))

    def test_expired_product_is_hidden_and_cannot_receive_interactions(self):
        expired = self.make_product(created_at=timezone.now() - relativedelta(months=2) - timedelta(days=1))
        self.client.force_login(self.viewer)
        self.assertNotContains(self.client.get(reverse("classificados:catalog")), expired.title)
        self.assertEqual(self.client.get(reverse("classificados:product_detail", args=[expired.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("classificados:toggle_like", args=[expired.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("classificados:add_comment", args=[expired.pk]), {"text": "Olá"}).status_code, 404)

    def test_likes_reorder_catalog_and_comments_are_public_to_signed_in_users(self):
        older = self.make_product("Mais curtido", timezone.now() - timedelta(days=1))
        newer = self.make_product("Mais novo")
        self.client.force_login(self.viewer)
        self.client.post(reverse("classificados:toggle_like", args=[older.pk]))
        response = self.client.get(reverse("classificados:catalog"))
        self.assertEqual(list(response.context["page"].object_list), [older, newer])
        self.assertEqual(Like.objects.filter(product=older, user=self.viewer).count(), 1)
        self.client.post(reverse("classificados:add_comment", args=[older.pk]), {"text": "Ainda disponível?"})
        self.assertEqual(Comment.objects.filter(product=older).count(), 1)
        self.client.force_login(self.seller)
        self.assertContains(self.client.get(reverse("classificados:product_detail", args=[older.pk])), "Ainda disponível?")
        self.client.force_login(self.viewer)
        self.client.post(reverse("classificados:toggle_like", args=[older.pk]))
        self.assertFalse(Like.objects.filter(product=older, user=self.viewer).exists())
