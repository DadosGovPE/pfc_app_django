from django.core.management.base import BaseCommand
from pfc_app.models import User


class Command(BaseCommand):
    help = "Check"

    def handle(self, *args, **kwargs):
        users = User.objects.all()

        for user in users:
            if user.is_primeiro_acesso:
                user.is_primeiro_acesso = False
                user.save()

        self.stdout.write(self.style.SUCCESS("FINALIZADO"))
