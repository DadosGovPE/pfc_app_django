from django import forms
from .models import Avaliacao, Subtema, User  # Certifique-se de importar o modelo Avaliacao
from django.forms import FileInput


CHOICES=[('1','1'),
         ('2','2'),
         ('3','3'),
         ('4','4'),
         ('5','5'),
         ('0','N/A'),
         ]
class AvaliacaoForm(forms.ModelForm):
    
    class Meta:
        model = Avaliacao
        fields = '__all__'  # Use todos os campos do modelo Avaliacao
        # widgets = {
        #     'nota_atributo1': forms.RadioSelect(),
        #     'nota_atributo2': forms.RadioSelect(),
        #     'nota_atributo3': forms.RadioSelect(),
        #     'nota_atributo4': forms.RadioSelect(),
        #     'nota_atributo5': forms.RadioSelect()
        # }
        #choices=CHOICES
        exclude = ['curso', 'participante']

    def __init__(self, *args, **kwargs):
        super(AvaliacaoForm, self).__init__(*args, **kwargs)

        # Personalize os widgets para usar classes do Bootstrap
        #for field_name, field in self.fields.items():
         #   field.widget.attrs['class'] = 'form-control'

class DateFilterForm(forms.Form):
    data_inicio = forms.DateField(label='Data de Início', required=False, widget=forms.TextInput(attrs={'type': 'date'}))
    data_fim = forms.DateField(label='Data de Fim', required=False, widget=forms.TextInput(attrs={'type': 'date'}))

class SubtemaForm(forms.ModelForm):
    class Meta:
        model = Subtema
        fields = ['nome', 'tema', 'cor']  # Inclui apenas o campo que você deseja modificar
        widgets = {
            'cor': forms.TextInput(attrs={'type': 'color'}),
        }

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'telefone', 'avatar']
        widgets = {
            'avatar': forms.ClearableFileInput(attrs={'class': 'form-control-file'})
        }

    telefone = forms.CharField(required=False, max_length=40, label='Telefone')

class UsuarioForm(forms.ModelForm):
 
    class Meta:
        model = User
        fields = '__all__'
        widgets = {
            'lotacao_fk': forms.Select(attrs={'class': 'custom-select'}),
            'lotacao_especifica_fk': forms.Select(attrs={'class': 'custom-select'}),
        }