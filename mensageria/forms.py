from django import forms

from mensageria.models import MensagemTemplate
from pfc_app.models import Curso, StatusInscricao


class EnvioEmailCursoStatusForm(forms.Form):
    curso = forms.ModelChoiceField(
        queryset=Curso.objects.all().order_by("nome_curso"),
        label="Curso",
    )
    template = forms.ModelChoiceField(
        queryset=MensagemTemplate.objects.filter(ativo=True).order_by("nome"),
        label="Modelo de mensagem",
    )
    status = forms.ModelChoiceField(
        queryset=StatusInscricao.objects.all().order_by("nome"),
        label="Status da inscrição",
    )

    dry_run = forms.BooleanField(
        required=False,
        initial=False,
        label="Dry-run (não enviar)",
        help_text="Se marcado, não envia; apenas informa quantos seriam enviados.",
    )
    limite = forms.IntegerField(
        required=False,
        min_value=1,
        label="Limite (opcional)",
        help_text="Opcional: limita a quantidade de envios para teste (ex.: 5).",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "dry_run":
                field.widget.attrs.update({"class": "form-check-input"})
            else:
                field.widget.attrs.update({"class": "form-control"})
