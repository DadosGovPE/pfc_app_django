"""Entrada do job diário: usa a mesma sincronização da atualização manual."""
import json
import logging

from app.dados import Ocupado
from app.pfc_sync import executar
from sincronizar_pfc import ErroIntegracao


def main():
    try:
        resultado = executar()
    except Ocupado:
        print("Outra atualização está em andamento; o serviço tentará novamente.", flush=True)
        return 75
    except ErroIntegracao as exc:
        print(f"Falha na sincronização: {exc}", flush=True)
        return 1
    except Exception:
        logging.exception("Falha no job de avaliações do PFC")
        return 1
    print(json.dumps({"job": "sentimento-pfc-sync", **resultado}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
