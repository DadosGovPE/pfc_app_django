# Generated by Django 4.2.14 on 2024-07-26 17:39

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('pfc_app', '0083_alter_user_options'),
    ]

    operations = [
        migrations.CreateModel(
            name='Lotacao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='LotacaoEspecifica',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=255)),
                ('sigla', models.CharField(max_length=30)),
                ('lotacao', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='especificacoes', to='pfc_app.lotacao')),
            ],
        ),
        migrations.AddField(
            model_name='user',
            name='lotacao_especifica_fk',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='users_especifica', to='pfc_app.lotacaoespecifica'),
        ),
        migrations.AddField(
            model_name='user',
            name='lotacao_fk',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='users', to='pfc_app.lotacao'),
        ),
    ]
