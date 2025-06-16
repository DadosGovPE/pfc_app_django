from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Pesquisa, Resposta, GrupoPerguntas, Pergunta
from django.contrib import messages 
from django.contrib.auth.decorators import login_required
from django.utils import timezone

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


@login_required
def escolher_e_duplicar_pesquisa(request):
    if request.method == 'POST':
        pesquisa_id = request.POST.get('pesquisa_id')
        if not pesquisa_id:
            messages.error(request, "Selecione uma pesquisa para duplicar.")
            return redirect('duplicar_pesquisa_form')

        pesquisa_original = get_object_or_404(Pesquisa, pk=pesquisa_id)

        nova_pesquisa = Pesquisa.objects.create(
            titulo=f"{pesquisa_original.titulo} (Cópia)",
            data_inicio=timezone.now().date(),
            data_fim=pesquisa_original.data_fim,
            is_aberta=False
        )

        grupos_map = {}
        for grupo in pesquisa_original.grupos.all():
            novo_grupo = GrupoPerguntas.objects.create(
                pesquisa=nova_pesquisa,
                titulo=grupo.titulo
            )
            grupos_map[grupo.id] = novo_grupo

        for pergunta in pesquisa_original.perguntas.all():
            Pergunta.objects.create(
                pesquisa=nova_pesquisa,
                grupo=grupos_map.get(pergunta.grupo_id),
                texto=pergunta.texto,
                tipo=pergunta.tipo
            )

        messages.success(request, f"Pesquisa '{pesquisa_original.titulo}' duplicada com sucesso.")
        return redirect('duplicar_pesquisa_form')  # ajuste para o nome correto

    pesquisas = Pesquisa.objects.all()
    return render(request, 'pesquisas/duplicar_pesquisa.html', {'pesquisas': pesquisas})