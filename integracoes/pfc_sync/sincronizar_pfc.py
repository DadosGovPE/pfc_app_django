"""Execute no servidor do classificador existente. O PFC recebe somente resultados.

Usa a biblioteca padrão para HTTP/cache e importa o Classificador do projeto original
somente quando houver textos novos. Não requer Django nesta máquina.
"""

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class ErroIntegracao(RuntimeError):
    pass


class FonteAlterada(ErroIntegracao):
    pass


class SemRedirecionamento(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Nunca encaminhar o token a outro endereço por redirect.


def requisicao(base_url, caminho, token, payload=None, permitir_http=False):
    url = urljoin(base_url.rstrip("/") + "/", caminho)
    partes = urlsplit(url)
    if (partes.scheme not in {"http", "https"} or not partes.hostname
            or partes.username or partes.password or partes.query or partes.fragment):
        raise ErroIntegracao("URL do PFC inválida.")
    if partes.scheme != "https" and not permitir_http:
        raise ErroIntegracao("Use HTTPS. HTTP interno exige --permitir-http explicitamente.")
    body = None if payload is None else json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
    req = Request(url, data=body, headers={
        "Authorization": "Bearer " + token, "Accept": "application/json",
        "Content-Type": "application/json", "User-Agent": "PFC-Sentimento-Sync/1",
    })
    try:
        with build_opener(SemRedirecionamento()).open(req, timeout=60) as response:
            if response.headers.get_content_type() != "application/json":
                raise ErroIntegracao("O PFC respondeu fora do formato JSON esperado.")
            data = response.read(16 * 1024 * 1024 + 1)
            if len(data) > 16 * 1024 * 1024:
                raise ErroIntegracao("Resposta do PFC acima do limite esperado.")
            return json.loads(data.decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 409:
            raise FonteAlterada("A fonte mudou durante a análise; será consultada novamente.") from None
        raise ErroIntegracao(f"PFC respondeu HTTP {exc.code}. Confira a configuração e os logs do PFC.") from None
    except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ErroIntegracao("Falha de conexão ou resposta inválida do PFC. A publicação anterior permanece disponível.") from exc


def salvar_cache(caminho, modelo, classes):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fd, temporario = tempfile.mkstemp(prefix=".pfc-cache-", dir=caminho.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
            json.dump({"model_version": modelo, "classificacoes": classes}, arquivo,
                      ensure_ascii=False, allow_nan=False)
        os.replace(temporario, caminho)
    finally:
        if os.path.exists(temporario):
            os.unlink(temporario)


def carregar_cache(caminho, modelo):
    if not caminho.exists():
        return {}
    try:
        data = json.loads(caminho.read_text(encoding="utf-8"))
        if data.get("model_version") != modelo:
            return {}
        classes = data["classificacoes"]
        if not isinstance(classes, dict):
            raise ValueError
        return classes
    except (ValueError, KeyError, AttributeError) as exc:
        raise ErroIntegracao("Cache local inválido. Restaure o arquivo ou escolha outro caminho de cache.") from exc


def analisar(fonte, classes, classificar, salvar=lambda: None, lote=16):
    if not isinstance(fonte, dict) or fonte.get("schema_version") != 1:
        raise ErroIntegracao("Versão da fonte incompatível.")
    textos = {}
    for r in fonte["registros"]:
        texto = r["txt"]
        chave = hashlib.sha256(texto.encode("utf-8")).hexdigest()
        if chave != r["text_hash"]:
            raise ErroIntegracao("Hash de texto incompatível com a fonte.")
        if texto:
            textos[chave] = texto
    pendentes = [h for h in textos if h not in classes]
    print(f"Textos únicos: {len(textos)}; novos/alterados: {len(pendentes)}.", flush=True)
    for inicio in range(0, len(pendentes), lote):
        chaves = pendentes[inicio:inicio + lote]
        resultados = classificar([textos[h] for h in chaves])
        if len(resultados) != len(chaves):
            raise ErroIntegracao("O classificador não concluiu o lote.")
        for h, resultado in zip(chaves, resultados):
            classes[h] = resultado
        salvar()
        print(f"Classificados: {min(inicio + lote, len(pendentes))}/{len(pendentes)}.", flush=True)
    return [{"text_hash": h, **classes[h]} for h in sorted(textos)]


def sincronizar(args, classificar_callback=None, antes_publicar=None, apos_publicar=None):
    token = os.getenv("PFC_AVALIACOES_SYNC_TOKEN", "")
    if len(token) < 32:
        raise ErroIntegracao("Defina PFC_AVALIACOES_SYNC_TOKEN com pelo menos 32 caracteres.")
    projeto = args.projeto_classificador.resolve()
    modelo_path = projeto / "modelos" / "classificador.joblib"
    if not modelo_path.is_file():
        raise ErroIntegracao("Classificador treinado não encontrado na pasta informada.")
    modelo = hashlib.sha256(modelo_path.read_bytes()).hexdigest()
    classes = carregar_cache(args.cache, modelo)
    clf = None

    def classificar(textos):
        nonlocal clf
        if classificar_callback is not None:
            return classificar_callback(textos)
        if clf is None:
            sys.path.insert(0, str(projeto))
            from classificador import Classificador
            clf = Classificador.carregar(modelo_path)
        return clf.classificar(textos)

    for tentativa in range(3):
        fonte = requisicao(args.pfc_url, "api/avaliacoes/fonte/", token, permitir_http=args.permitir_http)
        resultados = analisar(fonte, classes, classificar,
                             salvar=lambda: salvar_cache(args.cache, modelo, classes))
        payload = {
            "schema_version": 1, "source_hash": fonte["source_hash"], "model_version": modelo,
            "generated_at": datetime.now(timezone.utc).isoformat(), "resultados": resultados,
        }
        if antes_publicar is not None:
            antes_publicar(fonte, resultados)
        try:
            resposta = requisicao(args.pfc_url, "api/avaliacoes/resultados/", token, payload,
                                  permitir_http=args.permitir_http)
        except FonteAlterada:
            if tentativa == 2:
                raise ErroIntegracao("A fonte continua mudando. Execute novamente em instantes.") from None
            print("Fonte alterada; atualizando a extração e reaproveitando o cache.", flush=True)
            continue
        ativos = {r["text_hash"] for r in resultados}
        salvar_cache(args.cache, modelo, {h: classes[h] for h in ativos})
        if apos_publicar is not None:
            apos_publicar(fonte, resultados, resposta)
        print(f"PFC atualizado: {resposta['avaliacoes']} avaliações; {resposta['comentarios']} comentários; "
              f"{resposta['cursos']} cursos. Alterado: {resposta['alterado']}.", flush=True)
        return resposta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pfc-url", default=os.getenv("PFC_API_URL", "https://www.pfc.seplag.pe.gov.br/"))
    parser.add_argument("--projeto-classificador", type=Path, default=Path.cwd())
    parser.add_argument("--cache", type=Path, default=Path(os.getenv("PFC_SYNC_CACHE", "dados/pfc/classificacoes.json")))
    parser.add_argument("--permitir-http", action="store_true", help="Permite HTTP explicitamente na rede interna.")
    args = parser.parse_args()
    try:
        sincronizar(args)
    except ErroIntegracao as exc:
        parser.exit(1, f"Erro: {exc}\n")
    except Exception as exc:
        parser.exit(1, f"Falha no processamento ({type(exc).__name__}). Confira a instalação local do classificador.\n")


if __name__ == "__main__":
    main()
