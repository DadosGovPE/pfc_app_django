"""Impede atualizações simultâneas entre o painel web e o job no Linux."""
import fcntl
import threading


class TravaAtualizacao:
    def __init__(self, caminho):
        self.caminho = caminho
        self._thread = threading.Lock()
        self._arquivo = None

    def acquire(self, blocking=True):
        if not self._thread.acquire(blocking=blocking):
            return False
        arquivo = None
        try:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            arquivo = self.caminho.open("a")
            fcntl.flock(arquivo, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            self._arquivo = arquivo
            return True
        except BlockingIOError:
            if arquivo is not None:
                arquivo.close()
            self._thread.release()
            return False
        except BaseException:
            if arquivo is not None:
                arquivo.close()
            self._thread.release()
            raise

    def release(self):
        if self._arquivo is None:
            raise RuntimeError("Atualização sem trava adquirida.")
        try:
            fcntl.flock(self._arquivo, fcntl.LOCK_UN)
        finally:
            self._arquivo.close()
            self._arquivo = None
            self._thread.release()
