from django.core.management.base import BaseCommand
from django.db.models import Q
from pfc_app.models import User, Lotacao, LotacaoEspecifica

class Command(BaseCommand):
    help = 'Popula as tabelas Lotacao e LotacaoEspecifica com valores existentes nos campos lotacao e lotacao_especifica do modelo User'

    def handle(self, *args, **kwargs):
        users = User.objects.all()
        # Popula Lotacao e Lotacao Especifica
        for user in users:
            try:
                lotacao_fk = Lotacao.objects.filter(nome=user.lotacao).first()
                if lotacao_fk:
                    user.lotacao_fk = lotacao_fk


                lotacao_especifica_fk = LotacaoEspecifica.objects.filter(nome=user.lotacao_especifica).first()
                if lotacao_especifica_fk:
                    user.lotacao_especifica_fk = lotacao_especifica_fk
                
                user.save()
            except Exception as e:
                print("ERRO: " + e)

        self.stdout.write(self.style.SUCCESS('Tabelas Lotacao e LotacaoEspecifica foram populadas com sucesso'))