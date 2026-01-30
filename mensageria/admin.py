from django import forms
from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
from django.urls import path, reverse

from .models import MensagemTemplate, TagTemplate


# @admin.register(Empresa)
# class EmpresaAdmin(admin.ModelAdmin):
#     list_display = ("id", "nome", "cnpj")
#     search_fields = ("nome", "cnpj")


# @admin.register(Pedido)
# class PedidoAdmin(admin.ModelAdmin):
#     list_display = ("id", "empresa", "cliente_nome", "valor_total", "criado_em")
#     list_filter = ("empresa",)
#     search_fields = ("cliente_nome",)


@admin.register(MensagemTemplate)
class MensagemTemplateAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo")
    search_fields = ("nome", "assunto", "corpo")


class TagTemplateAdminForm(forms.ModelForm):
    help_primeiro_nivel = forms.CharField(
        required=False,
        disabled=True,
        label="Dica (campos do 1º nível)",
    )

    class Meta:
        model = TagTemplate
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        ct_id = None
        if self.instance and self.instance.pk and self.instance.content_type_id:
            ct_id = self.instance.content_type_id

        if self.data.get("content_type"):
            try:
                ct_id = int(self.data.get("content_type"))
            except Exception:
                pass

        dica = "Selecione um model para listar campos do 1º nível."
        if ct_id:
            ct = ContentType.objects.filter(id=ct_id).first()
            model = ct.model_class() if ct else None
            if model:
                names = []
                for f in model._meta.get_fields():
                    name = getattr(f, "name", None)
                    if name and not name.startswith("_"):
                        names.append(name)
                names = sorted(set(names))
                dica = ", ".join(names[:60]) + (" ..." if len(names) > 60 else "")

        self.fields["help_primeiro_nivel"].initial = dica


@admin.register(TagTemplate)
class TagTemplateAdmin(admin.ModelAdmin):
    form = TagTemplateAdminForm

    class Media:
        js = ("mensageria/admin/tagtemplate_dynamic_help.js",)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "fields-help/",
                self.admin_site.admin_view(self.fields_help_view),
                name="mensageria_tagtemplate_fields_help",
            )
        ]
        return custom + urls

    def fields_help_view(self, request):
        ct_id = request.GET.get("ct_id")
        if not ct_id:
            return JsonResponse(
                {"help": "Selecione um model para listar campos do 1º nível."}
            )

        ct = ContentType.objects.filter(id=ct_id).first()
        model = ct.model_class() if ct else None
        if not model:
            return JsonResponse({"help": "Model inválido."})

        names = []
        for f in model._meta.get_fields():
            name = getattr(f, "name", None)
            if name and not name.startswith("_"):
                names.append(name)

        names = sorted(set(names))
        help_text = ", ".join(names[:80]) + (" ..." if len(names) > 80 else "")
        return JsonResponse({"help": help_text or "Nenhum campo encontrado."})

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # injeta URL absoluta do endpoint no <select id="id_content_type">
        form.base_fields["content_type"].widget.attrs["data-fields-help-url"] = reverse(
            "admin:mensageria_tagtemplate_fields_help"
        )
        return form
