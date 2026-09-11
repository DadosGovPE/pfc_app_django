from django.core.cache import cache

from .models import Pesquisa


def pesquisa_aberta(request):
    resolver_match = getattr(request, "resolver_match", None)
    if getattr(resolver_match, "namespace", None) == "admin" or request.path.startswith(
        "/admin/"
    ):
        return {}

    cache_key = "pfc:pesquisas-abertas"
    abertas = cache.get(cache_key)
    if abertas is None:
        abertas = list(
            Pesquisa.objects.filter(is_aberta=True).values("id", "titulo")
        )
        cache.set(cache_key, abertas, 60)

    return {
        "pesquisas_abertas": abertas,
        "tem_pesquisa_aberta": bool(abertas),
    }
