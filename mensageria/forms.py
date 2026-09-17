from django import forms

from mensageria.attachments import validate_email_attachments
from mensageria.models import MensagemTemplate
from pfc_app.models import Curso, StatusInscricao


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        files = data if isinstance(data, (list, tuple)) else [data]
        cleaned_files = [
            super(MultipleFileField, self).clean(file, initial) for file in files
        ]
        return validate_email_attachments(cleaned_files)


class EnvioEmailCursoStatusForm(forms.Form):
    curso = forms.ModelChoiceField(
        queryset=Curso.objects.all().order_by("-data_inicio", "nome_curso", "pk"),
        label="Curso",
    )
    template = forms.ModelChoiceField(
        queryset=MensagemTemplate.objects.filter(ativo=True).order_by("nome"),
        label="Modelo de mensagem",
    )
    status = forms.ModelChoiceField(
        queryset=StatusInscricao.objects.all().order_by("nome"),
        label="Status da inscrição",
        required=False,
        empty_label="(Todos)",
    )
    concluido = forms.ChoiceField(
        label="Inscrição concluída?",
        choices=[
            ("", "(Todos)"),
            ("1", "Sim (somente concluídas)"),
            ("0", "Não (somente não concluídas)"),
        ],
        required=False,
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
    anexos = MultipleFileField(
        required=False,
        label="Anexos",
        help_text="Até 10 arquivos, com no máximo 10 MB cada e 20 MB no total.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "dry_run":
                field.widget.attrs.update({"class": "form-check-input"})
            else:
                field.widget.attrs.update({"class": "form-control"})
