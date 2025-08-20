from django.shortcuts import render,redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods, require_GET
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages, auth
from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth.forms import PasswordChangeForm, PasswordResetForm
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils import dateformat, timezone
from django.utils.timezone import now
from urllib.request import Request, urlopen
from django.urls import reverse
import random
import string
import uuid
from django.utils.encoding import force_bytes
from django.contrib.auth import update_session_auth_hash
from django.db import IntegrityError
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from django.template import loader
from .models import Curso, Inscricao, StatusInscricao, Avaliacao, \
                    Validacao_CH, StatusValidacao, User, Certificado,\
                    Tema, Subtema, Carreira, Modalidade, Categoria, ItemRelatorio,\
                    PlanoCurso, Trilha, Curadoria, AvaliacaoAberta, CursoPriorizado,\
                    AjustesPesquisa, PesquisaCursosPriorizados, CronogramaExecucao,\
                    LotacaoEspecifica, Lotacao, PageVisit, AjustesHoraAula, StatusCurso,\
                    UserCadastro
from .forms import AvaliacaoForm, DateFilterForm, UserUpdateForm
from django.db.models import Count, Q, Sum, F, \
                                Avg, FloatField, When, BooleanField, \
                                Exists, OuterRef, Value, Subquery, Min, Max, \
                                ExpressionWrapper, DecimalField, Case
from django.db.models.functions import Coalesce, Concat, Cast, ExtractYear, ExtractMonth
from django.contrib.postgres.aggregates import StringAgg
from django.contrib.postgres.expressions import ArraySubquery
from datetime import date, datetime
import calendar
from django.views.generic import DetailView
import os
import zipfile
from django.http import HttpResponse
from django.shortcuts import get_list_or_404
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, \
                                Spacer, Image, PageBreak, \
                                PageTemplate, SimpleDocTemplate, Table, TableStyle

from reportlab.graphics.charts.barcharts import HorizontalBarChart, VerticalBarChart                           
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.graphics.shapes import *
from io import BytesIO
from reportlab.lib.units import inch
from validate_docbr import CPF
from .filters import UserFilter
import matplotlib
matplotlib.use('Agg')  
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import matplotlib.colors as mc
import colorsys
from matplotlib.colors import to_rgb
from pdf2docx import Converter
from PIL import Image as pImage
import shutil
import re
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import json
from collections import defaultdict
import time
from collections import defaultdict
from django.core.cache import cache
from django.db.models.functions import TruncMonth
from logging import getLogger
logger = getLogger('django')





MONTHS = [
    (1, "Janeiro"), (2, "Fevereiro"), (3, "Março"),
    (4, "Abril"), (5, "Maio"), (6, "Junho"),
    (7, "Julho"), (8, "Agosto"), (9, "Setembro"),
    (10, "Outubro"), (11, "Novembro"), (12, "Dezembro")
]



# Create your views here.


@login_required
def dashboard(request):
    total_cursos = Curso.objects.count()
    total_inscricoes = Inscricao.objects.count()
    total_horas_aula = Curso.objects.aggregate(total=Sum('ch_curso'))['total'] or 0

    # Cursos por mês e ano
    cursos_qs = (
        Curso.objects
        .annotate(ano=ExtractYear('data_inicio'), mes=ExtractMonth('data_inicio'))
        .values('ano', 'mes')
        .annotate(total=Count('id'))
    )

    inscricoes_qs = (
        Inscricao.objects
        .annotate(ano=ExtractYear('curso__data_inicio'), mes=ExtractMonth('curso__data_inicio'))
        .values('ano', 'mes')
        .annotate(total=Count('id'))
    )

    cursos_por_ano_mes = defaultdict(lambda: [0] * 12)
    inscricoes_por_ano_mes = defaultdict(lambda: [0] * 12)

    for item in cursos_qs:
        cursos_por_ano_mes[item['ano']][item['mes'] - 1] = item['total']

    for item in inscricoes_qs:
        inscricoes_por_ano_mes[item['ano']][item['mes'] - 1] = item['total']

    anos = sorted(set(cursos_por_ano_mes) | set(inscricoes_por_ano_mes))
    meses = [name for _, name in MONTHS]

    context = {
        'total_cursos': total_cursos,
        'total_inscricoes': total_inscricoes,
        'total_horas_aula': total_horas_aula,
        'meses': json.dumps(meses),
        'anos': json.dumps(anos),
        'cursos_por_ano_mes': json.dumps({ano: cursos_por_ano_mes[ano] for ano in anos}),
        'inscricoes_por_ano_mes': json.dumps({ano: inscricoes_por_ano_mes[ano] for ano in anos}),
    }
    return render(request, 'pfc_app/dashboard.html', context)



def login(request):
    """Autentica o usuário e inicia a sessão."""
    if request.method != 'POST':
        if request.user.is_authenticated:
            return redirect('lista_cursos')
        return render(request, 'pfc_app/login.html')

    usuario = request.POST.get('usuario')
    senha = request.POST.get('senha')

    user = auth.authenticate(username=usuario, password=senha)

    if not user:
        messages.error(request, 'Usuário ou senha inválidos!')
        return render(request, 'pfc_app/login.html')
    else:
        auth.login(request, user)
        messages.success(request, f'Oi, {user.nome.split(" ")[0].capitalize()}!')
        return redirect('dashboard')

    return render(request, 'pfc_app/login.html')

def registrar(request):
    """Recebe solicitação de cadastro de novos usuários."""
    if request.method != 'POST':
        return render(request, 'pfc_app/registrar.html')

    nome = request.POST.get('nome')
    cpf = request.POST.get('cpf')
    username = request.POST.get('username')
    email = request.POST.get('email')
    telefone = request.POST.get('telefone')
    orgao_origem = request.POST.get('orgao_origem')

    
    # Contexto para manter os dados no formulário
    context = {
        'nome': nome,
        'cpf': cpf,
        'username': username,
        'email': email,
        'telefone': telefone,
        'orgao_origem': orgao_origem
    }
    
    # Validar nome
    nome_regex = r'^[a-zA-ZÀ-ÿ\s]+$'

    if not re.match(nome_regex, nome):
        messages.error(request, f'{nome}, por favor, insira um nome válido (não são aceitos nomes com apenas números).')
        return render(request, 'pfc_app/registrar.html', context)
    
    cpf_padrao = CPF()
    # Validar CPF
    if not cpf_padrao.validate(cpf):
        messages.error(request, f'CPF digitado está errado!')
        #return JsonResponse({'success': False, 'msg': 'CPF Inválido!'})
        return render(request, 'pfc_app/registrar.html', context)
    if not re.match(r'^\d{11}$', cpf):
        messages.error(request, f'Digite apenas números no CPF!')
        return render(request, 'pfc_app/registrar.html', context)
    
    # Validar email
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    if not re.match(email_regex, email):
        messages.error(request, 'Por favor, insira um endereço de email válido.')
        return render(request, 'pfc_app/registrar.html', context)
    
    if User.objects.filter(cpf=cpf).exists():
        messages.error(request, f'CPF digitado já existe!')
        return render(request, 'pfc_app/registrar.html', context)
    if User.objects.filter(username=username).exists():
        messages.error(request, f'Username digitado já existe!')
        return render(request, 'pfc_app/registrar.html', context)
    if User.objects.filter(email=email).exists():
        messages.error(request, f'Email digitado já existe!')
        return render(request, 'pfc_app/registrar.html', context)

    
   
    
    if len(telefone) < 15:
        messages.error(request, f'Celular precisa ter o DDD mais 9 números!')
        return render(request, 'pfc_app/registrar.html', context)
    

    send_mail('Solicitação de cadastro', 
              f'Nome:{nome}\n '
              f'CPF: {cpf}\n '
              f'Username: {username}\n '
              f'Email: {email}\n '
              f'Telefone: {telefone}\n '
              f'Órgão de origem: {orgao_origem}\n ', 
              'ncdseplag@gmail.com', 
              ['pfc.seplag@gmail.com', 'g.trindade@gmail.com'])
    
    UserCadastro.objects.create(
        nome = nome,
        cpf = cpf,
        username = email,
        email = email,
        celular = telefone,
        orgao_origem = orgao_origem,
    )

    messages.success(request, f'Solicitação enviada com sucesso. Aguarde suas credenciais!')
        
    return redirect('login')
    # return render(request, 'pfc_app/login.html')

def logout(request):
    """Encerra a sessão do usuário e redireciona para o login."""
    auth.logout(request)
    return redirect('login')


@login_required
def update_profile(request):
    """Permite que o usuário edite seu perfil."""
    if request.method == 'POST':
        form = UserUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f'Perfil atualizado com sucesso!')
            return redirect('update_profile')
        else:
            messages.error(request, f'Corrija os erros abaixo')
            #return redirect('update_profile')
    else:
        form = UserUpdateForm(instance=request.user)
    
    context = {
        'form': form,
        'user': request.user
    }
    return render(request, 'pfc_app/update_profile.html', context)


@login_required
def cursos(request):
  """Lista cursos abertos e dados de inscrições.

  Usa subqueries para computar o número de inscritos e se o usuário
  já está inscrito em cada curso. Também monta listas de participantes
  e docentes usando ``ArraySubquery`` para melhorar a performance.
  """
  logger.info(f'cursos: {request.user.cpf}')
  lista_cursos = Curso.objects.all()
  data_atual = date.today()
  status_inscricao=Subquery(
        Inscricao.objects.filter(
            curso=OuterRef('pk'), participante=request.user
        ).values('status__nome')[:1]
    )
  subquery = ArraySubquery(
    Inscricao.objects.filter(curso=OuterRef('pk'))
        .exclude(condicao_na_acao='DOCENTE')
        .exclude(status__nome='CANCELADA')
        .exclude(status__nome='EM FILA')
        .exclude(status__nome='PENDENTE')
        .order_by('participante__nome')
        .values('curso')
        .annotate(nomes_concatenados=StringAgg('participante__nome', delimiter=', '))
        .values('nomes_concatenados')
)
  subquery_docentes = ArraySubquery(
    Inscricao.objects.filter(curso=OuterRef('pk'))
        .exclude(condicao_na_acao='DISCENTE')
        .order_by('inscrito_em')
        .annotate(nome_completo=Concat('participante__first_name', Value(' '), 'participante__last_name'))
        .values('curso')
        .annotate(nomes_concatenados=StringAgg('nome_completo', delimiter=', '))
        .values('nomes_concatenados')
)
  
  cursos_com_inscricoes = Curso.objects.annotate(
        num_inscricoes=Count('inscricao', 
                             filter=~Q(inscricao__condicao_na_acao='DOCENTE') & 
                             ~Q(inscricao__status__nome='CANCELADA') &
                             ~Q(inscricao__status__nome='EM FILA') & 
                             ~Q(inscricao__status__nome='PENDENTE') 
                             ),
        usuario_inscrito=Exists(
           Inscricao.objects.filter(participante=request.user, curso=OuterRef('pk'))
                                ),
        lista_inscritos = subquery,
        lista_docentes = subquery_docentes,
        status_inscricao = status_inscricao
        
    ).order_by('data_inicio').all().filter(data_inicio__gte=data_atual).exclude(status__nome = 'CANCELADO')
  #template = loader.get_template('base.html')
  #cursos_nao_inscrito = cursos_com_inscricoes.exclude(inscricao__participante=request.user)
  #lista_inscritos=Inscricao.objects.filter(curso=OuterRef('pk'))
                        # .exclude(condicao_na_acao='DOCENTE')
                        # .exclude(status__nome='CANCELADA')
                        # .exclude(status__nome='EM FILA')
                        # .annotate(nome_com_virgula=Concat('participante__nome', Value(', ')))
                        # .values('nome_com_virgula')
                        # .order_by('participante__nome')
                        # .distinct('participante__nome')
                        # .values_list('participante__nome', flat=True)        

  context = {
    'cursos': cursos_com_inscricoes,
  }
  #print(context['cursos'][1].inscricao_set.count())
  return render(request, 'pfc_app/lista_cursos.html' ,context)

@login_required
def usuarios_sem_ch(request):
    """Lista usuários sem carga horária mínima.

    Realiza subqueries para calcular a soma de horas concluídas em
    inscrições e validações, filtrando por período informado.
    """
    # Inicialize o filtro para capturar as datas
    filtro = UserFilter(request.GET, queryset=User.objects.all())

    # Capturar os valores das datas
    data_inicio = request.GET.get('inicio')  # Use .get() para evitar o erro
    data_fim = request.GET.get('fim')       # Use .get() para evitar o erro

    # Se data_inicio ou data_fim não forem fornecidos, definir padrões
    hoje = date.today()
    if not data_inicio:
        if hoje >= date(hoje.year, 3, 1):
            ano_inicio = hoje.year
        else:
            ano_inicio = hoje.year - 1
        data_inicio = date(ano_inicio, 3, 1)

    if not data_fim:
        data_fim = hoje
    
    # Transformar para string se necessário (por exemplo, se o filtro espera string no formato 'YYYY-MM-DD')
    if isinstance(data_inicio, date):
        data_inicio = data_inicio.strftime('%Y-%m-%d')
    if isinstance(data_fim, date):
        data_fim = data_fim.strftime('%Y-%m-%d')


    inscricoes = Inscricao.objects.filter(
            participante=OuterRef('pk'),
            concluido=True,
            curso__status__nome='FINALIZADO'
    )

    if data_inicio:
        inscricoes = inscricoes.filter(curso__data_termino__gte=data_inicio)  # Substitua 'data' pelo campo correto
    if data_fim:
        inscricoes = inscricoes.filter(curso__data_termino__lte=data_fim)  # Substitua 'data' pelo campo correto

    inscricoes = inscricoes.values('participante').annotate(
        total_ch=Sum('ch_valida')
    ).values('total_ch')[:1]
    
    validacoes = Validacao_CH.objects.filter(
            Q(status__nome='DEFERIDA') | Q(status__nome='DEFERIDA PARCIALMENTE'),
            usuario=OuterRef('pk')
            
        )
    if data_inicio:
        validacoes = validacoes.filter(data_termino_curso__gte=data_inicio)  # Substitua 'data' pelo campo correto
    if data_fim:
        validacoes = validacoes.filter(data_termino_curso__lte=data_fim)  # Substitua 'data' pelo campo correto

    validacoes = validacoes.values('usuario').annotate(
        total_ch=Sum('ch_confirmada')
    ).values('total_ch')[:1]
    
    # Filter users with a total load less than 60
    users = User.objects.annotate(
        total_ch_inscricao=Coalesce(Subquery(inscricoes), 0),
        total_ch_validacao=Coalesce(Subquery(validacoes), 0)
    ).annotate(
        total_ch=F('total_ch_inscricao') + F('total_ch_validacao')
    ).filter(grupo_ocupacional='GGOV').order_by('nome')

    # Calculate remaining load needed to reach 60
    users = users.annotate(ch_faltante=60 - F('total_ch')).filter(
                            total_ch__lt=60)

    # Select the fields you need for the table
    users = users.values('id', 'nome', 'email', 'lotacao', 'lotacao_especifica', 'total_ch', 'ch_faltante')

    filtro = UserFilter(request.GET, queryset=users)
    users = filtro.qs
    # lotacao_values = User.objects.values_list('lotacao', flat=True).distinct().order_by('lotacao')
    # lotacao_especifica = User.objects.values_list('lotacao_especifica', flat=True).distinct().order_by('lotacao_especifica')
    
    context = {
        'usuarios_sem_ch': users,
        'filtro': filtro,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
    }
    return render(request, 'pfc_app/usuarios_sem_ch.html', context )

@login_required
def user_cadastro(request):
    """Lista solicitações de cadastro pendentes."""
    data_hoje = datetime.now()
    data_hoje = data_hoje.strftime("%Y-%m-%d")
    form = DateFilterForm(request.GET)

    lista_usuarios = UserCadastro.objects.filter(data_solicitacao=data_hoje)
    
    if form.is_valid():
        data_inicio = form.cleaned_data['data_inicio']
        data_fim = form.cleaned_data['data_fim']
        if data_inicio and  data_fim:
            lista_usuarios = UserCadastro.objects.filter(data_solicitacao__gte=data_inicio, data_solicitacao__lte=data_fim)

    
    context = {
        'form': form,
        'values': request.GET if request.GET else {'data_inicio': data_hoje, 'data_fim': data_hoje},
        'lista_usuarios': lista_usuarios
    }

    return render(request, 'pfc_app/lista_cadastro.html' ,context)

def processar_checkboxes(request):
    """Cria usuários a partir das solicitações selecionadas."""
    if request.method == "POST":
        # Obter valores dos filtros de data
        data_inicio = request.POST.get('data_inicio', '')
        data_fim = request.POST.get('data_fim', '')
        # Obter IDs dos usuários marcados nos checkboxes
        usuarios_selecionados = request.POST.getlist('criar_user')
        
        if not usuarios_selecionados:
            messages.error(request, "Nenhum usuário foi selecionado.")
            return redirect(f"{reverse('user_cadastro')}?data_inicio={data_inicio}&data_fim={data_fim}")

        # Listas para controle de sucesso e erro
        usuarios_criados = []
        usuarios_nao_criados = []

        for usuario_cpf in usuarios_selecionados:
            # Obter o usuário da tabela intermediária UserCadastro
            try:
                usuario_cadastro = UserCadastro.objects.get(cpf=usuario_cpf)
            except UserCadastro.DoesNotExist:
                messages.error(request, f"Usuário com CPF {usuario_cpf} não encontrado.")
                continue

            # Verificar se o usuário já existe na tabela principal User
            if User.objects.filter(cpf=usuario_cadastro.cpf).exists():
                usuarios_nao_criados.append(usuario_cadastro.nome)
            else:
                # Criar o novo usuário na tabela principal User
                User.objects.create_user(
                    cpf = usuario_cadastro.cpf,
                    username=usuario_cadastro.email.split('@')[0],
                    password='123@mudar',  # Substitua por uma lógica de geração de senha
                    email=usuario_cadastro.email,
                    nome=usuario_cadastro.nome,
                    telefone = usuario_cadastro.celular,
                    origem = usuario_cadastro.orgao_origem,
                    lotacao = usuario_cadastro.orgao_origem,
                    lotacao_especifica = usuario_cadastro.orgao_origem,
                    is_externo = True,
                )
                usuarios_criados.append(usuario_cadastro.nome)
                send_mail('Solicitação de cadastro', 
                            f"Boa tarde {usuario_cadastro.nome.split(' ')[0]},\n "
                            f"Informo que seu cadastro no APP do PFC foi efetuado com sucesso.\n "
                            f"Para acessar o sistema, o login é o seu CPF e a senha inicial do primeiro acesso é 123@mudar (pode ser alterada na área de alteração de senha).\n "
                            f"\n "
                            f"\n "
                            f"\n "
                            f"Atenciosamente, \n "
                            f"Time PFC \n ", 
                            "ncdseplag@gmail.com", 
                            [f'{usuario_cadastro.email}', ])
                time.sleep(1)
        # Mensagens de sucesso e erro
        if usuarios_criados:
            messages.success(
                request,
                f"Usuários criados com sucesso: {', '.join(usuarios_criados)}."
            )
        if usuarios_nao_criados:
            messages.error(
                request,
                f"Usuários não criados (já existentes): {', '.join(usuarios_nao_criados)}."
            )

        return redirect(f"{reverse('user_cadastro')}?data_inicio={data_inicio}&data_fim={data_fim}") 

    # Redireciona caso o método não seja POST
    return redirect(user_cadastro) 

