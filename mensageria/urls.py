from django.urls import path
from .views import (
    alterar_status_participantes,
    email_status_batch_detail,
    enviar_emails_curso_participantes,
    enviar_emails_cursos,
    enviar_emails_por_curso_status,
    enviar_emails_por_curso_status_preview,
    enviar_emails_por_curso_status_confirmar,
    enviar_emails_por_curso_status_progress,
    enviar_emails_por_curso_status_stream,
    enviar_emails_por_curso_status_legado,
)

app_name = "mensageria"

urlpatterns = [
    path("enviar-emails/", enviar_emails_cursos, name="enviar_emails_cursos"),
    path(
        "enviar-emails/cursos/<int:curso_id>/",
        enviar_emails_curso_participantes,
        name="enviar_emails_curso_participantes",
    ),
    path(
        "enviar-emails/cursos/<int:curso_id>/alterar-status/",
        alterar_status_participantes,
        name="alterar_status_participantes",
    ),
    path(
        "enviar-emails/lotes/<str:job_id>/",
        email_status_batch_detail,
        name="email_status_batch_detail",
    ),
    path(
        "enviar-curso-status/",
        enviar_emails_por_curso_status,
        name="enviar_curso_status",
    ),
    path(
        "enviar-curso-status/legado/",
        enviar_emails_por_curso_status_legado,
        name="enviar_curso_status_legado",
    ),
    path(
        "enviar-curso-status/preview/",
        enviar_emails_por_curso_status_preview,
        name="enviar_curso_status_preview",
    ),
    path(
        "enviar-curso-status/confirmar/",
        enviar_emails_por_curso_status_confirmar,
        name="enviar_curso_status_confirmar",
    ),
    path(
        "enviar-curso-status/progresso/",
        enviar_emails_por_curso_status_progress,
        name="enviar_curso_status_progresso",
    ),
    path(
        "enviar-curso-status/stream/",
        enviar_emails_por_curso_status_stream,
        name="enviar_curso_status_stream",
    ),
]
