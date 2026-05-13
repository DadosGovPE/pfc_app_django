from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class CursoConcluidoMoodle(models.Model):
    usuario_pfc = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="cursos_moodle",
    )
    usuario_moodle_id = models.IntegerField()
    curso_moodle_id = models.IntegerField()
    nome_curso = models.CharField(max_length=255)
    carga_horaria = models.CharField(max_length=50)
    data_conclusao = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("usuario_pfc", "curso_moodle_id")

    def __str__(self):
        return f"{self.usuario_pfc} - {self.nome_curso}"


class CursoCompletoUsuario(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="cursos_moodle_completos",
    )
    id_curso_moodle = models.IntegerField()
    carga_horaria_curso_moodle = models.CharField(max_length=50)
    data_inicio_curso_moodle = models.DateTimeField(null=True, blank=True)
    data_fim_curso_moodle = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "id_curso_moodle")
        ordering = ("-data_fim_curso_moodle", "-id")

    def __str__(self):
        return f"{self.user} - curso {self.id_curso_moodle}"


NOTAS_AVALIACAO = (
    ("1", "1"),
    ("2", "2"),
    ("3", "3"),
    ("4", "4"),
    ("5", "5"),
    ("0", "N/A"),
)


class AvaliacaoMoodle(models.Model):
    curso_moodle = models.ForeignKey(
        CursoConcluidoMoodle,
        on_delete=models.CASCADE,
        related_name="avaliacoes",
    )
    participante = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="avaliacoes_moodle",
    )
    subtema = models.ForeignKey(
        "pfc_app.Subtema",
        on_delete=models.CASCADE,
        related_name="avaliacoes_moodle",
    )
    nota = models.TextField(choices=NOTAS_AVALIACAO, default=None)

    class Meta:
        verbose_name = "avaliacao Moodle"
        verbose_name_plural = "avaliacoes Moodle"
        unique_together = ("curso_moodle", "participante", "subtema")
        indexes = [
            models.Index(fields=["curso_moodle", "participante"]),
        ]

    def __str__(self):
        return f"{self.curso_moodle.nome_curso} > {self.participante.username}"


class AvaliacaoAbertaMoodle(models.Model):
    curso_moodle = models.ForeignKey(
        CursoConcluidoMoodle,
        on_delete=models.CASCADE,
        related_name="avaliacoes_abertas",
    )
    participante = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="avaliacoes_abertas_moodle",
    )
    avaliacao = models.TextField(max_length=4000, default=None, blank=True, null=True)

    class Meta:
        verbose_name = "avaliacao aberta Moodle"
        verbose_name_plural = "avaliacoes abertas Moodle"
        unique_together = ("curso_moodle", "participante")
        indexes = [
            models.Index(fields=["curso_moodle", "participante"]),
        ]

    def __str__(self):
        return f"{self.curso_moodle.nome_curso} > {self.participante.username}"
