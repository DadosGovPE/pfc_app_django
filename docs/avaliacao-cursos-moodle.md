# Avaliacao de Cursos Moodle

## Contexto

O app ja possui sincronizacao com o Moodle. Quando uma pessoa conclui um curso no Moodle, o sistema consulta a API do Moodle e grava as informacoes em tabelas proprias do app, principalmente em `CursoConcluidoMoodle` e `CursoCompletoUsuario`.

Hoje a avaliacao de curso do PFC depende de `Curso`, `Inscricao`, `periodo_avaliativo`, status do curso e conclusao da inscricao. Cursos Moodle nao seguem esse mesmo modelo, porque nao existem como registros de `Curso`/`Inscricao` no PFC.

## Objetivo

Permitir que cursos Moodle concluidos:

- aparecam na aba **Meus Cursos**;
- possam ser avaliados pelo usuario;
- permitam geracao de certificado;
- nao dependam da regra de "aberto para avaliacao", pois sao cursos permanentes.

## Regra Principal

Para cursos Moodle, a entrada na tabela de cursos Moodle concluidos ja deve liberar a avaliacao.

Ou seja:

- se existe `CursoConcluidoMoodle` para o usuario e o curso Moodle, o usuario pode avaliar;
- nao precisa verificar `periodo_avaliativo`;
- nao precisa verificar `StatusCurso = FINALIZADO`;
- nao precisa verificar `Inscricao`;
- deve impedir avaliacao duplicada.

## Arquitetura Recomendada

Criar modelos especificos para avaliacao Moodle no app `moodle_sync`, em vez de reaproveitar diretamente `Avaliacao` e `AvaliacaoAberta`.

Motivo: os modelos atuais de avaliacao apontam para `Curso`, mas o curso Moodle nao e um `Curso` do PFC. Separar os modelos reduz risco de quebrar regras ja existentes para cursos presenciais/PFC.

Modelos sugeridos:

```python
class AvaliacaoMoodle(models.Model):
    curso_moodle = models.ForeignKey(CursoConcluidoMoodle, on_delete=models.CASCADE)
    participante = models.ForeignKey(User, on_delete=models.CASCADE)
    subtema = models.ForeignKey(Subtema, on_delete=models.CASCADE)
    nota = models.TextField(choices=notas)


class AvaliacaoAbertaMoodle(models.Model):
    curso_moodle = models.ForeignKey(CursoConcluidoMoodle, on_delete=models.CASCADE)
    participante = models.ForeignKey(User, on_delete=models.CASCADE)
    avaliacao = models.TextField(max_length=4000, blank=True, null=True)
```

Tambem e recomendavel criar restricoes ou validacoes para evitar duplicidade por usuario, curso e subtema.

## Tela Meus Cursos

A view `inscricoes` deve carregar:

- inscricoes PFC atuais;
- cursos Moodle concluidos do usuario.

No template `pfc_app/inscricoes.html`, incluir uma secao para cursos Moodle com campos como:

- ID Moodle;
- ano de conclusao;
- nome do curso;
- status: concluido;
- carga horaria;
- acao: `AVALIAR` ou `AVALIADO`;
- certificado.

## Avaliacao Moodle

Criar rota separada:

```python
path(
    "avaliacao/moodle/<int:curso_moodle_id>/",
    views.avaliacao_moodle,
    name="avaliacao_moodle",
)
```

Fluxo da view:

1. Buscar `CursoConcluidoMoodle` pelo `curso_moodle_id` e `request.user`.
2. Se nao existir, bloquear acesso.
3. Verificar se ja existe avaliacao Moodle para esse usuario/curso.
4. Em `GET`, renderizar formulario de avaliacao.
5. Em `POST`, salvar notas por subtema e avaliacao aberta.
6. Redirecionar para `inscricoes`.

O template `pfc_app/avaliacao.html` pode ser reaproveitado, desde que receba um objeto com nome do curso ou seja ajustado para aceitar um contexto Moodle.

## Certificado Moodle

Criar rota separada:

```python
path(
    "certificado/moodle/<int:curso_moodle_id>/",
    views.generate_moodle_pdf,
    name="generate_moodle_pdf",
)
```

A geracao pode reaproveitar a estrutura atual do certificado PFC, trocando o mapeamento de tags:

- `[nome_completo]`: nome do usuario;
- `[cpf]`: CPF formatado;
- `[nome_curso]`: `CursoConcluidoMoodle.nome_curso`;
- `[data_inicio]`: `CursoCompletoUsuario.data_inicio_curso_moodle`, se disponivel;
- `[data_termino]`: `CursoConcluidoMoodle.data_conclusao` ou `CursoCompletoUsuario.data_fim_curso_moodle`;
- `[curso_carga_horaria]`: carga horaria Moodle;
- `[condicao_na_acao]`: `discente`.

## Regra do Certificado

Opcao recomendada:

- curso Moodle concluido libera avaliacao;
- certificado Moodle so aparece depois da avaliacao.

Essa regra mantem a avaliacao como etapa do fluxo, semelhante aos cursos PFC.

Opcao alternativa:

- liberar certificado imediatamente quando o curso entrar como concluido.

Essa alternativa e mais simples para o usuario, mas reduz a chance de coleta da avaliacao.

## Admin e Relatorios

Registrar os novos modelos no admin para permitir consulta das avaliacoes Moodle.

Em uma etapa posterior, avaliar se os relatorios de avaliacao devem:

- exibir PFC e Moodle separados;
- consolidar PFC + Moodle em uma mesma visao;
- filtrar por origem do curso.

## Checklist de Implementacao

- [ ] Criar modelos `AvaliacaoMoodle` e `AvaliacaoAbertaMoodle`.
- [ ] Criar migration.
- [ ] Registrar modelos no admin.
- [ ] Criar view `avaliacao_moodle`.
- [ ] Criar URL `avaliacao_moodle`.
- [ ] Adaptar `inscricoes` para buscar cursos Moodle concluidos.
- [ ] Atualizar `pfc_app/inscricoes.html` com secao Moodle.
- [ ] Criar view de certificado Moodle.
- [ ] Criar URL de certificado Moodle.
- [ ] Reaproveitar ou extrair helper de geracao de PDF.
- [ ] Validar bloqueio de avaliacao duplicada.
- [ ] Rodar `python manage.py check`.
- [ ] Criar ou ajustar testes focados.

