from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.conf import settings
from django.db import models
from django.utils import timezone
from uuid import uuid4

TAG_NAME_RE = r"^[a-z][a-z0-9_]*$"


# class Empresa(models.Model):
#     nome = models.CharField(max_length=120)
#     cnpj = models.CharField(max_length=20, blank=True, default="")

#     def __str__(self):
#         return self.nome


# class Pedido(models.Model):
#     empresa = models.ForeignKey(
#         Empresa, on_delete=models.CASCADE, related_name="pedidos"
#     )
#     cliente_nome = models.CharField(max_length=120)
#     valor_total = models.DecimalField(max_digits=12, decimal_places=2)
#     criado_em = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"Pedido #{self.id} - {self.cliente_nome}"


class MensagemTemplate(models.Model):
    nome = models.CharField(max_length=120, unique=True)
    assunto = models.CharField(max_length=200)
    corpo = models.TextField(
        help_text="Use tags no formato [pedido_empresa_nome], [user_email], etc."
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


def _generate_job_id() -> str:
    return uuid4().hex


class EmailStatusBatch(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Na fila"
        RUNNING = "running", "Processando"
        COMPLETED = "completed", "Concluido"
        FAILED = "failed", "Falhou"

    job_id = models.CharField(
        max_length=32, unique=True, default=_generate_job_id, editable=False
    )
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="email_status_batches",
    )
    curso = models.ForeignKey(
        "pfc_app.Curso",
        on_delete=models.CASCADE,
        related_name="email_status_batches",
    )
    status_destino = models.ForeignKey(
        "pfc_app.StatusInscricao",
        on_delete=models.PROTECT,
        related_name="email_status_batches",
    )
    template = models.ForeignKey(
        MensagemTemplate,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="email_status_batches",
    )
    enviar_email = models.BooleanField(default=False)
    assunto = models.CharField(max_length=200, blank=True)
    corpo = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.QUEUED
    )
    current_step = models.CharField(max_length=120, blank=True)
    total_selecionado = models.PositiveIntegerField(default=0)
    total_alterado = models.PositiveIntegerField(default=0)
    total_ignorado = models.PositiveIntegerField(default=0)
    total_enviado = models.PositiveIntegerField(default=0)
    total_sem_email = models.PositiveIntegerField(default=0)
    total_falha = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "lote de e-mails por status"
        verbose_name_plural = "lotes de e-mails por status"

    @property
    def is_processing(self):
        return self.status in {self.Status.QUEUED, self.Status.RUNNING}

    def __str__(self):
        return f"{self.job_id} - {self.get_status_display()}"


class EmailStatusBatchItem(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        SENT = "sent", "Enviado"
        NO_EMAIL = "no_email", "Sem e-mail"
        FAILED = "failed", "Falhou"

    batch = models.ForeignKey(
        EmailStatusBatch, on_delete=models.CASCADE, related_name="items"
    )
    inscricao = models.ForeignKey(
        "pfc_app.Inscricao",
        on_delete=models.CASCADE,
        related_name="email_status_items",
    )
    participante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="email_status_items",
    )
    status_origem = models.ForeignKey(
        "pfc_app.StatusInscricao",
        on_delete=models.PROTECT,
        related_name="email_status_items_origem",
    )
    email = models.EmailField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["id"]
        verbose_name = "item do lote de e-mails por status"
        verbose_name_plural = "itens do lote de e-mails por status"

    def __str__(self):
        return f"{self.batch.job_id} - {self.participante}"


class TagTemplate(models.Model):
    nome = models.CharField(
        max_length=64,
        unique=True,
        validators=[
            RegexValidator(TAG_NAME_RE, "Use snake_case: ex. pedido_empresa_nome")
        ],
        help_text="Nome sem colchetes. Ex: pedido_empresa_nome para usar como [pedido_empresa_nome].",
    )

    contexto_alias = models.CharField(
        max_length=40,
        help_text="Chave do contexto: ex. user, pedido, empresa.",
    )

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        help_text="Model do objeto raiz esperado para este contexto_alias.",
    )

    path = models.CharField(
        max_length=300,
        help_text="Caminho com '.' (profundidade livre). Ex: empresa.nome ou perfil.endereco.cidade",
    )

    padrao = models.CharField(max_length=200, blank=True, default="")
    ativa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return f"[{self.nome}] => {self.contexto_alias}.{self.path}"

    def clean(self):
        super().clean()

        parts = [p.strip() for p in (self.path or "").split(".") if p.strip()]
        if not parts:
            raise ValidationError(
                {"path": "Informe um path válido. Ex: nome ou empresa.nome"}
            )

        for p in parts:
            if "__" in p:
                raise ValidationError({"path": "Não use '__' no path."})
            if p.startswith("_"):
                raise ValidationError(
                    {"path": "Não use atributos iniciados com '_' no path."}
                )

        model = self.content_type.model_class() if self.content_type_id else None
        if model:
            # valida só o 1º nível se for campo; properties/métodos podem passar
            try:
                model._meta.get_field(parts[0])
            except Exception:
                pass
