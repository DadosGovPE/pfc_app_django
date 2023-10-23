from django.shortcuts import render,redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages, auth
from django.db import IntegrityError
from django.http import HttpResponse
from django.template import loader
from .models import Curso, Inscricao, StatusInscricao, Avaliacao, Validacao_CH, StatusValidacao, User
from .forms import AvaliacaoForm 
from django.db.models import Count, Q, Sum, Case, When, BooleanField, Exists, OuterRef
from datetime import date
from django.views.generic import DetailView
import os
import zipfile
from django.http import HttpResponse
from django.shortcuts import get_list_or_404
from reportlab.pdfgen import canvas

# Create your views here.

def login(request):
    if request.method != 'POST':
        return render(request, 'pfc_app/login.html')

    usuario = request.POST.get('usuario')
    senha = request.POST.get('senha')

    user = auth.authenticate(username=usuario, password=senha)

    if not user:
        messages.error(request, 'Usuário ou senha inválidos!')
        return render(request, 'pfc_app/login.html')
    else:
        auth.login(request, user)
        messages.success(request, 'Seja bem vindo!')
        return redirect('lista_cursos')

    return render(request, 'pfc_app/login.html')

def logout(request):
    auth.logout(request)
    return redirect('login')




@login_required
def cursos(request):
  lista_cursos = Curso.objects.all()
  data_atual = date.today()
  cursos_com_inscricoes = Curso.objects.annotate(
        num_inscricoes=Count('inscricao', 
                             filter=~Q(inscricao__condicao_na_acao='DOCENTE') & 
                             ~Q(inscricao__status__nome='CANCELADA') &
                             ~Q(inscricao__status__nome='EM FILA') 
                             ),
        usuario_inscrito=Exists(
           Inscricao.objects.filter(participante=request.user, curso=OuterRef('pk'))
            
        )
    ).order_by('data_inicio').all().filter(data_inicio__gt=data_atual)
  #template = loader.get_template('base.html')
  #cursos_nao_inscrito = cursos_com_inscricoes.exclude(inscricao__participante=request.user)
  context = {
    'cursos': cursos_com_inscricoes,
  }
  #print(context['cursos'][1].inscricao_set.count())
  return render(request, 'pfc_app/lista_cursos.html' ,context)


@login_required
def carga_horaria(request):
  inscricoes_do_usuario = Inscricao.objects.filter(
     ~Q(status__nome='CANCELADA'),
     ~Q(status__nome='EM FILA'),
     Q(curso__status__nome='FINALIZADO'),
     Q(concluido=True),
     participante=request.user
     
     )
    
  # Calcula a soma da carga horária das inscrições do usuário
  satus_validacao = StatusValidacao.objects.get(nome='APROVADA')
  carga_horaria_pfc = inscricoes_do_usuario.aggregate(Sum('ch_valida'))['ch_valida__sum'] or 0
  validacoes_ch = Validacao_CH.objects.filter(usuario=request.user, status=satus_validacao).aggregate(Sum('ch_confirmada'))['ch_confirmada__sum'] or 0
  carga_horaria_total = carga_horaria_pfc + validacoes_ch
  context = {
      'carga_horaria_total': carga_horaria_total,
  }

  return render(request, 'pfc_app/carga_horaria.html' ,context)


@login_required
def inscricoes(request):
    #inscricoes_do_usuario = Inscricao.objects.filter(participante=request.user)

    inscricoes_do_usuario = Inscricao.objects.annotate(
        curso_avaliado=Exists(
           Avaliacao.objects.filter(participante=request.user, curso=OuterRef('curso'))
            
        )
    ).filter(participante=request.user)
    
    context = {
        'inscricoes': inscricoes_do_usuario,
    }
    
    return render(request, 'pfc_app/inscricoes.html', context)


class CursoDetailView(DetailView):
   # model_detail.html
   model = Curso

   def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Recupere o usuário docente relacionado ao curso atual
        curso = self.get_object()
        usuario_docente = None

        # Verifique se há uma inscrição do tipo 'DOCENTE' relacionada a este curso
        inscricoes_docentes = Inscricao.objects.filter(curso=curso, condicao_na_acao='DOCENTE')

        usuarios_docentes = [inscricao.participante for inscricao in inscricoes_docentes]

        # Adicione o usuário docente ao contexto
        context['usuarios_docentes'] = usuarios_docentes

        return context


