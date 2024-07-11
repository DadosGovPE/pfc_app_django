from django.db import models
from django import forms
import os
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import pre_save
from django.dispatch import receiver
import base64
from django.conf import settings
from django.utils import timezone
from datetime import datetime

# Create your models here.
class PesquisaCursosPriorizados(models.Model):
    nome = models.CharField(max_length=200, blank=False, null=False)
    ano_ref = models.IntegerField(default=datetime.now().year)
    def __str__(self):
        return self.nome


class User(AbstractUser):
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    cpf = models.CharField(max_length=11, blank=False, null=False, unique=True)
    nome = models.CharField(max_length=400, blank=False, null=False)
    email = models.EmailField(default='a@b.com', null=False, blank=False, unique=True)
    telefone = models.CharField(max_length=40, blank=True, null=True)
    cargo = models.CharField(max_length=400, blank=True, null=True)
    nome_cargo = models.CharField(max_length=400, blank=True, null=True)
    categoria = models.CharField(max_length=400, blank=True, null=True)
    grupo_ocupacional = models.CharField(max_length=400, blank=True, null=True)
    origem = models.CharField(max_length=400, blank=True, null=True)
    simbologia = models.CharField(max_length=400, blank=True, null=True)
    tipo_atuacao = models.CharField(max_length=400, blank=True, null=True)
    lotacao = models.CharField(max_length=400, blank=True, null=True)
    lotacao_especifica = models.CharField(max_length=400, blank=True, null=True)
    lotacao_especifica_2 = models.CharField(max_length=400, blank=True, null=True, verbose_name = ("Lotação sigla"))
    classificacao_lotacao = models.CharField(max_length=400, blank=True, null=True)
    pesquisa_cursos_priorizados = models.ManyToManyField(PesquisaCursosPriorizados, blank=True, null=True)

    is_ativo = models.BooleanField(default=True)
    role = models.CharField(max_length=40, default="USER")
    is_externo = models.BooleanField(default=False, verbose_name = ("É externo"))
    avatar = models.ImageField(null=True, blank=True)
    avatar_base64 = models.TextField(blank=True, null=True)
    
    USERNAME_FIELD = "cpf"

    def publish(self):
        self.published_date = timezone.now()
        self.save()

    def __str__(self):
        return self.nome
    
    def save(self, *args, **kwargs):
        self.nome = self.nome.upper()
        self.first_name = self.first_name.upper()
        self.last_name = self.last_name.upper()
        if self.avatar:
            # Leia a imagem em bytes
            image_data = self.avatar.read()
            # Converta a imagem em base64
            base64_data = base64.b64encode(image_data).decode('utf-8')
            # Salve a imagem em base64 no campo avatar_base64
            self.avatar_base64 = base64_data

        self.avatar = None
        super(User, self).save(*args, **kwargs)

        if self.avatar:
            os.remove(self.avatar.path)

            # Defina o campo avatar como vazio para garantir que o arquivo não seja salvo novamente
             
class AjustesPesquisa(models.Model):
    nome = models.CharField(max_length=50)
    is_aberta = models.BooleanField(default=False)
    ano_ref = models.IntegerField()

    def __str__(self):
        return self.nome

class StatusCurso(models.Model):
    nome = models.CharField(max_length=50)
    
    def __str__(self):
        return self.nome

class StatusInscricao(models.Model):
    nome = models.CharField(max_length=50)
    
    def __str__(self):
        return self.nome
    
    class Meta:
        verbose_name_plural = "status inscrições"
    

class Competencia(models.Model):
    nome = models.CharField(max_length=400, blank=False, null=False)

    def __str__(self):
        return self.nome
    

