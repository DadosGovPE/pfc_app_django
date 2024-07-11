# Generated by Django 4.2.4 on 2024-07-11 17:22

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('pfc_app', '0071_cursopriorizado'),
    ]

    operations = [
        migrations.AddField(
            model_name='curadoria',
            name='curso_priorizado',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='curadorias_priorizadas', to='pfc_app.cursopriorizado'),
        ),
        migrations.AddField(
            model_name='curso',
            name='curso_priorizado',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cursos_priorizados', to='pfc_app.cursopriorizado'),
        ),
    ]
