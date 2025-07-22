from django.urls import path, re_path, include
from . import views
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.cursos, name='home'),
    path('accounts/login/', views.login, name='login'),
    path('registrar/', views.registrar, name='registrar'),
    path('logout/', views.logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('update-profile/', views.update_profile, name='update_profile'),
    path('cursos/', views.cursos, name='lista_cursos'),
    path('ch/', views.carga_horaria, name='carga_horaria'),
    path('inscricoes/', views.inscricoes, name='inscricoes'),
    path('curso_detail/<int:pk>', views.CursoDetailView.as_view(), name='detail_curso'),
    path('curso_detail/<int:pk>/<str:lotado>', views.CursoDetailView.as_view(), name='detail_curso'),
    path('sucesso_inscricao/', views.sucesso_inscricao, name='sucesso_inscricao'),
    path('inscricao_existente/', views.inscricao_existente, name='inscricao_existente'),
    path('inscrever/<int:curso_id>/', views.inscrever, name='inscrever_curso'),
    path('avaliacao/<int:curso_id>/', views.avaliacao, name='avaliacao'),
    path('inscricao_cancelar/<int:inscricao_id>/', views.cancelar_inscricao, name='cancelar_inscricao'),
    path('validar_ch/', views.validar_ch, name='validar_ch'),
    path('download_all_pdfs/', views.download_all_pdfs, name='download_all_pdfs'),
    path('generate_all_pdfs/<int:curso_id>/', views.generate_all_pdfs, name='generate_all_pdfs'),
    path('generate_all_pdfs/<int:curso_id>/<int:unico>/', views.generate_all_pdfs, name='generate_all_pdfs'),
    path('generate_single_pdf/<int:inscricao_id>/', views.generate_single_pdf, name='generate_single_pdf'),
    path('reset-password/', views.reset_password_request, name='reset_password_request'),
    path('change-password/', views.change_password, name='change_password'),
    path('generate_reconhecimento/<int:validacao_id>/', views.generate_all_reconhecimento, name='generate_reconhecimento'),
    path('gerar_ata/<int:curso_id>/', views.gerar_ata, name='gerar_ata'),
    path('gerar_relatorio/<int:curso_id>/', views.gerar_relatorio, name='gerar_relatorio'),
    path('relatorio/', views.relatorio, name='relatorio'),
    path('explorer/', include('explorer.urls')),
    path('usuarios_sem_ch/', views.usuarios_sem_ch, name='usuarios_sem_ch'),
    path('gerar_curadoria/<int:ano>/<int:mes>', views.gerar_curadoria, name='gerar_curadoria'),
    path('curadoria/', views.curadoria, name='curadoria'),
    path('curadoria_show/', views.curadoria_html_show, name='curadoria_show'),
    path('curadoria_html/<int:ano>/<int:mes>/', views.curadoria_html, name='curadoria_html'),
    path('estatisticas_lnt/', views.estatistica_lnt, name='estatisticas_lnt'),
    path('pesquisa_priorizacao/', views.listar_cursos_priorizados, name='listar_cursos_priorizados'),
    path('votar/', views.votar_cursos, name='votar_cursos'),
    path('cursos_mais_votados/', views.cursos_mais_votados, name='cursos_mais_votados'),
    path('gerar-pdf-bda/<int:ano>/<int:mes>', views.generate_bda_pdf, name='gerar_pdf_bda'),
    path('pdf_bda/', views.estatistica_bda, name='estatistica_bda'),
    path('planocurso_duplicar/', views.duplicar_plano_curso, name='duplicar_plano_curso'),
    path('change-lotacao/', views.select_lotacao_view, name='change_lotacao'),
    path('lotacao-especifica/', views.get_lotacao_especifica, name='get_lotacao_especifica'),
    path('nova-lotacao-especifica/', views.get_nova_lotacao_especifica, name='get_nova_lotacao_especifica'),
    path('listar-usuarios/', views.listar_usuarios, name='listar_usuarios'),
    path('atualizar-lotacao-usuario/', views.atualizar_lotacao_usuario, name='atualizar_lotacao_usuario'),
    path('abrir-modal/', views.abrir_modal, name='abrir_modal'),
    path('log-time/', views.log_time, name='log_time'),
    path('gastos/', views.gastos, name='gastos'),
    path('user-cadastro/', views.user_cadastro, name='user_cadastro'),
    path('cria-users/', views.processar_checkboxes, name='processar_checkboxes'),
    path('pesquisas/', include('pesquisas.urls')),
    
    ##API
    path('api/carga-horaria/', views.carga_horaria_por_cpf, name='api_carga_horaria'),
    path('api/cursos-disponiveis/', views.cursos_disponiveis, name='cursos_disponiveis'),
    path("api/emendas/", views.buscar_parlamentares, name="buscar_emendas"),
    

]   

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)