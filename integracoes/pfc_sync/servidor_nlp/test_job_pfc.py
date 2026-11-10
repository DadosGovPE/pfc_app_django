import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import job_pfc
from app.pfc_lock import TravaAtualizacao


class JobTests(unittest.TestCase):
    def test_job_usa_fluxo_dos_dois_paineis(self):
        with patch.object(job_pfc, "executar", return_value={"alterado": True}) as executar, \
                contextlib.redirect_stdout(io.StringIO()) as saida:
            self.assertEqual(job_pfc.main(), 0)
            executar.assert_called_once_with()
            self.assertIn('"alterado": true', saida.getvalue())

    def test_job_sem_mudancas_termina_com_sucesso(self):
        with patch.object(job_pfc, "executar", return_value={"alterado": False}), \
                contextlib.redirect_stdout(io.StringIO()) as saida:
            self.assertEqual(job_pfc.main(), 0)
            self.assertIn('"alterado": false', saida.getvalue())

    def test_ocupado_pede_nova_tentativa(self):
        with patch.object(job_pfc, "executar", side_effect=job_pfc.Ocupado()), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(job_pfc.main(), 75)

    def test_falha_de_rede_sinaliza_erro_para_servico(self):
        with patch.object(job_pfc, "executar", side_effect=job_pfc.ErroIntegracao("PFC indisponível")), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(job_pfc.main(), 1)

    def test_falha_inesperada_sinaliza_erro(self):
        with patch.object(job_pfc, "executar", side_effect=OSError("disco indisponível")), \
                self.assertLogs(level="ERROR"):
            self.assertEqual(job_pfc.main(), 1)


class TravaTests(unittest.TestCase):
    def test_impede_segunda_thread_e_libera(self):
        with tempfile.TemporaryDirectory() as tmp:
            trava = TravaAtualizacao(Path(tmp) / "sync.lock")
            self.assertTrue(trava.acquire(blocking=False))
            self.assertFalse(trava.acquire(blocking=False))
            trava.release()
            self.assertTrue(trava.acquire(blocking=False))
            trava.release()

    def test_impede_segundo_processo_e_libera(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "sync.lock"
            trava = TravaAtualizacao(caminho)
            codigo = """import sys
from pathlib import Path
from app.pfc_lock import TravaAtualizacao
trava = TravaAtualizacao(Path(sys.argv[1]))
obtida = trava.acquire(blocking=False)
if obtida: trava.release()
assert obtida == (sys.argv[2] == 'livre')
"""
            trava.acquire()
            try:
                subprocess.run([sys.executable, "-c", codigo, str(caminho), "ocupada"], check=True)
            finally:
                trava.release()
            subprocess.run([sys.executable, "-c", codigo, str(caminho), "livre"], check=True)

    def test_falha_de_arquivo_nao_bloqueia_nova_tentativa(self):
        with tempfile.TemporaryDirectory() as tmp:
            pai = Path(tmp) / "pasta"; pai.touch()
            trava = TravaAtualizacao(pai / "sync.lock")
            with self.assertRaises(FileExistsError):
                trava.acquire(blocking=False)
            pai.unlink()
            self.assertTrue(trava.acquire(blocking=False))
            trava.release()


if __name__ == "__main__":
    unittest.main()
