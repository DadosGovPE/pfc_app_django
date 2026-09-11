from django.contrib import admin
from django.db.models import Count, Q
from django.contrib.auth.admin import UserAdmin
from .models import *
from django import forms
from django.contrib import messages
from django.contrib.admin.widgets import RelatedFieldWidgetWrapper


# Curso, User, Inscricao, StatusCurso, StatusInscricao, \
# StatusValidacao, Avaliacao, Validacao_CH,Certificado, \
# RequerimentoCH, Competencia, Trilha
from .forms import UsuarioForm
from django.utils.html import format_html
from django.urls import reverse


class CachedRelatedChoiceField(forms.ChoiceField):
    """Model choice rendered from objects already loaded for this request."""

    def __init__(self, objects, *args, **kwargs):
        self.objects_by_id = {str(obj.pk): obj for obj in objects}
        choices = [("", "---------")]
        choices.extend((str(obj.pk), str(obj)) for obj in objects)
        super().__init__(choices=choices, *args, **kwargs)

    def prepare_value(self, value):
        return getattr(value, "pk", value)

    def has_changed(self, initial, data):
        if self.disabled:
            return False
        initial_id = self.prepare_value(initial)
        return str(initial_id or "") != str(data or "")

    def clean(self, value):
        object_id = super().clean(value)
        if not object_id:
            return None
        return self.objects_by_id[str(object_id)]


def cached_related_changelist_form(model, field_name, objects, base_form=forms.ModelForm):
    """Build a changelist form without querying the same choices for every row."""

    meta = type("Meta", (), {"model": model, "fields": "__all__"})
    attributes = {
        "__module__": __name__,
        "Meta": meta,
        field_name: CachedRelatedChoiceField(
            objects, required=not model._meta.get_field(field_name).blank
        ),
    }
    return type(f"{model.__name__}CachedChangelistForm", (base_form,), attributes)


class CronogramaExecucaoInline(admin.TabularInline):
    model = CronogramaExecucao
    extra = 1
    fields = ["aula", "turno", "conteudo", "atividade"]
    # list_display = ('curso', 'participante', 'ch_valida', 'condicao_na_acao', 'status')
    # ordering = ['-participante__nome']


class PlanoCursoAdmin(admin.ModelAdmin):
    inlines = [CronogramaExecucaoInline]
    list_display = ("curso",)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("curso")
            .defer(
                "curso__ementa_curso",
                "curso__descricao",
                "curso__observacao",
            )
        )


class TemaAdmin(admin.ModelAdmin):
    list_display = [
        "nome",
        "evento",
    ]
    list_editable = ("evento",)


class SubtemaAdmin(admin.ModelAdmin):
    list_display = ["nome", "tema", "cor"]
    list_filter = ("tema",)


class LotacaoAdmin(admin.ModelAdmin):
    search_fields = ("nome",)


class LotacaoEspecificaAdmin(admin.ModelAdmin):
    list_select_related = ("lotacao",)
    search_fields = ("nome", "sigla", "lotacao__nome")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("lotacao")


class CarreiraAdmin(admin.ModelAdmin):
    search_fields = ("nome", "sigla")


class CursoNomeTurmaFilter(admin.SimpleListFilter):
    title = "Curso e Turma"
    parameter_name = "curso_nome_turma"

    def lookups(self, request, model_admin):
        cursos = Curso.objects.all().values_list("id", "nome_curso", "turma")
        return [(curso[0], f"{curso[1]} - {curso[2]}") for curso in cursos]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(id=self.value())
        return queryset


class CursoRelacionadoFilter(admin.SimpleListFilter):
    title = "Curso"
    parameter_name = "curso_id"

    def lookups(self, request, model_admin):
        cursos = Curso.objects.values_list("id", "nome_curso", "turma")
        return [(curso_id, f"{nome} - {turma}") for curso_id, nome, turma in cursos]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(curso_id=self.value())
        return queryset


