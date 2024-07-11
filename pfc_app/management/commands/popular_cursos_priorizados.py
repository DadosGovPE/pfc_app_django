from django.core.management.base import BaseCommand
from pfc_app.models import CursoPriorizado
from datetime import datetime
import pandas as pd


class Command(BaseCommand):
    help = 'Popula a tabela com dados de uma planilha'

    def handle(self, *args, **kwargs):
        df = pd.read_csv('LNT_2024.csv', sep=';')
        month_mapping = {
            'Janeiro': 1, 'Fevereiro': 2, 'Março': 3, 'Abril': 4,
            'Maio': 5, 'Junho': 6, 'Julho': 7, 'Agosto': 8,
            'Setembro': 9, 'Outubro': 10, 'Novembro': 11, 'Dezembro': 12
        }

        for index, row in df.iterrows():
            try:
                # Obtenha o número do mês a partir do nome
                month = row['mes']
                if pd.isna(month) or month.strip() == '':
                    month = 'Janeiro'
                month = month_mapping[month]

                forma = row['forma_atendimento']
                if pd.isna(forma) or forma.strip() == '':
                    forma = 'PFC'

                # Crie a data no formato YYYY-MM-DD
                mes_competencia_date = datetime(2024, month, 1).date()

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