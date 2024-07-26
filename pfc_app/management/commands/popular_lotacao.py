from django.core.management.base import BaseCommand
from django.db.models import Q
from pfc_app.models import User, Lotacao, LotacaoEspecifica

class Command(BaseCommand):
    help = 'Popula as tabelas Lotacao e LotacaoEspecifica com valores existentes nos campos lotacao e lotacao_especifica do modelo User'

    def handle(self, *args, **kwargs):
        lotacoes = User.objects.values_list('lotacao', flat=True).distinct()
        lotacoes_especificas = User.objects.values('lotacao', 'lotacao_especifica').distinct()

        # Popula Lotacao
        for lotacao_nome in lotacoes:
            if lotacao_nome:
                Lotacao.objects.get_or_create(nome=lotacao_nome)

        # Popula LotacaoEspecifica
        for entry in lotacoes_especificas:
            lotacao_nome = entry['lotacao']
            lotacao_especifica_nome = entry['lotacao_especifica']
            if lotacao_nome and lotacao_especifica_nome:
                lotacao = Lotacao.objects.get(nome=lotacao_nome)
                LotacaoEspecifica.objects.get_or_create(nome=lotacao_especifica_nome, lotacao=lotacao)

        self.stdout.write(self.style.SUCCESS('Tabelas Lotacao e LotacaoEspecifica foram populadas com sucesso'))