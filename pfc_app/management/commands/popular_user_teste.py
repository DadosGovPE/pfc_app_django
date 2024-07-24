from django.core.management.base import BaseCommand
from pfc_app.models import User
from datetime import datetime
import pandas as pd


class Command(BaseCommand):
    help = 'Popula a tabela com dados de uma planilha'

    def handle(self, *args, **kwargs):    
        try:

            User.objects.create(
            username="Teste-APAGAR",
            email="Teste-APAGAR",
            password="Teste-APAGAR",
            cpf="00991496485",
            nome="Teste-APAGAR",
            role="ADMIN",
            )   
                
        except Exception as e:
            print('Erro: ' + str(e))
            
        self.stdout.write(self.style.SUCCESS('Tabela populada com sucesso!'))


# nome_sugestão_acao
# forma_atendimento
# mes_competencia
# trilha