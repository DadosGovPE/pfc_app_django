from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("pfc_app", "0108_turma_dinamica")]

    operations = [
        migrations.CreateModel(
            name="PainelAvaliacoes",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("publicado", models.JSONField(default=dict)),
                ("rascunho", models.JSONField(blank=True, null=True)),
                ("classificacoes", models.JSONField(default=dict)),
                ("atualizado_em", models.DateTimeField(blank=True, null=True)),
            ],
        ),
    ]
