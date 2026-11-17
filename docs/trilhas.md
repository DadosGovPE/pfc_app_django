# Ativação e histórico de trilhas

O campo **Está ativa** controla as novas escolhas de trilha. Ele pode ser alterado
diretamente na lista de trilhas do administrador, que também permite filtrar por
esse campo.

## Cadastros

Cursos, curadorias, cursos priorizados, cursos da pesquisa de priorização e
validações de carga horária oferecem somente trilhas ativas na criação.

Ao editar um registro, sua trilha atual também fica disponível, mesmo inativa.
Isso permite manter o vínculo ao corrigir outros campos. Outra trilha inativa
não pode ser escolhida. A mesma regra vale para edição em lista de cursos
priorizados e cursos da pesquisa, individualmente por registro.

## Pesquisa de priorização

A pesquisa mostra somente trilhas com cursos disponíveis no ano configurado.
Novos votos são permitidos em cursos de trilhas ativas. Se a pessoa já escolheu
um curso cuja trilha foi desativada, essa escolha continua visível e pode ser
mantida ou retirada. Os demais cursos dessa trilha inativa não são oferecidos.
Votos de outros anos são preservados ao atualizar a resposta.

## Fusão de trilhas

1. Cadastre a nova trilha.
2. Vincule a ela os novos registros.
3. Desmarque **Está ativa** nas trilhas anteriores quando deixar de oferecê-las.
4. Mantenha os nomes e vínculos dos registros históricos.

Desativar uma trilha não exclui registros nem troca seus vínculos. Relatórios,
agenda e filtros de consulta continuam incluindo trilhas inativas para permitir
consultar períodos anteriores. O controle é manual; não há vigência por data.

Essa regra utiliza o campo existente e não exige migração de banco de dados.
