# Generated by Django 4.2.14 on 2024-12-17 15:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pfc_app', '0095_usercadastro_alter_historicaluser_is_ativo_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='usercadastro',
            name='data_solicitacao',
            field=models.DateField(auto_now_add=True),
        ),
    ]