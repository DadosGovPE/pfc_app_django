"""Fonte do Explorer e publicação de classificações recebidas do servidor NLP."""

import hashlib
import re
import json
import math
from datetime import date, datetime

import sqlparse
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from explorer.models import Query
from explorer.utils import get_valid_connection

from pfc_app.models import PainelAvaliacoes

COLUNAS = ("participante_id", "ID do Curso", "Turma", "Nome do Curso", "Data de Início", "Avaliacao Aberta")
SENTIMENTOS = {"Positivo", "Misto", "Negativo", "Neutro"}


class DadosInvalidos(ValueError):
    pass


class FonteAlterada(ValueError):
    pass


def limpar_texto(valor):
    texto = "" if valor is None else str(valor)
    texto = texto.replace("_x000D_", "")
    return re.sub(r"[ \t]+", " ", re.sub(r"\s*\n\s*", "\n", texto)).strip()


def mes_inicio(valor):
    if isinstance(valor, (date, datetime)):
        return valor.strftime("%Y-%m")
    texto = str(valor or "").strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto[:10], formato).strftime("%Y-%m")
        except ValueError:
            continue
    raise DadosInvalidos("A consulta retornou uma data de início inválida. Confira a consulta no Explorer.")


def data_iso(valor):
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(valor).strip()[:10], formato).date().isoformat()
        except ValueError:
            continue
    raise DadosInvalidos("A consulta retornou uma data inválida.")


def normalizar_resultado(cabecalhos, linhas):
    cabecalhos = [str(c).strip() for c in cabecalhos]
    if len(cabecalhos) != len(set(cabecalhos)):
        raise DadosInvalidos("A consulta retornou colunas repetidas. Confira os nomes no Explorer.")
    faltam = set(COLUNAS) - set(cabecalhos)
    if faltam:
        raise DadosInvalidos("Colunas ausentes na consulta: " + ", ".join(sorted(faltam)) + ".")
    registros = []
    for linha in linhas:
        r = dict(zip(cabecalhos, linha))
        if not str(r["Nome do Curso"] or "").strip() or r["ID do Curso"] is None:
            raise DadosInvalidos("A consulta retornou uma avaliação sem identificação do curso.")
        registros.append({
            "p": str(r["participante_id"] or ""),
            "id_curso": str(r["ID do Curso"]),
            "t": str(r["Turma"] or ""),
            "curso": str(r["Nome do Curso"]).strip(),
            "mes": mes_inicio(r["Data de Início"]),
            "data_inicio": data_iso(r["Data de Início"]),
            "data_termino": data_iso(r.get("Data de Término")),
            "txt": limpar_texto(r["Avaliacao Aberta"]),
        })
    return registros


def consultar_explorer():
    consulta_id = getattr(settings, "PFC_AVALIACOES_QUERY_ID", 33)
    try:
        consulta = Query.objects.get(pk=consulta_id)
    except Query.DoesNotExist as exc:
        raise DadosInvalidos("A consulta de avaliações não foi encontrada no Explorer.") from exc
    instrucoes = sqlparse.parse(consulta.final_sql())
    if len(instrucoes) != 1 or instrucoes[0].get_type() != "SELECT":
        raise DadosInvalidos("A fonte do painel deve ser uma única consulta SELECT no Explorer.")
    conexao = get_valid_connection(consulta.connection)
    with transaction.atomic(using=conexao.alias):
        if conexao.vendor == "postgresql":
            with conexao.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute("SET LOCAL statement_timeout = '30s'")
        # Mantém a conexão e a validação de SQL do próprio Explorer; sem transforms HTML.
        resultado = consulta.execute_query_only()
    return normalizar_resultado(resultado.header_strings, resultado.data)


TEMAS = {
    "Instrutor e didática", "Conteúdo e aplicabilidade", "Organização e equipe",
    "Carga horária e tempo", "Infraestrutura (sala, internet, equipamentos)",
    "Material e recursos visuais", "Continuidade / novos cursos",
    "Divulgação e inscrição", "Metodologia e prática", "Elogio genérico",
}