class Trilha(models.Model):
    nome = models.CharField(max_length=400, blank=False, null=False)
    ativa = models.BooleanField(default=True, verbose_name = ("Está ativa"))
    competencias = models.ManyToManyField(Competencia)
    cor_circulo = models.CharField(max_length=7, default='#000000')
    ordem_relatorio = models.PositiveSmallIntegerField(blank=True, null=True, verbose_name = ("Ordem no relatório"))
    fundo_tabela = models.CharField(max_length=7, default='#F3F3F3')

    def __str__(self):
        return self.nome

class CursoPriorizado(models.Model):
    FORMA_CHOICES = [
        ('PFC', 'PFC'),
        ('Curadoria', 'Curadoria'),
    ]
    nome_sugestao_acao = models.CharField(max_length=400, blank=False, null=False)
    forma_atendimento = models.CharField(max_length=10, choices=FORMA_CHOICES,  blank=True, null=True)
    mes_competencia = models.DateField()
    trilha = models.ForeignKey(Trilha, on_delete=models.SET_NULL, blank=True, null=True, related_name='cursos_priorizados')

    class Meta:
        verbose_name_plural = "cursos priorizados"
    def __str__(self):
        return f"({self.mes_competencia.strftime('%Y')}) {self.nome_sugestao_acao}"

class InstituicaoPromotora(models.Model):
    nome = models.CharField(max_length=400, blank=False, null=False)
    def __str__(self):
        return self.nome


class InstituicaoCertificadora(models.Model):
    nome = models.CharField(max_length=400, blank=False, null=False)
    def __str__(self):
        return self.nome

class Categoria(models.Model):
    nome = models.CharField(max_length=400, blank=False, null=False)
    def __str__(self):
        return self.nome
    
class Modalidade(models.Model):
    nome = models.CharField(max_length=400, blank=False, null=False)
    def __str__(self):
        return self.nome

class Curso(models.Model):
    TURNO_CHOICES = [
        ('MANHA', 'MANHÃ'),
        ('TARDE', 'TARDE'),
        ('NOITE', 'NOITE'),
    ]
    TURMA_CHOICES = [
        ('TURMA1', 'TURMA 1'),
        ('TURMA2', 'TURMA 2'),
        ('TURMA3', 'TURMA 3'),
        ('TURMA4', 'TURMA 4'),
        ('TURMA5', 'TURMA 5'),
    ]

    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    nome_curso =  models.CharField(max_length=400, blank=False, null=False)
    ementa_curso =  models.TextField(max_length=4000, blank=False, null=False)
    modalidade = models.ForeignKey(Modalidade, on_delete=models.SET_NULL, blank=True, null=True)
    tipo_reconhecimento = models.CharField(max_length=400, blank=True, null=True)
    ch_curso = models.IntegerField(blank=False, null=False)
    vagas = models.IntegerField(blank=False, null=False)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, blank=True, null=True)
    descricao = models.TextField(max_length=4000, default='')
    data_inicio = models.DateField(blank=False, null=False)
    data_termino = models.DateField(blank=True, null=True)
    turno = models.CharField(max_length=10, choices=TURNO_CHOICES, default="TARDE")
    turma = models.CharField(max_length=10, choices=TURMA_CHOICES, default="TURMA1")
    inst_certificadora = models.ForeignKey(InstituicaoCertificadora, on_delete=models.SET_NULL, blank=True, null=True)
    inst_promotora = models.ForeignKey(InstituicaoPromotora, on_delete=models.SET_NULL, blank=True, null=True)
    participantes = models.ManyToManyField(User, through='Inscricao', related_name='curso_participante')
    avaliacoes = models.ManyToManyField(User, through='Avaliacao', related_name='curso_avaliacao')
    avaliacoes_abertas = models.ManyToManyField(User, through='AvaliacaoAberta', related_name='avaliacoes_abertas')
    #acao = models.ForeignKey(Acao, on_delete=models.CASCADE)
    #gestor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    coordenador = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    #history = HistoricalRecords()
    status = models.ForeignKey(StatusCurso, on_delete=models.PROTECT)
    trilha = models.ForeignKey(Trilha, on_delete=models.PROTECT, blank=True, null=True, related_name='cursos')
    periodo_avaliativo = models.BooleanField(default=False)
    eh_evento = models.BooleanField(default=False, verbose_name = ("É evento"))
    observacao = models.TextField(max_length=4000, blank=True, null=True, verbose_name = ("Observação"))
    horario = models.TextField(max_length=400, blank=True, null=True, verbose_name = ("Horário"))
    curso_priorizado = models.ForeignKey(CursoPriorizado, on_delete=models.SET_NULL, blank=True, null=True, related_name='cursos_priorizados')

    def publish(self):
        self.published_date = timezone.now()
        self.save()

    def __str__(self):
        return self.nome_curso
    


