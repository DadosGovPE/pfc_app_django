# Generated by Django 4.2.14 on 2024-08-09 14:16

from django.db import migrations, models
import django.db.models.deletion
import pfc_app.models


class Migration(migrations.Migration):

    dependencies = [
        ('pfc_app', '0090_alter_ajusteshoraaula_options_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ArquivoCurso',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('arquivo', models.FileField(upload_to=pfc_app.models.curso_arquivo_upload_path)),
                ('descricao', models.CharField(blank=True, max_length=400, null=True)),
                ('curso', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='arquivos', to='pfc_app.curso')),
            ],
        ),
    ]
