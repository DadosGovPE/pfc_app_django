from django.contrib import admin
from django.db.models import Q
from django.contrib.auth.admin import UserAdmin
from .models import Curso, User, Inscricao, StatusCurso, StatusInscricao, \
                    StatusValidacao, Avaliacao, Validacao_CH,Certificado, \
                    RequerimentoCH
from .forms import AvaliacaoForm 
from django.utils.html import format_html
from django.urls import reverse


class InscricaoInline(admin.TabularInline):
    model = Inscricao
    extra = 1
    fields = ['curso', 'participante', 'condicao_na_acao', 'status']
    list_display = ('curso', 'participante', 'ch_valida', 'condicao_na_acao', 'status')
    ordering = ['-participante__nome']


class CursoAdmin(admin.ModelAdmin):
    inlines = [ InscricaoInline ]

    list_display = ('nome_curso', 'data_criacao', 'data_inicio', 'data_termino', 'vagas', 'numero_inscritos', 'status', 'periodo_avaliativo','gerar_certificados',)
    fields = ['nome_curso', 'ementa_curso', 'modalidade', 'tipo_reconhecimento', 'ch_curso', 'vagas',
               'categoria', 'competencia', 'descricao', ('data_inicio', 'data_termino'), 'turno', 'turma',
               'inst_certificadora', 'inst_promotora', 'coordenador', 'status', 'periodo_avaliativo', 'eh_evento',]
    list_filter = ('nome_curso', 'data_inicio', 'data_termino', 'periodo_avaliativo',)
    list_editable = ('status', 'periodo_avaliativo',)

    def numero_inscritos(self, obj):
        users_aprovados = obj.inscricao_set.filter(
            ~Q(status__nome="CANCELADA") & Q(condicao_na_acao="DISCENTE")
        )
        return users_aprovados.count()
    numero_inscritos.short_description = 'Número de Inscritos'

    def gerar_certificados(self, obj):
        return format_html('<a href="{}">Gerar Certificados</a>', reverse('generate_all_pdfs', args=[obj.id]))



    class Meta:
        model = Curso

class CustomUserAdmin(UserAdmin):
    #add_form = UserCreationForm
    #form = UserChangeForm
    model = User
    list_display = ('username', 'nome', 'cpf', 'email', 'is_externo', )
    fieldsets = (
        ('Geral', {'fields': ('username', 'email', 'password', 'first_name', 'last_name', 
                           'cpf', 'nome', 'telefone', 'lotacao', 'lotacao_especifica', 'lotacao_especifica_2',
                           'classificacao_lotacao', 'cargo', 'nome_cargo', 'categoria', 'grupo_ocupacional',
                           'origem', 'simbologia', 'tipo_atuacao',
                           'role', 'is_externo', 'avatar', )}),
        ('Permissões', {'fields': ('is_staff', 'is_active', 'is_superuser', 'groups')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'first_name', 'last_name', 
                       'cpf', 'nome', 'telefone', 'lotacao', 'lotacao_especifica', 'lotacao_especifica_2',
                       'classificacao_lotacao', 'cargo', 'nome_cargo', 'categoria', 'grupo_ocupacional', 
                       'origem', 'simbologia', 'tipo_atuacao',
                       'role', 'is_staff', 'is_active', 'is_superuser', 'is_externo', 
                       'avatar', 'groups', )}
        ),
    )

class InscricaoAdmin(admin.ModelAdmin):
    list_display = ('curso', 'participante', 'participante_username', 'condicao_na_acao', 'ch_valida', 'status', 'concluido', 'gerar_certificado', )
    list_filter = ('status', 'curso__nome_curso', 'condicao_na_acao',)
    list_editable = ('condicao_na_acao', 'status', 'concluido',)
    def participante_username(self, obj):
        return obj.participante.username if obj.participante else 'N/A'
    participante_username.short_description = 'Username'

    def gerar_certificado(self, obj):
        return format_html('<a href="{}">Gerar Certificado</a>', reverse('generate_single_pdf', args=[obj.id]))

class AvaliacaoAdmin(admin.ModelAdmin):
    form = AvaliacaoForm

class Validacao_CHAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'arquivo_pdf', 'enviado_em', 'ch_solicitada', 
                    'ch_confirmada', 'data_termino_curso', 'status',
                    'gerar_reconhecimento_ch',)
    list_editable = ('ch_solicitada', 'ch_confirmada', 'data_termino_curso', 'status',)
    list_filter = ('usuario', 'status',)

    def gerar_reconhecimento_ch(self, obj):
        return format_html('<a href="{}">Gerar Reconhecimento</a>', reverse('generate_reconhecimento', args=[obj.id]))


# Register your models here.
admin.site.register(Curso, CursoAdmin)
admin.site.register(User, CustomUserAdmin)
admin.site.register(Inscricao, InscricaoAdmin)
admin.site.register(StatusCurso)
admin.site.register(StatusInscricao)
admin.site.register(StatusValidacao)
admin.site.register(Avaliacao)
admin.site.register(Validacao_CH, Validacao_CHAdmin)
admin.site.register(Certificado)
admin.site.register(RequerimentoCH)


admin.site.site_header = 'PFC'