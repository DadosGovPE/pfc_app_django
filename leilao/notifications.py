from html import escape

from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Product


def _money(value):
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _user_name(user):
    return user.nome or user.get_full_name() or user.username


def _user_contact(user):
    lotacao = user.lotacao_fk or user.lotacao or "Não informada"
    return {
        "nome": _user_name(user),
        "email": user.email or "Não informado",
        "telefone": user.telefone or "Não informado",
        "lotacao": str(lotacao),
    }


def _send_message(*, subject, recipient, lines):
    text_body = "\n".join(lines)
    html_body = "".join(f"<p>{escape(line)}</p>" for line in lines)
    message = EmailMultiAlternatives(subject=subject, body=text_body, to=[recipient])
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)


@transaction.atomic
def process_product_outcome(product_id):
    product = (
        Product.objects.select_for_update()
        .select_related("auction", "creator", "creator__lotacao_fk")
        .get(pk=product_id)
    )
    effective_end = min(product.ends_at, product.auction.ends_at)
    if timezone.now() < effective_end:
        return False

    highest_bid = (
        product.bids.select_related("bidder", "bidder__lotacao_fk")
        .order_by("-amount", "created_at")
        .first()
    )
    winner = None
    if highest_bid and (
        not product.reserve_price or highest_bid.amount >= product.reserve_price
    ):
        winner = highest_bid.bidder

    errors = []
    now = timezone.now()
    if product.creator_notified_at is None:
        try:
            if winner:
                winner_contact = _user_contact(winner)
                creator_lines = [
                    f'O leilão do produto "{product.title}" foi encerrado.',
                    f"Valor final: {_money(highest_bid.amount)}.",
                    f"Arrematante: {winner_contact['nome']}.",
                    f"E-mail: {winner_contact['email']}.",
                    f"Telefone: {winner_contact['telefone']}.",
                    f"Lotação: {winner_contact['lotacao']}.",
                    "Combine diretamente com o arrematante as condições de pagamento e entrega.",
                ]
            else:
                creator_lines = [
                    f'O leilão do produto "{product.title}" foi encerrado sem arrematante.',
                    "Não houve lance válido ou o preço mínimo não foi atingido.",
                ]
            _send_message(
                subject=f"Leilão encerrado: {product.title}",
                recipient=product.creator.email,
                lines=creator_lines,
            )
            product.creator_notified_at = now
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Criador: {exc}")

    if product.winner_notified_at is None:
        if winner:
            try:
                creator_contact = _user_contact(product.creator)
                _send_message(
                    subject=f"Você arrematou: {product.title}",
                    recipient=winner.email,
                    lines=[
                        f'Você venceu o leilão do produto "{product.title}".',
                        f"Valor final: {_money(highest_bid.amount)}.",
                        f"Anunciante: {creator_contact['nome']}.",
                        f"E-mail: {creator_contact['email']}.",
                        f"Telefone: {creator_contact['telefone']}.",
                        f"Lotação: {creator_contact['lotacao']}.",
                        "Combine diretamente com o anunciante as condições de pagamento e entrega.",
                    ],
                )
                product.winner_notified_at = now
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Arrematante: {exc}")
        else:
            product.winner_notified_at = now

    product.notification_error = " | ".join(errors)
    product.save(
        update_fields=[
            "creator_notified_at",
            "winner_notified_at",
            "notification_error",
        ]
    )
    return not errors


def process_ended_products(limit=50):
    now = timezone.now()
    product_ids = list(
        Product.objects.filter(Q(ends_at__lte=now) | Q(auction__ends_at__lte=now))
        .filter(
            Q(creator_notified_at__isnull=True)
            | Q(winner_notified_at__isnull=True)
        )
        .values_list("id", flat=True)[:limit]
    )
    processed = 0
    for product_id in product_ids:
        if process_product_outcome(product_id):
            processed += 1
    return processed
