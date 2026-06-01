# Backlog - Enviar Emails no Admin

## Contexto

O app ja possui uma entrada no menu Admin para envio de e-mails por curso/status, em `mensageria:enviar_curso_status`. A feature nova deve evoluir esse fluxo para permitir que administradores escolham um curso, visualizem participantes agrupados por status da inscricao, selecionem inscricoes manualmente, alterem o status em lote e, opcionalmente, enviem e-mail aos participantes alterados.

## Decisao sobre job

Sim, e melhor usar job para o envio de e-mails quando houver alteracao em lote.

Motivo: alterar status deve ser uma operacao transacional e curta. Enviar e-mails pode demorar, falhar parcialmente, sofrer timeout de SMTP e deixar a tela presa. O ideal e salvar a alteracao de status imediatamente, registrar os destinatarios que devem receber e-mail e disparar um job assincrono para enviar as mensagens.

Para este projeto, Celery/RQ parece pesado demais. A referencia em `C:\workspace\relatorio-rgs-django` usa um job simples com banco + `subprocess.Popen`: a view cria um registro de job, salva os dados necessarios, e apos o commit dispara um comando Django em background (`manage.py process_seges_job <job_id>`). A tela de detalhe consulta o status do job e atualiza periodicamente.

Esse mesmo desenho e suficiente aqui: status alterado na requisicao principal, lote de e-mails registrado no banco, e envio executado por um comando Django separado.

## Epico 1 - Entrada e navegacao

- [ ] Ajustar o texto da entrada do menu Admin para `Enviar Emails`.
- [ ] Garantir que a entrada esteja visivel apenas para usuarios autorizados, mantendo a regra atual de `user.role == "ADMIN"` quando aplicavel.
- [ ] Criar ou reaproveitar rota inicial em `mensageria` para listagem de cursos.
- [ ] Manter botao/link de retorno para o Admin ou para a tela anterior.

## Epico 2 - Tela de escolha do curso

- [ ] Criar tela `Enviar Emails` com lista de cursos.
- [ ] Ordenar cursos do mais recente para o mais antigo, preferencialmente por `Curso.data_inicio` descendente e, como desempate, `Curso.data_criacao` descendente.
- [ ] Exibir informacoes suficientes para diferenciar turmas: nome formatado, turma, data de inicio, data de termino e status do curso.
- [ ] Adicionar busca por nome do curso.
- [ ] Adicionar paginacao para evitar uma lista pesada.
- [ ] Ao selecionar um curso, redirecionar para a tela de participantes daquele curso.

## Epico 3 - Tela de participantes por curso

- [ ] Criar rota de detalhe do curso, por exemplo `mensageria/enviar-emails/cursos/<curso_id>/`.
- [ ] Carregar inscricoes com `select_related("participante", "status", "curso")`.
- [ ] Mostrar todos os participantes inscritos no curso.
- [ ] Exibir em cada linha: checkbox, nome, CPF ou identificador necessario para administracao, e-mail, lotacao, status atual, concluido e condicao na acao.
- [ ] Agrupar participantes em secoes por `StatusInscricao`.
- [ ] Ordenar secoes por nome do status e participantes por nome.
- [ ] Exibir contadores por secao e contador geral de selecionados.
- [ ] Tratar inscricoes sem status, se existirem, em uma secao propria.

## Epico 4 - Selecao em lote

- [ ] Adicionar checkbox por inscricao.
- [ ] Adicionar checkbox `Marcar todos` em cada secao.
- [ ] Implementar JavaScript para selecionar/desselecionar apenas os participantes da secao.
- [ ] Atualizar estado visual do `Marcar todos` quando parte da secao estiver selecionada.
- [ ] Preservar selecoes ao abrir o modal.
- [ ] Bloquear o botao `Alterar status` quando nenhuma inscricao estiver selecionada.

## Epico 5 - Modal de alteracao de status

- [ ] Adicionar botao `Alterar status` acima e a direita da tela de participantes, logo abaixo da navbar/conteudo superior.
- [ ] Abrir modal ao clicar no botao.
- [ ] No modal, incluir select com todos os `StatusInscricao`.
- [ ] No modal, incluir checkbox `Enviar email`.
- [ ] Se `Enviar email` estiver marcado, exigir selecao de um `MensagemTemplate` ativo ou definir template padrao da acao.
- [ ] Mostrar resumo no modal: curso, quantidade selecionada e status de destino.
- [ ] Confirmar via POST com CSRF.
- [ ] Validar no backend que todas as inscricoes selecionadas pertencem ao curso informado.

## Epico 6 - Alteracao de status em lote

- [ ] Criar servico de dominio para alterar status das inscricoes selecionadas.
- [ ] Ignorar ou registrar separadamente inscricoes que ja estejam no status escolhido.
- [ ] Atualizar apenas inscricoes cujo status realmente mudou.
- [ ] Usar `transaction.atomic()` para a alteracao de status.
- [ ] Registrar mensagens de sucesso/alerta com total selecionado, total alterado e total ignorado.
- [ ] Registrar auditoria minima: usuario admin que executou, data/hora, curso, status origem/destino e inscricoes alteradas.

## Epico 7 - Envio de e-mails

- [ ] Reaproveitar o motor atual de renderizacao de templates em `mensageria.render`.
- [ ] Definir contexto por destinatario com `user`, `curso`, `inscricao` e `status_inscricao`.
- [ ] Enviar e-mail somente para participantes cujo status foi alterado com sucesso.
- [ ] Nao enviar para inscricoes ignoradas por ja estarem no status de destino.
- [ ] Registrar destinatarios sem e-mail como falha controlada.
- [ ] Registrar falhas individuais de envio sem desfazer a alteracao de status ja concluida.
- [ ] Exibir uma tela de acompanhamento ou resumo com enviados, sem e-mail e falhas.

