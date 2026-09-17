from django.core.management.base import BaseCommand

from leilao.notifications import process_ended_products


class Command(BaseCommand):
    help = "Envia as notificações pendentes dos produtos encerrados no leilão."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        processed = process_ended_products(limit=options["limit"])
        self.stdout.write(
            self.style.SUCCESS(f"{processed} produto(s) processado(s).")
        )
