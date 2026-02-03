from django.urls import path
from .views import (
    enviar_emails_por_curso_status,
    enviar_emails_por_curso_status_preview,
    enviar_emails_por_curso_status_confirmar,
    enviar_emails_por_curso_status_progress,
    enviar_emails_por_curso_status_stream,
)

app_name = "mensageria"

urlpatterns = [
    path(
        "enviar-curso-status/",
        enviar_emails_por_curso_status,
        name="enviar_curso_status",
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