class LotacaoEspecificaFilter(admin.SimpleListFilter):
    title = "Lotação específica"
    parameter_name = "lotacao_especifica_fk_id"

    def lookups(self, request, model_admin):
        lotacoes = LotacaoEspecifica.objects.values_list(
            "id", "nome", "lotacao__nome"
        )
        return [
            (lotacao_id, f"{lotacao_nome} - {nome}")
            for lotacao_id, nome, lotacao_nome in lotacoes
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(lotacao_especifica_fk_id=self.value())
        return queryset


class ArquivoCursoInline(admin.TabularInline):
    model = ArquivoCurso
    extra = 1


class CursoAdmin(admin.ModelAdmin):
    inlines = [ArquivoCursoInline]
    list_per_page = 25
    show_full_result_count = False

    list_display = (
        "nome_formatado",
        "data_inicio",
        "data_termino",
        "vagas",
        "numero_inscritos",
        "status",
        "curso_priorizado",
        "periodo_avaliativo",
        "gerar_certificados",
        "gerar_ata",
    )
    fields = [
        "nome_curso",
        "ementa_curso",
        "modalidade",
        "tipo_reconhecimento",
        "ch_curso",
        "vagas",
        "ver_inscricoes",
        "categoria",
        "trilha",
        "curso_priorizado",
        "descricao",
        ("data_inicio", "data_termino"),
        "turno",
        "turma",
        "inst_certificadora",
        "inst_promotora",
        "coordenador",
        "origem_pagamento",
        "status",
        "periodo_avaliativo",
        "eh_evento",
        "is_externo",
        "material_curso",
        "horario",
        "observacao",
    ]
    list_filter = (
        CursoNomeTurmaFilter,
        "data_inicio",
        "data_termino",
        "periodo_avaliativo",
        "origem_pagamento",
    )
    list_editable = (
        "status",
        "periodo_avaliativo",
        "curso_priorizado",
    )
    autocomplete_fields = ["curso_priorizado", "coordenador"]
    readonly_fields = ["ver_inscricoes"]
    search_fields = ["nome_curso", "turma"]
    ordering = ["-data_inicio"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("status", "curso_priorizado", "origem_pagamento")
            .annotate(
                total_inscritos=Count(
                    "inscricao",
                    filter=~Q(inscricao__status__nome="CANCELADA")
                    & Q(inscricao__condicao_na_acao="DISCENTE"),
                )
            )
        )

    def get_changelist_form(self, request, **kwargs):
        statuses = list(StatusCurso.objects.only("id", "nome"))
        return cached_related_changelist_form(Curso, "status", statuses)

    def numero_inscritos(self, obj):
        url = reverse("admin:pfc_app_inscricao_changelist")
        return format_html(
            '<a href="{}?curso_id={}">{}</a>', url, obj.pk, obj.total_inscritos
        )

    def ver_inscricoes(self, obj):
        if not obj.pk:
            return "Salve o curso para gerenciar as inscrições."
        url = reverse("admin:pfc_app_inscricao_changelist")
        return format_html(
            '<a class="btn btn-outline-primary" href="{}?curso_id={}">'
            '<i class="fas fa-users"></i> Gerenciar inscrições</a>',
            url,
            obj.pk,
        )

    ver_inscricoes.short_description = "Inscrições"

    numero_inscritos.short_description = "Número de Inscritos"

    def gerar_certificados(self, obj):
        return format_html(
            '<a href="{}" class="btn btn-primary">Gerar Certificados</a>',
            reverse("generate_all_pdfs", args=[obj.id]),
        )

    def gerar_ata(self, obj):
        return format_html(
            '<a href="{}" class="btn btn-primary">Gerar Ata</a>',
            reverse("gerar_ata", args=[obj.id]),
        )

    class Meta:
        model = Curso


class CustomUserAdmin(UserAdmin):
    # add_form = UserCreationForm
    # form = UsuarioForm
    model = User
    list_per_page = 25
    show_full_result_count = False
    # raw_id_fields = ['lotacao_fk', 'lotacao_especifica_fk']
    list_display = (
        "nome",
        "cpf",
        "lotacao_fk",
        "lotacao_especifica_fk",
        "is_externo",
    )
    fieldsets = (
        (
            "Geral",
            {
                "fields": (
                    "username",
                    "email",
                    "password",
                    "first_name",
                    "last_name",
                    "cpf",
                    "nome",
                    "telefone",
                    "carreira",
                    "lotacao_fk",
                    "lotacao_especifica_fk",
                    "lotacao_especifica_2",
                    "classificacao_lotacao",
                    "cargo",
                    "nome_cargo",
                    "categoria",
                    "grupo_ocupacional",
                    "origem",
                    "simbologia",
                    "tipo_atuacao",
                    "role",
                    "is_externo",
                    "is_primeiro_acesso",
                    "avatar",
                    "pesquisa_cursos_priorizados",
                )
            },
        ),
        ("Permissões", {"fields": ("is_staff", "is_active", "is_superuser", "groups")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "email",
                    "password1",
                    "password2",
                    "first_name",
                    "last_name",
                    "cpf",
                    "nome",
                    "telefone",
                    "carreira",
                    "lotacao_fk",
                    "lotacao_especifica_fk",
                    "lotacao_especifica_2",
                    "classificacao_lotacao",
                    "cargo",
                    "nome_cargo",
                    "categoria",
                    "grupo_ocupacional",
                    "origem",
                    "simbologia",
                    "tipo_atuacao",
                    "role",
                    "is_staff",
                    "is_active",
                    "is_superuser",
                    "is_externo",
                    "avatar",
                    "groups",
                ),
            },
        ),
    )
    autocomplete_fields = (
        "carreira",
        "lotacao_fk",
        "lotacao_especifica_fk",
        "pesquisa_cursos_priorizados",
    )
    list_filter = (
        "lotacao_fk",
        LotacaoEspecificaFilter,
        "is_externo",
        "is_active",
    )
    search_fields = ["nome", "username", "email", "cpf"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("lotacao_fk", "lotacao_especifica_fk")
            .defer("avatar_base64")
        )

    # def save_model(self, request, obj, form, change):
    #     if User.objects.filter(username=obj.username).exists() and not change:
    #         form.add_error('username', "Este nome de usuário já está em uso.")
    #         return super().changeform_view(request, str(obj.pk), form_url='', extra_context={'form': form})
    #     elif User.objects.filter(email=obj.email).exists() and not change:
    #         form.add_error('email', "Este endereço de e-mail já está em uso.")
    #         return super().changeform_view(request, str(obj.pk), form_url='', extra_context={'form': form})
    #     elif User.objects.filter(email=obj.cpf).exists() and not change:
    #         form.add_error('cpf', "Este CPF já está em uso.")
    #         return super().changeform_view(request, str(obj.pk), form_url='', extra_context={'form': form})
    #     else:
    #         super().save_model(request, obj, form, change)


