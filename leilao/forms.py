from datetime import timedelta

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from .models import Auction, Product, validate_image_size


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_clean(item, initial) for item in data]
        else:
            result = [single_clean(data, initial)] if data else []
        if len(result) > 3:
            raise ValidationError("Envie no máximo 3 fotos.")
        for image in result:
            validate_image_size(image)
        return result


class ProductForm(forms.ModelForm):
    DURATION_CHOICES = [
        (1, "1 hora"),
        (6, "6 horas"),
        (12, "12 horas"),
        (24, "1 dia"),
        (48, "2 dias"),
        (72, "3 dias"),
        (168, "7 dias"),
    ]
    duration_hours = forms.TypedChoiceField(
        label="Duração", choices=DURATION_CHOICES, coerce=int, initial=24
    )
    photos = MultipleImageField(
        label="Fotos",
        required=True,
        help_text="Até 3 imagens JPG, PNG ou WebP, com no máximo 10 MB cada.",
    )

    class Meta:
        model = Product
        fields = [
            "auction",
            "title",
            "description",
            "initial_price",
            "reserve_price",
            "increment_type",
            "increment_value",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}
        help_texts = {
            "reserve_price": (
                "Opcional. Sem atingir este valor, o produto termina sem vencedor."
            ),
            "increment_value": (
                "Informe reais para valor fixo ou o percentual para incremento percentual."
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        now = timezone.now()
        self.fields["auction"].queryset = (
            Auction.objects.filter(is_published=True)
            .filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now))
            .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
        )
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def save(self, commit=True):
        product = super().save(commit=False)
        product.starts_at = timezone.now()
        product.ends_at = product.starts_at + timedelta(
            hours=self.cleaned_data["duration_hours"]
        )
        if commit:
            product.save()
        return product

    def clean(self):
        cleaned = super().clean()
        auction = cleaned.get("auction")
        duration = cleaned.get("duration_hours")
        if (
            auction
            and auction.ends_at
            and duration
            and timezone.now() + timedelta(hours=duration) > auction.ends_at
        ):
            self.add_error(
                "duration_hours",
                "A duração ultrapassa o encerramento do leilão selecionado.",
            )
        return cleaned
