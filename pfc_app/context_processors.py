from datetime import datetime
from .models import AjustesPesquisa

def ajustes_pesquisa_context(request):
    ajustes, created = AjustesPesquisa.objects.get_or_create(
        nome='padrao',
        defaults={'nome':'padrao', 'ano_ref': datetime.now().year}
    )
    return {
        'is_aberta': ajustes.is_aberta,
    }