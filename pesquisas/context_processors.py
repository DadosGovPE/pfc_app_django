# apps/pesquisas/context_processors.py

from .models import Pesquisa

def pesquisa_aberta(request):
    abertas = Pesquisa.objects.filter(is_aberta=True)
    return {
        'pesquisas_abertas': abertas,
        'tem_pesquisa_aberta': abertas.exists()
    }
