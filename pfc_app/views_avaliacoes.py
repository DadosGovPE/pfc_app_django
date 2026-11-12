import hmac
import json
import logging
from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, RequestDataTooBig, ValidationError
from django.db import DatabaseError
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import PainelAvaliacoes
from .sentimento.services import (
    DadosInvalidos, FonteAlterada, dados_painel_com_filtros, fonte_avaliacoes, publicar_resultados,
)

logger = logging.getLogger(__name__)


def somente_admin(view):
    @wraps(view)
    @login_required
    def protegida(request, *args, **kwargs):
        if not request.user.is_active or request.user.role != "ADMIN":
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return protegida


def autenticacao_sincronizacao(view):
    @wraps(view)
    def protegida(request, *args, **kwargs):
        segredo = getattr(settings, "PFC_AVALIACOES_SYNC_TOKEN", "")
        if not segredo or len(segredo) < 32:
            return JsonResponse({"erro": "Integração de avaliações não configurada."}, status=503)
        recebido = request.headers.get("Authorization", "")
        esperado = "Bearer " + segredo
        if not hmac.compare_digest(recebido.encode("utf-8"), esperado.encode("utf-8")):
            return JsonResponse({"erro": "Autenticação inválida."}, status=401)
        return view(request, *args, **kwargs)
    return protegida


@never_cache
@somente_admin
@require_GET
def painel_avaliacoes(request):
    painel = PainelAvaliacoes.objects.filter(pk=1).first()
    dados = painel.publicado if painel else {}
    atualizado = timezone.localtime(painel.atualizado_em).strftime("%d/%m/%Y %H:%M") if painel and painel.atualizado_em else ""
    return render(request, "pfc_app/painel_avaliacoes.html", {
        "dados_painel": dados_painel_com_filtros(dados) if dados else {"registros": [], "total_linhas": 0, "total_cursos": 0},
        "atualizado": atualizado, "tem_publicacao": bool(dados),
    })


@never_cache
@autenticacao_sincronizacao
@require_GET
def api_fonte_avaliacoes(request):
    try:
        return JsonResponse(fonte_avaliacoes())
    except DadosInvalidos as exc:
        return JsonResponse({"erro": str(exc)}, status=422)
    except (DatabaseError, ValidationError):
        logger.exception("Falha ao consultar a fonte do painel de avaliações")
        return JsonResponse({"erro": "Não foi possível consultar as avaliações."}, status=503)


@csrf_exempt  # API máquina a máquina: exige token dedicado, nunca sessão do navegador.
@never_cache
@autenticacao_sincronizacao
@require_POST
def api_resultados_avaliacoes(request):
    if request.content_type != "application/json":
        return JsonResponse({"erro": "Use application/json."}, status=415)
    limite = getattr(settings, "PFC_AVALIACOES_SYNC_MAX_BYTES", 2 * 1024 * 1024)
    try:
        if int(request.META.get("CONTENT_LENGTH") or 0) > limite:
            raise RequestDataTooBig
        body = request.body
        if len(body) > limite:
            raise RequestDataTooBig
        payload = json.loads(body.decode("utf-8"))
        return JsonResponse(publicar_resultados(payload))
    except RequestDataTooBig:
        return JsonResponse({"erro": "Payload acima do limite permitido."}, status=413)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"erro": "JSON inválido."}, status=400)
    except DadosInvalidos as exc:
        return JsonResponse({"erro": str(exc)}, status=422)
    except FonteAlterada as exc:
        return JsonResponse({"erro": str(exc)}, status=409)
    except (DatabaseError, ValidationError):
        logger.exception("Falha ao publicar resultados de avaliações")
        return JsonResponse({"erro": "Não foi possível publicar a análise. Os dados anteriores foram preservados."}, status=503)
