from django.db import models
from django.conf import settings

class Pesquisa(models.Model):
    titulo = models.CharField(max_length=200)
    data_inicio = models.DateField()
    data_fim = models.DateField()
    is_aberta = models.BooleanField(default=False)

    def __str__(self):
        return self.titulo

class GrupoPerguntas(models.Model):
    pesquisa = models.ForeignKey(Pesquisa, on_delete=models.CASCADE, related_name='grupos')
    titulo = models.CharField(max_length=255)

    def __str__(self):
        return self.titulo

class Pergunta(models.Model):
    TIPO_CHOICES = (
        ('RADIO', 'Nota (1-5)'),
        ('TEXTO', 'Texto aberto'),
    )
    pesquisa = models.ForeignKey(Pesquisa, on_delete=models.CASCADE, related_name='perguntas')
    grupo = models.ForeignKey(GrupoPerguntas, on_delete=models.SET_NULL, null=True, blank=True, related_name='perguntas')
    texto = models.TextField()
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)

    def __str__(self):
        return self.texto


class Resposta(models.Model):
    pergunta = models.ForeignKey(Pergunta, on_delete=models.CASCADE, related_name='respostas')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    resposta_texto = models.TextField(blank=True, null=True)
    resposta_numero = models.IntegerField(blank=True, null=True)

    class Meta:
        unique_together = ('pergunta', 'usuario')


