from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Bid, Product


@transaction.atomic
def place_next_bid(*, product_id, bidder):
    product = (
        Product.objects.select_for_update()
        .select_related("auction", "creator")
        .get(pk=product_id)
    )
    if not product.is_active:
        raise ValidationError("Este leilão não está mais aceitando lances.")
    if product.creator_id == bidder.id:
        raise ValidationError("Você não pode dar lance no próprio produto.")
    highest = product.bids.order_by("-amount", "created_at").first()
    if highest and highest.bidder_id == bidder.id:
        raise ValidationError(
            "Você já deu o último lance. Aguarde outra pessoa participar."
        )
    amount = (
        product.calculate_next_bid(highest.amount)
        if highest
        else product.initial_price
    )
    return Bid.objects.create(product=product, bidder=bidder, amount=amount)