@login_required
def carga_horaria(request):
  """Exibe relatório de carga horária do usuário.

  Soma horas de cursos finalizados e validações externas utilizando
  subqueries para cálculo do total de horas no período filtrado.
  """
  form = DateFilterForm(request.GET)

  # por padrão, mostra do próprio usuário
  usuario_alvo = request.user  
  
  usuarios = None
  if request.user.role=='ADMIN' or request.user.is_superuser:
    usuarios = cache.get("lista_usuarios")
    if usuarios is None:
        usuarios = list(User.objects.all().order_by("nome"))  # força materializar
        cache.set("lista_usuarios", usuarios, timeout=60*60*24)  # guarda por 24h

    usuario_id = request.GET.get("usuario_id")
    if usuario_id:
        try:
            usuario_alvo = User.objects.get(id=usuario_id)
        except User.DoesNotExist:
            usuario_alvo = request.user

  inscricoes_do_usuario = Inscricao.objects.filter(
     ~Q(status__nome='CANCELADA'),
     ~Q(status__nome='EM FILA'),
     Q(curso__status__nome='FINALIZADO'),
     Q(concluido=True),
     participante=usuario_alvo
     
     )
  try:
    status_validacao_deferida = StatusValidacao.objects.get(nome='DEFERIDA')
    status_validacao_deferida_parc = StatusValidacao.objects.get(nome='DEFERIDA PARCIALMENTE')
    status_validacao_indeferida = StatusValidacao.objects.get(nome='INDEFERIDA')
  except:
    novo_status_deferida = StatusValidacao(nome="DEFERIDA")
    novo_status_deferida_parc = StatusValidacao(nome="DEFERIDA PARCIALMENTE")
    novo_status_deferida.save()
    novo_status_deferida_parc.save()
    status_validacao_deferida = StatusValidacao.objects.get(nome='DEFERIDA')
    status_validacao_deferida_parc = StatusValidacao.objects.get(nome='DEFERIDA PARCIALMENTE')

  validacoes = Validacao_CH.objects.filter(usuario=usuario_alvo, 
                                           status__in=[status_validacao_deferida, 
                                                       status_validacao_deferida_parc])
  validacoes_indeferidas = Validacao_CH.objects.filter(usuario=usuario_alvo, 
                                           status__in=[status_validacao_indeferida]).order_by('-analisado_em')
  
  ## Calculo para verificar se o usuario ja está inscrito em um dado curso

  data_hoje = datetime.now()
  
  # Verificar se a data atual é anterior a "01/03" do ano atual
  if data_hoje.month < 3:
       ano_atual = data_hoje.year - 1
  else:
       ano_atual = data_hoje.year
  
  data_hoje = data_hoje.strftime("%Y-%m-%d")

  if form.is_valid():
        data_inicio = form.cleaned_data['data_inicio']
        data_fim = form.cleaned_data['data_fim']
        
        if data_inicio:
            inscricoes_do_usuario = inscricoes_do_usuario.filter(curso__data_termino__gte=data_inicio)
            validacoes = validacoes.filter(data_termino_curso__gte=data_inicio)
        else:# Se data_inicio não estiver preenchida filtra com a data 01/03/{ano_atual}
            inscricoes_do_usuario = inscricoes_do_usuario.filter(curso__data_termino__gte=f'{ano_atual}-03-01')
            validacoes = validacoes.filter(data_termino_curso__gte=f'{ano_atual}-03-01')
        if data_fim:
            inscricoes_do_usuario = inscricoes_do_usuario.filter(curso__data_termino__lte=data_fim)
            validacoes = validacoes.filter(data_termino_curso__lte=data_fim)
        else:
            inscricoes_do_usuario = inscricoes_do_usuario.filter(curso__data_termino__lte=data_hoje)
            validacoes = validacoes.filter(data_termino_curso__lte=data_hoje)
  
  cursos_feitos_pfc = inscricoes_do_usuario
  # Distinc para que so conte 1 curso por periodo
  inscricoes_do_usuario = inscricoes_do_usuario.values('curso__nome_curso').distinct()
  # Calcula a soma da carga horária das inscrições do usuário
  carga_horaria_pfc = inscricoes_do_usuario.aggregate(Sum('ch_valida'))['ch_valida__sum'] or 0
  validacoes_ch = validacoes.aggregate(Sum('ch_confirmada'))['ch_confirmada__sum'] or 0
  carga_horaria_total = carga_horaria_pfc + validacoes_ch
  


  context = {
      'inscricoes_pfc': cursos_feitos_pfc,
      'validacoes_externas': validacoes,
      'validacoes_indeferidas': validacoes_indeferidas,
      'carga_horaria_pfc': carga_horaria_pfc,
      'carga_horaria_validada': validacoes_ch,
      'carga_horaria_total': carga_horaria_total,
      'form': form,
      'values': request.GET if request.GET else {'data_inicio': f'{ano_atual}-03-01', 'data_fim': data_hoje},
      'usuarios': usuarios,
      'usuario_alvo': usuario_alvo,
  }

  return render(request, 'pfc_app/carga_horaria.html' ,context)


@login_required
def inscricoes(request):
    """Mostra todas as inscrições do usuário e se já foram avaliadas."""
    inscricoes_do_usuario = Inscricao.objects.annotate(
        curso_avaliado=Exists(
           Avaliacao.objects.filter(participante=request.user, curso=OuterRef('curso'))

        )
    ).filter(participante=request.user).order_by('-curso__data_termino')
    
    context = {
        'inscricoes': inscricoes_do_usuario,
    }
    
    return render(request, 'pfc_app/inscricoes.html', context)


class CursoDetailView(LoginRequiredMixin, DetailView):
   # model_detail.html
   model = Curso

   def get_context_data(self, **kwargs):
        """Adiciona informações extras para a página de detalhes do curso."""
        context = super().get_context_data(**kwargs)
        
        # Recupere o usuário docente relacionado ao curso atual
        curso = self.get_object()
        usuario_docente = None

        lotado = self.kwargs.get('lotado', None)
        if lotado:
            lotado_bool = lotado.lower() == 'true'
            context['lotado'] = lotado_bool
        else:
            context['lotado'] = False

        # Verifique se há uma inscrição do tipo 'DOCENTE' relacionada a este curso
        inscricoes_docentes = Inscricao.objects.filter(curso=curso, condicao_na_acao='DOCENTE')

        usuarios_docentes = [inscricao.participante for inscricao in inscricoes_docentes]
        usuario_inscrito = Inscricao.objects.filter(curso=curso, participante=self.request.user).exists()
    
        # Adicione o usuário docente ao contexto
        context['usuarios_docentes'] = usuarios_docentes
        context['usuario_inscrito'] = usuario_inscrito

        return context


@login_required
def cancelar_inscricao(request, inscricao_id):
    """Cancela a inscrição do usuário em um curso."""
    try:
      inscricao = Inscricao.objects.get(pk=inscricao_id)
    except:
       messages.error(request, 'Inscrição não existe!')
       return render(request, 'pfc_app/inscricoes.html')
    
    if request.user == inscricao.participante:
       status_cancelado = StatusInscricao.objects.get(nome='CANCELADA')
       inscricao.status = status_cancelado
       inscricao.save()
       messages.success(request, 'Inscrição cancelada')
       return redirect('inscricoes')
    else:
       messages.error(request, 'Você não está inscrito nesse curso!')
       return render(request, 'pfc_app/inscricoes.html')
    
    #return render(request, 'pfc_app/inscricoes.html', context)

@login_required
def inscrever(request, curso_id):
    """Realiza inscrição do usuário em um curso, colocando em fila se lotado."""
    curso = Curso.objects.get(pk=curso_id)
    status_id_aprovada = StatusInscricao.objects.get(nome='APROVADA')
    status_id_pendente = StatusInscricao.objects.get(nome='PENDENTE')
    status_id_fila = StatusInscricao.objects.get(nome='EM FILA')
    
    # Conta quantas inscrições válidas há nesse curso
    inscricoes_validas = Inscricao.objects.filter(
        ~Q(status__nome='CANCELADA'),
        ~Q(status__nome='EM FILA'),
        ~Q(status__nome='PENDENTE'),
        ~Q(condicao_na_acao='DOCENTE'),
        curso=curso
    ).count()
    
    if curso.status.nome != 'A INICIAR' :
        messages.error(request, 'Curso não disponível!')
        return redirect('lista_cursos')

    # Compara com o número de vagas
    # Caso seja maior ou igual redireciona
    if inscricoes_validas >= curso.vagas:
        # print(inscricoes_validas)
        # O curso está lotado
        
        try:
          inscricao, criada = Inscricao.objects.get_or_create(participante=request.user, curso=curso, status=status_id_fila)
          if criada:
            messages.success(request, 'Inscrição adicionada à fila')
            return render(request, 'pfc_app/curso_lotado.html')
          else:
            messages.error(request, 'Você já está inscrito')
            return redirect('lista_cursos')
        except IntegrityError:
          print("INTEGRITY ERROR 1")
          messages.error(request, 'Você já está inscrito')
          return redirect('detail_curso', pk=curso_id)
    
    try:
      if curso.eh_evento or curso.is_externo or not request.user.is_externo:
          inscricao, criada = Inscricao.objects.get_or_create(participante=request.user, curso=curso, status=status_id_aprovada)
      else:
          inscricao, criada = Inscricao.objects.get_or_create(participante=request.user, curso=curso, status=status_id_pendente)

      if criada:
          # A inscrição foi criada com sucesso
          messages.success(request, 'Inscrição realizada!')
          #send_mail('Teste', f'Follow this link to reset your password: ihaa', 'g.trindade@gmail.com', [request.user.email])
          return redirect('lista_cursos')
      else:
          # A inscrição já existe
          messages.error(request, 'Você já está inscrito')
          return redirect('lista_cursos')
    except IntegrityError:
       print("INTEGRITY ERROR")
       messages.error(request, 'Você já está inscrito')
       return redirect('detail_curso', pk=curso_id)
    
def sucesso_inscricao(request):
    """Página simples exibida após inscrição bem sucedida."""
    return render(request, 'pfc_app/sucesso_inscricao.html')

def inscricao_existente(request):
    """Informativo quando usuário tenta se inscrever mais de uma vez."""
    return render(request, 'pfc_app/inscricao_existente.html')

@login_required
def avaliacao(request, curso_id):
    """Formulário de avaliação de curso finalizado."""
    # Checa se o curso existe
    try:
      curso = Curso.objects.get(pk=curso_id)
    except:
       messages.error(request, f"Curso não encontrado!")
       return redirect('lista_cursos')
    
    if curso.eh_evento:
        temas = Tema.objects.filter(evento=True)
        subtemas = Subtema.objects.filter(tema__evento = True)
    else:
        temas = Tema.objects.filter(evento=False)
        subtemas = Subtema.objects.filter(tema__evento = False)
    
    # Se existe, checa se o status está como "FINALIZADO"
    if curso.status.nome != "FINALIZADO":
       messages.error(request, f"Curso não finalizado!")
       return redirect('lista_cursos')
    
    try:
       inscricao = Inscricao.objects.get(participante=request.user, curso=curso)
    except:
       messages.error(request, f"Você não está inscrito neste curso!")
       return redirect('lista_cursos')
    
    if request.method == 'POST':
        #form = AvaliacaoForm(request.POST)
        #if form.is_valid():
            # Faça o que for necessário com os dados da avaliação, como salvá-los no banco de dados
        usuario = request.user
        ja_avaliado=Avaliacao.objects.filter(participante=usuario, curso=curso)
        
        if ja_avaliado:
            messages.error(request, f"Avaliação já realizada!")
            return redirect('inscricoes')
        
        
        for subtema in subtemas:
            #print("id: "+subtema.id)
            avaliacao = Avaliacao(curso=curso, participante=request.user,
                                    subtema=subtema, 
                                    nota=request.POST.get(subtema.nome)
                                    )
            avaliacao.save()


        avaliacao_aberta = AvaliacaoAberta(curso=curso, participante=request.user,
                                           avaliacao=request.POST.get("avaliacao")
                                           )
        avaliacao_aberta.save()
        #avaliacao = form.save(commit=False)
        #avaliacao.participante = usuario
        
        #avaliacao.curso = curso
        #form.save()
        #avaliacao.save()
        # Redirecione para uma página de sucesso ou outra ação apropriada
        messages.success(request, 'Avaliação Realizada!')
        return redirect('inscricoes')
    #messages.error(request, form.errors)
        #return render(request, 'sucesso.html')
    #else:
        #messages.error(request, 'Nenhum item pode ficar em branco')
        #return render(request, 'pfc_app/avaliacao.html', {'form': form})

    
        
        

        #form = AvaliacaoForm()

    return render(request, 'pfc_app/avaliacao.html', {'temas': temas, 'curso':curso})

@login_required
def validar_ch(request):
    """Envia solicitação de validação de carga horária externa."""
    if request.method == 'POST':
        status_validacao = StatusValidacao.objects.get(nome="EM ANÁLISE")
        arquivo_pdf = request.FILES['arquivo_pdf']
        nome_curso = request.POST['nome_curso']
        ch_solicitada = request.POST['ch_solicitada']
        data_inicio = request.POST['data_inicio']
        data_termino = request.POST['data_termino']
        instituicao_promotora = request.POST['instituicao_promotora']
        ementa = request.POST['ementa']
        condicao_na_acao = request.POST['condicao_acao']
        carreira_id = request.POST['carreira']
        conhecimento_previo = request.POST['conhecimento_previo']
        conhecimento_posterior = request.POST['conhecimento_posterior']
        voce_indicaria = request.POST['voce_indicaria']
        modalidade = Modalidade.objects.get(id=request.POST['modalidade'])
        try:
            agenda_pfc_check = request.POST['agenda_pfc']
            agenda_pfc = True
        except:
            agenda_pfc = False
      
        try:
           ch_solicitada = int(ch_solicitada)
        except:
            messages.error(request, 'O campo carga horária precisa ser númerico!')
            return redirect('validar_ch')
        try:
            carreira = Carreira.objects.get(pk=carreira_id)
        except:
            messages.error(request, 'Carreira não encontrada')
            return redirect('validar_ch')
        
        validacao = Validacao_CH(usuario=request.user, arquivo_pdf=arquivo_pdf, 
                                 nome_curso=nome_curso, ch_solicitada=ch_solicitada, 
                                 data_termino_curso=data_termino, data_inicio_curso = data_inicio,
                                 instituicao_promotora=instituicao_promotora, ementa=ementa, 
                                 agenda_pfc=agenda_pfc, status=status_validacao,
                                 condicao_na_acao=condicao_na_acao, carreira=carreira,
                                 conhecimento_previo=conhecimento_previo, 
                                 conhecimento_posterior=conhecimento_posterior,
                                 voce_indicaria=voce_indicaria, modalidade=modalidade)
        validacao.save()

         # Renomeando o arquivo PDF
        caminho_antigo = validacao.arquivo_pdf.path
        novo_nome_arquivo = f"{validacao.numero_sequencial}-{request.user.nome}.pdf"
        pasta_destino = os.path.dirname(caminho_antigo)
        caminho_novo = os.path.join(pasta_destino, novo_nome_arquivo)

        # Renomeando o arquivo no sistema de arquivos
        os.rename(caminho_antigo, caminho_novo)

        # Atualizando o campo arquivo_pdf do objeto validacao
        validacao.arquivo_pdf.name = os.path.join('uploads', request.user.username, novo_nome_arquivo)
        validacao.save()

        # Redirecionar ou fazer algo após o envio bem-sucedido
        messages.success(request, 'Arquivo enviado com sucesso!')
        return redirect('validar_ch')

    validacoes_user = Validacao_CH.objects.filter(usuario=request.user)
    condica_acao = Validacao_CH.CONDICAO_ACAO_CHOICES
    carreiras = Carreira.objects.all()
    modalidades = Modalidade.objects.all()
    categorias = Categoria.objects.all()


    return render(request, 'pfc_app/validar_ch.html', 
                  {'validacoes': validacoes_user, 
                   'opcoes': condica_acao, 
                   'carreiras': carreiras,
                   'modalidades': modalidades,
                   'categorias': categorias
                   })


def download_all_pdfs(request):
    """Página para seleção de certificados em lote."""
    return render(request, 'pfc_app/download_all_pdfs.html')