@login_required
def cancelar_inscricao(request, inscricao_id):
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
       return render(request, 'pfc_app/inscricoes.html')
    else:
       messages.error(request, 'Você não está inscrito nesse curso!')
       return render(request, 'pfc_app/inscricoes.html')
    
    #return render(request, 'pfc_app/inscricoes.html', context)

@login_required
def inscrever(request, curso_id):
    curso = Curso.objects.get(pk=curso_id)
    status_id_pendente = StatusInscricao.objects.get(nome='PENDENTE')
    status_id_fila = StatusInscricao.objects.get(nome='EM FILA')
    
    # Conta quantas inscrições válidas há nesse curso
    inscricoes_validas = Inscricao.objects.filter(
        ~Q(status__nome='CANCELADA'),
        ~Q(status__nome='EM FILA'),
        ~Q(condicao_na_acao='DOCENTE'),
        curso=curso
    ).count()
    
    # Compara com o número de vagas
    # Caso seja maior ou igual redireciona
    if inscricoes_validas >= curso.vagas:
        print(inscricoes_validas)
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
      inscricao, criada = Inscricao.objects.get_or_create(participante=request.user, curso=curso, status=status_id_pendente)
      
      if criada:
          # A inscrição foi criada com sucesso
          messages.success(request, 'Inscrição realizada!')
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
    return render(request, 'pfc_app/sucesso_inscricao.html')

def inscricao_existente(request):
    return render(request, 'pfc_app/inscricao_existente.html')

@login_required
def avaliacao(request, curso_id):
    # Checa se o curso existe
    try:
      curso = Curso.objects.get(pk=curso_id)
    except:
       messages.error(request, f"Curso não encontrado!")
       return redirect('lista_cursos')
    
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
        form = AvaliacaoForm(request.POST)
        if form.is_valid():
            # Faça o que for necessário com os dados da avaliação, como salvá-los no banco de dados
            usuario = request.user
            ja_avaliado=Avaliacao.objects.filter(participante=usuario, curso=curso)
            
            if ja_avaliado:
                messages.error(request, f"Avaliação já realizada!")
                return redirect('inscricoes')
            


            avaliacao = form.save(commit=False)
            avaliacao.participante = usuario
            
            avaliacao.curso = curso
            #form.save()
            avaliacao.save()
            # Redirecione para uma página de sucesso ou outra ação apropriada
            messages.success(request, 'Avaliação Realizada!')
            return redirect('inscricoes')
        messages.error(request, form.errors)
            #return render(request, 'sucesso.html')
       #else:
           #messages.error(request, 'Nenhum item pode ficar em branco')
           #return render(request, 'pfc_app/avaliacao.html', {'form': form})

    else:
        form = AvaliacaoForm()

    return render(request, 'pfc_app/avaliacao.html', {'form': form, 'curso':curso})


def enviar_pdf(request):
    if request.method == 'POST':
        arquivo_pdf = request.FILES['arquivo_pdf']
        avaliacao = Validacao_CH(usuario=request.user, arquivo_pdf=arquivo_pdf)
        avaliacao.save()
        # Redirecionar ou fazer algo após o envio bem-sucedido
        messages.success(request, 'Arquivo enviado com sucesso!')
        return redirect('enviar_pdf')

    return render(request, 'pfc_app/enviar_pdf.html')


def download_all_pdfs(request):
    return render(request, 'pfc_app/download_all_pdfs.html')


def generate_all_pdfs(request):
    users = get_list_or_404(User)

    output_folder = "pdf_output"  # Pasta onde os PDFs temporários serão salvos
    zip_filename = "all_pdfs.zip"

    # Crie a pasta de saída se ela não existir
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Crie o arquivo ZIP
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for user in users:
            pdf_filename = os.path.join(output_folder, f"{user.username}.pdf")
            # Crie o PDF usando ReportLab
            p = canvas.Canvas(pdf_filename)
            p.drawString(100, 750, f'Nome do Usuário: {user.username}')
            # Adicione mais informações conforme necessário

            p.showPage()
            p.save()

            # Adicione o PDF ao arquivo ZIP
            zipf.write(pdf_filename, os.path.basename(pdf_filename))

    # Configure a resposta HTTP para o arquivo ZIP
    response = HttpResponse(content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'

    # Abra o arquivo ZIP e envie seu conteúdo como resposta
    with open(zip_filename, 'rb') as zip_file:
        response.write(zip_file.read())

    # Exclua os PDFs temporários e o arquivo ZIP após o envio
    for user in users:
        pdf_filename = os.path.join(output_folder, f"{user.username}.pdf")
        os.remove(pdf_filename)
    os.remove(zip_filename)

    return response