## Epico 8 - Job assincorno simples

- [ ] Implementar job sem Celery/RQ, seguindo o padrao do projeto `relatorio-rgs-django`.
- [ ] Criar modelo de controle de lote, por exemplo `EmailStatusBatch`, com `job_id`, curso, admin, status destino, totais e status do job.
- [ ] Criar modelo de item do lote, por exemplo `EmailStatusBatchItem`, com inscricao, participante, e-mail, status de envio e mensagem de erro.
- [ ] Ao confirmar a alteracao, criar lote e itens para participantes alterados.
- [ ] Usar estados de lote como `queued`, `running`, `completed` e `failed`.
- [ ] Criar comando Django, por exemplo `python manage.py process_email_status_batch <job_id>`.
- [ ] Disparar o comando com `subprocess.Popen` dentro de `transaction.on_commit(...)`, apos criar o lote e seus itens.
- [ ] Redirecionar para uma tela de detalhe/progresso do lote.
- [ ] Implementar job idempotente, evitando reenvio para item ja marcado como enviado.
- [ ] Criar tela de progresso/resumo do lote.
- [ ] Fazer a tela de progresso atualizar automaticamente a cada 5 segundos enquanto o lote estiver em `queued` ou `running`.
- [ ] Permitir reprocessar apenas falhas, se necessario.
- [ ] Registrar log do processo em arquivo simples ou no proprio modelo do lote, para ajudar depuracao.

## Epico 9 - Permissoes e seguranca

- [ ] Proteger todas as views com `staff_member_required` ou regra equivalente de admin.
- [ ] Confirmar se grupo `GESPE` deve acessar essa feature ou se ela fica restrita a `role == "ADMIN"`.
- [ ] Validar IDs recebidos no POST no backend, sem confiar nos checkboxes do front.
- [ ] Impedir alteracao de inscricoes de outro curso.
- [ ] Garantir CSRF em todos os formularios.
- [ ] Evitar exposicao desnecessaria de CPF se nao for indispensavel na tela.

## Epico 10 - UX e estados vazios

- [ ] Mostrar mensagem amigavel quando o curso nao tiver inscricoes.
- [ ] Mostrar aviso quando participantes selecionados nao tiverem e-mail.
- [ ] Confirmar visualmente o status de destino antes de aplicar.
- [ ] Usar feedback apos submissao: sucesso, alerta parcial ou erro.
- [ ] Manter layout responsivo para secoes com muitos participantes.
- [ ] Adicionar busca/filtro dentro da tela de participantes se os cursos tiverem turmas grandes.

## Epico 11 - Testes

- [ ] Testar listagem de cursos ordenada do mais recente ao mais antigo.
- [ ] Testar agrupamento de inscricoes por status.
- [ ] Testar validacao de inscricoes pertencentes ao curso.
- [ ] Testar alteracao em lote sem envio de e-mail.
- [ ] Testar alteracao em lote com envio marcado.
- [ ] Testar que e-mail so e enviado para status alterado.
- [ ] Testar inscricao ja no status de destino.
- [ ] Testar participante sem e-mail.
- [ ] Testar permissao de acesso.
- [ ] Testar job idempotente e reprocessamento de falhas, caso o job em background seja implementado.

## MVP sugerido

1. Tela de cursos ordenada por data.
2. Tela de participantes agrupada por status.
3. Checkboxes individuais e `Marcar todos` por secao.
4. Modal com status de destino e `Enviar email`.
5. Alteracao transacional de status.
6. Envio de e-mail desacoplado em servico, inicialmente podendo rodar sincrono para validar fluxo.
7. Depois, introduzir job simples via comando Django em background e modelos de lote para producao.

## Observacoes tecnicas

- A tela atual `mensageria/enviar_emails_por_curso_status.html` pode ser preservada ou substituida pelo novo fluxo.
- O formulario atual `EnvioEmailCursoStatusForm` ordena cursos por `nome_curso`; para a nova tela, criar formulario/queryset especifico ordenando por `-data_inicio`.
- O envio atual usa `StreamingHttpResponse` e SSE; isso ajuda no acompanhamento, mas ainda roda dentro da requisicao. Para listas grandes, o job simples com comando Django em background e armazenamento de progresso e mais seguro.
- A alteracao de status e o envio de e-mail devem ser tratados como etapas separadas: primeiro muda status, depois envia e registra resultado.

## Referencia de implementacao local

No projeto `C:\workspace\relatorio-rgs-django`, o app `apps.seges_reports` implementa o padrao recomendado:

- `models.py`: modelo `SegesReportJob` com `job_id`, `status`, `current_step`, timestamps, manifest de resultado e mensagem de erro.
- `services.py`: `create_report_job(...)` cria o job e usa `transaction.on_commit(lambda: _spawn_job_processor(job.job_id))`.
- `services.py`: `_spawn_job_processor(...)` chama `subprocess.Popen([sys.executable, manage.py, process_seges_job, job_id])`, redirecionando logs para arquivo.
- `management/commands/process_seges_job.py`: comando Django que chama o servico de processamento.
- `job_detail.html`: tela de acompanhamento com refresh automatico quando o job esta em processamento.

Para esta feature, adaptar o mesmo padrao com nomes como `EmailStatusBatch`, `process_email_status_batch` e tela de detalhe do lote.