@login_required
def generate_all_pdfs(request, curso_id, unico=0):
    """Gera certificados PDF para todos os inscritos no curso."""
    try:
      curso = Curso.objects.get(pk=curso_id)
    except:
       messages.error(request, f"Curso não encontrado!")
       return redirect('lista_cursos')
    

    certificado = Certificado.objects.get(codigo='conclusao')
    #texto_certificado = certificado.texto
    if unico:
        users=[]
        users.append(request.user)
    else:
        users = curso.participantes.all()

    #output_folder = "pdf_output"  # Pasta onde os PDFs temporários serão salvos
    zip_filename = "all_pdfs.zip"

    # Crie a pasta de saída se ela não existir
    #if not os.path.exists(output_folder):
    #    os.makedirs(output_folder)

    # Crie o arquivo ZIP
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for user in users:
            # Verifica o status da incrição do usuário, 
            # se não estiver concluída pula esse usuário.
            try:
                inscricao = Inscricao.objects.get(participante=user, curso=curso, concluido=True)
            except:
                continue
            
            pdf_filename = generate_single_pdf(request, inscricao.id)
    #         texto_certificado = certificado.texto
    #         data_inicio = str(curso.data_inicio)
    #         data_termino = str(curso.data_termino)
    #         # Converte a string para um objeto datetime
    #         data_inicio_formatada = datetime.strptime(data_inicio, "%Y-%m-%d")
    #         data_termino_formatada = datetime.strptime(data_termino, "%Y-%m-%d")
    #         # Formata a data no formato "DD/MM/YYYY"
    #         data_inicio_formatada_str = data_inicio_formatada.strftime("%d/%m/%Y")
    #         data_termino_formatada_str = data_termino_formatada.strftime("%d/%m/%Y")

    #         try:
                
    #             cpf = CPF()
    #             # Validar CPF
    #             if not cpf.validate(user.cpf):
    #                 messages.error(request, f'CPF de {user.nome} está errado! ({user.cpf})')
    #                 return redirect('lista_cursos')
                
    #             # Formata o CPF no formato "000.000.000-00"
    #             cpf_formatado = f"{user.cpf[:3]}.{user.cpf[3:6]}.{user.cpf[6:9]}-{user.cpf[9:]}"
    #         except:
    #             messages.error(request, f'CPF de {user.nome} está com número de caracteres errado!')
    #             return redirect('lista_cursos')

    #         tag_mapping = {
    #             "[nome_completo]": user.nome,
    #             "[cpf]": cpf_formatado,
    #             "[nome_curso]": curso.nome_curso,
    #             "[data_inicio]": data_inicio_formatada_str,
    #             "[data_termino]": data_termino_formatada_str,
    #             "[curso_carga_horaria]": curso.ch_curso,
    #         }
    
    # # Substitua as tags pelo valor correspondente no texto
    #         for tag, value in tag_mapping.items():
    #             texto_certificado = texto_certificado.replace(tag, str(value))

    #         texto_customizado = texto_certificado
    #         pdf_filename = os.path.join(output_folder, f"{user.username}-{curso.nome_curso}.pdf")
    #         # Crie o PDF usando ReportLab

    #         style_body = ParagraphStyle('body',
    #                                     fontName = 'Helvetica',
    #                                     fontSize=13,
    #                                     leading=17,
    #                                     alignment=TA_JUSTIFY)
    #         style_title = ParagraphStyle('title',
    #                                     fontName = 'Helvetica',
    #                                     fontSize=36)
    #         style_subtitle = ParagraphStyle('subtitle',
    #                                     fontName = 'Helvetica',
    #                                     fontSize=24)
            
    #         width, height = landscape(A4)
    #         c = canvas.Canvas(pdf_filename, pagesize=landscape(A4))
    #         p_title=Paragraph(certificado.cabecalho, style_title)
    #         p_subtitle=Paragraph(certificado.subcabecalho1, style_subtitle)
    #         p_subtitle2=Paragraph(certificado.subcabecalho2, style_subtitle)
    #         p1=Paragraph(texto_customizado, style_body)
    #          # Caminho relativo para a imagem dentro do diretório 'static'
    #         imagem_relative_path = 'Certificado-FUNDO.png'
    #         assinatura_relative_path = 'assinatura.jpg'
    #         igpe_relative_path = 'Igpe.jpg'
    #         egape_relative_path = 'Egape.jpg'
    #         pfc_relative_path = 'PFC1.png'
    #         seplag_relative_path = 'seplag-transp-horizontal.png'


    #         # Construa o caminho absoluto usando 'settings.STATIC_ROOT'
    #         imagem_path = os.path.join(settings.MEDIA_ROOT, imagem_relative_path)
    #         assinatura_path = os.path.join(settings.MEDIA_ROOT, assinatura_relative_path)
    #         igpe_path = os.path.join(settings.MEDIA_ROOT, igpe_relative_path)
    #         egape_path = os.path.join(settings.MEDIA_ROOT, egape_relative_path)
    #         pfc_path = os.path.join(settings.MEDIA_ROOT, pfc_relative_path)
    #         seplag_path = os.path.join(settings.MEDIA_ROOT, seplag_relative_path)




    #         # Desenhe a imagem como fundo
    #         c.drawImage(imagem_path, 230, 0, width=width, height=height, preserveAspectRatio=True, mask='auto')
    #         c.drawImage(assinatura_path, 130, 100, width=196, height=63, preserveAspectRatio=True, mask='auto')
    #         c.drawImage(igpe_path, width-850, 20, width=196, height=63, preserveAspectRatio=True, mask='auto')
    #         c.drawImage(egape_path, width-650, 20, width=196, height=63, preserveAspectRatio=True, mask='auto')
    #         c.drawImage(pfc_path, width-450, 20, width=196, height=63, preserveAspectRatio=True, mask='auto')
    #         c.drawImage(seplag_path, width-250, 20, width=196, height=63, preserveAspectRatio=True, mask='auto')
    #         p_title.wrapOn(c, 500, 100)
    #         p_title.drawOn(c, width-800, height-100)
    #         p_subtitle.wrapOn(c, 500, 100)
    #         p_subtitle.drawOn(c, width-800, height-165)
    #         p_subtitle2.wrapOn(c, 500, 100)
    #         p_subtitle2.drawOn(c, width-800, height-190)
    #         p1.wrapOn(c, 500, 100)
    #         p1.drawOn(c, width-800, height-300)
    #         c.save()
           
            
            zipf.write(pdf_filename, os.path.basename(pdf_filename))
            os.remove(pdf_filename)

    # Configure a resposta HTTP para o arquivo ZIP
    response = HttpResponse(content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'

    # Abra o arquivo ZIP e envie seu conteúdo como resposta
    with open(zip_filename, 'rb') as zip_file:
        response.write(zip_file.read())

    try:
        os.remove(zip_filename)
    except:
        messages.error(request, f"Tente baixa um certificado por vez!")
        return redirect('inscricoes')

    return response

@login_required
def generate_single_pdf(request, inscricao_id):
    """Gera o PDF de certificado para uma inscrição específica."""
    try:
      inscricao = Inscricao.objects.get(pk=inscricao_id)
    except:
       messages.error(request, f"Inscrição não encontrada!")
       return redirect('lista_cursos')
    
    certificado = Certificado.objects.get(codigo='conclusao')
    #texto_certificado = certificado.texto
    user = inscricao.participante
    curso = inscricao.curso

    output_folder = "pdf_output"  # Pasta onde os PDFs temporários serão salvos
    #zip_filename = "all_pdfs.zip"

    # Crie a pasta de saída se ela não existir
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Crie o arquivo ZIP
    #with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        #for user in users:
    texto_certificado = certificado.texto
    data_inicio = str(curso.data_inicio)
    data_termino = str(curso.data_termino)
    # Converte a string para um objeto datetime
    data_inicio_formatada = datetime.strptime(data_inicio, "%Y-%m-%d")
    data_termino_formatada = datetime.strptime(data_termino, "%Y-%m-%d")
    # Formata a data no formato "DD/MM/YYYY"
    data_inicio_formatada_str = data_inicio_formatada.strftime("%d/%m/%Y")
    data_termino_formatada_str = data_termino_formatada.strftime("%d/%m/%Y")

    try:
        
        cpf = CPF()
        # Validar CPF
        if not cpf.validate(user.cpf):
            messages.error(request, f'CPF de {user.nome} está errado! ({user.cpf})')
            return redirect('lista_cursos')
        
        # Formata o CPF no formato "000.000.000-00"
        cpf_formatado = f"{user.cpf[:3]}.{user.cpf[3:6]}.{user.cpf[6:9]}-{user.cpf[9:]}"
    except:
        messages.error(request, f'CPF de {user.nome} está com número de caracteres errado!')
        return redirect('lista_cursos')

    tag_mapping = {
        "[nome_completo]": user.nome,
        "[cpf]": cpf_formatado,
        "[nome_curso]": curso.nome_curso,
        "[data_inicio]": data_inicio_formatada_str,
        "[data_termino]": data_termino_formatada_str,
        "[curso_carga_horaria]": curso.ch_curso,
        "[condicao_na_acao]": str(inscricao.condicao_na_acao).lower(),
    }

# Substitua as tags pelo valor correspondente no texto
    for tag, value in tag_mapping.items():
        texto_certificado = texto_certificado.replace(tag, str(value))

    texto_customizado = texto_certificado
    pdf_filename = os.path.join(output_folder, f"{user.username}-{curso.nome_curso}.pdf")
    # Crie o PDF usando ReportLab

    pdf_filename = os.path.join(output_folder, f"{user.username}-{curso.nome_curso}.pdf")
        # Crie o PDF usando ReportLab

    style_body = ParagraphStyle('body',
                                fontName = 'Helvetica',
                                fontSize=13,
                                leading=17,
                                alignment=TA_JUSTIFY)
    style_title = ParagraphStyle('title',
                                fontName = 'Helvetica',
                                fontSize=36)
    style_subtitle = ParagraphStyle('subtitle',
                                fontName = 'Helvetica',
                                fontSize=24)
    
    width, height = landscape(A4)
    c = canvas.Canvas(pdf_filename, pagesize=landscape(A4))
    p_title=Paragraph(certificado.cabecalho, style_title)
    p_subtitle=Paragraph(certificado.subcabecalho1, style_subtitle)
    p_subtitle2=Paragraph(certificado.subcabecalho2, style_subtitle)
    p1=Paragraph(texto_customizado, style_body)
        # Caminho relativo para a imagem dentro do diretório 'static'
    imagem_relative_path = 'Certificado-FUNDO.png'
    assinatura_relative_path = 'upload/certificado/assinatura.jpg'
    igpe_relative_path = 'igpe.png'
    ed_corp_relative_path = 'educacao_corporativa_h.png'
    pfc_relative_path = 'retangulartransp.png'
    seplag_relative_path = 'seplagtransparente.png'

    # Construa o caminho absoluto usando 'settings.STATIC_ROOT'
    imagem_path = os.path.join(settings.MEDIA_ROOT, imagem_relative_path)
    assinatura_path = os.path.join(settings.MEDIA_ROOT, assinatura_relative_path)
    igpe_path = os.path.join(settings.MEDIA_ROOT, igpe_relative_path)
    ed_corp_path = os.path.join(settings.MEDIA_ROOT, ed_corp_relative_path)
    pfc_path = os.path.join(settings.MEDIA_ROOT, pfc_relative_path)
    seplag_path = os.path.join(settings.MEDIA_ROOT, seplag_relative_path)




    # Desenhe a imagem como fundo
    c.drawImage(imagem_path, 230, 0, width=width, height=height, preserveAspectRatio=True, mask='auto')
    c.drawImage(assinatura_path, 130, 100, width=196, height=50, preserveAspectRatio=True, mask='auto')
    c.drawImage(igpe_path, 50, 20, width=63, height=50, preserveAspectRatio=True, mask='auto')
    c.drawImage(seplag_path, 63+50+30, 20, width=196, height=50, preserveAspectRatio=True, mask='auto')
    c.drawImage(pfc_path, 63+30+50+196, 20, width=196, height=50, preserveAspectRatio=True, mask='auto')
    c.drawImage(ed_corp_path, 63+50+30+196+166, 20, width=196, height=50, preserveAspectRatio=True, mask='auto')
    
    p_title.wrapOn(c, 500, 100)
    p_title.drawOn(c, width-800, height-100)
    p_subtitle.wrapOn(c, 500, 100)
    p_subtitle.drawOn(c, width-800, height-165)
    p_subtitle2.wrapOn(c, 500, 100)
    p_subtitle2.drawOn(c, width-800, height-190)
    p1.wrapOn(c, 500, 100)
    p1.drawOn(c, width-800, height-300)
    c.setTitle("Certificado PFC")
    c.save()
        
        #zipf.write(pdf_filename, os.path.basename(pdf_filename))
        #os.remove(pdf_filename)

    # Configure a resposta HTTP para o arquivo ZIP
    #response = HttpResponse(content_type='application/zip')
    #response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'

    # Abra o arquivo ZIP e envie seu conteúdo como resposta
    #with open(zip_filename, 'rb') as zip_file:
    #    response.write(zip_file.read())

    #os.remove(zip_filename)

    return pdf_filename


@login_required
def generate_all_reconhecimento(request, validacao_id):
    """Gera documentos de reconhecimento de carga horária."""
    try:
      validacao = Validacao_CH.objects.get(pk=validacao_id)
    except:
       messages.error(request, f"Validação não encontrada!")
       return redirect('lista_cursos')
    
    try:
        requerimento = validacao.requerimento_ch.do_requerimento
        fundamentacao = validacao.requerimento_ch.da_fundamentacao
        conclusao = validacao.requerimento_ch.da_conclusao
        local_data = validacao.requerimento_ch.local_data
        rodape = validacao.requerimento_ch.rodape
        rodape2 = validacao.requerimento_ch.rodape2
        
        #responsavel = validacao.responsavel_analise
    except:
        messages.error(request, f'Erro ao gerar reconhecimento')
        # Redireciona para a página de lista do modelo Validacao no app pfc_app
        return redirect(reverse('admin:pfc_app_validacao_ch_changelist'))

    #texto_certificado = certificado.texto
    user = validacao.usuario

    output_folder = "req_output"  # Pasta onde os PDFs temporários serão salvos
    zip_filename = "requerimento_ch.zip"

    # Crie a pasta de saída se ela não existir
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Crie o arquivo ZIP
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:

        try:
            cpf = CPF()
            # Validar CPF
            if not cpf.validate(user.cpf):
                messages.error(request, f'CPF de {user.nome} está errado! ({user.cpf})')
                return redirect('lista_cursos')
            
            # Formata o CPF no formato "000.000.000-00"
            cpf_formatado = f"{user.cpf[:3]}.{user.cpf[3:6]}.{user.cpf[6:9]}-{user.cpf[9:]}"
        except:
            messages.error(request, f'CPF de {user.nome} está com número de caracteres errado!')
            return redirect('lista_cursos')

        competencias = [competencia.nome for competencia in validacao.competencia.all()]
        if competencias:  # Verifica se a lista não está vazia
            # Caso haja mais de uma competência, substitui a última vírgula por " e "
            texto_competencia = ", ".join(competencias[:-1]) + " e " + competencias[-1] if len(competencias) > 1 else competencias[0]
        else:
            texto_competencia = ""

        texto_carreira = 'Gestor Governamental'
        if user.carreira:
            texto_carreira = user.carreira


        tag_mapping = {
            "[nome_completo]": validacao.usuario.nome,
            "[cpf]": cpf_formatado,
            "[origem]": user.origem,
            "[data_envio]": validacao.enviado_em.strftime("%d/%m/%Y"),
            "[lotacao]": user.lotacao,
            "[nome_curso]": validacao.nome_curso,
            "[instituicao_promotora]": validacao.instituicao_promotora,
            "[data_inicio]": validacao.data_inicio_curso.strftime("%d/%m/%Y"),
            "[data_termino]": validacao.data_termino_curso.strftime("%d/%m/%Y"),
            "[ch_valida]": validacao.ch_confirmada,
            "[ch_solicitada]": validacao.ch_solicitada,
            "[data_analise]": dateformat.format(datetime.now(), r'd \d\e F \d\e Y'),
            "[responsavel_analise]": validacao.responsavel_analise,
            "[competencias]": texto_competencia,
            "[carreira]": texto_carreira,
            
        }

# Substitua as tags pelo valor correspondente no texto
        for tag, value in tag_mapping.items():
            requerimento = requerimento.replace(tag, str(value))
            fundamentacao = fundamentacao.replace(tag, str(value))
            conclusao = conclusao.replace(tag, str(value))
            local_data = local_data.replace(tag, str(value))
            rodape = rodape.replace(tag, str(value))


        requerimento_custom = requerimento
        fundamentacao_custom = fundamentacao
        conclusao_custom = conclusao
        rodape_custom = rodape
        local_data_custom = local_data
        rodape2_custom = rodape2
        pdf_filename = os.path.join(output_folder, f"{validacao.numero_sequencial}-{user.username}-requerimento.pdf")
        # Crie o PDF usando ReportLab

        style_body = ParagraphStyle('body',
                                    fontName = 'Helvetica',
                                    fontSize=12,
                                    leading=17,
                                    alignment=TA_JUSTIFY)
        style_rodape = ParagraphStyle('rodape',
                                    fontName = 'Helvetica',
                                    fontSize=12,
                                    leading=17,
                                    alignment=TA_CENTER)
        style_title = ParagraphStyle('title',
                                    fontName = 'Helvetica',
                                    fontSize=16,
                                    alignment=TA_CENTER)
        style_subtitle = ParagraphStyle('subtitle',
                                    fontName = 'Helvetica',
                                    fontSize=14)
        style_numero = ParagraphStyle('numero',
                                    fontName = 'Helvetica',
                                    fontSize=12,
                                    leading=17,
                                    alignment=TA_RIGHT)
        
        width, height = A4
        print(width)
        print(height)
        numero_doc = 'N° ' + str(validacao.numero_sequencial)+'/'+str(validacao.analisado_em.year)
        print(numero_doc)
        c = canvas.Canvas(pdf_filename, pagesize=A4)
        p_title=Paragraph("ANÁLISE PARA RECONHECIMENTO DE CARGA HORÁRIA", style_title)
        p_numero = Paragraph(numero_doc, style_numero)
        p_subtitle=Paragraph("I - DO REQUERIMENTO", style_subtitle)
        p_subtitle_f=Paragraph("II - DA FUNDAMENTAÇÃO", style_subtitle)
        p_subtitle_c=Paragraph("III - DA CONCLUSÃO", style_subtitle)
        #p_subtitle2=Paragraph(certificado.subcabecalho2, style_subtitle)
        p1=Paragraph(requerimento_custom, style_body)
        p2=Paragraph(fundamentacao_custom, style_body)
        p3=Paragraph(conclusao_custom, style_body)
        p4=Paragraph(local_data_custom, style_rodape)
        p5=Paragraph(rodape_custom, style_rodape)
        p6=Paragraph(rodape2_custom, style_rodape)
        
            # Caminho relativo para a imagem dentro do diretório 'static'
        
        assinatura_relative_path = 'upload/certificado/assinatura.jpg'
        igpe_relative_path = 'igpe.png'
        egape_relative_path = 'Egape.jpg'
        pfc_relative_path = 'retangulartransp.png'
        seplag_relative_path = 'seplag-transp-horizontal.png'


        # Construa o caminho absoluto usando 'settings.STATIC_ROOT'
       
        #assinatura_path = os.path.join(settings.MEDIA_ROOT, assinatura_relative_path)
        igpe_path = os.path.join(settings.MEDIA_ROOT, igpe_relative_path)
        egape_path = os.path.join(settings.MEDIA_ROOT, egape_relative_path)
        pfc_path = os.path.join(settings.MEDIA_ROOT, pfc_relative_path)
        seplag_path = os.path.join(settings.MEDIA_ROOT, seplag_relative_path)




        # Desenhe a imagem como fundo
        
        #c.drawImage(assinatura_path, 200, 80, width=196, height=63, preserveAspectRatio=True, mask='auto')
        c.drawImage(igpe_path, 32 + 20, height-35, width=32, height=32, preserveAspectRatio=True, mask='auto')
        #c.drawImage(egape_path, width-650, 20, width=196, height=63, preserveAspectRatio=True, mask='auto')
        c.drawImage(pfc_path, width-100, height-35, width=98, height=32, preserveAspectRatio=True, mask='auto')
        #c.drawImage(seplag_path, width-250, 20, width=196, height=63, preserveAspectRatio=True, mask='auto')
        off_set = height
        espaco_entre_paragrafos = 35

        # REQUERIMENTO
        off_set = off_set - 120
        p_subtitle.wrapOn(c, 300, 100)
        p_subtitle.drawOn(c, width-550, off_set)
         
        p1.wrapOn(c, 500, 400)
        off_set = off_set - 30 - p1.height
        p1.drawOn(c, width-550, off_set)
        
        # FUNDAMENTAÇÃO
        p_subtitle_f.wrapOn(c, 300, 100)
        off_set = off_set - p_subtitle_f.height - espaco_entre_paragrafos
        p_subtitle_f.drawOn(c, width-550, off_set)
        p2.wrapOn(c, 500, 100)
        off_set = off_set - 30 - p2.height
        p2.drawOn(c, width-550, off_set)
        
        # CONCLUSÃO
        p_subtitle_c.wrapOn(c, 300, 100)
        off_set = off_set - p_subtitle_c.height - espaco_entre_paragrafos
        p_subtitle_c.drawOn(c, width-550, off_set)
        p3.wrapOn(c, 500, 100)
        off_set = off_set - 30 - p3.height
        p3.drawOn(c, width-550, off_set)
        
        # DATA
        p4.wrapOn(c, 500, 100)
        meio = (width/2)-(p4.width/2)
        off_set = off_set - p4.height - espaco_entre_paragrafos
        p4.drawOn(c, meio, off_set)
        
        # RODAPÉ
        p5.wrapOn(c, 500, 100)
        meio = (width/2)-(p5.width/2)
        off_set = off_set - p4.height - espaco_entre_paragrafos
        p5.drawOn(c, meio, off_set)

        # RODAPÉ 2
        p6.wrapOn(c, 500, 100)
        meio = (width/2)-(p5.width/2)
        off_set = off_set - p4.height - 20
        p6.drawOn(c, meio, off_set)

        p_title.wrapOn(c, 500, 100)
        meio = (width/2)-(p_title.width/2)
        p_title.drawOn(c, meio, height-50)

        p_numero.wrapOn(c, 500, 30)
        right = (width/2) - (p_numero.width/2)
        p_numero.drawOn(c, width-550, height-100)
        
        c.setTitle("Requerimento de Carga Horária")
        
        
        #p_subtitle2.wrapOn(c, 500, 100)
        #p_subtitle2.drawOn(c, width-800, height-190)
        
        c.save()
        
        # Caminho para o arquivo DOCX que será criado
        docx_filename = pdf_filename.replace('.pdf', '.docx')

        # Converte o PDF em DOCX
        cv = Converter(pdf_filename)
        cv.convert(docx_filename)
        cv.close()

        # Adiciona o PDF ao arquivo ZIP
        zipf.write(pdf_filename, os.path.basename(pdf_filename))
        
        # Adiciona o DOCX ao arquivo ZIP
        zipf.write(docx_filename, os.path.basename(docx_filename))

        os.remove(pdf_filename)
        os.remove(docx_filename)

    # Configure a resposta HTTP para o arquivo ZIP
    response = HttpResponse(content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'

    # Abra o arquivo ZIP e envie seu conteúdo como resposta
    with open(zip_filename, 'rb') as zip_file:
        response.write(zip_file.read())

    os.remove(zip_filename)

    return response


def reset_password_request(request):
    """Gera nova senha para o usuário e envia por e-mail."""
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            #user = form.get_users(request.POST['email']).first()
            users = form.get_users(request.POST['email'])
            user = next(users, None) 
            if user:
                senha_aleatoria = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
                try:
                    user.set_password(senha_aleatoria)
                    user.save()
                except:
                    messages.error(request, 'Erro no BD inesperado, entre em contato com o IG!')
                    return redirect('reset_password_request')
                
                try:
                    send_mail('Senha Nova - AppPFC', f'Sua nova senha é: {senha_aleatoria}', 'ncdseplag@gmail.com', [user.email])
                except:
                    user.set_password("12345678")
                    user.save()
                    messages.error(request, 'Erro no envio de email. Sua nova senha é: 12345678')
                    return redirect('lista_cursos')
            else:
                messages.error(request, 'Email não encontrado em nosso sistema!')
                return redirect('reset_password_request')

            messages.success(request, 'Email enviado com sua nova senha. Aproveite!')
            return redirect('lista_cursos')
    else:
        form = PasswordResetForm()
    return render(request, 'pfc_app/reset_password_request.html', {'form': form})

@login_required
def change_password(request):
    """Permite ao usuário alterar sua senha atual."""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Senha alterada com sucesso!')
            return redirect('lista_cursos')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    # A mensagem de erro é adicionada para cada erro encontrado.
                    # Você pode personalizar esta parte para melhor atender às suas necessidades.
                    messages.error(request, f"Erro: {error}")
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'pfc_app/change_password.html', {'form': form})

def draw_logos_infos(curso, canvas, doc):
    """Desenha logos e informações do curso nas páginas da ata."""
    draw_logos(curso, canvas, doc)
        # Coordenadas para o logo (ajuste conforme necessário)
    logo_width = 50
    logo_height = 50
    x_ig = doc.width + doc.leftMargin +doc.rightMargin - 27.5 - logo_width  # Alinhamento à direita
    y_ig = doc.height + doc.bottomMargin + doc.topMargin - logo_height -20 # No topo
        # Posição e texto do parágrafo
    x_text = 27.5
    y_text = y_ig + 30  # Ajuste conforme necessário
    text = f"Curso: {curso.nome_curso}<br/>Data:<br/>Horário:<br/>Local:"

    # Definir o estilo do texto
    styles = getSampleStyleSheet()
    style = styles['Normal']
    style.fontSize = 10
    style.leading = 12  # Espaçamento entre linhas

     # Criando o objeto Paragraph para o texto do curso
    paragraph = Paragraph(text, style)

    # Determina a largura máxima para o texto
    max_width = doc.width / 2  # Metade da largura da página

    # Calcula a altura necessária para o texto
    required_height = paragraph.wrap(max_width, 40)[1]  # Retorna uma tupla (width, height)
    # Desenha o parágrafo no canvas
    paragraph.drawOn(canvas, x_text, y_text - required_height)

def draw_logos(curso, canvas, doc):
    """Insere logos padrão no cabeçalho das páginas."""
    # Coordenadas para o logo (ajuste conforme necessário)
    logo_width = 50
    logo_height = 50
    x_ig = doc.width + doc.leftMargin +doc.rightMargin - 27.5 - logo_width  # Alinhamento à direita
    y_ig = doc.height + doc.bottomMargin + doc.topMargin - logo_height -20 # No topo

    x_pfc = x_ig - logo_width - 10
    y_pfc = y_ig

    igpe_relative_path = 'igpe.png'
    pfc_relative_path = 'PFC-NOVO-180x180.png'
    igpe_path = os.path.join(settings.MEDIA_ROOT, igpe_relative_path)
    pfc_path = os.path.join(settings.MEDIA_ROOT, pfc_relative_path)
    
    # Substitua 'path/to/your/logo.png' pelo caminho do seu logo
    canvas.drawImage(igpe_path, x_ig, y_ig, width=logo_width, height=logo_height, mask='auto')
    canvas.drawImage(pfc_path, x_pfc, y_pfc, width=logo_width, height=logo_height, mask='auto')

def docentes_curso(curso):
    """Retorna a lista de docentes aprovados para o curso."""

    # Obtém as inscrições que são de 'DOCENTE' para este curso específico
    inscricoes_docentes = Inscricao.objects.filter(curso=curso, condicao_na_acao='DOCENTE', status__nome='APROVADA')

    # Extrai os participantes (Users) dessas inscrições
    participantes_docentes = [inscricao.participante for inscricao in inscricoes_docentes]

    return participantes_docentes

def create_signature_line(width=200, height=1):
    """
    Cria uma linha para a área de assinatura.

    :param width: Largura da linha.
    :param height: Altura (espessura) da linha.
    :return: Objeto Drawing contendo a linha.
    """
    d = Drawing(width, height)
    d.add(Line(0, 0, width, 0))
    return d

def assinatura_ata(curso):
    """Monta a tabela de assinaturas utilizada na ata."""
    # Obtém a folha de estilos padrão do ReportLab
    styles = getSampleStyleSheet()

    # Obtém um estilo existente da folha de estilos e o personaliza para as assinaturas
    signature_style = styles['Normal'].clone('SignatureStyle')
    signature_style.fontSize = 7  # Define o tamanho da fonte
    signature_style.alignment = 1  # Centraliza o texto (0 = esquerda, 1 = centro, 2 = direita)
    # Elementos para a primeira assinatura
    coordinator_elements = [
        [Paragraph(curso.coordenador.nome, signature_style)],
        [Spacer(1, 15)],
        [create_signature_line()],
        [Paragraph("Assinatura da Coordenação", signature_style)]
    ]

    coordinator_table = Table(coordinator_elements, colWidths=[400])
    coordinator_table.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))

    if not curso.eh_evento:  
        # Assinaturas dos instrutores
        docentes = docentes_curso(curso)
        instrutor_elements = []
        for i, docente in enumerate(docentes):
            instrutor_elements.append([
            Paragraph(docente.nome, signature_style),
            Spacer(1, 20),
            create_signature_line(),
            Paragraph("Assinatura Instrutoria", signature_style)
            ])
            # Adiciona o separador apenas entre os instrutores, não após o último
            if i < len(docentes) - 1:  # Verifica se não é o último instrutor
                instrutor_elements.append([
                    Paragraph("", signature_style)            
                ] * 4)

        if len(docentes) > 1:
            # Inserir uma coluna de separação entre as assinaturas dos instrutores
            col_widths = [200,50,200]
            instrutor_elements = [instrutor_elements[:4],  instrutor_elements[4:]]
        else:
            col_widths = [400]
            instrutor_elements = [instrutor_elements]
        
        if docentes:
            instrutor_table = Table(instrutor_elements, colWidths=col_widths)
            instrutor_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP')
            ]))
            # Combinar as tabelas de assinaturas verticalmente
            elements = [Spacer(1, 20), coordinator_table, Spacer(1, 40), instrutor_table]
        else:
            elements = [Spacer(1, 20), coordinator_table, Spacer(1, 40)]
    else:
        elements = [Spacer(1, 20), coordinator_table, Spacer(1, 40)]
    return (
        elements
    )


