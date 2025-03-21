# Generated by Django 4.2.14 on 2025-03-18 17:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pfc_app', '0098_remove_subtema_evento_tema_evento'),
    ]

    operations = [
        migrations.AddField(
            model_name='validacao_ch',
            name='ano',
            field=models.IntegerField(blank=True, default=2025, null=True),
        ),
        migrations.AddField(
            model_name='validacao_ch',
            name='numero_sequencial',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterUniqueTogether(
            name='validacao_ch',
            unique_together={('ano', 'numero_sequencial')},
        ),
    ]
