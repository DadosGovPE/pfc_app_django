from django.contrib import admin

from .models import GrupoPerguntas, Pergunta, Pesquisa, Resposta


class PerguntaInline(admin.TabularInline):
    model = Pergunta
    extra = 1


class GrupoPerguntaInline(admin.TabularInline):
    model = GrupoPerguntas
    extra = 0


class PesquisaAdmin(admin.ModelAdmin):
    inlines = [GrupoPerguntaInline, PerguntaInline]
    list_display = ("titulo", "data_inicio", "data_fim")
    search_fields = ("titulo",)


@admin.register(Resposta)
class RespostaAdmin(admin.ModelAdmin):
    list_display = (
        "usuario",
        "get_pesquisa",
        "get_pergunta_texto",
        "resposta_numero",
        "resposta_texto",
    )
    list_filter = ("pergunta__pesquisa", "pergunta__tipo")
    list_per_page = 50
    show_full_result_count = False
    autocomplete_fields = ("usuario",)
    search_fields = (
        "usuario__nome",
        "usuario__username",
        "usuario__cpf",
        "pergunta__texto",
        "pergunta__pesquisa__titulo",
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("usuario", "pergunta__pesquisa")
            .defer("usuario__avatar_base64")
        )

    def get_pergunta_texto(self, obj):
        return obj.pergunta.texto

    get_pergunta_texto.short_description = "Pergunta"

    def get_pesquisa(self, obj):
        return obj.pergunta.pesquisa.titulo

    get_pesquisa.short_description = "Pesquisa"


admin.site.register(Pesquisa, PesquisaAdmin)
admin.site.register(Pergunta)
