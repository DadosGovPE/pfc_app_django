# Generated by Django 4.2.4 on 2024-03-25 12:58

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('pfc_app', '0057_alter_planocurso_options_curso_horario'),
    ]

    operations = [
        migrations.CreateModel(
            name='Relatorio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(max_length=100)),
            ],
            options={
                'verbose_name_plural': 'relatórios',
            },
        ),
        migrations.AlterField(
            model_name='validacao_ch',
            name='competencia',
            field=models.ManyToManyField(to='pfc_app.competencia'),
        ),
        migrations.CreateModel(
            name='ItemRelatorio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('texto', models.TextField(blank=True, max_length=4000, null=True)),
                ('relatorio', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='pfc_app.relatorio')),
                ('subtema', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='pfc_app.subtema')),
            ],
        ),
    ]