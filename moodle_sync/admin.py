from django.contrib import admin

from .models import (
    AvaliacaoAbertaMoodle,
    AvaliacaoMoodle,
    CursoCompletoUsuario,
    CursoConcluidoMoodle,
)


@admin.register(CursoConcluidoMoodle)
class CursoConcluidoMoodleAdmin(admin.ModelAdmin):
    list_display = (
        "usuario_pfc",
        "curso_moodle_id",
        "nome_curso",
        "carga_horaria",
        "data_conclusao",
    )
    list_per_page = 50
    show_full_result_count = False
    autocomplete_fields = ("usuario_pfc",)
    search_fields = ("usuario_pfc__nome", "usuario_pfc__cpf", "nome_curso")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("usuario_pfc")
            .defer("usuario_pfc__avatar_base64")
        )


@admin.register(CursoCompletoUsuario)
class CursoCompletoUsuarioAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "id_curso_moodle",
        "carga_horaria_curso_moodle",
        "data_inicio_curso_moodle",
        "data_fim_curso_moodle",
    )
    list_per_page = 50
    show_full_result_count = False
    autocomplete_fields = ("user",)
    search_fields = ("user__nome", "user__cpf", "id_curso_moodle")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("user")
            .defer("user__avatar_base64")
        )


@admin.register(AvaliacaoMoodle)
class AvaliacaoMoodleAdmin(admin.ModelAdmin):
    list_display = ("curso_moodle", "participante", "subtema", "nota")
    list_filter = ("subtema", "nota")
    search_fields = (
        "curso_moodle__nome_curso",
        "participante__nome",
        "participante__cpf",
    )
    list_per_page = 50
    show_full_result_count = False
    autocomplete_fields = ("curso_moodle", "participante")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "curso_moodle", "curso_moodle__usuario_pfc", "participante", "subtema"
            )
            .defer(
                "participante__avatar_base64",
                "curso_moodle__usuario_pfc__avatar_base64",
            )
        )


@admin.register(AvaliacaoAbertaMoodle)
class AvaliacaoAbertaMoodleAdmin(admin.ModelAdmin):
    list_display = ("curso_moodle", "participante")
    search_fields = (
        "curso_moodle__nome_curso",
        "participante__nome",
        "participante__cpf",
        "avaliacao",
    )
    list_per_page = 50
    show_full_result_count = False
    autocomplete_fields = ("curso_moodle", "participante")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("curso_moodle", "curso_moodle__usuario_pfc", "participante")
            .defer(
                "participante__avatar_base64",
                "curso_moodle__usuario_pfc__avatar_base64",
            )
        )
