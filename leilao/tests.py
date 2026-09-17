from datetime import timedelta
from decimal import Decimal
from itertools import islice

from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from pfc_app.models import User

from .models import Auction, Bid, Product
from .notifications import process_product_outcome
from .services import place_next_bid


class AuctionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(
            username="seller",
            cpf="00000000031",
            nome="Ana Vendedora",
            email="seller@example.com",
            telefone="81999990001",
            password="test",
        )
        cls.bidder = User.objects.create_user(
            username="bidder",
            cpf="00000000032",
            nome="Bruno Comprador",
            email="bidder@example.com",
            telefone="81999990002",
            password="test",
        )
        now = timezone.now()
        cls.auction = Auction.objects.create(
            name="Interno",
            slug="interno",
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(days=2),
            is_published=True,
            created_by=cls.seller,
        )

    def make_user(self, suffix):
        return User.objects.create_user(
            username=f"user{suffix}",
            cpf=f"0000000{suffix:04d}",
            nome=f"Usuário {suffix}",
            email=f"user{suffix}@example.com",
        )

    def product(self, **kwargs):
        data = {
            "auction": self.auction,
            "creator": self.seller,
            "title": "Produto",
            "initial_price": Decimal("100.00"),
            "increment_type": Product.IncrementType.FIXED,
            "increment_value": Decimal("10.00"),
            "starts_at": timezone.now() - timedelta(minutes=1),
            "ends_at": timezone.now() + timedelta(hours=2),
        }
        data.update(kwargs)
        return Product.objects.create(**data)

    def test_fixed_bid_uses_server_calculated_amount(self):
        product = self.product()
        first = place_next_bid(product_id=product.pk, bidder=self.bidder)
        second = place_next_bid(product_id=product.pk, bidder=self.make_user(33))
        self.assertEqual(first.amount, Decimal("100.00"))
        self.assertEqual(second.amount, Decimal("110.00"))

    def test_percentage_increment_compounds(self):
        product = self.product(
            increment_type=Product.IncrementType.PERCENTAGE,
            increment_value=Decimal("10"),
        )
        Bid.objects.create(
            product=product, bidder=self.bidder, amount=Decimal("110.00")
        )
        self.assertEqual(product.calculate_next_bid(), Decimal("121.00"))

    def test_creator_cannot_bid_on_own_product(self):
        product = self.product()
        with self.assertRaisesMessage(ValidationError, "próprio produto"):
            place_next_bid(product_id=product.pk, bidder=self.seller)

    def test_same_user_cannot_place_two_consecutive_bids(self):
        product = self.product()
        place_next_bid(product_id=product.pk, bidder=self.bidder)
        with self.assertRaisesMessage(ValidationError, "já deu o último lance"):
            place_next_bid(product_id=product.pk, bidder=self.bidder)
        self.assertEqual(product.bids.count(), 1)

    def test_ended_product_rejects_bid(self):
        product = self.product(ends_at=timezone.now() - timedelta(seconds=1))
        with self.assertRaisesMessage(ValidationError, "não está mais"):
            place_next_bid(product_id=product.pk, bidder=self.bidder)

    def test_reserve_price_controls_winner(self):
        product = self.product(
            reserve_price=Decimal("150.00"),
            ends_at=timezone.now() - timedelta(seconds=1),
        )
        Bid.objects.create(
            product=product, bidder=self.bidder, amount=Decimal("140.00")
        )
        self.assertIsNone(product.winner)
        Bid.objects.create(
            product=product, bidder=self.bidder, amount=Decimal("150.00")
        )
        self.assertEqual(product.winner, self.bidder)

    def test_catalog_uses_pfc_login_and_user(self):
        product = self.product(title="Cafeteira")
        response = self.client.get(reverse("leilao:catalog"))
        self.assertEqual(response.status_code, 302)
        self.client.force_login(self.bidder)
        response = self.client.get(reverse("leilao:catalog"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, product.title)
        self.assertContains(response, self.seller.nome)

    def test_htmx_bid_updates_only_bid_zone(self):
        product = self.product()
        self.client.force_login(self.bidder)
        response = self.client.post(
            reverse("leilao:place_bid", args=[product.pk]),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'id="bid-zone-{product.pk}"')
        self.assertContains(response, "R$ 100,00")
        self.assertNotContains(response, f'id="product-{product.pk}"')
        self.assertIn("catalogReordered", response.headers["HX-Trigger-After-Settle"])

    def test_creator_sees_pfc_winner_contact(self):
        product = self.product(ends_at=timezone.now() - timedelta(seconds=1))
        Bid.objects.create(
            product=product, bidder=self.bidder, amount=Decimal("110.00")
        )
        self.client.force_login(self.seller)
        response = self.client.get(reverse("leilao:my_products"))
        self.assertContains(response, self.bidder.nome)
        self.assertContains(response, self.bidder.telefone)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="PFC <pfc@example.com>",
    )
    def test_ended_product_notifies_creator_and_winner_once(self):
        product = self.product(ends_at=timezone.now() - timedelta(seconds=1))
        Bid.objects.create(
            product=product, bidder=self.bidder, amount=Decimal("110.00")
        )

        self.assertTrue(process_product_outcome(product.id))
        self.assertTrue(process_product_outcome(product.id))

        product.refresh_from_db()
        self.assertIsNotNone(product.creator_notified_at)
        self.assertIsNotNone(product.winner_notified_at)
        self.assertEqual(len(mail.outbox), 2)
        recipients = {message.to[0] for message in mail.outbox}
        self.assertEqual(recipients, {self.seller.email, self.bidder.email})
        combined_body = "\n".join(message.body for message in mail.outbox)
        self.assertIn("R$ 110,00", combined_body)
        self.assertIn("pagamento e entrega", combined_body)
        self.assertIn(self.bidder.telefone, combined_body)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_ended_product_without_winner_notifies_only_creator(self):
        product = self.product(
            reserve_price=Decimal("150.00"),
            ends_at=timezone.now() - timedelta(seconds=1),
        )
        Bid.objects.create(
            product=product, bidder=self.bidder, amount=Decimal("110.00")
        )

        self.assertTrue(process_product_outcome(product.id))

        product.refresh_from_db()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.seller.email])
        self.assertIn("sem arrematante", mail.outbox[0].body)
        self.assertIsNotNone(product.winner_notified_at)

    def test_live_stream_announces_new_bid_version(self):
        product = self.product()
        Bid.objects.create(
            product=product, bidder=self.bidder, amount=Decimal("100.00")
        )
        self.client.force_login(self.seller)

        response = self.client.get(
            reverse("leilao:catalog_events"),
            {"version": "0"},
        )
        chunks = b"".join(islice(response.streaming_content, 2)).decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: catalog-update", chunks)
        self.assertIn("retry: 1500", chunks)