##
## Verificar a performance. Ficou mais lento.
##


class InscricaoAdminForm(forms.ModelForm):
    class Meta:
        model = Inscricao
        fields = "__all__"


class InscricaoAdmin(admin.ModelAdmin):
    form = InscricaoAdminForm
    list_per_page = 25
    show_full_result_count = False
    list_display = (
        "curso",
        "participante",
        "participante_username",
        "instrutor_principal",
        "condicao_na_acao",
        "ch_valida",
        "status",
        "concluido",
    )
    list_filter = (
        CursoRelacionadoFilter,
        "status",
        "condicao_na_acao",
        "instrutor_principal",
    )
    list_editable = (
        "condicao_na_acao",
        "status",
        "concluido",
        "instrutor_principal",
    )
    autocomplete_fields = ("curso", "participante")
    search_fields = (
        "curso__nome_curso",
        "participante__nome",
        "participante__cpf",
        "participante__username",
    )

    def get_changelist_form(self, request, **kwargs):
        statuses = list(StatusInscricao.objects.only("id", "nome"))
        return cached_related_changelist_form(
            Inscricao, "status", statuses, base_form=InscricaoAdminForm
        )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("curso", "participante", "status")
            .defer(
                "participante__avatar_base64",
                "curso__ementa_curso",
                "curso__descricao",
                "curso__observacao",
            )
        )

    @staticmethod
    def _form_tem_erro_de_conclusao(form):
        return any(
            error.code == "status_nao_aprovado_para_conclusao"
            for error in form.errors.as_data().get("concluido", [])
        )

    def _mostrar_erros_de_conclusao(self, request, response):
        if request.method != "POST" or not hasattr(response, "context_data"):
            return response

        context = response.context_data or {}
        forms = []
        change_list = context.get("cl")
        if change_list is not None and change_list.formset is not None:
            forms = change_list.formset.forms
        elif context.get("adminform") is not None:
            forms = [context["adminform"].form]

        bloqueadas = [form for form in forms if self._form_tem_erro_de_conclusao(form)]
        if not bloqueadas:
            return response

        detalhes = []
        for form in bloqueadas[:3]:
            inscricao = form.instance
            status = form.cleaned_data.get("status")
            detalhes.append(
                f"{inscricao.participante} — {inscricao.curso} "
                f"(status: {status or 'não informado'})"
            )

        # O Django normalmente reapresenta o valor enviado em formulários inválidos.
        # Desmarcar aqui evita que o admin pareça ter persistido a conclusão bloqueada.
        for form in bloqueadas:
            form.data = form.data.copy()
            form.data.pop(form.add_prefix("concluido"), None)

        excedentes = len(bloqueadas) - len(detalhes)
        complemento = f" e mais {excedentes}" if excedentes else ""
        self.message_user(
            request,
            "Nenhuma alteração desta página foi salva. "
            "Para concluir, a inscrição precisa estar com status APROVADA. "
            f"Inscrição bloqueada: {'; '.join(detalhes)}{complemento}.",
            level=messages.ERROR,
        )
        return response

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context=extra_context)
        return self._mostrar_erros_de_conclusao(request, response)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        response = super().changeform_view(
            request,
            object_id=object_id,
            form_url=form_url,
            extra_context=extra_context,
        )
        return self._mostrar_erros_de_conclusao(request, response)

    def participante_username(self, obj):
        return obj.participante.username if obj.participante else "N/A"

    participante_username.short_description = "Username"

    def gerar_certificado(self, obj):
        return format_html(
            '<a href="{}">Gerar Certificado</a>',
            reverse("generate_single_pdf", args=[obj.id]),
        )


