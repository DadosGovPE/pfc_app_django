# Generated by Django 4.2.14 on 2024-08-06 17:54

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('pfc_app', '0088_historicaluser'),
    ]

    operations = [
        migrations.CreateModel(
            name='AjustesHoraAula',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('valor_instrutor_primario', models.PositiveSmallIntegerField()),
                ('valor_instrutor_secundário', models.PositiveSmallIntegerField()),
                ('valor_instrutor_coordenador', models.PositiveSmallIntegerField()),
                ('ano_mes_referencia', models.DateField()),
            ],
        ),
        migrations.CreateModel(
            name='OrigemPagamento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=400)),
            ],
        ),
        migrations.AddField(
            model_name='curso',
            name='origem_pagamento',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cursos_origem', to='pfc_app.origempagamento'),
        ),
    ]
