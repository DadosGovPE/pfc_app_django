from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.mail import EmailMultiAlternatives
from django.shortcuts import render, redirect

from mensageria.forms import EnvioEmailCursoStatusForm
from mensageria.models import TagTemplate
from mensageria.render import render_template

from pfc_app.models import Inscricao


@staff_member_required
def enviar_emails_por_curso_status(request):
    if request.method == "POST":
        form = EnvioEmailCursoStatusForm(request.POST)
        if form.is_valid():
            curso = form.cleaned_data["curso"]
            template = form.cleaned_data["template"]
            status = form.cleaned_data["status"]
            dry_run = form.cleaned_data["dry_run"]
            limite = form.cleaned_data.get("limite")
            concluido = form.cleaned_data.get("concluido")

            qs = (
                Inscricao.objects.select_related("curso", "participante", "status")
                .filter(curso=curso)
                .order_by("id")
            )

            # status opcional
            if status:
                qs = qs.filter(status=status)

            # concluído opcional
            if concluido == "1":
                qs = qs.filter(concluido=True)
            elif concluido == "0":
                qs = qs.filter(concluido=False)

            if limite:
                qs = qs[:limite]

            total = qs.count()
            if total == 0:
                messages.warning(
                    request, "Nenhuma inscrição encontrada para esse curso e status."
                )
                return redirect(request.path)

            if dry_run:
                messages.info(request, f"DRY RUN: {total} e-mails seriam enviados.")
                return redirect(request.path)

            tags = TagTemplate.objects.filter(ativa=True).select_related("content_type")

            enviados = 0
            falhas = 0
            sem_email = 0

            for insc in qs.iterator(chunk_size=200):
                user = insc.participante
                if not user.email:
                    sem_email += 1
                    continue

                ctx = {
                    "user": user,
                    "curso": insc.curso,
                    "inscricao": insc,
                    "status_inscricao": insc.status,  # se quiser tags diretas
                }

                payload = render_template(template, context=ctx, tags_queryset=tags)
                assunto = (payload.get("assunto") or "").strip() or template.assunto
                corpo = payload.get("corpo") or ""

                try:
                    msg = EmailMultiAlternatives(
                        subject=assunto,
                        body=corpo,
                        to=[user.email],
                    )
                    msg.send()
                    enviados += 1
                except Exception:
                    falhas += 1

            messages.success(
                request,
                f"Envio finalizado. Total filtrado: {total}. Enviados: {enviados}. "
                f"Sem e-mail: {sem_email}. Falhas: {falhas}.",
            )
            return redirect(request.path)
    else:
        form = EnvioEmailCursoStatusForm()

    return render(
        request, "mensageria/enviar_emails_por_curso_status.html", {"form": form}
    )
