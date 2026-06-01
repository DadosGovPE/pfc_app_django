# Generated manually for the admin e-mail status batch feature.

import django.db.models.deletion
import mensageria.models
from django.conf import settings
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("mensageria", "0001_initial"),
        ("pfc_app", "0106_alter_pesquisacursospriorizados_ano_ref_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailStatusBatch",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "job_id",
                    models.CharField(
                        default=mensageria.models._generate_job_id,
                        editable=False,
                        max_length=32,
                        unique=True,
                    ),
                ),
                ("enviar_email", models.BooleanField(default=False)),
                ("assunto", models.CharField(blank=True, max_length=200)),
                ("corpo", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Na fila"),
                            ("running", "Processando"),
                            ("completed", "Concluido"),
                            ("failed", "Falhou"),
                        ],
                        default="queued",
                        max_length=20,
                    ),
                ),
                ("current_step", models.CharField(blank=True, max_length=120)),
                ("total_selecionado", models.PositiveIntegerField(default=0)),
                ("total_alterado", models.PositiveIntegerField(default=0)),
                ("total_ignorado", models.PositiveIntegerField(default=0)),
                ("total_enviado", models.PositiveIntegerField(default=0)),
                ("total_sem_email", models.PositiveIntegerField(default=0)),
                ("total_falha", models.PositiveIntegerField(default=0)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "admin",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="email_status_batches",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "curso",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="email_status_batches",
                        to="pfc_app.curso",
                    ),
                ),
                (
                    "status_destino",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="email_status_batches",
                        to="pfc_app.statusinscricao",
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="email_status_batches",
                        to="mensageria.mensagemtemplate",
                    ),
                ),
            ],
            options={
                "verbose_name": "lote de e-mails por status",
                "verbose_name_plural": "lotes de e-mails por status",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="EmailStatusBatchItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("email", models.EmailField(blank=True, max_length=254)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pendente"),
                            ("sent", "Enviado"),
                            ("no_email", "Sem e-mail"),
                            ("failed", "Falhou"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("error_message", models.TextField(blank=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                (
                    "batch",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="mensageria.emailstatusbatch",
                    ),
                ),
                (
                    "inscricao",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="email_status_items",
                        to="pfc_app.inscricao",
                    ),
                ),
                (
                    "participante",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="email_status_items",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "status_origem",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="email_status_items_origem",
                        to="pfc_app.statusinscricao",
                    ),
                ),
            ],
            options={
                "verbose_name": "item do lote de e-mails por status",
                "verbose_name_plural": "itens do lote de e-mails por status",
                "ordering": ["id"],
            },
        ),
    ]
