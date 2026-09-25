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

    def test_owner_can_edit_photos_and_toggle_visibility_without_extending_expiry(self):
        product = self.make_product()
        original_expiry = product.expires_at
        self.client.force_login(self.seller)
        edit_url = reverse("classificados:product_edit", args=[product.pk])
        response = self.client.post(edit_url, {
            "title": "Produto editado", "description": "Nova descrição", "price": "55.00",
        })
        self.assertRedirects(response, reverse("classificados:my_products"))
        product.refresh_from_db()
        self.assertEqual(product.title, "Produto editado")
        self.assertEqual(product.images.count(), 1)
        self.assertEqual(product.expires_at, original_expiry)

        self.client.post(edit_url, {
            "title": "Produto editado", "description": "Nova descrição", "price": "55.00",
            "photos": [photo("nova1.png"), photo("nova2.png")],
        })
        self.assertEqual(product.images.count(), 2)
        self.assertEqual(list(product.images.values_list("position", flat=True)), [0, 1])

        toggle_url = reverse("classificados:toggle_active", args=[product.pk])
        self.assertRedirects(self.client.post(toggle_url), reverse("classificados:my_products"))
        product.refresh_from_db()
        self.assertFalse(product.is_enabled)
        self.assertEqual(self.client.get(reverse("classificados:product_detail", args=[product.pk])).status_code, 200)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse("classificados:product_detail", args=[product.pk])).status_code, 404)
        self.client.force_login(self.seller)
        self.assertContains(self.client.get(reverse("classificados:my_products")), "Desativado")
        self.client.post(toggle_url)
        product.refresh_from_db()
        self.assertTrue(product.is_enabled)
        self.assertEqual(product.expires_at, original_expiry)
        self.assertEqual(self.client.get(reverse("classificados:product_detail", args=[product.pk])).status_code, 200)

    def test_only_owner_can_manage_and_expired_product_cannot_be_reactivated(self):
        product = self.make_product()
        self.client.force_login(self.viewer)
        self.assertNotContains(self.client.get(reverse("classificados:my_products")), product.title)
        self.assertEqual(self.client.get(reverse("classificados:product_edit", args=[product.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("classificados:toggle_active", args=[product.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("classificados:product_delete", args=[product.pk])).status_code, 404)

        product.expires_at = timezone.now() - timedelta(seconds=1)
        product.is_enabled = False
        product.save(update_fields=["expires_at", "is_enabled"])
        self.client.force_login(self.seller)
        self.client.post(reverse("classificados:toggle_active", args=[product.pk]))
        product.refresh_from_db()
        self.assertFalse(product.is_enabled)
        self.assertContains(self.client.get(reverse("classificados:my_products")), "Prazo encerrado")

    def test_delete_requires_confirmation_and_removes_publication(self):
        product = self.make_product()
        Like.objects.create(product=product, user=self.viewer)
        Comment.objects.create(product=product, author=self.viewer, text="Tenho interesse")
        self.client.force_login(self.seller)
        url = reverse("classificados:product_delete", args=[product.pk])
        self.assertContains(self.client.get(url), "Excluir publicação?")
        self.assertTrue(Product.objects.filter(pk=product.pk).exists())
        self.assertRedirects(self.client.post(url), reverse("classificados:my_products"))
        self.assertFalse(Product.objects.filter(pk=product.pk).exists())
        self.assertFalse(Like.objects.filter(product_id=product.pk).exists())
        self.assertFalse(Comment.objects.filter(product_id=product.pk).exists())

    def test_unread_badges_count_comments_and_opening_own_product_marks_them_read(self):
        first = self.make_product("Primeiro")
        second = self.make_product("Segundo")
        comment_one = Comment.objects.create(product=first, author=self.viewer, text="Primeira pergunta")
        comment_two = Comment.objects.create(product=second, author=self.viewer, text="Segunda pergunta")
        Comment.objects.create(product=first, author=self.seller, text="Minha resposta")

        self.client.force_login(self.seller)
        catalog = self.client.get(reverse("classificados:catalog"))
        self.assertContains(catalog, 'aria-label="2 comentários não lidos"', count=2)
        self.assertContains(catalog, reverse("classificados:my_products"))
        count_url = reverse("classificados:unread_count")
        self.assertEqual(self.client.get(count_url).json(), {"count": 2})
        self.assertEqual(self.client.get(count_url)["Cache-Control"], "no-store")
        self.assertContains(self.client.get(reverse("classificados:my_products")), "Primeira pergunta", count=0)

        self.client.force_login(self.viewer)
        self.client.get(reverse("classificados:product_detail", args=[first.pk]))
        comment_one.refresh_from_db()
        self.assertIsNone(comment_one.read_at)

        self.client.force_login(self.seller)
        detail = self.client.get(reverse("classificados:product_detail", args=[first.pk]))
        self.assertContains(detail, "Primeira pergunta")
        comment_one.refresh_from_db()
        comment_two.refresh_from_db()
        self.assertIsNotNone(comment_one.read_at)
        self.assertIsNone(comment_two.read_at)
        self.assertEqual(self.client.get(count_url).json(), {"count": 1})
        self.assertContains(self.client.get(reverse("classificados:catalog")), 'aria-label="1 comentário não lido"', count=2)

    def test_owner_can_read_comments_on_disabled_product_without_republishing(self):
        product = self.make_product()
        product.is_enabled = False
        product.save(update_fields=["is_enabled"])
        comment = Comment.objects.create(product=product, author=self.viewer, text="Ainda disponível?")

        self.client.force_login(self.seller)
        response = self.client.get(reverse("classificados:product_detail", args=[product.pk]))
        self.assertContains(response, "Ainda disponível?")
        self.assertNotContains(response, "Publicar comentário")
        comment.refresh_from_db()
        self.assertIsNotNone(comment.read_at)
        product.refresh_from_db()
        self.assertFalse(product.is_enabled)
