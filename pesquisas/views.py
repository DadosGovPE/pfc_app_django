from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Pesquisa, Resposta

from .models import Resposta

@login_required
def responder_pesquisa(request, pesquisa_id):
    pesquisa = get_object_or_404(Pesquisa, id=pesquisa_id)

    # Verifica se já existem respostas do usuário para essa pesquisa
    ja_respondeu = Resposta.objects.filter(
        pergunta__pesquisa=pesquisa,
        usuario=request.user
    ).exists()

    if request.method == 'POST':
        if ja_respondeu:
            messages.error(request, "Você já respondeu essa pesquisa.")
            return redirect('responder_pesquisa', pesquisa_id=pesquisa.id)

        for pergunta in pesquisa.perguntas.all():
            key = f'pergunta_{pergunta.id}'
            valor = request.POST.get(key)

            if pergunta.tipo == 'RADIO':
                Resposta.objects.create(
                    pergunta=pergunta,
                    usuario=request.user,
                    resposta_numero=int(valor)
                )
            elif pergunta.tipo == 'TEXTO':
                Resposta.objects.create(
                    pergunta=pergunta,
                    usuario=request.user,
                    resposta_texto=valor
                )

        messages.success(request, 'Obrigado por responder!')
        return redirect('pagina_sucesso')

    context = {
        'pesquisa': pesquisa,
        'grupos': pesquisa.grupos.prefetch_related('perguntas'),
        'perguntas_sem_grupo': pesquisa.perguntas.filter(grupo__isnull=True),
        'ja_respondeu': ja_respondeu,
    }
    return render(request, 'pesquisas/responder.html', context)
