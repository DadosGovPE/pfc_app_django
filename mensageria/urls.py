from django.urls import path
from .views import enviar_emails_por_curso_status

app_name = "mensageria"

urlpatterns = [
    path(
        "enviar-curso-status/",
        enviar_emails_por_curso_status,
        name="enviar_curso_status",
    ),
]
