from django.contrib import admin
from django.db.models import Q, Prefetch
from django.contrib.auth.admin import UserAdmin
from .models import *
#Curso, User, Inscricao, StatusCurso, StatusInscricao, \
#StatusValidacao, Avaliacao, Validacao_CH,Certificado, \
#RequerimentoCH, Competencia, Trilha
from .forms import UsuarioForm 
from django.utils.html import format_html
from django.urls import reverse


class InscricaoInline(admin.TabularInline):
    model = Inscricao
    extra = 1
    fields = ['participante', 'condicao_na_acao', 'status']
    raw_id_fields = ['participante']
    #list_display = ('curso', 'participante', 'ch_valida', 'condicao_na_acao', 'status')
    #ordering = ['-participante__nome']
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('participante').only('participante__id', 'condicao_na_acao', 'status')
    

    

class CronogramaExecucaoInline(admin.TabularInline):
    model = CronogramaExecucao
    extra = 1
    fields = ['aula', 'turno', 'conteudo', 'atividade']
    #list_display = ('curso', 'participante', 'ch_valida', 'condicao_na_acao', 'status')
    #ordering = ['-participante__nome']

class PlanoCursoAdmin(admin.ModelAdmin):
    inlines = [CronogramaExecucaoInline]
    list_display = ('curso',)

class TemaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'evento',]
    list_editable = ('evento',)

class SubtemaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'tema', 'cor']
    list_filter = ('tema',)

class CursoNomeTurmaFilter(admin.SimpleListFilter):
    title = 'Curso e Turma'
    parameter_name = 'curso_nome_turma'

    def lookups(self, request, model_admin):
        cursos = Curso.objects.all().values_list('id', 'nome_curso', 'turma')
        return [(curso[0], f"{curso[1]} - {curso[2]}") for curso in cursos]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(id=self.value())
        return queryset

class ArquivoCursoInline(admin.TabularInline):
    model = ArquivoCurso
    extra = 1

class CursoAdmin(admin.ModelAdmin):
    inlines = [ InscricaoInline,  ArquivoCursoInline]

    list_display = ('nome_formatado', 'data_inicio', 'data_termino', 
                    'vagas', 'numero_inscritos', 'status', 'curso_priorizado', 'periodo_avaliativo',
                    'gerar_certificados', 'gerar_ata',)
    fields = ['nome_curso', 'ementa_curso', 'modalidade', 'tipo_reconhecimento', 'ch_curso', 'vagas',
               'categoria', 'trilha', 'curso_priorizado', 'descricao', ('data_inicio', 'data_termino'), 'turno', 'turma',
               'inst_certificadora', 'inst_promotora', 'coordenador', 'origem_pagamento', 'status', 'periodo_avaliativo', 'eh_evento',
               'is_externo', 'material_curso', 'horario', 'observacao', 
               ]
    list_filter = (CursoNomeTurmaFilter, 'data_inicio', 'data_termino', 'periodo_avaliativo', 'origem_pagamento',)
    list_editable = ('status', 'periodo_avaliativo', 'curso_priorizado',)
    autocomplete_fields = ['curso_priorizado']
    ordering = ['-data_inicio']




    def numero_inscritos(self, obj):
        users_aprovados = obj.inscricao_set.filter(
            ~Q(status__nome="CANCELADA") & Q(condicao_na_acao="DISCENTE")
        )
        return users_aprovados.count()
    numero_inscritos.short_description = 'Número de Inscritos'

    def gerar_certificados(self, obj):
        return format_html('<a href="{}" class="btn btn-primary">Gerar Certificados</a>', reverse('generate_all_pdfs', args=[obj.id]))

    def gerar_ata(self, obj):
        return format_html('<a href="{}" class="btn btn-primary">Gerar Ata</a>', reverse('gerar_ata', args=[obj.id]))



    class Meta:
        model = Curso

