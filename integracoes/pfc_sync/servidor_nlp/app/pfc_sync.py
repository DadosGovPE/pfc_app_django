"""Atualiza o painel local e o PFC usando o classificador já instalado na LAB."""
import hmac
import hashlib
import json
import logging
import os
import secrets
import shutil
import uuid
from html import escape
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from fastapi import APIRouter, Form, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse

from analise_sentimento import CAMPOS_BASE, CAMPOS_PLANILHA, gravar, validar
from sincronizar_pfc import ErroIntegracao, sincronizar
from . import dados, paginas
from .config import DADOS, PREFIX

router = APIRouter()
log = logging.getLogger("sentimento.pfc")


def converter_base(fonte, resultados):
    classes = {r["text_hash"]: r for r in resultados}
    linhas = [{
        "participante_id": r["p"], "ID do Curso": r["id_curso"], "Turma": r["t"],
        "Nome do Curso": r["curso"], "Data de Início": r["data_inicio"],
        "Data de Término": r.get("data_termino"), "Avaliacao Aberta": r["txt"],
    } for r in fonte["registros"]]
    df = validar(pd.DataFrame(linhas, columns=CAMPOS_PLANILHA), exigir_comentarios=False)
    registros = df.astype(object).where(df.notna(), None).to_dict("records")
    for linha, origem in zip(registros, fonte["registros"]):
        c = classes.get(origem["text_hash"]) if origem["txt"] else None
        linha.update(Sentimento=c["sentimento"] if c else None,
                     Confiança=c["confianca"] if c else None,
                     Temas="; ".join(c["temas"]) if c else None)
    return pd.DataFrame(registros, columns=CAMPOS_BASE)


def executar():
    if not dados._ocupado.acquire(blocking=False):
        raise dados.Ocupado("Outra atualização está em andamento. Tente novamente em instantes.")
    try:
        return _executar_bloqueado()
    finally:
        dados._ocupado.release()


def _executar_bloqueado():
    novo = None
    raiz = Path(__file__).resolve().parent.parent
    modelo = hashlib.sha256((raiz / "modelos" / "classificador.joblib").read_bytes()).hexdigest()
    template = hashlib.sha256((raiz / "painel_template.html").read_bytes()).hexdigest()

    def preparar(fonte, resultados):
        nonlocal novo
        if novo is not None:
            shutil.rmtree(novo, ignore_errors=True)
        novo = DADOS / f"novo-pfc-{uuid.uuid4().hex}"
        novo.mkdir(parents=True)
        gravar(converter_base(fonte, resultados), novo)
        (novo / "pfc_sync.json").write_text(json.dumps({
            "source_hash": fonte["source_hash"], "model_version": modelo,
            "template_version": template,
        }), encoding="utf-8")

    def publicar_local(fonte, resultados, resposta):
        nonlocal novo
        anterior = dados.ATUAL / "pfc_sync.json"
        if (not resposta["alterado"] and anterior.exists()
                and json.loads(anterior.read_text(encoding="utf-8")) == {
                    "source_hash": fonte["source_hash"], "model_version": modelo,
                    "template_version": template}):
            return
        dados._publicar(novo, guardar_anterior=True)
        novo = None

    try:
        args = SimpleNamespace(
            projeto_classificador=raiz,
            pfc_url=os.getenv("PFC_API_URL", "https://www.pfc.seplag.pe.gov.br/"),
            cache=DADOS / "pfc" / "classificacoes.json", permitir_http=False,
        )
        def classificar(textos):
            return dados.classificador().classificar(textos)

        return sincronizar(args, classificar_callback=classificar,
                           antes_publicar=preparar, apos_publicar=publicar_local)
    finally:
        if novo is not None:
            shutil.rmtree(novo, ignore_errors=True)


def pagina(request, erro="", sucesso=""):
    nonce = secrets.token_urlsafe(32)
    request.session["pfc_sync_csrf"] = nonce
    mensagem = f'<div class="erro" role="alert">{escape(erro)}</div>' if erro else ""
    if sucesso:
        mensagem = f'<div class="ok" role="status">{escape(sucesso)}</div>'
    return paginas.pagina("Atualizar avaliações do PFC", f"""
<form class="card" method="post" action="sincronizar-pfc" id="pfc-sync">
  <h1>Atualizar avaliações do PFC</h1>
  <p>Busca as avaliações mais recentes do PFC, analisa os comentários novos ou alterados
  e atualiza os dois painéis. As classificações já feitas são reaproveitadas.</p>
  {mensagem}
  <input type="hidden" name="csrf" value="{nonce}">
  <div class="linha"><button type="submit" id="pfc-enviar">Buscar, classificar e publicar</button>
  <a class="btn sec" href="./">Voltar ao painel</a></div>
  <p><a href="atualizar">Importar uma planilha</a></p>
  <small>A primeira atualização pode levar alguns minutos. Os últimos dados publicados
  continuam disponíveis durante o processamento.</small>
</form>
<script>document.getElementById("pfc-sync").addEventListener("submit", function () {{
  var b = document.getElementById("pfc-enviar"); b.disabled = true;
  b.textContent = "Buscando e analisando avaliações…"; }});</script>""")


@router.get("/sincronizar-pfc", response_class=HTMLResponse)
def formulario(request: Request):
    if not request.session.get("usuario"):
        return RedirectResponse(f"{PREFIX}/login", status_code=303)
    return HTMLResponse(pagina(request))


@router.post("/sincronizar-pfc", response_class=HTMLResponse)
async def atualizar(request: Request, csrf: str = Form("")):
    if not request.session.get("usuario"):
        return RedirectResponse(f"{PREFIX}/login", status_code=303)
    esperado = request.session.pop("pfc_sync_csrf", "")
    if not esperado or not hmac.compare_digest(esperado.encode("utf-8"), csrf.encode("utf-8")):
        return HTMLResponse(pagina(request, erro="Recarregue a página e tente novamente."), status_code=403)
    try:
        r = await run_in_threadpool(executar)
    except (ErroIntegracao, dados.Ocupado) as exc:
        return HTMLResponse(pagina(request, erro=str(exc)), status_code=503)
    except Exception:
        log.exception("Falha ao sincronizar avaliações com o PFC")
        return HTMLResponse(pagina(request, erro="Não foi possível concluir a atualização. Tente novamente em instantes."), status_code=500)
    return HTMLResponse(pagina(request, sucesso=(
        f"Atualização concluída: {r['avaliacoes']} avaliações, {r['comentarios']} comentários e {r['cursos']} cursos. "
        + ("Os painéis foram atualizados." if r["alterado"] else "Os dados já estavam atualizados.")
    )))