class AvaliacaoAdmin(admin.ModelAdmin):
    # form = AvaliacaoForm
    list_display = ("curso", "participante", "subtema", "nota")
    list_filter = ("subtema", "nota")
    list_per_page = 50
    show_full_result_count = False
    autocomplete_fields = ("curso", "participante")
    search_fields = (
        "curso__nome_curso",
        "participante__nome",
        "participante__cpf",
        "participante__username",
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("curso", "participante", "subtema")
            .defer(
                "participante__avatar_base64",
                "curso__ementa_curso",
                "curso__descricao",
                "curso__observacao",
            )
        )


class Validacao_CHAdmin(admin.ModelAdmin):
    list_per_page = 25
    show_full_result_count = False
    list_display = (
        "usuario",
        "nome_curso",
        "enviado_em",
        "ch_solicitada",
        "ch_confirmada",
        "data_termino_curso",
        "status",
        "gerar_reconhecimento_ch",
        "analisado_em",
    )
    list_editable = (
        "ch_solicitada",
        "ch_confirmada",
        "data_termino_curso",
        "status",
    )
    list_filter = (
        "status",
    )
    autocomplete_fields = ("usuario", "responsavel_analise")
    search_fields = (
        "usuario__nome",
        "usuario__cpf",
        "usuario__username",
        "nome_curso",
    )
    readonly_fields = (
        "conhecimento_previo",
        "conhecimento_posterior",
        "voce_indicaria",
    )

    def gerar_reconhecimento_ch(self, obj):
        return format_html(
            '<a href="{}">Gerar Reconhecimento</a>',
            reverse("generate_reconhecimento", args=[obj.id]),
        )

    def get_caminho_arquivo(self, obj):
        return obj.arquivo_pdf.url[-30:] if obj.arquivo_pdf else ""

    get_caminho_arquivo.short_description = "Caminho do Arquivo"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "curadoria":
            kwargs["queryset"] = Curadoria.objects.order_by("-mes_competencia")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_changelist_form(self, request, **kwargs):
        statuses = list(StatusValidacao.objects.only("id", "nome"))
        return cached_related_changelist_form(Validacao_CH, "status", statuses)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related(
            "usuario", "responsavel_analise", "status"
        ).defer(
            "usuario__avatar_base64",
            "responsavel_analise__avatar_base64",
            "ementa",
            "conhecimento_previo",
            "conhecimento_posterior",
            "voce_indicaria",
        )
        return queryset

    # def save_model(self, request, obj, form, change):
    #     if change:
    #         obj.responsavel_analise = request.user  # Define o usuário logado como responsável pela análise
    #         print(request.user)
    #     super().save_model(request, obj, form, change)