class CustomUserAdmin(UserAdmin):
    #add_form = UserCreationForm
    # form = UsuarioForm
    model = User
    list_per_page = 20
    # raw_id_fields = ['lotacao_fk', 'lotacao_especifica_fk']
    list_display = ('nome', 'cpf', 'lotacao_fk', 'lotacao_especifica_fk', 'is_externo', )
    fieldsets = (
        ('Geral', {'fields': ('username', 'email', 'password', 'first_name', 'last_name', 
                           'cpf', 'nome', 'telefone', 'carreira', 'lotacao_fk', 'lotacao_especifica_fk', 'lotacao_especifica_2',
                           'classificacao_lotacao', 'cargo', 'nome_cargo', 'categoria', 'grupo_ocupacional',
                           'origem', 'simbologia', 'tipo_atuacao',
                           'role', 'is_externo', 'avatar', 'pesquisa_cursos_priorizados')}),
        ('Permissões', {'fields': ('is_staff', 'is_active', 'is_superuser', 'groups')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'first_name', 'last_name', 
                       'cpf', 'nome', 'telefone', 'carreira', 'lotacao_fk', 'lotacao_especifica_fk', 'lotacao_especifica_2',
                       'classificacao_lotacao', 'cargo', 'nome_cargo', 'categoria', 'grupo_ocupacional', 
                       'origem', 'simbologia', 'tipo_atuacao',
                       'role', 'is_staff', 'is_active', 'is_superuser', 'is_externo', 
                       'avatar', 'groups', )}
        ),
    )
    list_editable = ('lotacao_fk', 'lotacao_especifica_fk',)
    list_filter = ('nome', 'lotacao_fk', 'lotacao_especifica_fk',)
    search_fields = ['username', 'email', 'cpf']

    def formfield_for_dbfield(self, db_field, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, **kwargs)
        if db_field.name in self.list_editable:
            formfield.widget.attrs.update({'class': 'custom-select'})
        return formfield

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


class InscricaoAdmin(admin.ModelAdmin):
    list_display = ('curso', 'participante', 'participante_username', 'instrutor_principal', 'condicao_na_acao', 'ch_valida', 'status', 'concluido', )
    list_filter = ('participante', 'status', 'curso' , 'condicao_na_acao','instrutor_principal',) #CursoNomeTurmaFilter
    list_editable = ('condicao_na_acao', 'status', 'concluido','instrutor_principal',)
    
    def participante_username(self, obj):
        return obj.participante.username if obj.participante else 'N/A'
    participante_username.short_description = 'Username'

    def gerar_certificado(self, obj):
        return format_html('<a href="{}">Gerar Certificado</a>', reverse('generate_single_pdf', args=[obj.id]))

class AvaliacaoAdmin(admin.ModelAdmin):
    #form = AvaliacaoForm
    list_display = ('curso', 'participante', 'subtema', 'nota')
    list_filter = ('curso', 'participante',)

