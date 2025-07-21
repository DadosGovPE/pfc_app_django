from django.core.management.base import BaseCommand
from pfc_app.models import User


class Command(BaseCommand):
    help = 'Check'
    

    def handle(self, *args, **kwargs):   
        users = User.objects.all() 
        celPhone = ""
        for user in users:
            if user.telefone:
                if user.telefone.endswith("66"):
                    self.stdout.write(f'{user.nome}-{user.telefone}')
        
            
        self.stdout.write(self.style.SUCCESS('FINALIZADO'))