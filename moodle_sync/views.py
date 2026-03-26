from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .services import (
    buscar_usuario_moodle_por_cpf,
    montar_dashboard_cursos,
    moodle_api_get,
    normalizar_cpf,
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
