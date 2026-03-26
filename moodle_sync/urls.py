from django.urls import path

from .views import painel_cursos_usuario, realizar_inscricao_curso

app_name = "moodle_sync"

urlpatterns = [
    path("cursos/", painel_cursos_usuario, name="painel_cursos_usuario"),
    path(
        "cursos/<int:curso_id>/inscrever/",
        realizar_inscricao_curso,
        name="inscrever_curso",
    ),
]
