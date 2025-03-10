import django_filters
from django_filters import DateFilter
from .models import *

class UserFilter(django_filters.FilterSet):
    #     # Obtenha os valores únicos e ordene-os
    lotacao_especifica_values = User.objects.values_list('lotacao_especifica', flat=True).distinct().order_by('lotacao_especifica')

    # # Crie uma lista de tuplas ordenadas
    lotacao_especifica_choices = [(choice, choice) for choice in lotacao_especifica_values]
    lotacao_especifica = django_filters.ChoiceFilter(
        choices=lotacao_especifica_choices)
    

    # # Obtenha os valores únicos e ordene-os
    lotacao_values = User.objects.values_list('lotacao', flat=True).distinct().order_by('lotacao')

    # # Crie uma lista de tuplas ordenadas
    lotacao_choices = [(choice, choice) for choice in lotacao_values]
    lotacao = django_filters.ChoiceFilter(
        choices=lotacao_choices)
    
    # # Campos de data
    # inicio = DateFilter(label='Data de início (>=)', required=False)
    # fim = DateFilter(label='Data de fim (<=)', required=False)
    
    class Meta:
        model = User
        fields = {
            'nome': ['icontains'],
            'email': ['icontains'],
        }
