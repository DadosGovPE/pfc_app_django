from datetime import datetime

from django.core.cache import cache

from .models import AjustesPesquisa


def ajustes_pesquisa_context(request):
    resolver_match = getattr(request, "resolver_match", None)
    if getattr(resolver_match, "namespace", None) == "admin" or request.path.startswith(
        "/admin/"
    ):
        return {}

    cache_key = "pfc:ajustes-pesquisa:is-aberta"
    is_aberta = cache.get(cache_key)
    if is_aberta is None:
        ajustes, _created = AjustesPesquisa.objects.get_or_create(
            nome="padrao",
            defaults={"nome": "padrao", "ano_ref": datetime.now().year},
        )
        is_aberta = ajustes.is_aberta
        cache.set(cache_key, is_aberta, 60)

    return {
        "is_aberta": is_aberta,
    }

