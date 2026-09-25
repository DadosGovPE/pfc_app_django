from django import forms
from django.core.exceptions import ValidationError

from .models import Comment, Product, validate_image_size


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        images = data if isinstance(data, (list, tuple)) else ([data] if data else [])
        if not images and not self.required:
            return []
        if not 1 <= len(images) <= 3:
            raise ValidationError("Envie de 1 a 3 fotos.")
        result = [super(MultipleImageField, self).clean(image, initial) for image in images]
        for image in result:
            validate_image_size(image)
            if image.content_type not in ("image/jpeg", "image/png", "image/webp"):
                raise ValidationError("Use fotos JPG, PNG ou WebP.")
        return result


class ProductForm(forms.ModelForm):
    photos = MultipleImageField(
        label="Fotos", required=True,
        help_text="Envie de 1 a 3 fotos JPG, PNG ou WebP (até 10 MB cada).",
        widget=MultipleFileInput(attrs={"accept": "image/jpeg,image/png,image/webp", "multiple": True}),
    )

    class Meta:
        model = Product
        fields = ["title", "description", "price"]
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}
        help_texts = {"price": "O contato com o anunciante acontece nos comentários públicos."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class EditProductForm(ProductForm):
    photos = MultipleImageField(
        label="Substituir fotos", required=False,
        help_text="Opcional. Se enviar novas fotos, elas substituirão todas as atuais (1 a 3 imagens).",
        widget=MultipleFileInput(attrs={"accept": "image/jpeg,image/png,image/webp", "multiple": True}),
    )


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["text"]
        widgets = {"text": forms.Textarea(attrs={"rows": 3, "placeholder": "Escreva um comentário público...", "class": "form-control"})}