class PlanoCurso(models.Model):
    curso = models.OneToOneField(Curso, on_delete=models.CASCADE) 
    publico_alvo = models.TextField(max_length=4000, blank=True, null=True, verbose_name = ("Público-alvo"))
    quantidade_turma = models.SmallIntegerField(blank=True, null=True, verbose_name = ("Quantidade de turmas"))
    pre_requisitos = models.TextField(max_length=4000, blank=True, null=True, verbose_name = ("Pré-requisitos"))
    objetivo_geral = models.TextField(max_length=4000, blank=True, null=True, verbose_name = ("Objetivo geral"))
    objetivo_especifico = models.TextField(max_length=4000, blank=True, null=True, verbose_name = ("Objetivo específico"))
    metodologia_ensino = models.TextField(max_length=4000, blank=True, null=True, verbose_name = ("Metodologia de ensino"))
    metodologia_avaliacao = models.TextField(max_length=4000, blank=True, null=True, verbose_name = ("Metodologia de avaliação"))
    recursos_professor = models.TextField(max_length=4000, blank=True, null=True, verbose_name = ("Recursos professor"))
    recursos_aluno = models.TextField(max_length=4000, blank=True, null=True, verbose_name = ("Recursos aluno"))
    referencia_bibliografica = models.TextField(max_length=4000, blank=True, null=True, verbose_name = ("Referências bibliográficas"))
    criado_em = models.DateField(auto_now_add=True)

    def __str__(self):
        return 'Plano do curso: ' + self.curso.nome_curso
    
    class Meta:
        verbose_name_plural = "planos de curso"
        verbose_name = "plano de curso"

class CronogramaExecucao(models.Model):
    TURNO = [
        ('MANHÃ', 'MANHÃ'),
        ('TARDE', 'TARDE'),
    ]
    plano = models.ForeignKey(PlanoCurso, on_delete=models.CASCADE) 
    aula = models.SmallIntegerField(blank=True, null=True)
    turno = models.CharField(max_length=10, choices=TURNO, blank=True, null=True)
    conteudo = models.TextField(max_length=4000, blank=True, null=True, verbose_name = ("Conteúdo"))
    atividade = models.TextField(max_length=4000, blank=True, null=True, verbose_name = ("Atividades"))

    class Meta:
        verbose_name_plural = "cronogramas de execução"

class Inscricao(models.Model):
    CONDICAO_ACAO_CHOICES = [
        ('DISCENTE', 'DISCENTE'),
        ('DOCENTE', 'DOCENTE'),
    ]
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE)
    participante = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name = ("Usuário"))
    ch_valida = models.IntegerField(blank=True, null=True)
    condicao_na_acao = models.CharField(max_length=400, choices=CONDICAO_ACAO_CHOICES, blank=False, null=False, default="DISCENTE")
    status = models.ForeignKey(StatusInscricao, on_delete=models.PROTECT)
    concluido = models.BooleanField(default=False)
    inscrito_em = models.DateTimeField(auto_now_add=True)#auto_now_add=True,

    class Meta:
        verbose_name_plural = "inscrições"
        unique_together = ('curso', 'participante')

    def __str__(self):
        return f'Curso: {self.curso.nome_curso} >> Participante: {self.participante.nome}'

