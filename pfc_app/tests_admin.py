from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from pfc_app.admin import InscricaoAdmin, InscricaoAdminForm
from pfc_app.models import Inscricao


class InscricaoAdminFormTests(SimpleTestCase):
    def _clean_form(self, *, status, concluido):
        form = InscricaoAdminForm()
        form.cleaned_data = {
            "status": SimpleNamespace(nome=status),
            "concluido": concluido,
        }
        return form.clean()

    def test_permite_concluir_inscricao_aprovada(self):
        cleaned_data = self._clean_form(status="APROVADA", concluido=True)

        self.assertTrue(cleaned_data["concluido"])

    def test_impede_concluir_inscricao_nao_aprovada(self):
        with self.assertRaisesMessage(
            ValidationError,
            "A inscrição só pode ser concluída quando o status for APROVADA.",
        ):
            self._clean_form(status="PENDENTE", concluido=True)

    def test_permite_manter_inscricao_nao_aprovada_sem_conclusao(self):
        cleaned_data = self._clean_form(status="PENDENTE", concluido=False)

        self.assertFalse(cleaned_data["concluido"])

    def test_regra_tambem_e_usada_na_edicao_em_massa(self):
        model_admin = InscricaoAdmin(Inscricao, AdminSite())
        status = SimpleNamespace(pk=1, nome="APROVADA")

        with patch("pfc_app.admin.StatusInscricao.objects.only", return_value=[status]):
            changelist_form = model_admin.get_changelist_form(request=None)

        self.assertTrue(issubclass(changelist_form, InscricaoAdminForm))
        status_field = changelist_form.base_fields["status"]
        self.assertIs(status_field.clean("1"), status)
        self.assertFalse(status_field.has_changed(status, "1"))
