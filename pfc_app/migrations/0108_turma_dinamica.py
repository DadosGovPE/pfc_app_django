from django.db import migrations, models
import django.db.models.deletion
import pfc_app.models


def vincular_turmas(apps, schema_editor):
    Turma = apps.get_model("pfc_app", "Turma")
    Curso = apps.get_model("pfc_app", "Curso")
    alias = schema_editor.connection.alias
    for numero in range(1, 11):
        Turma.objects.using(alias).get_or_create(
            codigo=f"TURMA{numero}",
            defaults={"nome": f"TURMA {numero}", "ordem": numero},
        )
    for codigo in Curso.objects.using(alias).order_by().values_list("turma", flat=True).distinct():
        turma, _ = Turma.objects.using(alias).get_or_create(
            codigo=codigo, defaults={"nome": codigo, "ordem": 0}
        )
        Curso.objects.using(alias).filter(turma=codigo).update(turma_ref_id=turma.pk)


def restaurar_codigos(apps, schema_editor):
    Turma = apps.get_model("pfc_app", "Turma")
    Curso = apps.get_model("pfc_app", "Curso")
    alias = schema_editor.connection.alias
    for turma in Turma.objects.using(alias).all():
        codigo = turma.codigo or turma.nome
        cursos = Curso.objects.using(alias).filter(turma_ref_id=turma.pk)
        if cursos.exists() and len(codigo) > 10:
            raise ValueError("Uma turma nova excede o limite antigo de 10 caracteres; ajuste antes de reverter.")
        cursos.update(turma=codigo)


class Migration(migrations.Migration):
    dependencies = [("pfc_app", "0107_normaliza_instituicao_promotora_enap")]

    operations = [
        migrations.CreateModel(
            name="Turma",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=100, unique=True)),
                ("ordem", models.PositiveIntegerField(default=0)),
                ("codigo", models.CharField(blank=True, editable=False, max_length=100, null=True, unique=True)),
            ],
            options={"ordering": ["ordem", "nome"]},
        ),
        migrations.AddConstraint(
            model_name="turma",
            constraint=models.UniqueConstraint(
                models.functions.Lower(models.functions.Trim("nome")),
                name="turma_nome_normalizado_unico",
            ),
        ),
        migrations.AddConstraint(
            model_name="turma",
            constraint=models.CheckConstraint(check=~models.Q(nome=""), name="turma_nome_nao_vazio"),
        ),
        migrations.AddField(
            model_name="curso", name="turma_ref",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to="pfc_app.turma"),
        ),
        migrations.RunPython(vincular_turmas, restaurar_codigos),
        migrations.RemoveField(model_name="curso", name="turma"),
        migrations.RenameField(model_name="curso", old_name="turma_ref", new_name="turma"),
        migrations.AlterField(
            model_name="curso", name="turma",
            field=models.ForeignKey(default=pfc_app.models.turma_padrao_id, on_delete=django.db.models.deletion.PROTECT, related_name="cursos", to="pfc_app.turma"),
        ),
    ]