@login_required
def gerar_ata(request, curso_id):
    """Gera a ata de frequência do curso em formato PDF."""
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="Ata.pdf"'
    curso = Curso.objects.get(pk=curso_id)
    doc = SimpleDocTemplate(response, pagesize=A4)
    
    styles = getSampleStyleSheet()
    header_style = styles['Heading1']  # Pode ajustar o estilo conforme necessário
    header_style.alignment = 1  # 1 para centralizar
    info_style = styles['Normal']  # Usando o estilo Normal como base
    info_style.fontSize = 10

    header = Paragraph("FREQUÊNCIA", header_style)
    # Assume que a largura da página seja dividida igualmente pelas colunas
    column_widths = [30, 270, 240]  # A largura total é 595, ajuste conforme necessário
    # lista_inscritos = curso.inscricoes.filter(
    #     condicao_na_acao='DISCENTE',
    #     status__nome='APROVADA'
    # ).order_by('participante__nome')
    
    lista_inscritos = curso.participantes.filter(
        inscricao__condicao_na_acao='DISCENTE', inscricao__status__nome='APROVADA').order_by('nome')
    # Cabeçalho da tabela
    data = [['ORD', 'NOME', 'ASSINATURA']]
    ordem = 0

    # Adicionando algumas linhas de exemplo. Você pode ajustar isso conforme necessário
    # Por exemplo, você pode querer calcular o número de linhas que cabem em uma página
    for i, participante in enumerate(lista_inscritos, start=1):
        data.append([str(i), participante.nome, ''])
        ordem = i

    # for j in range(1, 6):
    #     data.append([str(ordem + j), '', ''])  # Adiciona 5 linhas em branco.

    table = Table(data, colWidths=column_widths)

    # Estilizando a tabela
    table.setStyle(TableStyle([
                       ('BACKGROUND', (0, 0), (-1, 0), colors.gray),
                       ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                       ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                       ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                       ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                       ('TOPPADDING', (0, 0), (-1, 0), 6),
                       ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
                       ('FONTSIZE', (0, 1), (-1, -1), 8),
                       ('GRID', (0, 0), (-1, -1), 1, colors.black),
                   ]))
    table.repeatRows = 1

    espaco_altura = 20
    spacer = Spacer(1, espaco_altura)

    assinatura = assinatura_ata(curso)

    elements = [header, spacer, table]  # Adicione o header antes da tabela
    elements += assinatura
    doc.build(
        elements, 
        onFirstPage=lambda canvas, doc: draw_logos_infos(curso, canvas, doc),
        onLaterPages=lambda canvas, doc: draw_logos(curso, canvas, doc)
        )
    return response

def adjust_lightness(color, amount):
    """Ajusta a luminosidade de uma cor."""
    try:
        c = mc.cnames[color]
    except:
        c = color
    c = colorsys.rgb_to_hls(*mc.to_rgb(c))
    return colorsys.hls_to_rgb(c[0], max(0, min(1, amount * c[1])), c[2])

def draw_logos_relatorio(c: canvas.Canvas, width, height):
    """Desenha os logos no relatório de avaliação."""
    # Coordenadas para o logo (ajuste conforme necessário)
    logo_width = 50
    logo_width_seplag = 150
    logo_height_seplag = 30
    logo_height = 50
    x_ig = width  - 40 - logo_width  # Alinhamento à direita
    y_ig = height - logo_height -20 # No topo

    x_seplag =(width/2) - (logo_width_seplag/2)  # Alinhamento à direita
    y_seplag = y_ig # No topo
    
    x_pfc = 40
    y_pfc = y_ig

    igpe_relative_path = 'igpe.png'
    pfc_relative_path = 'PFC-NOVO-180x180.png'
    seplag_relative_path = 'seplagtransparente.png'
    igpe_path = os.path.join(settings.MEDIA_ROOT, igpe_relative_path)
    pfc_path = os.path.join(settings.MEDIA_ROOT, pfc_relative_path)
    seplag_path = os.path.join(settings.MEDIA_ROOT, seplag_relative_path)
    
    # Substitua 'path/to/your/logo.png' pelo caminho do seu logo
    c.drawImage(igpe_path, x_ig, y_ig, width=logo_width, height=logo_height, mask='auto')
    c.drawImage(seplag_path, x_seplag, y_seplag, width=logo_width_seplag, height=logo_height_seplag, mask='auto')
    c.drawImage(pfc_path, x_pfc, y_pfc, width=logo_width, height=logo_height, mask='auto')


def capa_relatorio(c: canvas.Canvas, width, height, plano_curso: PlanoCurso):
    """Cria a capa do relatório com logos e título."""
    draw_logos_relatorio(c, width, height)
    x_position = (width) / 2
    y_position = (height) / 2
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor('#4472C4')
    text_width = c.stringWidth('Relatório Geral', "Helvetica-Bold", 16)
    c.drawString(x_position-(text_width/2), y_position, 'Relatório Geral')
    c.setFont("Helvetica", 12)
    text_width = c.stringWidth(plano_curso.curso.nome_curso, "Helvetica-Bold", 11)
    c.drawString(x_position-(text_width/2), y_position-40, plano_curso.curso.nome_curso)

    c.showPage()


def pagina_dados_curso(c: canvas.Canvas, width, height, curso_id):
    """Insere dados gerais do curso na primeira página do relatório."""
    
    plano_curso = PlanoCurso.objects.get(curso_id = curso_id)
    capa_relatorio(c, width, height, plano_curso)
    inscricoes_validas = Inscricao.objects.filter(
        ~Q(status__nome='CANCELADA'),
        ~Q(status__nome='EM FILA'),
        ~Q(condicao_na_acao='DOCENTE'),
        curso=plano_curso.curso
    ).count()
    concluintes = Inscricao.objects.filter(
        ~Q(status__nome='CANCELADA'),
        ~Q(status__nome='EM FILA'),
        ~Q(condicao_na_acao='DOCENTE'),
        Q(concluido=True),
        curso=plano_curso.curso
    ).count()
    instrutores = Inscricao.objects.filter(
        ~Q(status__nome='CANCELADA'),
        ~Q(status__nome='EM FILA'),
        Q(condicao_na_acao='DOCENTE'),
        curso=plano_curso.curso
    ).order_by('inscrito_em')
    # c.setFont("Helvetica-Bold", 14)
    # c.drawAlignedString(100, height - 100, 'Dados do curso')
    style_body = ParagraphStyle('title',
                                    fontName = 'Helvetica-Bold',
                                    fontSize=12,
                                    leading=17,
                                    textColor=HexColor('#4472C4'),
                                    alignment=TA_JUSTIFY)
    style_body_sub = ParagraphStyle('subtitle',
                                    fontName = 'Helvetica-Bold',
                                    fontSize=11,
                                    leading=17,
                                    textColor=HexColor('#4472C4'),
                                    alignment=TA_JUSTIFY)
    style_body_center = ParagraphStyle('body-center',
                                    fontName = 'Helvetica',
                                    fontSize=11,
                                    leading=17,
                                    textColor=HexColor('#4472C4'),
                                    alignment=TA_CENTER)
    style_body_justify = ParagraphStyle('body-center',
                                    fontName = 'Helvetica',
                                    fontSize=10,
                                    leading=17,
                                    textColor=HexColor('#4472C4'),
                                    alignment=TA_JUSTIFY)
    
    
    draw_logos_relatorio(c, width, height)
    p1=Paragraph('Dados do curso', style_body)
    text_width, text_height = p1.wrapOn(c, 500, 20)
    x_position = (width - text_width) / 2
    p1.drawOn(c, x_position, height-100)

    # Define a cor da linha usando um código hexadecimal
    cor_linha = HexColor("#4472C4")

    # Define a cor e desenha uma linha horizontal
    c.setStrokeColor(cor_linha)
    c.line(50, height-100-text_height , width - 50, height-100-text_height)

    nome_curso = plano_curso.curso.nome_curso
    obj_geral = plano_curso.objetivo_geral
    metodologia = plano_curso.metodologia_ensino
    ch = plano_curso.curso.ch_curso
    data_inicio = plano_curso.curso.data_inicio
    data_termino = plano_curso.curso.data_termino
    inst_promotora = plano_curso.curso.inst_promotora.nome
    #ch, data_inicio, data_termino, inst_promotora, 
    #total_inscritos, total_Certificados, instrutor_princ, instrutor_sec

    p2=Paragraph('Nome da ação de capacitação: '+nome_curso, style_body_center)
    text_width, text_height = p2.wrapOn(c, 500, 40)
    x_position = (width - text_width) / 2
    p2.drawOn(c, x_position, height-150)

    # OBJETIVO GERAL #
    p3=Paragraph('Objetivo geral', style_body_sub)
    text_width, text_height = p3.wrapOn(c, 500, 40)
    x_position = (width - text_width) / 2
    p3.drawOn(c, x_position, height-200)
    p4=Paragraph(obj_geral, style_body_justify)
    text_width, text_height = p4.wrapOn(c, 500, 400)
    x_position = (width - text_width) / 2
    y_position = height-text_height-220
    p4.drawOn(c, x_position, y_position)

    # # METODOLOGIA #
    p5=Paragraph('Metodologia', style_body_sub)
    text_width, text_height = p5.wrapOn(c, 500, 40)
    x_position = (width - text_width) / 2
    y_position = y_position - 30
    p5.drawOn(c, x_position, y_position)
    p6=Paragraph(metodologia, style_body_justify)
    text_width, text_height = p6.wrapOn(c, 500, 400)
    x_position = (width - text_width) / 2
    y_position = y_position - 20
    p6.drawOn(c, x_position, y_position-text_height)

    # INFOS #
    
    c.setFont("Helvetica", 10)
    c.setFillColor('#4472C4')
    y_position = y_position-text_height - 30
    c.drawString(x_position, y_position, 'Carga-horária: '+str(ch)+' horas-aula')
    y_position = y_position - 20
    c.drawString(x_position, y_position, 'Data de início: '+str(data_inicio.strftime('%d/%m/%Y')))
    y_position = y_position - 20
    c.drawString(x_position, y_position, 'Data de término: '+str(data_termino.strftime('%d/%m/%Y')))
    y_position = y_position - 20
    c.drawString(x_position, y_position, 'Instituição promotora: '+inst_promotora)
    y_position = y_position - 20
    c.drawString(x_position, y_position, 'Total inscritos: '+str(inscricoes_validas))
    y_position = y_position - 20
    c.drawString(x_position, y_position, 'Total concluintes: '+str(concluintes))

    for index, instrutor in enumerate(instrutores):
        if index == 0:
            label = 'Instrutor principal: '
        else:
            label = 'Instrutor secundário: '
        y_position = y_position - 20
        c.drawString(x_position, y_position, label+instrutor.participante.nome)

    c.showPage()

