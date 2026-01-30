from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

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
