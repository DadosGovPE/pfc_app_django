# Generated by Django 4.2.14 on 2024-11-08 17:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pfc_app', '0092_alter_curso_horario'),
    ]

    operations = [
        migrations.AddField(
            model_name='curso',
            name='is_externo',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='curso',
            name='material_curso',
            field=models.CharField(blank=True, max_length=400, null=True),
        ),
    ]