class ItemRelatorioInline(admin.TabularInline):
    model = ItemRelatorio
    extra = 1
    fields = ["texto", "tema"]
    # list_display = ('curso', 'participante', 'ch_valida', 'condicao_na_acao', 'status')
    # ordering = ['-participante__nome']


class RelatorioAdmin(admin.ModelAdmin):
    inlines = [ItemRelatorioInline]
    list_display = ("codigo",)


class CuradoriaAdminForm(forms.ModelForm):
    class Meta:
        model = Curadoria
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()

        mes_competencia = cleaned_data.get("mes_competencia")
        curso_priorizado = cleaned_data.get("curso_priorizado")

        # Só valida se os dois estiverem preenchidos
        if mes_competencia and curso_priorizado and curso_priorizado.mes_competencia:
            ano_curadoria = mes_competencia.year
            ano_priorizado = curso_priorizado.mes_competencia.year

            if ano_curadoria != ano_priorizado:
                self.add_error(
                    "curso_priorizado",
                    f"O curso priorizado selecionado é de {ano_priorizado}, "
                    f"mas a curadoria está em {ano_curadoria}. O ano deve ser o mesmo.",
                )

        return cleaned_data


class CuradoriaAdmin(admin.ModelAdmin):
    list_per_page = 25
    show_full_result_count = False
    list_display = (
        "nome_curso",
        "curso_priorizado",
        "mes_competencia",
        "permanente",
    )
    list_editable = (
        "permanente",
        "curso_priorizado",
    )
    autocomplete_fields = ["curso_priorizado"]

    change_list_template = "admin/pfc_app/curadoria/change_list.html"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("curso_priorizado", "modalidade", "trilha")
        )

    def save_model(self, request, obj, form, change):
        if obj.curso_priorizado and obj.mes_competencia:
            ano_curadoria = obj.mes_competencia.year
            ano_priorizado = obj.curso_priorizado.mes_competencia.year

            if ano_curadoria != ano_priorizado:
                messages.error(
                    request,
                    (
                        f"Erro ao salvar '{obj.nome_curso}': "
                        f"o curso priorizado é de {ano_priorizado}, "
                        f"mas a curadoria está em {ano_curadoria}."
                    ),
                )
                return  # impede o save
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)

        if db_field.name == "curso_priorizado":
            # o Django geralmente já envolve em RelatedFieldWidgetWrapper
            if isinstance(formfield.widget, RelatedFieldWidgetWrapper):
                formfield.widget.can_delete_related = False
            else:
                # fallback (caso não venha envolvido)
                formfield.widget = RelatedFieldWidgetWrapper(
                    formfield.widget,
                    db_field.remote_field,
                    self.admin_site,
                    can_add_related=True,
                    can_change_related=True,
                    can_delete_related=False,
                    can_view_related=True,
                )

        return formfield


class TrilhaAdmin(admin.ModelAdmin):
    list_display = ("nome", "cor_circulo", "ordem_relatorio", "fundo_tabela")
    list_editable = (
        "ordem_relatorio",
        "cor_circulo",
        "fundo_tabela",
    )


class CursoPriorizadoAdmin(admin.ModelAdmin):
    search_fields = ["nome_sugestao_acao"]
    list_display = (
        "nome_sugestao_acao",
        "forma_atendimento",
        "mes_competencia",
        "trilha",
    )
    list_editable = (
        "forma_atendimento",
        "mes_competencia",
        "trilha",
    )
    list_select_related = ("trilha",)
    list_per_page = 50

    def get_changelist_form(self, request, **kwargs):
        trilhas = list(Trilha.objects.only("id", "nome"))
        return cached_related_changelist_form(CursoPriorizado, "trilha", trilhas)


class CursoNomeFilter(admin.SimpleListFilter):
    title = "Nome do Curso"
    parameter_name = "curso__nome_curso"

    def lookups(self, request, model_admin):
        return list(Curso.objects.values_list("id", "nome_curso"))

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(curso_id=self.value())
        return queryset


