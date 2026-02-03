from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
import json
from django.core.mail import EmailMultiAlternatives
from django.http import StreamingHttpResponse
from django.shortcuts import render, redirect

from mensageria.forms import EnvioEmailCursoStatusForm
from mensageria.models import TagTemplate, MensagemTemplate
from mensageria.render import render_text

from pfc_app.models import Curso, Inscricao, StatusInscricao


@staff_member_required
def enviar_emails_por_curso_status(request):
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
                msg = EmailMultiAlternatives(
                    subject=assunto,
                    body=corpo,
                    to=[user.email],
                )
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
