from django.db import migrations


def normalizar_enap(apps, schema_editor):
    InstituicaoPromotora = apps.get_model("pfc_app", "InstituicaoPromotora")
    Curadoria = apps.get_model("pfc_app", "Curadoria")
    Curso = apps.get_model("pfc_app", "Curso")
    db = schema_editor.connection.alias

    antigas = InstituicaoPromotora.objects.using(db).filter(nome="EVG/ENAP")
    if not antigas.exists():
        return

    destino = (
        InstituicaoPromotora.objects.using(db)
        .filter(nome="ENAP")
        .order_by("pk")
        .first()
    )
    if destino is None:
        destino = antigas.order_by("pk").first()
        destino.nome = "ENAP"
        destino.save(using=db, update_fields=["nome"])

    for antiga in antigas.exclude(pk=destino.pk).iterator():
        Curadoria.objects.using(db).filter(instituicao_promotora_id=antiga.pk).update(
            instituicao_promotora_id=destino.pk
        )
        Curso.objects.using(db).filter(inst_promotora_id=antiga.pk).update(
            inst_promotora_id=destino.pk
        )
        antiga.delete(using=db)


class Migration(migrations.Migration):
    dependencies = [
        ("pfc_app", "0106_alter_pesquisacursospriorizados_ano_ref_and_more"),
    ]

    operations = [
        migrations.RunPython(normalizar_enap, migrations.RunPython.noop),
    ]
