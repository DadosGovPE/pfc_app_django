from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from pfc_app.admin import InscricaoAdmin, InscricaoAdminForm
from pfc_app.models import Curso, Inscricao, StatusCurso, StatusInscricao, User


class InscricaoAdminFormTests(SimpleTestCase):
    def _clean_inscricao(self, *, status, concluido):
        inscricao = Inscricao(
            status=StatusInscricao(id=1, nome=status),
            concluido=concluido,
        )
        inscricao.clean()
        return inscricao

    def test_permite_concluir_inscricao_aprovada(self):
        inscricao = self._clean_inscricao(status="APROVADA", concluido=True)

        self.assertTrue(inscricao.concluido)

    def test_impede_concluir_inscricao_nao_aprovada(self):
        with self.assertRaisesMessage(
            ValidationError,
            Inscricao.ERRO_STATUS_CONCLUSAO,
        ):
            self._clean_inscricao(status="PENDENTE", concluido=True)

    def test_permite_manter_inscricao_nao_aprovada_sem_conclusao(self):
        inscricao = self._clean_inscricao(status="PENDENTE", concluido=False)

        self.assertFalse(inscricao.concluido)

    def test_regra_tambem_e_usada_na_edicao_em_massa(self):
        model_admin = InscricaoAdmin(Inscricao, AdminSite())
        status = SimpleNamespace(pk=1, nome="APROVADA")

        with patch("pfc_app.admin.StatusInscricao.objects.only", return_value=[status]):
            changelist_form = model_admin.get_changelist_form(request=None)

        self.assertTrue(issubclass(changelist_form, InscricaoAdminForm))
        status_field = changelist_form.base_fields["status"]
        self.assertIs(status_field.clean("1"), status)
        self.assertFalse(status_field.has_changed(status, "1"))


class InscricaoAdminIntegrationTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username="admin",
            cpf="00000000001",
            nome="Admin",
            email="admin@example.com",
            password="123",
        )
        self.participante = User.objects.create_user(
            username="participante",
            cpf="00000000002",
            nome="Participante",
            email="participante@example.com",
            password="123",
        )
        self.status_curso = StatusCurso.objects.create(nome="A INICIAR")
        self.status_pendente = StatusInscricao.objects.create(nome="PENDENTE")
        self.curso = Curso.objects.create(
            nome_curso="Curso Teste",
            ementa_curso="Ementa",
            ch_curso=8,
            vagas=20,
            data_inicio="2026-01-10",
            status=self.status_curso,
        )
        self.inscricao = Inscricao.objects.create(
            curso=self.curso,
            participante=self.participante,
            status=self.status_pendente,
        )
        self.client = Client()
        self.client.force_login(self.admin_user)

    def test_edicao_em_massa_exibe_detalhe_e_nao_salva_conclusao(self):
        response = self.client.post(
            reverse("admin:pfc_app_inscricao_changelist"),
            {
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "1",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-id": str(self.inscricao.pk),
                "form-0-condicao_na_acao": "DISCENTE",
                "form-0-status": str(self.status_pendente.pk),
                "form-0-concluido": "on",
                "_save": "Salvar",
            },
        )

        self.inscricao.refresh_from_db()
        self.assertFalse(self.inscricao.concluido)
        self.assertContains(response, "Nenhuma alteração desta página foi salva")
        self.assertContains(response, Inscricao.ERRO_STATUS_CONCLUSAO)
        self.assertContains(response, "PARTICIPANTE")
        form = response.context["cl"].formset.forms[0]
        self.assertFalse(form["concluido"].value())

    def test_modelo_tambem_impede_gravacao_invalida(self):
        self.inscricao.concluido = True

        with self.assertRaisesMessage(ValidationError, Inscricao.ERRO_STATUS_CONCLUSAO):
            self.inscricao.save()

        self.inscricao.refresh_from_db()
        self.assertFalse(self.inscricao.concluido)
