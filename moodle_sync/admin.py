from django.contrib import admin

from .models import CursoCompletoUsuario, CursoConcluidoMoodle


@admin.register(CursoConcluidoMoodle)
class CursoConcluidoMoodleAdmin(admin.ModelAdmin):
    list_display = (
        "usuario_pfc",
        "curso_moodle_id",
        "nome_curso",
        "carga_horaria",
        "data_conclusao",
    )
    search_fields = ("usuario_pfc__nome", "usuario_pfc__cpf", "nome_curso")


@admin.register(CursoCompletoUsuario)
class CursoCompletoUsuarioAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "id_curso_moodle",
        "carga_horaria_curso_moodle",
        "data_inicio_curso_moodle",
        "data_fim_curso_moodle",
    )
    search_fields = ("user__nome", "user__cpf", "id_curso_moodle")

