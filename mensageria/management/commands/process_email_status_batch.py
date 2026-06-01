from django.core.management.base import BaseCommand, CommandError

from mensageria.status_batch import process_email_status_batch


class Command(BaseCommand):
    help = "Processa um lote de envio de e-mails por alteracao de status."

    def add_arguments(self, parser):
        parser.add_argument("job_id", help="Identificador do lote.")

    def handle(self, *args, **options):
        job_id = options["job_id"]
        processed = process_email_status_batch(job_id)
        if not processed:
            raise CommandError(f"Lote {job_id} nao encontrado.")
