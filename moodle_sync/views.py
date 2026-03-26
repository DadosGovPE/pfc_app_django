from datetime import datetime, timezone

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.html import strip_tags
from django.views.decorators.http import require_POST

from .models import CursoCompletoUsuario, CursoConcluidoMoodle


def timestamp_to_utc_datetime(timestamp):
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def optional_timestamp_to_utc_datetime(timestamp):
    if not timestamp:
        return None
    if isinstance(timestamp, datetime):
        return timestamp
    return timestamp_to_utc_datetime(timestamp)


def moodle_api_get(wsfunction, **params):
    token = getattr(settings, "MOODLE_TOKEN", "")
    moodle_url = getattr(settings, "MOODLE_URL", "").rstrip("/")
    if not token or not moodle_url:
        raise ValueError("Configuração do Moodle ausente no ambiente.")

    query = urlencode(
        {
            "wstoken": token,
            "wsfunction": wsfunction,
            "moodlewsrestformat": "json",
            **params,
        },
        doseq=True,
    )
    try:
        with urlopen(f"{moodle_url}/webservice/rest/server.php?{query}", timeout=20) as response:
            payload = response.read().decode("utf-8")
    except (HTTPError, URLError) as exc:
        raise ValueError(f"Erro ao consultar o Moodle: {exc}") from exc

    data = json.loads(payload)

    if isinstance(data, dict) and data.get("exception"):
        raise ValueError(data.get("message", "Erro ao consultar o Moodle."))

    return data


def normalizar_cpf(valor):
    return "".join(char for char in (valor or "") if char.isdigit())


def obter_campo_customizado(usuario, shortname):
    for campo in usuario.get("customfields", []):
        if campo.get("shortname") == shortname:
            return campo.get("value") or ""
    return ""


def buscar_usuario_moodle_por_cpf(cpf):
    cpf_normalizado = normalizar_cpf(cpf)
    if len(cpf_normalizado) != 11:
        raise ValueError("Informe um CPF com 11 dígitos.")

    usuarios = moodle_api_get(
        "core_user_get_users",
        **{
            "criteria[0][key]": "cpf",
            "criteria[0][value]": cpf_normalizado,
        },
    )
    candidatos = usuarios.get("users", [])
    for usuario in candidatos:
        if normalizar_cpf(obter_campo_customizado(usuario, "cpf")) == cpf_normalizado:
            return usuario
    return None


def extrair_carga_horaria(curso):
    for campo in curso.get("customfields", []):
        if campo.get("shortname") == "carga_horaria":
            return campo.get("value") or "N/D"
    return "N/D"


def resumir_texto_html(texto):
    texto_limpo = strip_tags(texto or "").strip()
    if not texto_limpo:
        return "Sem descrição disponível."
    if len(texto_limpo) <= 180:
        return texto_limpo
    return f"{texto_limpo[:177].rstrip()}..."


def serializar_curso_catalogo(curso, progresso=None, inscrito=False):
    progresso_normalizado = progresso if progresso is not None else 0
    data_inicio = optional_timestamp_to_utc_datetime(curso.get("startdate"))
    moodle_url = getattr(settings, "MOODLE_URL", "").rstrip("/")
    return {
        "id": curso["id"],
        "nome": curso.get("displayname") or curso.get("fullname"),
        "resumo": resumir_texto_html(curso.get("summary")),
        "resumo_completo": curso.get("summary") or "",
        "imagem": curso.get("courseimage"),
        "carga_horaria": extrair_carga_horaria(curso),
        "progresso": progresso_normalizado,
        "inscrito": inscrito,
        "concluido": progresso_normalizado >= 100,
        "data_inicio": data_inicio,
        "data_inicio_txt": data_inicio.strftime("%d/%m/%Y") if data_inicio else "N/A",
        "data_fim": optional_timestamp_to_utc_datetime(curso.get("timecompleted")),
        "shortname": curso.get("shortname") or "",
        "categoria": curso.get("categoryname") or "N/A",
        "link": f"{moodle_url}/course/view.php?id={curso['id']}",
    }


