from django.core.management.base import BaseCommand
from pfc_app.models import CursoPriorizado
from datetime import datetime
import pandas as pd


class Command(BaseCommand):
    help = 'Popula a tabela com dados de uma planilha'

    def handle(self, *args, **kwargs):
        df = pd.read_csv('LNT_2024.csv', sep=';', usecols=['sugestao_acao_capacitacao', 'forma_atendimento'])
        df = df.drop_duplicates(subset=['sugestao_acao_capacitacao'])
        # print(df)
        for index, row in df.iterrows():
            try:
                # Crie a data no formato YYYY-MM-DD
                mes_competencia_date = datetime(2024, 1, 1).date()

                CursoPriorizado.objects.create(
                nome_sugestão_acao=row['sugestao_acao_capacitacao'],
                forma_atendimento=row['forma_atendimento'],
                mes_competencia=mes_competencia_date,
                )   
                    
            except Exception as e:
                print('Erro: ' + str(e))
            
        self.stdout.write(self.style.SUCCESS('Tabela populada com sucesso!'))


# nome_sugestão_acao
# forma_atendimento
# mes_competencia
# trilha