@receiver(pre_save, sender=Inscricao)
def calcular_carga_horaria(sender, instance, **kwargs):
    instance.ch_valida = instance.curso.ch_curso


notas=(('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5'),('0', 'N/A'))


class Tema(models.Model):
    nome = models.CharField(max_length=100)
    class Meta:
        verbose_name = "Avaliação-Tema"

    def __str__(self):
        return self.nome
    

class Subtema(models.Model):
    nome = models.CharField(max_length=100)
    tema = models.ForeignKey(Tema, on_delete=models.CASCADE)
    cor = models.CharField(max_length=7, default='#FFFFFF')

    def __str__(self):
        return self.nome
    class Meta:
        verbose_name = "Avaliação-Subtema"

class Avaliacao(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE)
    participante = models.ForeignKey(User, on_delete=models.CASCADE)
    
    subtema = models.ForeignKey(Subtema, blank=False, null=False, on_delete=models.CASCADE)
    nota = models.TextField(choices=notas, default=None, blank=False, null=False)
    # conteudo_estrutura_acao_capacitacao = models.TextField(choices=notas, default=None, blank=False, null=False)
    # interface_grafica_acao_capacitacao = models.TextField(choices=notas, default=None, blank=False, null=False)
    # nota_atributo4 = models.TextField(choices=notas, default=None, blank=False, null=False)
    # nota_atributo5 = models.TextField(choices=notas, default=None, blank=False, null=False)
    
    def __str__(self):
        return self.curso.nome_curso + ' > '+ self.participante.username
    
    class Meta:
        verbose_name_plural = "avaliações"


class AvaliacaoAberta(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE)
    participante = models.ForeignKey(User, on_delete=models.CASCADE)
    
    avaliacao = models.TextField(max_length=4000, default=None, blank=True, null=True)
    
    
    def __str__(self):
        return self.curso.nome_curso + ' > '+ self.participante.username
    
    class Meta:
        verbose_name_plural = "avaliações abertas"

def user_directory_path(instance, filename):
    # O "instance" é a instância do modelo Avaliacao e "filename" é o nome do arquivo original
    # Este exemplo adiciona o nome de usuário ao caminho de destino
    return f'uploads/{instance.usuario.username}/{filename}'

class StatusValidacao(models.Model):
    nome = models.CharField(max_length=50)
    
    def __str__(self):
        return self.nome
    
    class Meta:
        verbose_name_plural = "status validações"


class Carreira(models.Model):
    nome = models.CharField(max_length=80)
    sigla = models.CharField(max_length=20)
    def __str__(self):
        return self.nome+f' ({self.sigla})'


class Curadoria(models.Model):
    nome_curso = models.CharField(max_length=100, default='')
    link_inscricao = models.CharField(max_length=200, default='')
    modalidade = models.ForeignKey(Modalidade, on_delete=models.SET_NULL, blank=True, null=True)
    instituicao_promotora = models.ForeignKey(InstituicaoPromotora, on_delete=models.SET_NULL, blank=True, null=True)
    carga_horaria_total = models.IntegerField(blank=True, null=True)
    mes_competencia = models.DateField()
    trilha = models.ForeignKey(Trilha, on_delete=models.SET_NULL, blank=True, null=True, related_name='curadorias')
    permanente = models.BooleanField(default=False)
    curso_priorizado = models.ForeignKey(CursoPriorizado, on_delete=models.SET_NULL, blank=True, null=True, related_name='curadorias_priorizadas')



    def __str__(self):
        nome_curso_abv = ''
        if len(self.nome_curso) > 80:
            nome_curso_abv = self.nome_curso[:35]+' ... '+self.nome_curso[-35:]
        else:
            nome_curso_abv = self.nome_curso

        return str(self.mes_competencia) + ' - ' + nome_curso_abv

