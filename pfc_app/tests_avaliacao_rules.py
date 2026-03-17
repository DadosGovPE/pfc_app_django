from types import SimpleNamespace

from django.test import SimpleTestCase

from pfc_app.avaliacao_rules import validar_acesso_avaliacao


class ValidarAcessoAvaliacaoTests(SimpleTestCase):
    def make_curso(self, periodo_avaliativo=True, status_nome="FINALIZADO"):
        return SimpleNamespace(
            periodo_avaliativo=periodo_avaliativo,
            status=SimpleNamespace(nome=status_nome),
        )

    def make_inscricao(self, condicao_na_acao="DISCENTE", concluido=True):
        return SimpleNamespace(
            condicao_na_acao=condicao_na_acao,
            concluido=concluido,
        )

    def test_bloqueia_quando_periodo_avaliativo_fechado(self):
        permitido, mensagem = validar_acesso_avaliacao(
            self.make_curso(periodo_avaliativo=False),
            self.make_inscricao(),
        )

        self.assertFalse(permitido)
        self.assertEqual(mensagem, "Avaliação não está aberta para este curso.")

    def test_bloqueia_quando_nao_ha_inscricao(self):
        permitido, mensagem = validar_acesso_avaliacao(
            self.make_curso(),
            None,
        )

        self.assertFalse(permitido)
        self.assertEqual(mensagem, "Você não está inscrito neste curso!")

    def test_bloqueia_quando_nao_e_discente(self):
        permitido, mensagem = validar_acesso_avaliacao(
            self.make_curso(),
            self.make_inscricao(condicao_na_acao="DOCENTE"),
        )

        self.assertFalse(permitido)
        self.assertEqual(
            mensagem, "A avaliação está disponível apenas para discentes."
        )

    def test_bloqueia_quando_inscricao_nao_concluida(self):
        permitido, mensagem = validar_acesso_avaliacao(
            self.make_curso(),
            self.make_inscricao(concluido=False),
        )

        self.assertFalse(permitido)
        self.assertEqual(
            mensagem, "Somente inscrições concluídas podem avaliar o curso."
        )

    def test_libera_quando_todas_as_regras_sao_atendidas(self):
        permitido, mensagem = validar_acesso_avaliacao(
            self.make_curso(),
            self.make_inscricao(),
        )

        self.assertTrue(permitido)
        self.assertEqual(mensagem, "")