def hash_texto(texto):
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _json_canonico(valor):
    return json.dumps(valor, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fonte_avaliacoes():
    registros = consultar_explorer()
    canonicos = sorted(_json_canonico(r) for r in registros)
    versao = hashlib.sha256(_json_canonico(canonicos).encode("utf-8")).hexdigest()
    return {"schema_version": 1, "source_hash": versao,
            "registros": [{**r, "text_hash": hash_texto(r["txt"])} for r in registros]}


def publicar_resultados(payload):
    from django.utils.dateparse import parse_datetime

    if (not isinstance(payload, dict) or type(payload.get("schema_version")) is not int
            or payload["schema_version"] != 1):
        raise DadosInvalidos("Versão ou formato do payload inválido.")
    source_hash = payload.get("source_hash")
    modelo = payload.get("model_version")
    gerado = payload.get("generated_at")
    resultados = payload.get("resultados")
    if not isinstance(source_hash, str) or not re.fullmatch(r"[a-f0-9]{64}", source_hash):
        raise DadosInvalidos("Identificação da fonte inválida.")
    if not isinstance(modelo, str) or not re.fullmatch(r"[a-zA-Z0-9._:/-]{1,160}", modelo):
        raise DadosInvalidos("Identificação do modelo inválida.")
    try:
        quando = parse_datetime(gerado) if isinstance(gerado, str) else None
    except ValueError:
        quando = None
    if quando is None or timezone.is_naive(quando):
        raise DadosInvalidos("generated_at deve conter uma data e hora com fuso horário.")
    if (quando - timezone.now()).total_seconds() > 300:
        raise DadosInvalidos("Data de geração está no futuro. Confira o relógio do classificador.")
    if not isinstance(resultados, list):
        raise DadosInvalidos("resultados deve ser uma lista.")
    classes = {}
    for r in resultados:
        if not isinstance(r, dict):
            raise DadosInvalidos("Classificação inválida.")
        chave, sentimento, confianca, temas = (
            r.get("text_hash"), r.get("sentimento"), r.get("confianca"), r.get("temas")
        )
        if (not isinstance(chave, str) or not re.fullmatch(r"[a-f0-9]{64}", chave)
                or chave in classes or not isinstance(sentimento, str) or sentimento not in SENTIMENTOS
                or isinstance(confianca, bool) or not isinstance(confianca, (int, float))
                or not math.isfinite(confianca) or not 0 <= confianca <= 1
                or not isinstance(temas, list) or len(temas) > len(TEMAS)
                or not all(isinstance(t, str) and t in TEMAS for t in temas)
                or len(temas) != len(set(temas))):
            raise DadosInvalidos("Sentimento, confiança, temas ou hash inválidos/repetidos.")
        classes[chave] = {"sentimento": sentimento, "confianca": confianca, "temas": sorted(temas)}
    fonte = fonte_avaliacoes()
    if fonte["source_hash"] != source_hash:
        raise FonteAlterada("As avaliações mudaram. Busque a fonte novamente e reenvie a análise.")
    esperados = {r["text_hash"] for r in fonte["registros"] if r["txt"]}
    if set(classes) != esperados:
        raise DadosInvalidos("A análise deve conter exatamente uma classificação para cada texto não vazio da fonte.")
    registros = []
    for r in fonte["registros"]:
        if r["txt"]:
            registro = {k: v for k, v in r.items() if k != "text_hash"}
            c = classes[r["text_hash"]]
            registros.append({**registro, "sent": c["sentimento"], "conf": c["confianca"], "temas": c["temas"]})
    assinatura = hashlib.sha256(_json_canonico({
        "source_hash": source_hash, "model_version": modelo, "classes": classes,
    }).encode("utf-8")).hexdigest()
    publicado = {
        "registros": registros, "total_linhas": len(fonte["registros"]),
        "total_cursos": len({r["curso"] for r in fonte["registros"]}),
        "source_hash": source_hash, "model_version": modelo,
        "generated_at": quando.isoformat(), "signature": assinatura,
    }
    PainelAvaliacoes.objects.get_or_create(pk=1)
    with transaction.atomic():
        painel = PainelAvaliacoes.objects.select_for_update().get(pk=1)
        if painel.publicado.get("signature") == assinatura:
            alterado = False
        else:
            anterior = parse_datetime(painel.publicado.get("generated_at", ""))
            if anterior is not None and quando < anterior:
                raise FonteAlterada("Uma análise mais recente já foi publicada.")
            painel.publicado = publicado
            painel.rascunho = None
            painel.classificacoes = {}
            painel.atualizado_em = timezone.now()
            painel.save()
            alterado = True
    return {"ok": True, "alterado": alterado, "avaliacoes": publicado["total_linhas"],
            "comentarios": len(registros), "cursos": publicado["total_cursos"]}