def pagina_fotos(c: canvas.Canvas, width, height):
    """Adiciona ao relatório imagens enviadas pelo usuário."""
    style_body = ParagraphStyle('body',
                                    fontName = 'Helvetica-Bold',
                                    fontSize=12,
                                    leading=17,
                                    textColor=HexColor('#4472C4'),
                                    alignment=TA_JUSTIFY)
    
    # Definir o diretório onde as imagens estão armazenadas
    upload_dir = os.path.join(settings.BASE_DIR, 'tmp')

    # Calcular a posição inicial para colocar as imagens
    y_position = height - 330  # Deixar uma margem no topo
    print(height)
    # Listar todos os arquivos no diretório de upload
    draw_logos_relatorio(c, width, height)
    p_titulo_tema=Paragraph('Fotos do curso', style_body)
    text_width, text_height = p_titulo_tema.wrapOn(c, 500, 20)
    x_position = (width - text_width) / 2
    p_titulo_tema.drawOn(c, x_position, height-100)

    # Define a cor da linha usando um código hexadecimal
    cor_linha = HexColor("#4472C4")

    # Define a cor e desenha uma linha horizontal
    c.setStrokeColor(cor_linha)
    c.line(50, height-100-text_height , width - 50, height-100-text_height)

    for filename in os.listdir(upload_dir):
        if filename.lower().endswith((".png", ".jpg", ".jpeg")):  # Aceitar formatos de imagem comuns
            path = os.path.join(upload_dir, filename)
            img = pImage.open(path)
            img_width, img_height = img.size
            scale_factor = 300 / img_width
            scaled_height = img_height * scale_factor
            

            # Desenhar a imagem no canvas do PDF
            c.drawImage(path, 50, y_position, width=267, height=200, mask='auto')
            y_position -= 230 
            

    c.showPage()

@login_required
def gerar_relatorio(request, curso_id):
    """Gera relatório em PDF com gráficos das avaliações do curso."""
    avaliacoes = Avaliacao.objects.filter(curso_id=curso_id).select_related('subtema', 'subtema__tema')
    medias_notas_por_tema = Avaliacao.objects.filter(~Q(nota='0'), curso_id=curso_id ).annotate(
    nota_numerica=Cast('nota', FloatField())
        ).values('subtema__tema__id', 'subtema__tema__nome') \
        .annotate(media_notas=Avg('nota_numerica'))
    medias_notas_dict = {
        item['subtema__tema__id']: item['media_notas'] for item in medias_notas_por_tema
        }
    temas = Tema.objects.filter(subtema__avaliacao__curso_id=curso_id).distinct()

    # Conta o número de participantes distintos que avaliaram o curso
    quantidade_avaliadores = Avaliacao.objects.filter(curso_id=curso_id).values('participante').distinct().count()


    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="relatorio.pdf"'
    c = canvas.Canvas(response, pagesize=A4)

    # Gerar cores para cada nota
    base_rgb = to_rgb('#668923')
    # colors = [adjust_lightness('#4D6CFA', 1 - 0.15 * i) for i in range(5)]

    colors = [
        '#F8D9A3',
        '#FFD559',
        '#DDDDDD',
        '#B7E6E1',
        '#86D4CD',
        '#76C2AA'

    ]
    width, height = A4
    pagina_dados_curso(c, width, height, curso_id)

    # http://127.0.0.1:8000/gerar_relatorio/13
    for tema in temas:

        total_avaliacoes_tema = Avaliacao.objects.filter(subtema__tema_id=tema.id).count()
        avaliacoes_baixas_tema = Avaliacao.objects.filter(subtema__tema_id=tema.id, nota__in=['1', '2']).count()
        percentual_baixas_tema = (avaliacoes_baixas_tema / total_avaliacoes_tema) * 100 if total_avaliacoes_tema > 0 else 0
        percentual_baixas_tema = round(percentual_baixas_tema, 2)
        
        total_avaliacoes_zero = Avaliacao.objects.filter(subtema__tema_id=tema.id, nota='0').count()

        avaliacoes_altas_tema = Avaliacao.objects.filter(subtema__tema_id=tema.id, nota__in=['4', '5']).count()
        percentual_altas_tema = (avaliacoes_altas_tema / (total_avaliacoes_tema-total_avaliacoes_zero)) * 100 if total_avaliacoes_tema > 0 else 0
        percentual_altas_tema = round(percentual_altas_tema, 2)




        media_notas = medias_notas_dict.get(tema.id, 0)  # Obtém a média das notas para o tema ou 0 se não houver avaliações
        media_notas = round(media_notas, 1)
        # print(f'B+MB para o tema {tema.id}: {percentual_altas_tema}')

        item_relatorio = ItemRelatorio.objects.get(tema=tema)
        texto_tema = item_relatorio.texto
        notas_por_subtema = {}  # Dicionário para contagem de notas por subtema
        cor_por_subtema = {}
        
        
        
        for avaliacao in avaliacoes.filter(subtema__tema=tema):
            subtema_nome = avaliacao.subtema.nome
            nota = avaliacao.nota
            cor = avaliacao.subtema.cor
            if nota=='0':
                continue

            if subtema_nome not in notas_por_subtema:
                notas_por_subtema[subtema_nome] = {str(i): 0 for i in range(0, 6)}
                
            notas_por_subtema[subtema_nome][nota] += 1

            if subtema_nome not in cor_por_subtema:
                cor_por_subtema[subtema_nome] = cor
            
        #print(cor_por_subtema)
        media_conhecimento_previo = 0
        media_conhecimento_posterior = 0
        # Calcular as proporções
        proporcoes_por_subtema = {}
        contagens_por_subtema = {}
        cor_subtema_dict = {}
        
        for subtema, notas in notas_por_subtema.items():
            total = sum(notas.values())
            cor_subtema = {cor: cor}
            proporcoes = {nota: (count / total if total else 0) for nota, count in notas.items()}
            proporcoes_por_subtema[subtema] = proporcoes
            cor_subtema_dict[subtema] = cor_subtema
            contagens_por_subtema[subtema] = notas
            
            # TODO IMPLEMENTAR CONHECIMENTO PRÉVIO E ANTERIOR
            if tema.nome == 'Conhecimento':
                if subtema == "Conhecimento Prévio":
                    soma_notas_vezes_count = 0
                    soma_counts = 0
                    for nota, count in notas.items():
                        # print('nota: '+str(nota))
                        # print('count: '+str(count))
                        soma_notas_vezes_count += int(nota) * int(count)
                        soma_counts += int(count)
                    #print('previo: '+ media_conhecimento_previo)
                    # print(soma_notas_vezes_count)
                    # print(soma_counts)
                    # print(soma_notas_vezes_count/soma_counts)
                    media_conhecimento_previo = round(soma_notas_vezes_count/soma_counts, 1)
                elif subtema == "Conhecimento Posterior":
                    soma_notas_vezes_count = 0
                    soma_counts = 0
                    for nota, count in notas.items():
                        # print('nota: '+str(nota))
                        # print('count: '+str(count))
                        soma_notas_vezes_count += int(nota) * int(count)
                        soma_counts += int(count)
                    #print('previo: '+ media_conhecimento_previo)
                    # print(soma_notas_vezes_count)
                    # print(soma_counts)
                    # print(soma_notas_vezes_count/soma_counts)
                    media_conhecimento_posterior = round(soma_notas_vezes_count/soma_counts, 1)
                    
        # Criar o gráfico de barras empilhadas com proporções
        fig, ax = plt.subplots(figsize=(8, 4))
        bottom = [0] * len(proporcoes_por_subtema)
        subtema_names = list(proporcoes_por_subtema.keys())
        bar_heights = []
        for i, nota in enumerate(range(0, 6)):
            valores = [proporcoes_por_subtema[subtema].get(str(nota), 0) for subtema in proporcoes_por_subtema]
            cores = [cor_por_subtema[subtema] for subtema in subtema_names]
            barras = ax.barh(subtema_names, valores, left=bottom, label=f'Nota {nota}', color=colors[i])
            bottom = [bottom[i] + valores[i] for i in range(len(bottom))]

            for bar, valor in zip(barras, valores):
                    if valor > 0.05:  # Apenas mostrar texto para valores significativos
                        # # Colocar o nome do subtema acima do conjunto de barras
                        # ax.text(bar.get_x() + bar.get_width() / 2, bar.get_y() + bar.get_height() + 0.05,
                        #         subtema_names[i], ha='center', va='bottom', fontsize=10, color='black')
                        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_y() + bar.get_height() / 2,
                                f'{valor:.1%}',  # Exibir a proporção como percentual
                                fontsize=12, ha='center', va='center')
                        # Mostrar a nota abaixo do valor da proporção
                        if nota==0:
                            nota = 'N/A'
                        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_y() + 0.055,
                                f'Nota: {nota}', ha='center', va='center', fontsize=9, color='#222222')
                        max_width = max([bar.get_width() for bar in barras])
        # Definir o limite do eixo y para manter a altura das barras constante
        if len(subtema_names) == 1:
            ax.set_ylim(-1, 1)  # Ajuste estes valores conforme necessário para manter a altura das barras
        else:
            ax.set_ylim(-0.5, len(subtema_names))

        ax.set_yticks(range(len(subtema_names)), subtema_names)
        # Adicionar os nomes dos subtemas acima das barras
        # ax.get_yticks()[idx]
        background_color = (250/255, 250/255, 250/255, 0.5)
        for idx, subtema in enumerate(subtema_names):
            ax.text(0.5, ax.get_yticks()[idx]+0.35 , subtema, va='top', ha='center', fontsize=8, color='black', backgroundcolor=background_color)

        ax.set_xlim([0, 1])
        #ax.set_xlabel('Avaliações')
        ax.set_xticks([]) 
        ax.set_yticks([]) 
        plt.tight_layout()
        plt.title(f'{tema.nome}', fontsize=16)
        #plt.legend()

        # Salvar o gráfico como uma imagem
        fig.savefig(f'{tema.id}_proporcoes.png', bbox_inches='tight')
        plt.close(fig)

        # Adicionar a imagem do gráfico ao PDF
        #252423
        style_body = ParagraphStyle('body',
                                    fontName = 'Helvetica-Bold',
                                    fontSize=12,
                                    leading=17,
                                    textColor=HexColor('#4472C4'),
                                    alignment=TA_JUSTIFY)
        style_body_text = ParagraphStyle('body-text',
                                    fontName = 'Helvetica',
                                    fontSize=10,
                                    leading=17,
                                    textColor=HexColor('#4472C4'),
                                    alignment=TA_JUSTIFY)
        style_kpi = ParagraphStyle('body',
                                    fontName = 'Helvetica-Bold',
                                    fontSize=16,
                                    leading=17,
                                    textColor=HexColor('#4472C4'),
                                    alignment=TA_CENTER,
                                    )
        style_text_kpi = ParagraphStyle('body',
                                    fontName = 'Helvetica-Bold',
                                    fontSize=10,
                                    leading=12,
                                    textColor=HexColor('#bbbbbb'),
                                    alignment=TA_CENTER,
                                    )

        tag_mapping = {
            "[C_PREVIO]": media_conhecimento_previo,
            "[C_POST]": media_conhecimento_posterior,
            "[R+MR%]": str(percentual_baixas_tema)+'%',
            "[B+MB%]": str(percentual_altas_tema)+'%',
            "[media]": media_notas,
            "[num_resp]": quantidade_avaliadores
        }

        # Substitua as tags pelo valor correspondente no texto
        for tag, value in tag_mapping.items():
            texto_tema = texto_tema.replace(tag, str(value))
            
        draw_logos_relatorio(c, width, height)
        p_titulo_tema=Paragraph(tema.nome, style_body)
        text_width, text_height = p_titulo_tema.wrapOn(c, 500, 20)
        x_position = (width - text_width) / 2
        p_titulo_tema.drawOn(c, x_position, height-100)

        # Define a cor da linha usando um código hexadecimal
        cor_linha = HexColor("#4472C4")

        # Define a cor e desenha uma linha horizontal
        c.setStrokeColor(cor_linha)
        c.line(50, height-100-text_height , width - 50, height-100-text_height)

        texto = texto_tema

        p1=Paragraph(texto, style_body_text)
        text_width, text_height = p1.wrapOn(c, 500, 400)
        x_position = (width - text_width) / 2
        p1.drawOn(c, x_position, 700-text_height)
        c.setFont("Helvetica-Bold", 18)
        # c.drawCentredString(width / 2, height - 100, tema.nome)
        c.drawImage(f'{tema.id}_proporcoes.png', 50, 200, width=500, height=250)  # Ajuste as dimensões conforme necessário
# http://127.0.0.1:8000/gerar_relatorio/12
        width_rect = 100
        height_rect = 70
        c.roundRect((width / 2)+50, 470, width_rect, height_rect, 10, stroke=1, fill=0)
        c.roundRect((width / 2)-150, 470, width_rect, height_rect, 10, stroke=1, fill=0)
        media_text = 'Média Geral'
        if tema.nome == 'Conhecimento':
            media_conhecimento = round(media_conhecimento_posterior/media_conhecimento_previo, 1)
            media_notas = media_conhecimento
            media_text = 'Ganho de Conhecimento'
           
        kpi_media = Paragraph(str(media_notas), style_kpi)
        kpi_numero = Paragraph(str(quantidade_avaliadores), style_kpi)
        kpi_media_text = Paragraph(media_text, style_text_kpi)
        kpi_numero_text = Paragraph('N° de Respostas', style_text_kpi)
        kpi_media_width, kpi_media_height = kpi_media.wrapOn(c, 30, 20)
        kpi_numero_width, kpi_numero_height = kpi_numero.wrapOn(c, 30, 20)
        kpi_numero_text_width, kpi_numero_text_height = kpi_numero_text.wrapOn(c, 80, 40)
        kpi_media_text_width, kpi_media_text_height = kpi_media_text.wrapOn(c, 80, 40)
        texto_x = (width / 2) + 50 + (width_rect / 2) - (kpi_media_width / 2)
        texto_y = 470 + (height_rect / 2) - 6  # Ajuste o valor para centralizar verticalmente
        texto_x2 = (width / 2) - 150 + (width_rect / 2) - (kpi_numero_width / 2)
        texto_y2 = 470 + (height_rect / 2) - 6 
        kpi_text_numero_x = (width / 2) - 150 + (width_rect / 2) - (kpi_numero_text_width / 2)
        kpi_text_numero_y = 470 + height_rect - kpi_numero_text_height
        kpi_text_media_x = (width / 2) + 50 + (width_rect / 2) - (kpi_media_text_width / 2)
        kpi_text_media_y = 470 + height_rect - kpi_media_text_height
        # Desenha o texto da média no quadrado
        kpi_numero.drawOn(c, texto_x2, texto_y2)
        kpi_media.drawOn(c, texto_x, texto_y)
        kpi_media_text.drawOn(c, kpi_text_media_x, kpi_text_media_y)
        kpi_numero_text.drawOn(c, kpi_text_numero_x, kpi_text_numero_y)
        c.showPage()  # Cria uma nova página para cada tema
    pagina_fotos(c, width, height)    
    c.save()
    shutil.rmtree(os.path.join(settings.BASE_DIR, 'tmp'))
    return response


def salva_fotos(fotos):
    """Salva temporariamente as fotos enviadas para o relatório."""
    upload_dir = os.path.join(settings.BASE_DIR, 'tmp')
    # Verificar se o diretório existe, se não, criá-lo
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)

    for foto in fotos:
        if foto.content_type in ["image/jpeg", "image/png"]:
            # Salvar temporariamente o arquivo para leitura
            path = os.path.join(upload_dir, foto.name)
            with open(path, 'wb+') as f:
                for chunk in foto.chunks():
                    f.write(chunk)


@login_required
def relatorio(request):
    """Formulário para geração do relatório de avaliação."""
    cursos = Curso.objects.order_by('-data_inicio').filter(
        status__nome = 'FINALIZADO', planocurso__isnull=False)
    
    
    context = {
        'cursos': cursos,
    }

    if request.method == 'POST':
    
        curso_id = request.POST.get('curso')
        fotos = request.FILES.getlist('fotos')  # Pega a lista de arquivos enviados
        salva_fotos(fotos)
        #gerar_relatorio(request, curso_id)
        return redirect('gerar_relatorio', curso_id)
    

    return render(request, 'pfc_app/relatorio.html' ,context)

def hex_to_rgb_normalizado(hex_color):
    """Converte uma cor hexadecimal para tupla RGB normalizada."""
    # Remover o prefixo '#' se houver
    if hex_color.startswith('#'):
        hex_color = hex_color[1:]
    
    # Converter os componentes R, G, B de hexadecimal para decimal
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    
    # Normalizar os valores para o intervalo 0-1
    return (r / 255, g / 255, b / 255)

def draw_logos_curadoria(c: canvas.Canvas, width, height):
    """Desenha logos usados no relatório de curadoria."""
    # Coordenadas para o logo (ajuste conforme necessário)
    logo_width = 50
    logo_width_seplag = 150
    logo_height_seplag = 30
    logo_height = 50
    x_ig = width  - 50 - logo_width  # Alinhamento à direita
    y_ig = height - logo_height -20 # No topo

    x_seplag = width  - 50 - logo_width_seplag   # Alinhamento à direita
    y_seplag = 10 # No topo
    
    x_pfc = x_ig - logo_width - 10
    y_pfc = y_ig

    igpe_relative_path = 'igpe.png'
    pfc_relative_path = 'PFC-NOVO-180x180.png'
    seplag_relative_path = 'seplagtransparente.png'
    igpe_path = os.path.join(settings.MEDIA_ROOT, igpe_relative_path)
    pfc_path = os.path.join(settings.MEDIA_ROOT, pfc_relative_path)
    seplag_path = os.path.join(settings.MEDIA_ROOT, seplag_relative_path)
    
    # Substitua 'path/to/your/logo.png' pelo caminho do seu logo
    c.drawImage(igpe_path, x_ig, y_ig, width=logo_width, height=logo_height, mask='auto')
    c.drawImage(seplag_path, x_seplag, y_seplag, width=logo_width_seplag, height=logo_height_seplag, mask='auto')
    c.drawImage(pfc_path, x_pfc, y_pfc, width=logo_width, height=logo_height, mask='auto')


