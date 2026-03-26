from django.core.management.base import BaseCommand
from django.db import transaction

from pfc_app.models import User


class Command(BaseCommand):
    help = (
        "Atualiza e-mails que terminam com @seplag.pe.gov.br para "
        "@gd.seplag.pe.gov.br."
    )

    origem = "@seplag.pe.gov.br"
    destino = "@gd.seplag.pe.gov.br"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra o que seria alterado sem salvar no banco.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        candidatos = User.objects.filter(email__iendswith=self.origem).order_by("id")

        alterados = []
        ignorados = []

        self.stdout.write(
            f"Processando {candidatos.count()} usuário(s) com final {self.origem}."
        )

        with transaction.atomic():
            for user in candidatos.iterator():
                email_atual = (user.email or "").strip()
                email_novo = self._converter_email(email_atual)

                if not email_novo or email_novo == email_atual:
                    ignorados.append((user.id, user.cpf, user.nome, email_atual, "sem alteração"))
                    continue

                conflito = (
                    User.objects.filter(email__iexact=email_novo)
                    .exclude(pk=user.pk)
                    .exists()
                )
                if conflito:
                    ignorados.append(
                        (
                            user.id,
                            user.cpf,
                            user.nome,
                            email_atual,
                            f"conflito com {email_novo}",
                        )
                    )
                    continue

                alterados.append((user.id, user.cpf, user.nome, email_atual, email_novo))
                if not dry_run:
                    user.email = email_novo
                    user.save(update_fields=["email"])

            if dry_run:
                transaction.set_rollback(True)

        for item in alterados:
            self.stdout.write(
                f"[ALTERADO] id={item[0]} cpf={item[1]} nome={item[2]}: {item[3]} -> {item[4]}"
            )

        for item in ignorados:
            self.stdout.write(
                f"[IGNORADO] id={item[0]} cpf={item[1]} nome={item[2]}: {item[3]} ({item[4]})"
            )

        self.stdout.write("")
        self.stdout.write("Resumo:")
        self.stdout.write(f"- Alterados: {len(alterados)}")
        self.stdout.write(f"- Ignorados: {len(ignorados)}")
        self.stdout.write(f"- Modo dry-run: {'sim' if dry_run else 'não'}")

    def _converter_email(self, email):
        if not email:
            return email
        email_lower = email.lower()
        if not email_lower.endswith(self.origem):
            return email
        prefixo = email[: -len(self.origem)]
        return f"{prefixo}{self.destino}"