class Validacao_CHAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'nome_curso', 'enviado_em', 'ch_solicitada', 
                    'ch_confirmada', 'data_termino_curso', 'status',
                    'gerar_reconhecimento_ch', 'analisado_em',)
    list_editable = ('ch_solicitada', 'ch_confirmada', 'data_termino_curso', 'status',)
    list_filter = ('usuario', 'status',)
    readonly_fields = ('conhecimento_previo', 'conhecimento_posterior', 'voce_indicaria')

    def gerar_reconhecimento_ch(self, obj):
        return format_html('<a href="{}">Gerar Reconhecimento</a>', reverse('generate_reconhecimento', args=[obj.id]))
    
    def get_caminho_arquivo(self, obj):
        return obj.arquivo_pdf.url[-30:] if obj.arquivo_pdf else ""

    get_caminho_arquivo.short_description = 'Caminho do Arquivo'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "curadoria":
            kwargs["queryset"] = Curadoria.objects.order_by('-mes_competencia')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related('usuario', 'responsavel_analise').defer(
            'usuario__avatar_base64', 'responsavel_analise__avatar_base64'
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
    fields = ['texto', 'tema']
    #list_display = ('curso', 'participante', 'ch_valida', 'condicao_na_acao', 'status')
    #ordering = ['-participante__nome']

class RelatorioAdmin(admin.ModelAdmin):
    inlines = [ItemRelatorioInline]
    list_display = ('codigo',)

class CuradoriaAdmin(admin.ModelAdmin):
    list_display = ('nome_curso', 'curso_priorizado', 'mes_competencia', 'permanente',)
    list_editable = ('permanente', 'curso_priorizado',)
    autocomplete_fields = ['curso_priorizado']

class TrilhaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cor_circulo', 'ordem_relatorio', 'fundo_tabela')
    list_editable = ('ordem_relatorio', 'cor_circulo', 'fundo_tabela',)

class CursoPriorizadoAdmin(admin.ModelAdmin):
    search_fields = ['nome_sugestao_acao']
    list_display = ('nome_sugestao_acao', 'forma_atendimento', 'mes_competencia', 'trilha')
    list_editable = ('forma_atendimento', 'mes_competencia', 'trilha',)


class CursoNomeFilter(admin.SimpleListFilter):
    title = 'Nome do Curso'
    parameter_name = 'curso__nome_curso'

    def lookups(self, request, model_admin):
        return [(curso.id, curso.nome_curso) for curso in Curso.objects.all()]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(curso__nome_curso=self.value())
        return queryset

class ParticipanteNomeFilter(admin.SimpleListFilter):
    title = 'Nome do Participante'
    parameter_name = 'participante__nome'

    def lookups(self, request, model_admin):
        return [(participante.id, participante.nome) for participante in User.objects.all()]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(participante__id=self.value())
        return queryset
    
class AvaliacaoAbertaAdmin(admin.ModelAdmin):
    list_filter = (CursoNomeFilter, ParticipanteNomeFilter)
    list_display = ('curso_nome', 'participante_nome', 'avaliacao',)

    def curso_nome(self, obj):
        return obj.curso.nome_curso
    curso_nome.admin_order_field = 'curso__nome_curso'
    curso_nome.short_description = 'Nome do Curso'

    def participante_nome(self, obj):
        return obj.participante.nome
    participante_nome.admin_order_field = 'participante__nome'
    participante_nome.short_description = 'Nome do Participante'


class UserCadastroAdmin(admin.ModelAdmin):
    list_display = ('nome', 'data_solicitacao', )
    # list_editable = ('ch_solicitada', 'ch_confirmada', 'data_termino_curso', 'status',)


class UserPesquisaCursosAdmin(admin.ModelAdmin):
    list_display = ['user', 'pesquisacursospriorizados']
    search_fields = ['user__nome', 'pesquisacursospriorizados__nome']

intermediario = User.pesquisa_cursos_priorizados.through

intermediario._meta.verbose_name = "Relação Usuário - Curso Priorizado"
intermediario._meta.verbose_name_plural = "Relações Usuário - Cursos Priorizados"

class PesquisaCursosAdmin(admin.ModelAdmin):
    list_display = ('nome', 'trilha', 'forma_atendimento', 'ano_ref')
    list_editable = ('trilha', 'forma_atendimento')
    list_filter = ('trilha', 'forma_atendimento', 'ano_ref')
    search_fields = ('nome',)

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
admin.site.register(Carreira)
admin.site.register(Categoria)
admin.site.register(Modalidade)
admin.site.register(PlanoCurso, PlanoCursoAdmin)
admin.site.register(Relatorio, RelatorioAdmin)
admin.site.register(Curadoria, CuradoriaAdmin)
admin.site.register(CursoPriorizado, CursoPriorizadoAdmin)
admin.site.register(AjustesPesquisa)
admin.site.register(AjustesHoraAula)
admin.site.register(PesquisaCursosPriorizados, PesquisaCursosAdmin)
admin.site.register(Lotacao)
admin.site.register(LotacaoEspecifica)
admin.site.register(PageVisit)
admin.site.register(OrigemPagamento)
admin.site.register(UserCadastro, UserCadastroAdmin)
admin.site.register(User.pesquisa_cursos_priorizados.through, UserPesquisaCursosAdmin)




admin.site.site_header = 'PFC'