def gerar_curadoria(request, ano, mes):
    """Gera PDF com a agenda mensal de cursos e curadorias."""
    # Ano e mês são presumivelmente passados como inteiros, se não, converta-os.
    ano = int(ano)
    mes = int(mes)

    # O primeiro dia do mês é sempre 1
    data_inicio = date(ano, mes, 1)

    # Último dia do mês - monthrange retorna o dia da semana do primeiro dia do mês e o número de dias no mês
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    data_fim = date(ano, mes, ultimo_dia)

    trilhas = Trilha.objects.all().order_by('ordem_relatorio')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="agenda_pfc.pdf"'

    # Cria um objeto Canvas diretamente
    p = canvas.Canvas(response, pagesize=A4)
    p.setTitle('Agenda PFC')
    width, height = A4
    
    # Estilo para o cabeçalho
    header_style = ParagraphStyle(
        name='HeaderStyle',
        fontSize=10,
        fontName='Helvetica-Bold',
        textColor=colors.white,
        alignment=1,  # Centro
        spaceAfter=5,
    )

    # Estilo para o corpo da tabela
    body_style = ParagraphStyle(
        name='BodyStyle',
        fontSize=8,
        fontName='Helvetica',
        textColor=colors.black,
        alignment=1,  # Centro
        spaceAfter=5,
    )

    link_style = ParagraphStyle(
        name='link_style',  # Nome do estilo
        fontName='Helvetica',
        fontSize=8,
        textColor=colors.blue,  # Definindo a cor do texto para azul
        underline=True,  # Adicionando sublinhado
        alignment=1,  # Centro
        spaceAfter=5,
    )

    cabecalho = [Paragraph("Curadoria", header_style), 
                 Paragraph("Link", header_style), 
                 Paragraph("CH", header_style), 
                 Paragraph("Modalidade", header_style), 
                 Paragraph("Promotor", header_style)]
    cabecalho_pfc = [Paragraph("PFC", header_style), 
                 Paragraph("Link", header_style), 
                 Paragraph("CH", header_style), 
                 Paragraph("Modalidade", header_style), 
                 Paragraph("Período", header_style)]
    
    y_table = 730
    # http://127.0.0.1:8000/curadoria
    for trilha in trilhas:
        data_pfc = [
                cabecalho_pfc,
            ]
        for curso in trilha.cursos.filter(data_inicio__gte=data_inicio, data_inicio__lte=data_fim):
            url = f"https://www.pfc.seplag.pe.gov.br/curso_detail/{curso.id}"
            link_text = '<u><link href="' + url + '">' + 'Inscrição' + '</link></u>'
            curso_nome = curso.nome_curso
            if curso.turma != 'TURMA1':
                curso_nome += f" - ({curso.get_turma_display()})"

            data_pfc.append(
                [Paragraph(curso_nome, body_style), 
                 Paragraph(link_text, link_style), 
                 Paragraph(str(curso.ch_curso), body_style), 
                 Paragraph(curso.modalidade.nome, body_style), 
                 Paragraph(f"de {curso.data_inicio.strftime('%d/%m/%Y')} a {curso.data_termino.strftime('%d/%m/%Y')}", body_style) ],
            )
        
        data = [
                cabecalho,
            ]
        
        curadorias = trilha.curadorias.filter(
            Q(mes_competencia__gte=data_inicio, mes_competencia__lte=data_fim) |
            Q(permanente=True)
        )
        for curadoria in curadorias:
            
            url = curadoria.link_inscricao
            link_text = '<u><link href="' + url + '">' + 'Inscrição' + '</link></u>'
            #link_text = Hyperlink(url, 'Inscrição', color=colors.blue)
            data.append(
                [Paragraph(curadoria.nome_curso, body_style), 
                 Paragraph(link_text, link_style), 
                 Paragraph(str(curadoria.carga_horaria_total), body_style), 
                 Paragraph(curadoria.modalidade.nome, body_style), 
                 Paragraph("" if curadoria.instituicao_promotora is None else curadoria.instituicao_promotora.nome, body_style)],
            )
    
        if (len(data_pfc) + len(data)) <= 2:
            continue

        if len(data_pfc) > 1:
            table_pfc = Table(data_pfc, colWidths=[215, 50, 30, 80, 120])

        if len(data) > 1:
            table = Table(data, colWidths=[215, 50, 30, 80, 120])

        hex_color = trilha.cor_circulo
        rgb_normalized = hex_to_rgb_normalizado(hex_color)
        hex_color_fundo = trilha.fundo_tabela
        rgb_fundo_normalized = hex_to_rgb_normalizado(hex_color_fundo)

        table_style = TableStyle([
            ('BACKGROUND', (0,0), (-1,0), rgb_normalized),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('TOPPADDING', (0,0), (-1,0), 6),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BACKGROUND', (0,1), (-1,-1), rgb_fundo_normalized),
            ('GRID', (0,0), (-1,-1), 1, colors.white),
            ('FONTSIZE', (0,0), (-1,-1), 8)
        ])
        
        h_pfc = 0
        h = 0 
        if len(data_pfc) > 1:
            table_pfc.setStyle(table_style)
            w_pfc, h_pfc = table_pfc.wrapOn(p, 0, 0)

        if len(data) > 1:
            table.setStyle(table_style)
            w, h = table.wrapOn(p, 0, 0) 

        
        
        # if y_table-h_pfc > 40 and y_table-h > 40:
        #     p.setFillColorRGB(rgb_normalized[0], rgb_normalized[1], rgb_normalized[2])
        #     p.circle(60, y_table + 20, 10, stroke=0, fill=1)
        #     p.setFillColorRGB(0, 0, 0)
        #     p.drawString(75, y_table + 15, trilha.nome)

        if y_table - (h_pfc + h) > 40:
            p.setFillColorRGB(rgb_normalized[0], rgb_normalized[1], rgb_normalized[2])
            p.circle(60, y_table + 20, 10, stroke=0, fill=1)
            p.setFillColorRGB(0, 0, 0)
            p.drawString(75, y_table + 15, trilha.nome)

        if len(data_pfc) > 1:
            
            if y_table - (h_pfc + h) <= 40:
                draw_logos_curadoria(p, width, height)
                p.setFont("Helvetica", 26)
                mes_escolhido = MONTHS[int(mes)-1][1]
                text_title = f"Agenda de {mes_escolhido}"
                p.drawCentredString(width / 2, height - 50, text_title) 
                p.showPage()  # Cria uma nova página
                p.setFont("Helvetica", 26)  # Redefinindo a fonte para o título
                mes_escolhido = MONTHS[int(mes)-1][1]
                text_title = f"Agenda de {mes_escolhido}"
                p.drawCentredString(width / 2, height - 50, text_title)
                draw_logos_curadoria(p, width, height)
                y_table = 730 
                p.setFont("Helvetica", 13)
                p.setFillColorRGB(rgb_normalized[0], rgb_normalized[1], rgb_normalized[2])
                p.circle(60, y_table + 20, 10, stroke=0, fill=1)
                p.setFillColorRGB(0, 0, 0)
                p.drawString(75, y_table + 15, trilha.nome)
                 # Redefinir `y_table` para o topo da nova página  # Prepara a tabela para ser desenhada
            table_pfc.drawOn(p, 50, y_table-h_pfc)
            y_table -= h_pfc + 10
        if len(data) > 1:
            
            if y_table-h <= 40:
                draw_logos_curadoria(p, width, height)
                p.setFont("Helvetica", 26)
                mes_escolhido = MONTHS[int(mes)-1][1]
                text_title = f"Agenda de {mes_escolhido}"
                p.drawCentredString(width / 2, height - 50, text_title) 
                p.showPage()  # Cria uma nova página
                p.setFont("Helvetica", 26)  # Redefinindo a fonte para o título
                mes_escolhido = MONTHS[int(mes)-1][1]
                text_title = f"Agenda de {mes_escolhido}"
                p.drawCentredString(width / 2, height - 50, text_title)
                draw_logos_curadoria(p, width, height)
                y_table = 730
                p.setFont("Helvetica", 13)
                p.setFillColorRGB(rgb_normalized[0], rgb_normalized[1], rgb_normalized[2])
                p.circle(60, y_table + 20, 10, stroke=0, fill=1)
                p.setFillColorRGB(0, 0, 0)
                p.drawString(75, y_table + 15, trilha.nome)
                  # Redefinir `y_table` para o topo da nova página  # Prepara a tabela para ser desenhada
            table.drawOn(p, 50, y_table-h)
            y_table -= h + 60  # Desenha a tabela na posição x=50, y=500
        else:
            y_table -= 40
    draw_logos_curadoria(p, width, height)
    p.setFont("Helvetica", 26)
    mes_escolhido = MONTHS[int(mes)-1][1]
    text_title = f"Agenda de {mes_escolhido}"
    p.drawCentredString(width / 2, height - 50, text_title) 
    p.showPage()
    p.save()
    return response


@login_required
def curadoria(request):
    """Formulário para gerar agenda mensal da curadoria."""
    current_year = datetime.now().year
    if Curadoria.objects.exists():
        year_range_curadoria = Curadoria.objects.aggregate(
            min_year=Min(ExtractYear('mes_competencia')),
            max_year=Max(ExtractYear('mes_competencia'))
        )
        min_year_curadoria = year_range_curadoria['min_year'] if year_range_curadoria['min_year'] is not None else 0
        max_year_curadoria = year_range_curadoria['max_year'] if year_range_curadoria['max_year'] is not None else 0
    else:
        min_year_curadoria = current_year
        max_year_curadoria = current_year

    if Curso.objects.exists():
        year_range_pfc = Curso.objects.aggregate(
            min_year=Min(ExtractYear('data_inicio')),
            max_year=Max(ExtractYear('data_inicio'))
        )
        min_year_pfc = year_range_pfc['min_year'] if year_range_pfc['min_year'] is not None else 0
        max_year_pfc = year_range_pfc['max_year'] if year_range_pfc['max_year'] is not None else 0
    else:
        min_year_pfc = current_year
        max_year_pfc = current_year

    min_year = 0
    max_year = 0

    if int(min_year_pfc) < int(min_year_curadoria):
        min_year = int(min_year_pfc)
    else:
        min_year = int(min_year_curadoria)
    
    if int(max_year_pfc) > int(max_year_curadoria):
        max_year = int(max_year_pfc)
    else:
        max_year = int(max_year_curadoria)

    # Gera uma lista de anos desde o ano mínimo até o ano máximo
    available_years = list(range(min_year, max_year + 1))
    
    
    context = {
        'cursos': cursos,
        'anos': available_years,
        'meses': MONTHS,
    }

    if request.method == 'POST':
    
        ano = request.POST.get('ano')
        mes = request.POST.get('mes') 
        
        return redirect('gerar_curadoria', ano, mes)
    

    return render(request, 'pfc_app/curadoria.html' ,context)

@login_required
def curadoria_html_show(request):
    """Exibe o formulário de seleção para a agenda em HTML."""
    current_year = datetime.now().year
    if Curadoria.objects.exists():
        year_range_curadoria = Curadoria.objects.aggregate(
            min_year=Min(ExtractYear('mes_competencia')),
            max_year=Max(ExtractYear('mes_competencia'))
        )
        min_year_curadoria = year_range_curadoria['min_year'] if year_range_curadoria['min_year'] is not None else 0
        max_year_curadoria = year_range_curadoria['max_year'] if year_range_curadoria['max_year'] is not None else 0
    else:
        min_year_curadoria = current_year
        max_year_curadoria = current_year

    if Curso.objects.exists():
        year_range_pfc = Curso.objects.aggregate(
            min_year=Min(ExtractYear('data_inicio')),
            max_year=Max(ExtractYear('data_inicio'))
        )
        min_year_pfc = year_range_pfc['min_year'] if year_range_pfc['min_year'] is not None else 0
        max_year_pfc = year_range_pfc['max_year'] if year_range_pfc['max_year'] is not None else 0
    else:
        min_year_pfc = current_year
        max_year_pfc = current_year

    min_year = 0
    max_year = 0

    if int(min_year_pfc) < int(min_year_curadoria):
        min_year = int(min_year_pfc)
    else:
        min_year = int(min_year_curadoria)
    
    if int(max_year_pfc) > int(max_year_curadoria):
        max_year = int(max_year_pfc)
    else:
        max_year = int(max_year_curadoria)


    # Gera uma lista de anos desde o ano mínimo até o ano máximo
    available_years = list(range(min_year, max_year + 1))
    
    # Obtém o último mês com base na maior data de mes_competencia
    ultimo_mes_curadoria = None
    if Curadoria.objects.exists():
        ultima_data = Curadoria.objects.aggregate(
            ultima=Max('mes_competencia')
        )['ultima']
        if ultima_data:
            ultimo_mes_curadoria = ultima_data.month
    
    context = {
        'cursos': cursos,
        'anos': sorted(available_years, reverse=True),
        'meses': MONTHS,
        'ano_atual': current_year,
        'mes_atual': ultimo_mes_curadoria,
    }

    if request.method == 'POST':
    
        ano = request.POST.get('ano')
        mes = request.POST.get('mes') 
        
        return redirect('curadoria_html', ano, mes)
    

    return render(request, 'pfc_app/curadoria_show.html' ,context)

@login_required
def curadoria_html(request, ano, mes):
    """Renderiza a agenda mensal de curadoria em HTML."""

    ano = int(ano)
    mes = int(mes)

    data_inicio = date(ano, mes, 1)
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    data_fim = date(ano, mes, ultimo_dia)

    trilhas = Trilha.objects.all().order_by('ordem_relatorio')
    trilhas_com_cursos = {}
    for trilha in trilhas:
        curadorias = trilha.curadorias.filter(
            Q(mes_competencia__gte=data_inicio, mes_competencia__lte=data_fim) |
            Q(permanente=True)
        )
        cursos = trilha.cursos.filter(data_inicio__gte=data_inicio, data_inicio__lte=data_fim)
        
        trilhas_com_cursos[trilha] = {
            'curadorias': curadorias,
            'cursos': cursos,
            'cor_circulo': trilha.cor_circulo,
            'fundo_tabela': trilha.fundo_tabela
        }



    mes_escolhido = MONTHS[int(mes)-1][1].upper()

    context = {
        'trilhas_com_cursos': trilhas_com_cursos,
        # 'cursos': cursos,
        # 'curadorias': curadorias,
        'mes_escolhido': mes_escolhido
    }

    return render(request, 'pfc_app/agenda_pfc.html', context)

@login_required
def estatistica_lnt(request):
    """Mostra estatísticas da Lista de Necessidades de Treinamento."""
    if request.method == 'GET':
        ano_referencia = int(datetime.now().year)
    elif request.method == 'POST':
        ano_referencia = int(request.POST.get('ano'))

    todos_anos = CursoPriorizado.objects.dates('mes_competencia', 'year', order='ASC').distinct()


    total_cursos = Curso.objects.filter(Q(data_inicio__year=ano_referencia)).count()
    total_curadorias = Curadoria.objects.filter(Q(mes_competencia__year=ano_referencia)).count()
    total_cursos_ofertados = total_cursos + total_curadorias
    total_cursos_priorizados = CursoPriorizado.objects.filter(Q(mes_competencia__year=ano_referencia)).count()
 
    cursos_priorizados_count = Curso.objects.filter(curso_priorizado__isnull=False, data_inicio__year=ano_referencia).count()
    curadorias_priorizadas_count = Curadoria.objects.filter(curso_priorizado__isnull=False, mes_competencia__year=ano_referencia).count()
    cursos_priorizados_ids = Curso.objects.filter(curso_priorizado__isnull=False, data_inicio__year=ano_referencia).values_list('curso_priorizado_id', flat=True)
    curadorias_priorizadas_ids = Curadoria.objects.filter(curso_priorizado__isnull=False, mes_competencia__year=ano_referencia).values_list('curso_priorizado_id', flat=True)
    cursos_nao_ofertados_count = CursoPriorizado.objects.filter(
        ~Q(id__in=cursos_priorizados_ids) & ~Q(id__in=curadorias_priorizadas_ids) & Q(mes_competencia__year=ano_referencia)
    ).count()
    cursos_nao_ofertados = CursoPriorizado.objects.filter(
        ~Q(id__in=cursos_priorizados_ids) & ~Q(id__in=curadorias_priorizadas_ids) & Q(mes_competencia__year=ano_referencia)
    )


    cursos_priorizados_percent = (cursos_priorizados_count / total_cursos * 100) if total_cursos else 0
    curadorias_priorizadas_percent = (curadorias_priorizadas_count / total_curadorias * 100) if total_curadorias else 0
    total_ofertado_percent = ((total_cursos_priorizados - cursos_nao_ofertados_count) / total_cursos_priorizados * 100) if total_cursos_priorizados else 0

    cursos_priorizados_ofertados = total_cursos_priorizados - cursos_nao_ofertados_count
    context = {
        'todos_anos': [date.year for date in todos_anos],
        'ano_referencia': ano_referencia,
        'cursos_priorizados_count': cursos_priorizados_count,
        'curadorias_priorizadas_count': curadorias_priorizadas_count,
        'cursos_nao_ofertados_count': cursos_nao_ofertados_count,
        'cursos_priorizados_percent': round(cursos_priorizados_percent, 2),
        'curadorias_priorizadas_percent': round(curadorias_priorizadas_percent, 2),
        'total_ofertado_percent': round(total_ofertado_percent, 2),
        'total_cursos_ofertados': total_cursos_ofertados,
        'cursos_priorizados_ofertados': cursos_priorizados_ofertados,
        'cursos_nao_ofertados': cursos_nao_ofertados,
        'cursos_priorizados': cursos_nao_ofertados_count + cursos_priorizados_ofertados

    }
    
    return render(request, 'pfc_app/estatistica_priorizados.html', context)

@login_required
def listar_cursos_priorizados(request):
    """Exibe os cursos disponíveis na pesquisa de priorização."""
    # Supondo que você deseja que o ano de referência padrão seja o ano atual
    ano_atual = datetime.now().year

    # Obtenha ou crie o registro de AjustesPesquisa
    ajustes, created = AjustesPesquisa.objects.get_or_create(
        defaults={'nome': 'padrao', 'ano_ref': ano_atual}
    )

    if not ajustes.is_aberta:
        messages.error(request, f'Pesquisa de priorização fechada!')
        return redirect('lista_cursos')

    cursos = PesquisaCursosPriorizados.objects.filter(ano_ref=ajustes.ano_ref).select_related('trilha')
    user_cursos = request.user.pesquisa_cursos_priorizados.all()

    trilhas = Trilha.objects.order_by('ordem_relatorio')
    cursos_por_trilha = defaultdict(list)

    for curso in cursos:
        cursos_por_trilha[curso.trilha].append(curso)

    context = {
        'trilhas': trilhas,
        'cursos_por_trilha': cursos_por_trilha,
        'user_cursos': user_cursos,
        'ano_ref': ajustes.ano_ref
    }
    return render(request, 'pfc_app/pesquisa_priorizacao.html', context)

