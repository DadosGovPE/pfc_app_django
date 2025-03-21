# Generated by Django 4.2.14 on 2024-11-22 18:35

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('pfc_app', '0093_curso_is_externo_curso_material_curso'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicaluser',
            name='carreira',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='pfc_app.carreira'),
        ),
        migrations.AddField(
            model_name='user',
            name='carreira',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='pfc_app.carreira'),
        ),
    ]