class Validacao_CH(models.Model):
    CONDICAO_ACAO_CHOICES = [
        ('DISCENTE', 'DISCENTE'),
        ('DOCENTE', 'DOCENTE'),
    ]
    # try:
    #     status_validacao = StatusValidacao.objects.get(nome="PENDENTE")
    # except:
    #     status_validacao = StatusValidacao.objects.create(nome="PENDENTE")

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='requerente_validacao')
    arquivo_pdf = models.FileField(upload_to=user_directory_path)
    enviado_em = models.DateTimeField(auto_now_add=True)
    nome_curso = models.CharField(max_length=400, default='')
    instituicao_promotora = models.CharField(max_length=200, default='')
    requerimento_ch  = models.ForeignKey("RequerimentoCH", on_delete=models.SET_NULL, blank=True, null=True)
    responsavel_analise = models.ForeignKey(User, on_delete=models.DO_NOTHING, blank=True, null=True, related_name='responsavel_validacao')
    ch_solicitada = models.IntegerField(blank=True, null=True)
    ch_confirmada = models.IntegerField(blank=True, null=True)
    data_termino_curso = models.DateField(blank=False, null=False)
    data_inicio_curso = models.DateField(blank=False, null=False)
    ementa = models.TextField(default='', blank=False, null=False)
    curadoria = models.ForeignKey(Curadoria, on_delete=models.SET_NULL, blank=True, null=True)
    agenda_pfc = models.BooleanField(default=False, blank=False, null=False)
    status = models.ForeignKey(StatusValidacao, on_delete=models.DO_NOTHING)#, default=status_validacao.id)
    condicao_na_acao = models.CharField(max_length=20, choices=CONDICAO_ACAO_CHOICES, blank=False, null=False, default="DISCENTE")
    analisado_em = models.DateField(blank=False, null=False, default=timezone.now)
    carreira = models.ForeignKey(Carreira, on_delete=models.DO_NOTHING, blank=True, null=True)
    trilha = models.ForeignKey(Trilha, on_delete=models.DO_NOTHING, blank=True, null=True)
    competencia = models.ManyToManyField(Competencia)
    conhecimento_previo = models.TextField(choices=notas, blank=False, null=False)
    conhecimento_posterior = models.TextField(choices=notas, blank=False, null=False)
    voce_indicaria = models.TextField(choices=notas, blank=False, null=False)

    def __str__(self):
        return self.usuario.username

    class Meta:
        verbose_name_plural = "validações de CH"


class RequerimentoCH(models.Model):
    codigo = models.CharField(max_length=40, default='')
    do_requerimento = models.TextField(max_length=2000, default='')
    da_fundamentacao = models.TextField(max_length=1000, default='')
    da_conclusao = models.TextField(max_length=1000, default='')
    local_data = models.CharField(max_length=50, default='')
    rodape = models.CharField(max_length=400, default='')
    rodape2 = models.CharField(max_length=400, default='')
    

    def __str__(self):
        return self.codigo

    class Meta:
        verbose_name_plural = "requerimentos"

class Certificado(models.Model):
    codigo = models.CharField(max_length=40, default='')
    cabecalho = models.CharField(max_length=100, default='')
    subcabecalho1 = models.CharField(max_length=100, default='')
    subcabecalho2 = models.CharField(max_length=100, default='')
    texto = models.TextField(max_length=4000, default='')
    assinatura = models.FileField(upload_to='upload/certificado/', blank=True, null=True, default='upload/certificado/')


    def __str__(self):
        return self.codigo

    class Meta:
        verbose_name_plural = "certificados"


class Relatorio(models.Model):
    codigo = models.CharField(max_length=100)

    def __str__(self):
        return self.codigo

    class Meta:
        verbose_name_plural = "relatórios"

class ItemRelatorio(models.Model):
    texto = models.TextField(max_length=4000, blank=True, null=True)
    tema = models.ForeignKey(Tema, on_delete=models.CASCADE)
    relatorio = models.ForeignKey(Relatorio, on_delete=models.CASCADE)

    def __str__(self):
        return self.tema.nome