@login_required
def votar_cursos(request):
    """Registra as escolhas do usuário na pesquisa de priorização."""
    if request.method == 'POST':
        try:
            cursos_ids = request.POST.getlist('cursos')
            cursos_selecionados = PesquisaCursosPriorizados.objects.filter(id__in=cursos_ids)
            request.user.pesquisa_cursos_priorizados.set(cursos_selecionados)
            messages.success(request, f'Priorizações computadas com sucesso!')
        except:
            messages.error(request, f'Algo deu errado!')

    return redirect('lista_cursos')

@login_required
def cursos_mais_votados(request):
    """Exibe e atualiza a lista dos cursos mais votados."""
    ano_referencia_pesquisa = AjustesPesquisa.objects.get(nome='padrao').ano_ref
    data_referencia = datetime(ano_referencia_pesquisa, 1, 1).date()
    if request.method == 'POST':
        cursos_selecionados = request.POST.getlist('cursos')
        cursos_selecionados_ids = [int(curso_id) for curso_id in cursos_selecionados]

        # Cursos atualmente priorizados
        cursos_priorizados = CursoPriorizado.objects.filter(mes_competencia=data_referencia).values_list('nome_sugestao_acao', flat=True)

        # Adicionar cursos que foram selecionados e não estão na tabela CursoPriorizado
        for curso_id in cursos_selecionados_ids:
            curso = PesquisaCursosPriorizados.objects.get(id=curso_id)
            mes_ref = datetime(curso.ano_ref, 1, 1).date()
            if curso.nome not in cursos_priorizados:
                CursoPriorizado.objects.create(nome_sugestao_acao=curso.nome, mes_competencia=mes_ref)

        # Remover cursos que foram desmarcados e estão na tabela CursoPriorizado
        cursos_a_remover = PesquisaCursosPriorizados.objects.exclude(id__in=cursos_selecionados_ids)
        for curso in cursos_a_remover:
            CursoPriorizado.objects.filter(nome_sugestao_acao=curso.nome).delete()

        messages.success(request, f'Priorizações enviadas com sucesso!')
        return redirect('cursos_mais_votados')  # Redireciona para a própria página

    cursos_votados = PesquisaCursosPriorizados.objects.filter(ano_ref=ano_referencia_pesquisa).annotate(num_votos=Count('user')).order_by('-num_votos')

    # Obter os IDs dos cursos já priorizados
    cursos_priorizados_nomes = CursoPriorizado.objects.filter(mes_competencia=data_referencia).values_list('nome_sugestao_acao', flat=True)
    cursos_priorizados_ids = PesquisaCursosPriorizados.objects.filter(ano_ref=ano_referencia_pesquisa, nome__in=cursos_priorizados_nomes).values_list('id', flat=True)

    context = {
        'ano_referencia_pesquisa': ano_referencia_pesquisa,
        'cursos_votados': cursos_votados,
        'cursos_priorizados_ids': list(cursos_priorizados_ids),  # Convertendo para lista para usar no template
    }

    return render(request, 'pfc_app/cursos_mais_votados.html', context)


def get_month_name(month_number):
    """Retorna o nome do mês dado o seu número."""
    for month in MONTHS:
        if month[0] == month_number:
            return month[1]
    return ""

@login_required
def generate_bda_pdf(request, ano, mes):
    """Gera relatório PDF de cursos priorizados do BDA."""
    ano_referencia = ano
    mes_referencia = mes
    total_cursos_priorizados = CursoPriorizado.objects.filter(Q(mes_competencia__year=ano_referencia,)).count()
    status_curso = StatusCurso.objects.get(nome='CANCELADO')
    
    cursos = Curso.objects.filter(data_inicio__month=mes_referencia, data_inicio__year=ano_referencia ,curso_priorizado__isnull=False).exclude(status=status_curso)
    curadorias = Curadoria.objects.filter(mes_competencia__month=mes_referencia, mes_competencia__year=ano_referencia, curso_priorizado__isnull=False)
    
    # Caminho da imagem
    image_path = os.path.join(settings.MEDIA_ROOT, 'igpe.png')
    print(image_path)
    # Cria o documento PDF
    pdf_path = os.path.join(settings.BASE_DIR, 'pdf_output', 'comprovante_bda_{ano}.pdf')
    doc = SimpleDocTemplate(pdf_path, 
                            pagesize=A4,
                            title=f'Comprovante BDA IGPE {ano_referencia}')

    # Estilos
    styles = getSampleStyleSheet()
    style_normal = styles['Normal']
    style_title = styles['Title']

    # Estilo para células de tabela com quebra de linha
    table_cell_style = ParagraphStyle(name='Table_Cell', fontSize=10, leading=12, wordWrap='CJK')
    header_cell_style = ParagraphStyle(name='Header_Cell', fontSize=10, leading=12, alignment=1, wordWrap='CJK')  # Centralizado
    # Elementos do PDF
    elements = []

    # Título
    elements.append(Paragraph(f'ANEXO - Comprovante BDA IGPE {ano}', style_title))
    # Adiciona espaçamento
    elements.append(Spacer(1, 24))

    # Dados da tabela
    header = [
        Paragraph('Nome da Sugestão', header_cell_style),
        Paragraph('Curso ofertado', header_cell_style),
        Paragraph('Forma de Atendimento', header_cell_style),
        Paragraph('Mês', header_cell_style)
    ]
    data = [header]
    
    for curso in cursos:
        data.append([
            Paragraph(curso.curso_priorizado.nome_sugestao_acao, table_cell_style),
            Paragraph(curso.nome_curso, table_cell_style),
            'PFC',
            get_month_name(curso.data_inicio.month),
            
        ])
    for curadoria in curadorias:
        data.append([
            Paragraph(curadoria.curso_priorizado.nome_sugestao_acao, table_cell_style),
            Paragraph(curadoria.nome_curso, table_cell_style),
            'Curadoria',
            get_month_name(curadoria.mes_competencia.month),
            
        ])

    col_widths = [145, 195, 75, 65]  # Define larguras fixas para as colunas
    # Cria a tabela
    table = Table(data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), '#9FC5E8'),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 1), (-1, -1), 'TOP'),  # Alinha o texto ao topo da célula para as linhas de dados
    ]))

    elements.append(table)


    # Adiciona a tabela de estatísticas
    # Adiciona espaçamento
    elements.append(Spacer(1, 50))
    
    # Cabeçalho da tabela de estatísticas
    stats_header = [
        Paragraph('Mês', header_cell_style),
        Paragraph('% LNT do mês', header_cell_style),
        Paragraph('% LNT incremental do mês (considerando apenas cursos não atendidos)', header_cell_style),
        Paragraph('% LNT acumulado (incremental)', header_cell_style)
    ]
    stats_data = [stats_header]

    cursos_priorizados_jacontabilizados = set()
    acumulado = 0

    for month in range(1, mes_referencia + 1):
        cursos_priorizados_ofertados = CursoPriorizado.objects.filter(
            Q(curadorias_priorizadas__mes_competencia__month=month) | Q(cursos_priorizados__data_inicio__month=month),
            mes_competencia__year=ano_referencia
        ).distinct()
    
        cursos_novos_ofertados = cursos_priorizados_ofertados.exclude(pk__in=cursos_priorizados_jacontabilizados)
        
        # Atualiza o conjunto de cursos já contabilizados
        cursos_priorizados_jacontabilizados.update(cursos_novos_ofertados.values_list('pk', flat=True))
        
        percentage_ofertados = (cursos_priorizados_ofertados.count() / total_cursos_priorizados) * 100 if total_cursos_priorizados else 0
        percentage_novos = (cursos_novos_ofertados.count() / total_cursos_priorizados) * 100 if total_cursos_priorizados else 0
        acumulado += percentage_novos

        stats_data.append([
            get_month_name(month),
            f'{percentage_ofertados:.2f}%',
            f'{percentage_novos:.2f}%',
            f'{acumulado:.2f}%'  # Valor acumulado
        ])
    
    stats_col_widths = [80, 100, 200, 100]  # Define larguras fixas para as colunas
    stats_table = Table(stats_data, colWidths=stats_col_widths)
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), '#9FC5E8'),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 1), (-1, -1), 'TOP'),  # Alinha o texto ao topo da célula para as linhas de dados
    ]))

    elements.append(stats_table)

    # Gera o PDF
    #doc.build(elements)
    doc.build(
        elements, 
        onFirstPage=lambda canvas, doc: draw_igpe_logo(canvas, doc)
        )

    # Lê o PDF gerado
    with open(pdf_path, 'rb') as pdf_file:
        pdf_data = pdf_file.read()

    # Cria uma resposta HTTP com o PDF
    response = HttpResponse(pdf_data, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="comprovante_bda_{ano}.pdf"'


    return response


def draw_igpe_logo(canvas, doc):
    """Desenha o logo do IGPE no cabeçalho do documento."""
    # Coordenadas para o logo (ajuste conforme necessário)
    logo_width = 50
    logo_height = 50
    x_ig = doc.width/2  + logo_width  # Alinhamento à direita
    y_ig = doc.height + doc.bottomMargin + doc.topMargin - logo_height -20 # No topo

    x_pfc = x_ig - logo_width - 10
    y_pfc = y_ig

    igpe_relative_path = 'igpe.png'

    igpe_path = os.path.join(settings.MEDIA_ROOT, igpe_relative_path)

    # Substitua 'path/to/your/logo.png' pelo caminho do seu logo
    canvas.drawImage(igpe_path, x_ig, y_ig, width=logo_width, height=logo_height, mask='auto')

@login_required
def duplicar_plano_curso(request):
    """Permite duplicar um plano de curso existente."""
    
    
    if request.method == 'POST':
        plano_id = request.POST.get('plano')
        plano = get_object_or_404(PlanoCurso, pk=plano_id)
        novo_curso_id = request.POST.get('curso')
        novo_curso = get_object_or_404(Curso, pk=novo_curso_id)

        # Duplicar o plano de curso
        novo_plano = PlanoCurso.objects.create(
            curso=novo_curso,
            publico_alvo=plano.publico_alvo,
            quantidade_turma=plano.quantidade_turma,
            pre_requisitos=plano.pre_requisitos,
            objetivo_geral=plano.objetivo_geral,
            objetivo_especifico=plano.objetivo_especifico,
            metodologia_ensino=plano.metodologia_ensino,
            metodologia_avaliacao=plano.metodologia_avaliacao,
            recursos_professor=plano.recursos_professor,
            recursos_aluno=plano.recursos_aluno,
            referencia_bibliografica=plano.referencia_bibliografica,
        )

        # Duplicar os cronogramas associados
        cronogramas = CronogramaExecucao.objects.filter(plano=plano)
        for cronograma in cronogramas:
            CronogramaExecucao.objects.create(
                plano=novo_plano,
                aula=cronograma.aula,
                turno=cronograma.turno,
                conteudo=cronograma.conteudo,
                atividade=cronograma.atividade
            )
        
        messages.success(request, f'Plano de Curso duplicado com sucesso!')
        return redirect('duplicar_plano_curso')
    # planos = PlanoCurso.objects.all()
    planos = sorted(
            PlanoCurso.objects.select_related('curso').all(),
            key=lambda p: (p.curso.data_termino.year if p.curso.data_termino else 0, p.curso.nome_curso),
            reverse=True
            )

    # Listar cursos sem plano de curso associado
    # cursos_disponiveis = Curso.objects.filter(planocurso__isnull=True)

    cursos_disponiveis = sorted(
                    Curso.objects.filter(planocurso__isnull=True),
                    key=lambda c: (
                        c.data_termino.year if c.data_termino else 0,
                        c.nome_formatado_ano
                    ),
                    reverse=True
                    )
    return render(request, 
                  'pfc_app/duplicar_plano_curso.html', 
                  {'planos': planos, 'cursos_disponiveis': cursos_disponiveis})

@login_required
def estatistica_bda(request):
    """Mostra estatísticas do BDA para o ano corrente."""
    current_year = datetime.now().year
    status_cancelado = StatusCurso.objects.get(nome='CANCELADO')
    status_a_iniciar = StatusCurso.objects.get(nome='A INICIAR')

    cursos_priorizados_ids = Curso.objects.filter(curso_priorizado__isnull=False, data_inicio__year=current_year).exclude(status__nome__in=['CANCELADO', 'A INICIAR']).values_list('curso_priorizado_id', flat=True)
    curadorias_priorizadas_ids = Curadoria.objects.filter(curso_priorizado__isnull=False, mes_competencia__year=current_year).values_list('curso_priorizado_id', flat=True)
    print(len(curadorias_priorizadas_ids))
    cursos_nao_ofertados_count = CursoPriorizado.objects.filter(
        ~Q(id__in=cursos_priorizados_ids) & ~Q(id__in=curadorias_priorizadas_ids) & Q(mes_competencia__year=current_year)
    ).count()
    total_cursos_priorizados = CursoPriorizado.objects.filter(Q(mes_competencia__year=current_year)).count()
    cursos_priorizados_ofertados = total_cursos_priorizados - cursos_nao_ofertados_count
    print(f'Total cursos priorizados: {total_cursos_priorizados}')
    print(f'Total cursos nao odertados: {cursos_nao_ofertados_count}')
    
    total_ofertado_percent = ((total_cursos_priorizados - cursos_nao_ofertados_count) / total_cursos_priorizados * 100) if total_cursos_priorizados else 0
    
    if CursoPriorizado.objects.exists():
        year_range_priorizados = CursoPriorizado.objects.aggregate(
            min_year=Min(ExtractYear('mes_competencia')),
            max_year=Max(ExtractYear('mes_competencia'))
        )
        # min_year_curadoria
        min_year_priorizados = year_range_priorizados['min_year'] if year_range_priorizados['min_year'] is not None else 0
        max_year_priorizados = year_range_priorizados['max_year'] if year_range_priorizados['max_year'] is not None else 0
    else:
        min_year_priorizados = current_year
        max_year_priorizados = current_year
    
    available_years = list(range(min_year_priorizados, max_year_priorizados + 1))

    if request.method == 'POST':
        ano = request.POST.get('ano')
        mes = request.POST.get('mes') 
        
        return redirect('gerar_pdf_bda', ano, mes)

    context = {
        'anos': available_years,
        'meses': MONTHS,
        'cursos_priorizados_ofertados': cursos_priorizados_ofertados,
        'total_ofertado_percent': round(total_ofertado_percent, 2),
    }

    return render (request, 'pfc_app/estatistica_bda.html', context)

def select_lotacao_view(request):
    """Tela inicial para seleção de lotação a ser alterada."""
    lotacoes = Lotacao.objects.all()
    #lotacoes_especificas = LotacaoEspecifica.objects.all()
    context = {
        'lotacoes': lotacoes,
        #'lotacoes_especificas': lotacoes_especificas,
        }
    return render(request, 'pfc_app/change_lotacao.html', context)

def get_lotacao_especifica(request):
    """Retorna partial com lotações específicas da lotação atual."""
    lotacao = request.GET.get('lotacao')
    especificacoes = LotacaoEspecifica.objects.filter(lotacao=lotacao)
    usuarios = User.objects.filter(lotacao_fk=lotacao)
    context = {
        'lotacoes_especificas': especificacoes,
        'usuarios': usuarios,
        }
    return render(request, 'pfc_app/parciais/lotacao_especifica.html', context)

def get_nova_lotacao_especifica(request):
    """Busca lotações específicas para a nova lotação escolhida."""
    nova_lotacao = request.GET.get('nova_lotacao')
    especificacoes = LotacaoEspecifica.objects.filter(lotacao=nova_lotacao)

    context = {
        'nova_lotacoes_especificas': especificacoes
        }
    return render(request, 'pfc_app/parciais/nova_lotacao_especifica.html', context)

def listar_usuarios(request):
    """Lista usuários filtrados pela lotação específica."""
    lotacao_especifica = request.GET.get('lotacao-especifica')
    usuarios = User.objects.filter(lotacao_especifica_fk=lotacao_especifica)
    lotacoes = Lotacao.objects.all()
    #lotacoes_especificas = LotacaoEspecifica.objects.all()
    context = {
        'usuarios': usuarios,
        'lotacoes': lotacoes,
        #'lotacoes_especificas': lotacoes_especificas,
        }
    return render(request, 'pfc_app/parciais/lista_usuarios.html', context)

def atualizar_lotacao_usuario(request):
    """Atualiza a lotação dos usuários selecionados."""
    usuario_ids = request.POST.getlist('usuario_ids')
    print(usuario_ids)
    nova_lotacao_id = request.POST.get('nova_lotacao')
    nova_lotacao_especifica_id = request.POST.get('nova_lotacao_especifica')

    try:
        for usuario_id in usuario_ids:
            usuario = User.objects.get(id=usuario_id)
            usuario.lotacao_fk_id = nova_lotacao_id
            usuario.lotacao_especifica_fk_id = nova_lotacao_especifica_id
            usuario.save()

        #usuarios = User.objects.all()
        # lotacoes = Lotacao.objects.all()
        # lotacoes_especificas = LotacaoEspecifica.objects.all()
        messages.success(request, f'Lotação alterada com sucesso!')
        return redirect('change_lotacao')
    except:
        messages.error(request, f'Algo deu errado!')
        return redirect('change_lotacao')

def abrir_modal(request):
    """Abre modal para confirmar alteração de lotação."""
    usuario_ids = request.GET.getlist('usuario_check')
    usuarios = User.objects.filter(id__in=usuario_ids)
    lotacoes = Lotacao.objects.all()
    lotacoes_especificas = LotacaoEspecifica.objects.all()
    print(usuario_ids)
    context = {
        'usuario_ids': usuario_ids,
        'usuarios': usuarios,
        'lotacoes': lotacoes,
        'lotacoes_especificas': lotacoes_especificas
    }
    return render(request, 'pfc_app/parciais/modal_lotacao.html', context)

@csrf_exempt
def log_time(request):
    """Registra tempo de permanência em cada página."""
    if request.method == 'POST':
        data = json.loads(request.body)
        url = data.get('url')
        time_spent = data.get('time_spent')
        
        if request.user.is_authenticated:
            # Armazene os dados em um modelo
            PageVisit.objects.create(user=request.user, url=url, time_spent=time_spent, timestamp=timezone.now())

        return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'error'}, status=400)