def obter_data_conclusao_curso(userid, courseid):
    status = moodle_api_get(
        "core_completion_get_course_completion_status",
        userid=userid,
        courseid=courseid,
    )
    maiores_timestamps = []
    for comp in status.get("completionstatus", {}).get("completions", []):
        if comp.get("complete") and comp.get("timecompleted"):
            maiores_timestamps.append(comp["timecompleted"])
    if not maiores_timestamps:
        return None
    return timestamp_to_utc_datetime(max(maiores_timestamps))


def persistir_cursos_completos(user, cursos_concluidos):
    novos_registros = 0

    for curso in cursos_concluidos:
        _, created = CursoCompletoUsuario.objects.update_or_create(
            user=user,
            id_curso_moodle=curso["id"],
            defaults={
                "carga_horaria_curso_moodle": curso["carga_horaria"],
                "data_inicio_curso_moodle": curso["data_inicio"],
                "data_fim_curso_moodle": curso["data_fim"],
            },
        )
        curso_concluido, _ = CursoConcluidoMoodle.objects.get_or_create(
            usuario_pfc=user,
            curso_moodle_id=curso["id"],
            defaults={
                "usuario_moodle_id": 0,
                "nome_curso": curso["nome"],
                "carga_horaria": curso["carga_horaria"],
                "data_conclusao": curso["data_fim"],
            },
        )
        curso_concluido.nome_curso = curso["nome"]
        curso_concluido.carga_horaria = curso["carga_horaria"]
        curso_concluido.data_conclusao = curso["data_fim"]
        curso_concluido.save(
            update_fields=["nome_curso", "carga_horaria", "data_conclusao"]
        )
        if created:
            novos_registros += 1

    return novos_registros


def montar_dashboard_cursos(user):
    cpf = normalizar_cpf(getattr(user, "cpf", ""))
    if len(cpf) != 11:
        raise ValueError("O usuário logado precisa ter um CPF com 11 dígitos cadastrado.")

    usuario_moodle = buscar_usuario_moodle_por_cpf(cpf)
    if not usuario_moodle:
        raise ValueError("Usuário não encontrado no Moodle para o CPF informado.")

    cursos_inscritos = moodle_api_get(
        "core_enrol_get_users_courses",
        userid=usuario_moodle["id"],
    )
    catalogo = moodle_api_get("core_course_get_courses")

    catalogo_indexado = {
        curso["id"]: curso
        for curso in catalogo
        if curso.get("visible") and curso.get("id") != 1
    }
    ids_inscritos = {curso["id"] for curso in cursos_inscritos}

    cards_inscritos = []
    for curso in cursos_inscritos:
        base = catalogo_indexado.get(
            curso["id"],
            {
                "id": curso["id"],
                "fullname": curso.get("fullname"),
                "displayname": curso.get("displayname"),
                "summary": curso.get("summary", ""),
                "courseimage": curso.get("courseimage"),
                "startdate": curso.get("startdate"),
                "customfields": [],
            },
        )
        progresso = curso.get("progress")
        if progresso is None and curso.get("completed"):
            progresso = 100
        progresso_normalizado = progresso if progresso is not None else 0
        curso_completo = progresso_normalizado >= 100
        curso_base = {
            **base,
            "startdate": curso.get("startdate") or base.get("startdate"),
            "timecompleted": None,
        }
        if curso_completo:
            curso_base["timecompleted"] = obter_data_conclusao_curso(
                usuario_moodle["id"],
                curso["id"],
            )
        cards_inscritos.append(
            serializar_curso_catalogo(
                curso_base,
                progresso=progresso_normalizado,
                inscrito=True,
            )
        )

    cards_disponiveis = [
        serializar_curso_catalogo(curso)
        for curso in catalogo_indexado.values()
        if curso["id"] not in ids_inscritos
    ]

    cards_inscritos_em_andamento = [
        curso for curso in cards_inscritos if curso["progresso"] < 100
    ]
    cards_concluidos = [curso for curso in cards_inscritos if curso["progresso"] >= 100]

    cards_inscritos_em_andamento.sort(key=lambda curso: curso["nome"].lower())
    cards_concluidos.sort(key=lambda curso: curso["nome"].lower())
    cards_disponiveis.sort(key=lambda curso: curso["nome"].lower())
    cursos_salvos = persistir_cursos_completos(user, cards_concluidos)

    return (
        usuario_moodle,
        cpf,
        cards_inscritos_em_andamento,
        cards_disponiveis,
        cards_concluidos,
        cursos_salvos,
    )


