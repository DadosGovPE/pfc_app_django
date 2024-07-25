from django.core.management.base import BaseCommand
from pfc_app.models import User
from datetime import datetime
import pandas as pd
from validate_docbr import CPF


class Command(BaseCommand):
    help = 'Popula a tabela com dados de uma planilha'
    

    def handle(self, *args, **kwargs):   
        users = User.objects.all() 
        cpf_padrao = CPF()
        for user in users:
            if not cpf_padrao.validate(user.cpf):
                self.stdout.write(self.style.ERROR(f'CPF de {user.first_name} COM PROBLEMAS!'))
        
            
        self.stdout.write(self.style.SUCCESS('FINALIZADO'))


# nome_sugestão_acao
# forma_atendimento
# mes_competencia
# trilha

#  cpf_padrao = CPF()
#     # Validar CPF
#     if not cpf_padrao.validate(cpf):
#         messages.error(request, f'CPF digitado está errado!')
#         # return JsonResponse({'success': False, 'msg': 'CPF Inválido!'})
#         return render(request, 'pfc_app/registrar.html', context)