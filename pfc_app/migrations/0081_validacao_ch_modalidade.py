# Generated by Django 4.2.14 on 2024-07-19 13:29

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('pfc_app', '0080_user_pfc_app_use_nome_7b6aa4_idx'),
    ]

    operations = [
        migrations.AddField(
            model_name='validacao_ch',
            name='modalidade',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='pfc_app.modalidade'),
        ),
    ]