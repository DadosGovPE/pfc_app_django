# Generated by Django 4.2.4 on 2024-07-11 17:18

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('pfc_app', '0070_certificado_assinatura'),
    ]

    operations = [
        migrations.CreateModel(
            name='CursoPriorizado',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome_sugestão_acao', models.CharField(max_length=400)),
                ('forma_atendimento', models.CharField(blank=True, choices=[('PFC', 'PFC'), ('Curadoria', 'Curadoria')], max_length=10, null=True)),
                ('mes_competencia', models.DateField()),
                ('trilha', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cursos_priorizados', to='pfc_app.trilha')),
            ],
        ),
    ]