from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
import json
from django.core.mail import EmailMultiAlternatives
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import StreamingHttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from mensageria.forms import EnvioEmailCursoStatusForm
from mensageria.models import EmailStatusBatch, TagTemplate, MensagemTemplate
from mensageria.render import build_email_bodies, render_text
from mensageria.status_batch import create_status_batch

from pfc_app.models import Curso, Inscricao, StatusInscricao


@staff_member_required
def enviar_emails_por_curso_status(request):
    return redirect("mensageria:enviar_emails_cursos")


@staff_member_required
@require_GET
def enviar_emails_cursos(request):
    query = (request.GET.get("q") or "").strip()
    cursos = Curso.objects.select_related("status").order_by(
        "-data_inicio", "-data_criacao", "nome_curso"
    ).filter(
        Q(status__nome__iexact="A INICIAR")
        | Q(status__nome__iexact="EM ANDAMENTO")
    )
    if query:
        cursos = cursos.filter(nome_curso__icontains=query)

    paginator = Paginator(cursos, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    recent_batches = EmailStatusBatch.objects.select_related(
        "curso", "status_destino"
    ).order_by("-created_at")[:5]
    return render(
        request,
        "mensageria/enviar_emails_cursos.html",
        {
            "page_obj": page_obj,
            "query": query,
            "recent_batches": recent_batches,
        },
    )


@staff_member_required
@require_GET
def enviar_emails_curso_participantes(request, curso_id):
    curso = get_object_or_404(Curso.objects.select_related("status"), id=curso_id)
    inscricoes = (
        Inscricao.objects.select_related("participante", "status")
        .filter(curso=curso)
        .order_by("status__nome", "participante__nome")
    )
    secoes_map = {}
    for inscricao in inscricoes:
        status_nome = inscricao.status.nome if inscricao.status_id else "Sem status"
        status_id = str(inscricao.status_id or "sem-status")
        key = (status_id, status_nome)
        secoes_map.setdefault(key, []).append(inscricao)

    secoes = [
        {"status_id": status_id, "status_nome": status_nome, "inscricoes": values}
        for (status_id, status_nome), values in secoes_map.items()
    ]
    statuses = StatusInscricao.objects.all().order_by("nome")
    templates = MensagemTemplate.objects.filter(ativo=True).order_by("nome")
    return render(
        request,
        "mensageria/enviar_emails_curso_participantes.html",
        {
            "curso": curso,
            "secoes": secoes,
            "statuses": statuses,
            "templates": templates,
            "total_inscricoes": inscricoes.count(),
        },
    )


@staff_member_required
@require_POST
def alterar_status_participantes(request, curso_id):
    curso = get_object_or_404(Curso, id=curso_id)
    status_destino_id = request.POST.get("status_destino")
    if not status_destino_id:
        messages.error(request, "Selecione o status de destino.")
        return redirect("mensageria:enviar_emails_curso_participantes", curso_id=curso.id)
    status_destino = get_object_or_404(StatusInscricao, id=status_destino_id)
    inscricao_ids = request.POST.getlist("inscricoes")
    enviar_email = request.POST.get("enviar_email") == "on"
    template = None
    if enviar_email:
        template_id = request.POST.get("template")
        if not template_id:
            messages.error(request, "Selecione um modelo de mensagem.")
            return redirect(
                "mensageria:enviar_emails_curso_participantes", curso_id=curso.id
            )
        template = get_object_or_404(MensagemTemplate, id=template_id)

    try:
        batch = create_status_batch(
            curso=curso,
            inscricao_ids=inscricao_ids,
            status_destino=status_destino,
            enviar_email=enviar_email,
            template=template,
            assunto=request.POST.get("assunto") or "",
            corpo=request.POST.get("corpo") or "",
            admin=request.user,
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("mensageria:enviar_emails_curso_participantes", curso_id=curso.id)

    messages.success(
        request,
        (
            f"Status alterado em {batch.total_alterado} inscricao(oes). "
            f"{batch.total_ignorado} ja estava(m) no status escolhido."
        ),
    )
    return redirect("mensageria:email_status_batch_detail", job_id=batch.job_id)


@staff_member_required
@require_GET
def email_status_batch_detail(request, job_id):
    batch = get_object_or_404(
        EmailStatusBatch.objects.select_related(
            "curso", "admin", "status_destino", "template"
        ),
        job_id=job_id,
    )
    items = batch.items.select_related("participante", "inscricao", "status_origem")
    return render(
        request,
        "mensageria/email_status_batch_detail.html",
        {
            "batch": batch,
            "items": items,
            "is_processing": batch.is_processing,
        },
    )


@staff_member_required
def enviar_emails_por_curso_status_legado(request):
    form = EnvioEmailCursoStatusForm()
    return render(
        request, "mensageria/enviar_emails_por_curso_status.html", {"form": form}
    )


def _build_queryset(curso, status, concluido, limite):
    qs = (
        Inscricao.objects.select_related("curso", "participante", "status")
        .filter(curso=curso)
        .order_by("id")
    )

    # status opcional
    if status:
        qs = qs.filter(status=status)

    # concluÃ­do opcional
    if concluido == "1":
        qs = qs.filter(concluido=True)
    elif concluido == "0":
        qs = qs.filter(concluido=False)

    if limite:
        qs = qs[:limite]

    return qs


@staff_member_required
def enviar_emails_por_curso_status_preview(request):
    if request.method != "POST":
        return redirect("mensageria:enviar_curso_status")

    form = EnvioEmailCursoStatusForm(request.POST)
    if not form.is_valid():
        return render(
            request, "mensageria/enviar_emails_por_curso_status.html", {"form": form}
        )

    curso = form.cleaned_data["curso"]
    template = form.cleaned_data["template"]
    status = form.cleaned_data["status"]
    dry_run = form.cleaned_data["dry_run"]
    limite = form.cleaned_data.get("limite")
    concluido = form.cleaned_data.get("concluido")

    qs = _build_queryset(curso, status, concluido, limite)
    total = qs.count()
    if total == 0:
        messages.warning(
            request, "Nenhuma inscriÃ§Ã£o encontrada para esse curso e status."
        )
        return redirect("mensageria:enviar_curso_status")

    if concluido == "1":
        concluido_label = "Sim"
    elif concluido == "0":
        concluido_label = "Nao"
    else:
        concluido_label = "(Todos)"

    return render(
        request,
        "mensageria/enviar_emails_por_curso_status_preview.html",
        {
            "form": form,
            "total": total,
            "curso": curso,
            "template": template,
            "status": status,
            "concluido_label": concluido_label,
            "limite": limite,
            "dry_run": dry_run,
            "assunto": template.assunto,
            "corpo": template.corpo,
        },
    )


@staff_member_required
def enviar_emails_por_curso_status_confirmar(request):
    if request.method != "POST":
        return redirect("mensageria:enviar_curso_status")

    form = EnvioEmailCursoStatusForm(request.POST)
    if not form.is_valid():
        return render(
            request, "mensageria/enviar_emails_por_curso_status.html", {"form": form}
        )

    curso = form.cleaned_data["curso"]
    template = form.cleaned_data["template"]
    status = form.cleaned_data["status"]
    dry_run = form.cleaned_data["dry_run"]
    limite = form.cleaned_data.get("limite")
    concluido = form.cleaned_data.get("concluido")

    qs = _build_queryset(curso, status, concluido, limite)
    total = qs.count()
    if total == 0:
        messages.warning(
            request, "Nenhuma inscriÃ§Ã£o encontrada para esse curso e status."
        )
        return redirect("mensageria:enviar_curso_status")

    assunto_base = (request.POST.get("assunto") or "").strip() or template.assunto
    corpo_base = request.POST.get("corpo") or template.corpo

    request.session["mensageria_envio_payload"] = {
        "curso_id": curso.id,
        "template_id": template.id,
        "status_id": status.id if status else None,
        "concluido": concluido,
        "limite": limite,
        "dry_run": bool(dry_run),
        "assunto": assunto_base,
        "corpo": corpo_base,
    }
    request.session.modified = True
    return redirect("mensageria:enviar_curso_status_progresso")


@staff_member_required
def enviar_emails_por_curso_status_progress(request):
    payload = request.session.get("mensageria_envio_payload")
    if not payload:
        messages.warning(request, "Nenhum envio pendente para acompanhar.")
        return redirect("mensageria:enviar_curso_status")

    return render(
        request,
        "mensageria/enviar_emails_por_curso_status_progresso.html",
        {},
    )


def _sse_event(data: dict):
    return f"data: {json.dumps(data, ensure_ascii=True)}\n\n"


@staff_member_required
def enviar_emails_por_curso_status_stream(request):
    payload = request.session.pop("mensageria_envio_payload", None)
    request.session.modified = True

    if not payload:
        def error_stream():
            yield _sse_event({"type": "error", "message": "Nenhum envio pendente."})

        return StreamingHttpResponse(error_stream(), content_type="text/event-stream")

    curso = Curso.objects.get(id=payload["curso_id"])
    template = MensagemTemplate.objects.get(id=payload["template_id"])
    status = None
    if payload.get("status_id"):
        status = StatusInscricao.objects.get(id=payload["status_id"])
    concluido = payload.get("concluido")
    limite = payload.get("limite")
    dry_run = payload.get("dry_run")
    assunto_base = payload.get("assunto") or template.assunto
    corpo_base = payload.get("corpo") or template.corpo

    qs = _build_queryset(curso, status, concluido, limite)
    total = qs.count()
    tags = TagTemplate.objects.filter(ativa=True).select_related("content_type")
    tags_by_name = {t.nome: t for t in tags}

    def stream():
        yield _sse_event({"type": "start", "total": total, "dry_run": bool(dry_run)})
        enviados = 0
        falhas = 0
        sem_email = 0

        for insc in qs.iterator(chunk_size=200):
            user = insc.participante
            if not user.email:
                sem_email += 1
                yield _sse_event(
                    {
                        "type": "item",
                        "status": "sem_email",
                        "user": str(user),
                    }
                )
                continue

            ctx = {
                "user": user,
                "curso": insc.curso,
                "inscricao": insc,
                "status_inscricao": insc.status,
            }

            assunto = render_text(assunto_base, tags_by_name, ctx)
            corpo = render_text(corpo_base, tags_by_name, ctx)

            if dry_run:
                yield _sse_event(
                    {
                        "type": "item",
                        "status": "dry_run",
                        "user": str(user),
                        "email": user.email,
                    }
                )
                continue

            try:
                corpo_texto, corpo_html = build_email_bodies(corpo)
                msg = EmailMultiAlternatives(
                    subject=assunto,
                    body=corpo_texto,
                    to=[user.email],
                )
                msg.attach_alternative(corpo_html, "text/html")
                msg.send()
                enviados += 1
                yield _sse_event(
                    {
                        "type": "item",
                        "status": "enviado",
                        "user": str(user),
                        "email": user.email,
                    }
                )
            except Exception as exc:
                falhas += 1
                yield _sse_event(
                    {
                        "type": "item",
                        "status": "erro",
                        "user": str(user),
                        "email": user.email,
                        "message": str(exc),
                    }
                )

        yield _sse_event(
            {
                "type": "done",
                "total": total,
                "enviados": enviados,
                "sem_email": sem_email,
                "falhas": falhas,
            }
        )

    response = StreamingHttpResponse(stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
