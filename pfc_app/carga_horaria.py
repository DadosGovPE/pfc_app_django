"""Regra comum de CH do PFC: uma conclusão por nome no período."""

from django.db.models import F, OuterRef, Q, Subquery, Sum

from .models import Inscricao


def inscricoes_ch_unicas(data_inicio=None, data_fim=None, participante=None):
    elegiveis = Inscricao.objects.filter(
        ~Q(status__nome="CANCELADA"),
        ~Q(status__nome="EM FILA"),
        concluido=True,
        curso__status__nome="FINALIZADO",
    ).order_by()
    if data_inicio:
        elegiveis = elegiveis.filter(curso__data_termino__gte=data_inicio)
    if data_fim:
        elegiveis = elegiveis.filter(curso__data_termino__lte=data_fim)

    # Empate resolvido pelo ID para selecionar exatamente uma inscrição.
    maior_ch = elegiveis.filter(
        participante_id=OuterRef("participante_id"),
        curso__nome_curso=OuterRef("curso__nome_curso"),
    ).order_by(F("ch_valida").desc(nulls_last=True), "pk").values("pk")[:1]
    unicas = elegiveis.filter(pk=Subquery(maior_ch))
    if participante is not None:
        unicas = unicas.filter(participante=participante)
    return unicas


def total_ch_pfc(data_inicio=None, data_fim=None, participante=None):
    return inscricoes_ch_unicas(data_inicio, data_fim, participante).aggregate(
        total=Sum("ch_valida")
    )["total"] or 0
