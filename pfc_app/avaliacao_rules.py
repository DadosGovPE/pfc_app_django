def validar_acesso_avaliacao(curso, inscricao):
    if not getattr(curso, "periodo_avaliativo", False):
        return False, "Avaliação não está aberta para este curso."

    if getattr(curso.status, "nome", None) != "FINALIZADO":
        return False, "Curso não finalizado!"

    if inscricao is None:
        return False, "Você não está inscrito neste curso!"

    if getattr(inscricao, "condicao_na_acao", None) != "DISCENTE":
        return False, "A avaliação está disponível apenas para discentes."

    if not getattr(inscricao, "concluido", False):
        return False, "Somente inscrições concluídas podem avaliar o curso."

    return True, ""
