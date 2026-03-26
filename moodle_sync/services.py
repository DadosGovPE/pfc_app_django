from datetime import datetime, timezone
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.html import strip_tags

from .models import CursoCompletoUsuario, CursoConcluidoMoodle

User = get_user_model()


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
    try:
        status = moodle_api_get(
            "core_completion_get_course_completion_status",
            userid=userid,
            courseid=courseid,
        )
    except ValueError as exc:
        mensagem = str(exc)
        if "Não existem critérios de conclusão" in mensagem or "There are no completion criteria" in mensagem:
            return None
        raise
    maiores_timestamps = []
    for comp in status.get("completionstatus", {}).get("completions", []):
        if comp.get("complete") and comp.get("timecompleted"):
            maiores_timestamps.append(comp["timecompleted"])
    if not maiores_timestamps:
        return None
    return timestamp_to_utc_datetime(max(maiores_timestamps))


def persistir_cursos_completos(user, cursos_concluidos, usuario_moodle_id=0):
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
                "usuario_moodle_id": usuario_moodle_id or 0,
                "nome_curso": curso["nome"],
                "carga_horaria": curso["carga_horaria"],
                "data_conclusao": curso["data_fim"],
            },
        )
        if usuario_moodle_id and curso_concluido.usuario_moodle_id != usuario_moodle_id:
            curso_concluido.usuario_moodle_id = usuario_moodle_id
        curso_concluido.nome_curso = curso["nome"]
        curso_concluido.carga_horaria = curso["carga_horaria"]
        curso_concluido.data_conclusao = curso["data_fim"]
        curso_concluido.save(
            update_fields=[
                "usuario_moodle_id",
                "nome_curso",
                "carga_horaria",
                "data_conclusao",
            ]
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
    cursos_salvos = persistir_cursos_completos(
        user,
        cards_concluidos,
        usuario_moodle_id=usuario_moodle["id"],
    )

    return (
        usuario_moodle,
        cpf,
        cards_inscritos_em_andamento,
        cards_disponiveis,
        cards_concluidos,
        cursos_salvos,
    )


def sincronizar_usuario_moodle(user):
    inicio = time.perf_counter()
    try:
        (
            usuario_moodle,
            cpf,
            cursos_em_andamento,
            cursos_disponiveis,
            cursos_concluidos,
            cursos_salvos,
        ) = montar_dashboard_cursos(user)
        return {
            "ok": True,
            "user_id": user.id,
            "cpf": cpf,
            "usuario": getattr(user, "nome", None) or getattr(user, "username", str(user)),
            "usuario_moodle_id": usuario_moodle["id"],
            "cursos_em_andamento": len(cursos_em_andamento),
            "cursos_disponiveis": len(cursos_disponiveis),
            "cursos_concluidos": len(cursos_concluidos),
            "cursos_salvos": cursos_salvos,
            "duration_seconds": round(time.perf_counter() - inicio, 2),
            "message": "Sincronização concluída com sucesso.",
        }
    except ValueError as exc:
        return {
            "ok": False,
            "user_id": user.id,
            "cpf": getattr(user, "cpf", ""),
            "usuario": getattr(user, "nome", None) or getattr(user, "username", str(user)),
            "duration_seconds": round(time.perf_counter() - inicio, 2),
            "message": str(exc),
        }


def sincronizar_todos_usuarios_moodle(queryset=None, limit=None, carreira_sigla=None):
    inicio_total = time.perf_counter()
    queryset = queryset or User.objects.select_related("carreira").order_by("id")
    if carreira_sigla:
        queryset = queryset.filter(carreira__sigla=carreira_sigla)
    if limit:
        queryset = queryset[:limit]

    resultados = []
    total_processados = 0
    total_sucesso = 0
    total_erro = 0
    total_cursos_salvos = 0

    for user in queryset.iterator():
        resultado = sincronizar_usuario_moodle(user)
        resultados.append(resultado)
        total_processados += 1
        if resultado["ok"]:
            total_sucesso += 1
            total_cursos_salvos += resultado.get("cursos_salvos", 0)
        else:
            total_erro += 1

    return {
        "total_processados": total_processados,
        "total_sucesso": total_sucesso,
        "total_erro": total_erro,
        "total_cursos_salvos": total_cursos_salvos,
        "duration_seconds": round(time.perf_counter() - inicio_total, 2),
        "resultados": resultados,
    }
