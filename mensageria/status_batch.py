import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from mensageria.models import (
    EmailStatusBatch,
    EmailStatusBatchItem,
    MensagemTemplate,
    TagTemplate,
)
from mensageria.render import build_email_bodies, render_text
from pfc_app.models import Curso, Inscricao, StatusInscricao


def _jobs_root() -> Path:
    return Path(settings.MEDIA_ROOT) / "mensageria" / "email_status_jobs"


def _update_batch(batch: EmailStatusBatch, **fields) -> None:
    for key, value in fields.items():
        setattr(batch, key, value)
    batch.save(update_fields=list(fields.keys()))


def _spawn_batch_processor(job_id: str) -> None:
    command = [
        sys.executable,
        str(settings.BASE_DIR / "manage.py"),
        "process_email_status_batch",
        job_id,
    ]
    log_path = _jobs_root() / job_id / "processor.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("ab")
    popen_kwargs = {
        "cwd": str(settings.BASE_DIR),
        "stdout": log_file,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = getattr(
            subprocess, "CREATE_NO_WINDOW", 0
        ) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        popen_kwargs["start_new_session"] = True
    subprocess.Popen(command, **popen_kwargs)
    log_file.close()


def create_status_batch(
    *,
    curso: Curso,
    inscricao_ids: list[int],
    status_destino: StatusInscricao,
    enviar_email: bool,
    template: MensagemTemplate | None,
    assunto: str,
    corpo: str,
    admin,
) -> EmailStatusBatch:
    cleaned_ids = sorted({int(inscricao_id) for inscricao_id in inscricao_ids})
    if not cleaned_ids:
        raise ValueError("Selecione ao menos uma inscricao.")
    if enviar_email and template is None:
        raise ValueError("Selecione um modelo de mensagem para enviar e-mail.")

    with transaction.atomic():
        inscricoes = list(
            Inscricao.objects.select_for_update()
            .select_related("participante", "status", "curso")
            .filter(id__in=cleaned_ids, curso=curso)
            .order_by("id")
        )
        if len(inscricoes) != len(cleaned_ids):
            raise ValueError("Alguma inscricao selecionada nao pertence ao curso.")

        changed = [
            inscricao
            for inscricao in inscricoes
            if inscricao.status_id != status_destino.id
        ]
        ignored = len(inscricoes) - len(changed)
        effective_assunto = (assunto or "").strip()
        effective_corpo = corpo or ""
        if template:
            effective_assunto = effective_assunto or template.assunto
            effective_corpo = effective_corpo or template.corpo

        batch = EmailStatusBatch.objects.create(
            admin=admin,
            curso=curso,
            status_destino=status_destino,
            template=template,
            enviar_email=enviar_email,
            assunto=effective_assunto,
            corpo=effective_corpo,
            status=(
                EmailStatusBatch.Status.QUEUED
                if enviar_email and changed
                else EmailStatusBatch.Status.COMPLETED
            ),
            current_step=(
                "Aguardando envio de e-mails"
                if enviar_email and changed
                else "Concluido"
            ),
            total_selecionado=len(inscricoes),
            total_alterado=len(changed),
            total_ignorado=ignored,
            finished_at=timezone.now() if not (enviar_email and changed) else None,
        )

        items = [
            EmailStatusBatchItem(
                batch=batch,
                inscricao=inscricao,
                participante=inscricao.participante,
                status_origem=inscricao.status,
                email=inscricao.participante.email or "",
            )
            for inscricao in changed
            if enviar_email
        ]
        if items:
            EmailStatusBatchItem.objects.bulk_create(items)

        for inscricao in changed:
            inscricao.status = status_destino
        if changed:
            Inscricao.objects.bulk_update(changed, ["status"])

        if enviar_email and changed:
            transaction.on_commit(lambda: _spawn_batch_processor(batch.job_id))

        return batch


def _refresh_batch_totals(batch: EmailStatusBatch) -> None:
    counts = {
        row["status"]: row["total"]
        for row in batch.items.values("status").annotate(total=Count("id"))
    }
    _update_batch(
        batch,
        total_enviado=counts.get(EmailStatusBatchItem.Status.SENT, 0),
        total_sem_email=counts.get(EmailStatusBatchItem.Status.NO_EMAIL, 0),
        total_falha=counts.get(EmailStatusBatchItem.Status.FAILED, 0),
    )


def process_email_status_batch(job_id: str) -> bool:
    try:
        batch = (
            EmailStatusBatch.objects.select_related(
                "curso", "status_destino", "template"
            )
            .prefetch_related("items")
            .get(job_id=job_id)
        )
    except EmailStatusBatch.DoesNotExist:
        return False

    if batch.status == EmailStatusBatch.Status.COMPLETED:
        return True

    try:
        _update_batch(
            batch,
            status=EmailStatusBatch.Status.RUNNING,
            current_step="Enviando e-mails",
            started_at=batch.started_at or timezone.now(),
            error_message="",
        )
        tags = TagTemplate.objects.filter(ativa=True).select_related("content_type")
        tags_by_name = {tag.nome: tag for tag in tags}
        items = (
            batch.items.select_related(
                "inscricao",
                "inscricao__curso",
                "participante",
                "status_origem",
            )
            .exclude(status=EmailStatusBatchItem.Status.SENT)
            .order_by("id")
        )

        for item in items.iterator(chunk_size=100):
            if not item.email:
                item.status = EmailStatusBatchItem.Status.NO_EMAIL
                item.error_message = "Participante sem e-mail cadastrado."
                item.save(update_fields=["status", "error_message"])
                continue

            ctx = {
                "user": item.participante,
                "curso": batch.curso,
                "inscricao": item.inscricao,
                "status_inscricao": batch.status_destino,
            }
            assunto = render_text(batch.assunto, tags_by_name, ctx)
            corpo = render_text(batch.corpo, tags_by_name, ctx)

            try:
                corpo_texto, corpo_html = build_email_bodies(corpo)
                msg = EmailMultiAlternatives(
                    subject=assunto,
                    body=corpo_texto,
                    to=[item.email],
                )
                msg.attach_alternative(corpo_html, "text/html")
                msg.send()
                item.status = EmailStatusBatchItem.Status.SENT
                item.error_message = ""
                item.sent_at = timezone.now()
                item.save(update_fields=["status", "error_message", "sent_at"])
            except Exception as exc:
                item.status = EmailStatusBatchItem.Status.FAILED
                item.error_message = str(exc)
                item.save(update_fields=["status", "error_message"])

        _refresh_batch_totals(batch)
        _update_batch(
            batch,
            status=EmailStatusBatch.Status.COMPLETED,
            current_step="Concluido",
            finished_at=timezone.now(),
        )
        return True
    except Exception as exc:
        _refresh_batch_totals(batch)
        _update_batch(
            batch,
            status=EmailStatusBatch.Status.FAILED,
            current_step="Falhou",
            error_message=str(exc),
            finished_at=timezone.now(),
        )
        return True
