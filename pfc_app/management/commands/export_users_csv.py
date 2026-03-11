import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from pfc_app.models import User


class Command(BaseCommand):
    help = "Exporta usuarios para CSV com username, nome e cpf."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="usuarios.csv",
            help="Nome do arquivo ou caminho de saida do CSV.",
        )

    def handle(self, *args, **options):
        output_option = options["output"]
        output_path = Path(output_option)

        if not output_path.is_absolute():
            output_path = Path(settings.BASE_DIR) / output_path

        output_path.parent.mkdir(parents=True, exist_ok=True)

        users = User.objects.order_by("nome").values_list("username", "nome", "cpf")

        with open(output_path, "w", newline="", encoding="utf-8-sig") as csvfile:
            writer = csv.writer(csvfile, delimiter=";")
            writer.writerow(["username", "nome", "cpf"])
            writer.writerows(users)

        self.stdout.write(
            self.style.SUCCESS(f"Arquivo CSV gerado com sucesso em: {output_path}")
        )
