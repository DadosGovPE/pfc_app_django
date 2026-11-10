import asyncio
import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app import pfc_sync
from sincronizar_pfc import ErroIntegracao


def fonte():
    texto = "Ótimo curso"
    h = hashlib.sha256(texto.encode()).hexdigest()
    rows = [dict(p="1", id_curso="2", t="3", curso="Curso", mes="2026-11",
                 data_inicio="2026-11-09", data_termino="2026-11-10", txt=texto, text_hash=h),
            dict(p="4", id_curso="2", t="3", curso="Curso", mes="2026-11",
                 data_inicio="2026-11-09", data_termino=None, txt="", text_hash=hashlib.sha256(b"").hexdigest())]
    classes = [dict(text_hash=h, sentimento="Positivo", confianca=.9, temas=["Instrutor e didática"])]
    return dict(source_hash="a"*64, schema_version=1, registros=rows), classes


class IntegracaoPfcTests(unittest.TestCase):
    def test_converte_datas_e_classificacoes_sem_perder_aval_sem_texto(self):
        f, c = fonte()
        df = pfc_sync.converter_base(f, c)
        self.assertEqual(len(df), 2)
        self.assertEqual(df.iloc[0]["Data de Início"].strftime("%Y-%m-%d"), "2026-11-09")
        self.assertEqual(df.iloc[0]["Sentimento"], "Positivo")
        self.assertEqual(df.iloc[0]["Temas"], "Instrutor e didática")
        self.assertTrue(pfc_sync.pd.isna(df.iloc[1]["Sentimento"]))

    def test_formulario_exige_login(self):
        response = pfc_sync.formulario(SimpleNamespace(session={}))
        self.assertEqual(response.status_code, 303)

    def test_formulario_cria_csrf_e_indica_acao(self):
        request = SimpleNamespace(session={"usuario": "teste"})
        response = pfc_sync.formulario(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(request.session["pfc_sync_csrf"])
        self.assertIn(b"Buscar, classificar e publicar", response.body)

    def test_post_sem_sessao_ou_csrf_nao_executa(self):
        with patch.object(pfc_sync, "executar") as execute:
            self.assertEqual(asyncio.run(pfc_sync.atualizar(SimpleNamespace(session={}), "")).status_code, 303)
            response = asyncio.run(pfc_sync.atualizar(SimpleNamespace(session={"usuario": "t", "pfc_sync_csrf": "abc"}), "á"))
            self.assertEqual(response.status_code, 403)
            execute.assert_not_called()

    def test_post_valido_executa_e_confirma(self):
        request = SimpleNamespace(session={"usuario": "t", "pfc_sync_csrf": "nonce"})
        with patch.object(pfc_sync, "executar", return_value=dict(avaliacoes=2, comentarios=1, cursos=1, alterado=True)) as execute:
            response = asyncio.run(pfc_sync.atualizar(request, "nonce"))
            self.assertEqual(response.status_code, 200)
            execute.assert_called_once()

    def test_atualizacao_ocupada_nao_inicia(self):
        with patch.object(pfc_sync.dados, "_ocupado") as lock:
            lock.acquire.return_value = False
            with self.assertRaises(pfc_sync.dados.Ocupado):
                pfc_sync.executar()
            lock.release.assert_not_called()

    def test_falha_do_pfc_preserva_publicacao_local(self):
        f, c = fonte()
        def falhar(args, **kwargs):
            kwargs["antes_publicar"](f, c)
            raise ErroIntegracao("PFC indisponível")
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp); atual = d / "atual"; atual.mkdir(); (atual / "painel.html").write_text("anterior")
            with patch.object(pfc_sync, "DADOS", d), patch.object(pfc_sync.dados, "ATUAL", atual), \
                    patch.object(pfc_sync, "sincronizar", side_effect=falhar), patch.object(pfc_sync.dados, "_publicar") as publish:
                with self.assertRaises(ErroIntegracao): pfc_sync.executar()
                publish.assert_not_called()
                self.assertEqual((atual / "painel.html").read_text(), "anterior")
                self.assertEqual(list(d.glob("novo-pfc-*")), [])


if __name__ == "__main__":
    unittest.main()
