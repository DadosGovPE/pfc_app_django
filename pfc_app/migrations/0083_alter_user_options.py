# Generated by Django 4.2.14 on 2024-07-24 14:52

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('pfc_app', '0082_alter_user_pesquisa_cursos_priorizados'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='user',
            options={'ordering': ['nome'], 'verbose_name_plural': 'Usuários'},
        ),
    ]