class AvaliacaoAbertaAdmin(admin.ModelAdmin):
    list_filter = (CursoNomeFilter,)
    list_per_page = 50
    show_full_result_count = False
    autocomplete_fields = ("curso", "participante")
    search_fields = (
        "curso__nome_curso",
        "participante__nome",
        "participante__cpf",
        "participante__username",
        "avaliacao",
    )
    list_display = (
        "curso_nome",
        "participante_nome",
        "avaliacao",
    )

    def curso_nome(self, obj):
        return obj.curso.nome_curso

    curso_nome.admin_order_field = "curso__nome_curso"
    curso_nome.short_description = "Nome do Curso"

    def participante_nome(self, obj):
        return obj.participante.nome

    participante_nome.admin_order_field = "participante__nome"
    participante_nome.short_description = "Nome do Participante"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("curso", "participante")
            .defer(
                "participante__avatar_base64",
                "curso__ementa_curso",
                "curso__descricao",
                "curso__observacao",
            )
        )


class UserCadastroAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "data_solicitacao",
    )
    search_fields = ("cpf", "nome")
    # list_editable = ('ch_solicitada', 'ch_confirmada', 'data_termino_curso', 'status',)


class UserPesquisaCursosAdmin(admin.ModelAdmin):
    list_display = ["user", "pesquisacursospriorizados"]
    search_fields = ["user__nome", "pesquisacursospriorizados__nome"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("user", "pesquisacursospriorizados")
            .defer("user__avatar_base64")
        )


intermediario = User.pesquisa_cursos_priorizados.through

intermediario._meta.verbose_name = "Relação Usuário - Curso Priorizado"
intermediario._meta.verbose_name_plural = "Relações Usuário - Cursos Priorizados"


class PesquisaCursosAdmin(admin.ModelAdmin):
    list_display = ("nome", "trilha", "forma_atendimento", "ano_ref")
    list_editable = ("trilha", "forma_atendimento")
    list_filter = ("trilha", "forma_atendimento", "ano_ref")
    search_fields = ("nome",)
    list_select_related = ("trilha",)

    def get_changelist_form(self, request, **kwargs):
        trilhas = list(Trilha.objects.only("id", "nome"))
        return cached_related_changelist_form(
            PesquisaCursosPriorizados, "trilha", trilhas
        )


class PriorizacaoRespostaAdmin(admin.ModelAdmin):
    list_display = ("user", "ano_ref", "comentario")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("user")
            .defer("user__avatar_base64")
        )


class PageVisitAdmin(admin.ModelAdmin):
    list_display = ("user", "url", "time_spent", "timestamp")
    list_per_page = 50
    show_full_result_count = False
    search_fields = ("user__nome", "user__cpf", "url")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("user")
            .defer("user__avatar_base64")
        )


# Register your models here.

admin.site.register(Curso, CursoAdmin)
admin.site.register(User, CustomUserAdmin)
admin.site.register(Inscricao, InscricaoAdmin)
admin.site.register(StatusCurso)
admin.site.register(StatusInscricao)
admin.site.register(StatusValidacao)
admin.site.register(Avaliacao, AvaliacaoAdmin)
admin.site.register(AvaliacaoAberta, AvaliacaoAbertaAdmin)
admin.site.register(Tema, TemaAdmin)
admin.site.register(Subtema, SubtemaAdmin)
admin.site.register(Validacao_CH, Validacao_CHAdmin)
admin.site.register(Certificado)
admin.site.register(RequerimentoCH)
admin.site.register(Competencia)
admin.site.register(Trilha, TrilhaAdmin)
admin.site.register(InstituicaoCertificadora)
admin.site.register(InstituicaoPromotora)
admin.site.register(Carreira, CarreiraAdmin)
admin.site.register(Categoria)
admin.site.register(Modalidade)
admin.site.register(PlanoCurso, PlanoCursoAdmin)
admin.site.register(Relatorio, RelatorioAdmin)
admin.site.register(Curadoria, CuradoriaAdmin)
admin.site.register(CursoPriorizado, CursoPriorizadoAdmin)
admin.site.register(AjustesPesquisa)
admin.site.register(AjustesHoraAula)
admin.site.register(PesquisaCursosPriorizados, PesquisaCursosAdmin)
admin.site.register(Lotacao, LotacaoAdmin)
admin.site.register(LotacaoEspecifica, LotacaoEspecificaAdmin)
admin.site.register(PageVisit, PageVisitAdmin)
admin.site.register(OrigemPagamento)
admin.site.register(UserCadastro, UserCadastroAdmin)
admin.site.register(User.pesquisa_cursos_priorizados.through, UserPesquisaCursosAdmin)

admin.site.register(PriorizacaoResposta, PriorizacaoRespostaAdmin)


admin.site.site_header = "PFC"