@login_required
def gastos(request):
    """Calcula gastos estimados com instrutores e coordenação."""
    # Subquery para obter a última vigência (mais recente) de AjustesHoraAula
    # latest_date_subquery = AjustesHoraAula.objects.order_by(
    #     '-ano_mes_referencia').values('ano_mes_referencia')[:1]

    # latest_ajuste_subquery = AjustesHoraAula.objects.filter(
    #     ano_mes_referencia=Subquery(latest_date_subquery)
    # ).order_by('-ano_mes_referencia')[:1]
    latest_ajuste_subquery = AjustesHoraAula.objects.filter(
        ano_mes_referencia__lte=OuterRef('data_inicio')
    ).order_by('-ano_mes_referencia')[:1]


    # Consulta principal
    cursos = Curso.objects.filter(origem_pagamento__isnull=False).annotate(
        instrutores_count=Count('inscricao', filter=Q(inscricao__condicao_na_acao='DOCENTE')),
        valor_instrutor_primario=Case(
            When(
                origem_pagamento__nome="Sem Pagamento",
                then=Value(0)
            ),
            default=ExpressionWrapper(
                Subquery(
                    latest_ajuste_subquery.values('valor_instrutor_primario')
                ) * F('ch_curso'),
                output_field=DecimalField()
            ),
            output_field=DecimalField()
        ),
        valor_instrutor_secundario=Case(
            When(
                origem_pagamento__nome="Sem Pagamento",
                then=Value(0)
            ),
            default=ExpressionWrapper(
                Case(
                    When(
                        instrutores_count__gt=1, 
                        then=Subquery(latest_ajuste_subquery.values('valor_instrutor_secundario'))
                    ),
                    default=Value(0),
                    output_field=DecimalField()
                ) * F('ch_curso'),
                output_field=DecimalField()
            ),
            output_field=DecimalField()
        ),
        valor_coordenador=Case(
            When(
                origem_pagamento__nome="Sem Pagamento",
                then=Value(0)
            ),
            default=ExpressionWrapper(
                Subquery(
                    latest_ajuste_subquery.values('valor_coordenador')
                ) * F('ch_curso'),
                output_field=DecimalField()
            ),
            output_field=DecimalField()
        ),
        total_gastos=Case(
            When(
                origem_pagamento__nome="Sem Pagamento",
                then=Value(0)
            ),
            default=ExpressionWrapper(
                F('valor_instrutor_primario') + 
                Case(
                    When(instrutores_count__gt=1, then=F('valor_instrutor_secundario')),
                    default=Value(0),
                    output_field=DecimalField()
                ) + 
                F('valor_coordenador'),
                output_field=DecimalField()
            ),
            output_field=DecimalField()
        )
    )
    # Calcular o total geral gasto
    total_geral_gasto = cursos.aggregate(total=Sum('total_gastos'))['total'] or 0

    # Calcular o total gasto no ano atual
    current_year = now().year
    total_gasto_atual_ano = cursos.filter(
        data_inicio__year=current_year
    ).aggregate(total=Sum('total_gastos'))['total'] or 0

    context = {
        'cursos': cursos,
        'total_geral_gasto': total_geral_gasto,
        'total_gasto_atual_ano': total_gasto_atual_ano,
    }
    return render(request, 'pfc_app/gastos_com_cursos.html', context)


# from django.http import JsonResponse
# from django.views.decorators.csrf import csrf_exempt
# from .models import User, Inscricao

from datetime import date

@csrf_exempt
def carga_horaria_por_cpf(request):
    cpf = request.GET.get("cpf")

    if not cpf or len(cpf) != 11:
        return JsonResponse({"erro": "CPF inválido"}, status=400)

    try:
        usuario = User.objects.get(cpf=cpf)

        # Definindo 1º de março do ano atual
        hoje = timezone.now().date()
        ano_base = hoje.year
        data_corte = date(ano_base, 3, 1)

        # Caso ainda estejamos antes de 01/03, use 01/03 do ano anterior
        if hoje < data_corte:
            data_corte = date(ano_base - 1, 3, 1)

        inscricoes = Inscricao.objects.filter(
            ~Q(status__nome='CANCELADA'),
            ~Q(status__nome='EM FILA'),
            Q(curso__status__nome='FINALIZADO'),
            Q(concluido=True),
            participante=usuario,
            curso__data_termino__gte=data_corte
        )

        carga_pfc = sum(i.ch_valida or 0 for i in inscricoes)

        status_validacoes = StatusValidacao.objects.filter(
            nome__in=["DEFERIDA", "DEFERIDA PARCIALMENTE"]
        )

        validacoes = Validacao_CH.objects.filter(usuario=usuario, 
                                                 data_termino_curso__gte=data_corte,
                                           status__in=status_validacoes)
        
        carga_validacoes = sum(i.ch_confirmada or 0 for i in validacoes)

        carga_total = carga_pfc + carga_validacoes

        return JsonResponse({
            "nome": usuario.nome,
            "cpf": usuario.cpf,
            "carga_horaria_total": carga_total,
            "periodo": f"{data_corte.strftime('%d/%m/%Y')} até hoje"
        })

    except User.DoesNotExist:
        return JsonResponse({"erro": "Usuário não encontrado"}, status=404)



# from django.utils import timezone
# from .models import Curso

@csrf_exempt
def cursos_disponiveis(request):
    hoje = timezone.now().date()
    cursos = Curso.objects.filter(data_inicio__gte=hoje).order_by("data_inicio")[:10]

    lista = [{
        "nome": curso.nome_formatado,
        "data_inicio": curso.data_inicio,
        "data_termino": curso.data_termino,
        "ch": curso.ch_curso,
        "link": f"https://www.pfc.seplag.pe.gov.br/curso_detail/{curso.id}"
    } for curso in cursos]

    return JsonResponse({"cursos": lista})


import pandas as pd
import unicodedata


@csrf_exempt
def buscar_parlamentares(request):
    nome_param = request.GET.get("nome", "").strip()

    if not nome_param:
        return JsonResponse({"erro": "Parâmetro 'nome' é obrigatório."}, status=400)

    # Função para remover acentos e deixar em minúsculas
    def normalizar(texto):
        if pd.isna(texto):
            return ""
        return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode().lower()

    try:
        caminho_csv = os.path.join(settings.BASE_DIR, "media", "emendas.csv")
        df = pd.read_csv(caminho_csv)

        # Normaliza os nomes no dataframe
        df["parlamentar_normalizado"] = df["PARLAMENTAR"].apply(normalizar)

        # Normaliza o nome de busca
        nome_normalizado = normalizar(nome_param)

        # Filtra onde o nome buscado está contido
        df_filtrado = df[df["parlamentar_normalizado"].str.contains(nome_normalizado, na=False)]

        # Remove duplicados
        parlamentares_unicos = df_filtrado[["PARLAMENTAR", "ID_PARLAMENTAR"]].drop_duplicates()

        return JsonResponse({"resultados": parlamentares_unicos.to_dict(orient="records")})
    
    except Exception as e:
        return JsonResponse({"erro": str(e)}, status=500)

@csrf_exempt
def buscar_municipios(request):
    nome_param = request.GET.get("nome", "").strip()

    if not nome_param:
        return JsonResponse({"erro": "Parâmetro 'nome' é obrigatório."}, status=400)

    # Função para remover acentos e deixar em minúsculas
    def normalizar(texto):
        if pd.isna(texto):
            return ""
        return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode().lower()

    try:
        caminho_csv = os.path.join(settings.BASE_DIR, "media", "emendas.csv")
        df = pd.read_csv(caminho_csv)

        # Normaliza os nomes no dataframe
        df["municipio_normalizado"] = df["MUNICÍPIOS"].apply(normalizar)

        # Normaliza o nome de busca
        nome_normalizado = normalizar(nome_param)

        # Filtra onde o nome buscado está contido
        df_filtrado = df[df["municipio_normalizado"].str.contains(nome_normalizado, na=False)]

        # Remove duplicados
        municipios_unicos = df_filtrado[["municipio_normalizado", "CD_MUNICIPIO"]].drop_duplicates()
        municipios_unicos["municipio_normalizado"] = municipios_unicos["municipio_normalizado"].str.title()


        return JsonResponse({"resultados": municipios_unicos.to_dict(orient="records")})
    
    except Exception as e:
        return JsonResponse({"erro": str(e)}, status=500)


import os
import io
import base64
import pandas as pd
from django.http import JsonResponse

def resumo_emendas(request, id_parlamentar):
    caminho_csv = os.path.join('media', 'emendas.csv')
    df = pd.read_csv(caminho_csv, encoding='utf-8')

    # Filtra pelo parlamentar
    df_filtrado = df[df['ID_PARLAMENTAR'] == id_parlamentar]
    if df_filtrado.empty:
        return JsonResponse({'erro': 'Parlamentar não encontrado'}, status=404, json_dumps_params={"ensure_ascii": False})

    nome = df_filtrado['PARLAMENTAR'].iloc[0]
    # df_filtrado = df_filtrado[df_filtrado['ANO DA EMENDA']==2025]

    # Função para converter valores com vírgula em float
    def parse_valor(valor):
        if pd.isna(valor):
            return 0.0
        valor = str(valor).replace('.', '').replace(',', '.')
        try:
            return float(valor)
        except ValueError:
            return 0.0


    investimento_total = df_filtrado['INVESTIMENTO PREVISTO 2025'].apply(parse_valor).sum()
    liquidado_total = df_filtrado['LIQUIDAÇÃO 2025'].apply(parse_valor).sum()

    # Impedimentos (tratando NaN)
    impedimentos = df_filtrado[df_filtrado['IMPEDIMENTO TÉCNICO'].fillna('').str.upper() == 'SIM'].shape[0]

    # ===== CSV embutido (filtrado por ANO DA EMENDA = 2025) =====
    # Normaliza o tipo do ano (caso venha como string)
    # ano_col = 'ANO DA EMENDA'
    # df_filtrado[ano_col] = pd.to_numeric(df_filtrado[ano_col], errors='coerce').astype('Int64')

    colunas = [
        "PARLAMENTAR",
        "ANO DA EMENDA",
        "TEMÁTICA",
        "IMPEDIMENTO TÉCNICO",
        "INVESTIMENTO PREVISTO 2025",
        "MUNICÍPIOS",
        "EMPENHO 2025",
        "LIQUIDAÇÃO 2025",
        "PAGAMENTO 2025",
    ]

    # Seleciona somente 2025 e apenas as colunas desejadas
    df_csv = df_filtrado[colunas]

    # Gera CSV em memória (sep=';' e BOM p/ Excel)
    csv_buffer = io.StringIO()
    df_csv.to_csv(csv_buffer, index=False, sep=';', encoding="utf-8-sig")
    csv_text = '\ufeff' + csv_buffer.getvalue()  # BOM UTF-8
    csv_bytes = csv_text.encode('utf-8-sig')
    csv_b64 = base64.b64encode(csv_bytes).decode('ascii')

    return JsonResponse({
        'nome': nome,
        'investimento_total': f"R$ {investimento_total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
        'liquidado_total': f"R$ {liquidado_total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
        'impedimentos': impedimentos,
        'csv': {
            'filename': f"emendas_{nome}_2025.csv",
            'mimetype': 'text/csv; charset=utf-8',
            'encoding': 'base64',
            'content': csv_b64
        }
    }, json_dumps_params={"ensure_ascii": False})



@csrf_exempt
@require_GET
def resumo_emendas_municipio(request, cd_mun: int):
    """
    Lê /media/emendas.csv, filtra ANO==2025 e CD_MUNICIPIO==cd_mun,
    retorna resumo + CSV (base64) das linhas filtradas.
    """
    caminho_csv = os.path.join(getattr(settings, 'MEDIA_ROOT', 'media'), 'emendas.csv')
    if not os.path.exists(caminho_csv):
        return JsonResponse({"erro": "Arquivo emendas.csv não encontrado em /media"}, status=404)

    # Lê tudo como string para evitar problemas com zeros à esquerda / vírgulas decimais
    df = pd.read_csv(caminho_csv, encoding='utf-8')
    
    # Normaliza colunas esperadas
    for col in ['CD_MUNICIPIO', 'MUNICÍPIOS']:
        if col not in df.columns:
            return JsonResponse({"erro": f"Coluna obrigatória ausente: {col}"}, status=400)

    # Filtro do ano (se existir a coluna ANO)
    # if 'ANO DA EMENDA' in df.columns:
        # df['ANO DA EMENDA'] = df['ANO DA EMENDA'].astype(str).str.extract(r'(\d{4})', expand=False)
    #    df = df[df['ANO DA EMENDA'] == 2025]
    # Garante comparação como string
    df['CD_MUNICIPIO'] = df['CD_MUNICIPIO'].astype(str)
    df_filtrado = df[df['CD_MUNICIPIO'] == str(cd_mun)]

    if df_filtrado.empty:
        return JsonResponse(
            {'erro': 'Município não encontrado ou sem registros para 2025'},
            status=404,
            json_dumps_params={"ensure_ascii": False}
        )

    nome = df_filtrado['MUNICÍPIOS'].dropna().iloc[0]

    def parse_valor(valor):
        if pd.isna(valor):
            return 0.0
        s = str(valor).strip()
        if not s:
            return 0.0
        # pt-BR -> float
        s = s.replace('.', '').replace(',', '.')
        try:
            return float(s)
        except Exception:
            return 0.0

    def moeda_pt(valor_float: float) -> str:
        return f"R$ {valor_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

    col_inv = 'INVESTIMENTO PREVISTO 2025'
    col_liq = 'LIQUIDAÇÃO 2025'
    col_imp = 'IMPEDIMENTO TÉCNICO'

    investimento_total = df_filtrado[col_inv].apply(parse_valor).sum() if col_inv in df_filtrado.columns else 0.0
    liquidado_total   = df_filtrado[col_liq].apply(parse_valor).sum() if col_liq in df_filtrado.columns else 0.0
    impedimentos = (
        df_filtrado[col_imp].fillna('').astype(str).str.upper().eq('SIM').sum()
        if col_imp in df_filtrado.columns else 0
    )

        # ------ SOMENTE AS COLUNAS PEDIDAS NO CSV ------
    colunas_desejadas = [
        "PARLAMENTAR",
        "ANO DA EMENDA",
        "TEMÁTICA",
        "IMPEDIMENTO TÉCNICO",
        "INVESTIMENTO PREVISTO 2025",
        "MUNICÍPIOS",
        "EMPENHO 2025",
        "LIQUIDAÇÃO 2025",
        "PAGAMENTO 2025",
    ]
    disponiveis = [c for c in colunas_desejadas if c in df_filtrado.columns]
    ausentes = [c for c in colunas_desejadas if c not in df_filtrado.columns]

    df_csv = df_filtrado[disponiveis].copy()

    # CSV → base64
    buf = io.StringIO()
    df_csv.to_csv(buf, index=False, encoding="utf-8-sig")  # StringIO já é texto; depois codificamos para utf-8
    csv_bytes = buf.getvalue().encode('utf-8-sig')
    csv_b64 = base64.b64encode(csv_bytes).decode('ascii')

    return JsonResponse(
        {
            'nome': nome,
            'investimento_total': moeda_pt(investimento_total),
            'liquidado_total': moeda_pt(liquidado_total),
            'impedimentos': int(impedimentos),
            # payload para o n8n enviar como documento
            # 'csv_filename': f"emendas_municipio_{nome}_2025.csv",
            # 'csv_mimetype': "text/csv",
            # 'csv_b64': csv_b64,
            'csv': {
                'filename': f"emendas_municipio_{nome}_2025.csv",
                'mimetype': 'text/csv',
                'encoding': 'base64',
                'content': csv_b64
            },
            'csv_columns_used': disponiveis,
            'csv_columns_missing': ausentes,
        },
        json_dumps_params={"ensure_ascii": False}
    )



def top_deputados_emendas(request):
    caminho_csv = os.path.join('media', 'emendas.csv')
    df = pd.read_csv(caminho_csv, encoding='utf-8')

    # Função para converter valores monetários
    def parse_valor(valor):
        if pd.isna(valor):
            return 0.0
        valor = str(valor).replace('.', '').replace(',', '.')
        try:
            return float(valor)
        except ValueError:
            return 0.0

    df['valor'] = df['LIQUIDAÇÃO 2025'].apply(parse_valor)
    df_group = df.groupby(['PARLAMENTAR'])['valor'].sum().reset_index()

    df_group = df_group.sort_values(by='valor', ascending=False).head(10)

    resultado = [
        {
            'nome': row['PARLAMENTAR'],
            'total_emendas': f"{row['valor']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        }
        for _, row in df_group.iterrows()
    ]

    return JsonResponse({'top10': resultado}, json_dumps_params={'ensure_ascii': False})


def top_municipios_emendas(request):
    caminho_csv = os.path.join('media', 'emendas.csv')
    df = pd.read_csv(caminho_csv, encoding='utf-8')

    def parse_valor(valor):
        if pd.isna(valor):
            return 0.0
        valor = str(valor).replace('.', '').replace(',', '.')
        try:
            return float(valor)
        except ValueError:
            return 0.0

    df['valor'] = df['LIQUIDAÇÃO 2025'].apply(parse_valor)
    df_group = df.groupby(['MUNICÍPIOS'])['valor'].sum().reset_index()

    df_group = df_group.sort_values(by='valor', ascending=False).head(10)

    resultado = [
        {
            'municipio': row['MUNICÍPIOS'],
            'total_emendas': f"{row['valor']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        }
        for _, row in df_group.iterrows()
    ]

    return JsonResponse({'top10': resultado}, json_dumps_params={'ensure_ascii': False})


# Se preferir, mova essa URL para settings.py como EMENDAS_CSV_URL
EMENDAS_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/1MwwFDqkmlXjtImorlUGoSaccADrkmrwUfiW6FvtcFsc/export?format=csv&gid=0"
)

@csrf_exempt
@require_http_methods(["GET", "POST"])  # aceita GET ou POST (mais simples para o n8n)
def update_emendas_csv(request):
    """
    Baixa o CSV público do Google Sheets e salva em MEDIA_ROOT/emendas.csv
    - Sobrescreve o arquivo existente de forma atômica (os.replace).
    - Não recebe arquivo no corpo da requisição.
    """
    media_root = getattr(settings, "MEDIA_ROOT", "media")
    os.makedirs(media_root, exist_ok=True)

    final_path = os.path.join(media_root, "emendas.csv")
    tmp_path = os.path.join(media_root, f".emendas.csv.tmp-{uuid.uuid4().hex}")

    # Requisição HTTP simples usando urllib (sem dependências externas)
    req = Request(
        EMENDAS_CSV_URL,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/csv, */*;q=0.1",
        },
        method="GET",
    )

    try:
        with urlopen(req, timeout=30) as resp, open(tmp_path, "wb") as dest:
            # Status check (em versões mais novas de Python resp.status existe)
            status = getattr(resp, "status", 200)
            if status != 200:
                return JsonResponse({"ok": False, "error": f"HTTP {status} ao baixar CSV"}, status=502)

            # Stream em chunks para arquivo temporário
            while True:
                chunk = resp.read(1024 * 64)
                if not chunk:
                    break
                dest.write(chunk)

        # Substitui de forma atômica (sobrescreve se já existir)
        os.replace(tmp_path, final_path)

        size = os.path.getsize(final_path)
        return JsonResponse({"ok": True, "saved_as": "emendas.csv", "bytes": size})

    except Exception as e:
        # Limpa temporário se algo falhar
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        return JsonResponse({"ok": False, "error": f"Falha ao atualizar: {e}"}, status=500)