from django.contrib.auth import get_user_model
# from django.contrib.admin.views.decorators import staff_member_required
# from django.shortcuts import get_object_or_404, render

# from .models import MensagemTemplate, TagTemplate
# from .render import render_template

User = get_user_model()


# @staff_member_required
# def preview_template(request):
#     templates = MensagemTemplate.objects.filter(ativo=True).order_by("nome")

#     template_id = request.GET.get("template_id") or ""
#     user_id = request.GET.get("user_id") or ""
#     empresa_id = request.GET.get("empresa_id") or ""
#     pedido_id = request.GET.get("pedido_id") or ""

#     selected_template = None
#     output = None
#     context = {}

#     if template_id:
#         selected_template = get_object_or_404(MensagemTemplate, id=template_id)

#     if user_id:
#         context["user"] = get_object_or_404(User, id=user_id)

#     if empresa_id:
#         context["empresa"] = get_object_or_404(Empresa, id=empresa_id)

#     if pedido_id:
#         context["pedido"] = get_object_or_404(Pedido, id=pedido_id)

#     if selected_template:
#         tags = TagTemplate.objects.filter(ativa=True).select_related("content_type")
#         output = render_template(selected_template, context=context, tags_queryset=tags)

#     return render(
#         request,
#         "mensageria/preview_template.html",
#         {
#             "templates": templates,
#             "template_id": template_id,
#             "user_id": user_id,
#             "empresa_id": empresa_id,
#             "pedido_id": pedido_id,
#             "output": output,
#         },
#     )