@login_required
def painel_cursos_usuario(request):
    usuario_moodle = None
    cpf = normalizar_cpf(getattr(request.user, "cpf", ""))
    cursos_em_andamento = []
    cursos_disponiveis = []
    cursos_concluidos = []
    cursos_salvos = 0
    erro = None

    try:
        (
            usuario_moodle,
            cpf,
            cursos_em_andamento,
            cursos_disponiveis,
            cursos_concluidos,
            cursos_salvos,
        ) = montar_dashboard_cursos(request.user)
    except ValueError as exc:
        erro = str(exc)

    return render(
        request,
        "moodle_sync/painel_cursos.html",
        {
            "cpf": cpf,
            "usuario_moodle": usuario_moodle,
            "cursos_em_andamento": cursos_em_andamento,
            "cursos_disponiveis": cursos_disponiveis,
            "cursos_concluidos": cursos_concluidos,
            "cursos_salvos": cursos_salvos,
            "erro": erro,
        },
    )


@login_required
@require_POST
def realizar_inscricao_curso(request, curso_id):
    try:
        curso_id_int = int(curso_id)
        if curso_id_int <= 0:
            raise ValueError("Curso inválido.")
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "message": "ID do curso inválido."}, status=400)

    try:
        cpf = normalizar_cpf(getattr(request.user, "cpf", ""))
        if len(cpf) != 11:
            return JsonResponse(
                {
                    "ok": False,
                    "message": "O usuário precisa ter CPF com 11 dígitos.",
                },
                status=400,
            )

        usuario_moodle = buscar_usuario_moodle_por_cpf(cpf)
        if not usuario_moodle:
            return JsonResponse(
                {
                    "ok": False,
                    "message": "Usuário não encontrado no Moodle para o CPF informado.",
                },
                status=400,
            )

        cursos_atuais = moodle_api_get(
            "core_enrol_get_users_courses",
            userid=usuario_moodle["id"],
        )
        curso_id_busca = str(curso_id_int)
        if any(
            str(c.get("id")).strip() == curso_id_busca
            for c in cursos_atuais
            if c.get("id") is not None
        ):
            return JsonResponse(
                {"ok": False, "message": "Você já está inscrito nesse curso."},
                status=400,
            )

        resposta = moodle_api_get(
            "enrol_manual_enrol_users",
            **{
                "enrolments[0][roleid]": 5,
                "enrolments[0][userid]": usuario_moodle["id"],
                "enrolments[0][courseid]": curso_id_int,
            },
        )

        avisos = resposta.get("warnings", []) if isinstance(resposta, dict) else []
        if avisos:
            mensagens = [
                aviso.get("message", "Erro ao realizar a inscrição.")
                for aviso in avisos
                if isinstance(aviso, dict)
            ]
            return JsonResponse(
                {
                    "ok": False,
                    "message": " ".join(mensagens)
                    if mensagens
                    else "Não foi possível completar a inscrição.",
                },
                status=400,
            )

        return JsonResponse({"ok": True, "message": "Inscrição realizada com sucesso."})
    except ValueError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=500)
