# Generated by Django 4.2.14 on 2024-07-18 19:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pfc_app', '0079_alter_curso_options'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='user',
            index=models.Index(fields=['nome'], name='pfc_app_use_nome_7b6aa4_idx'),
        ),
    ]