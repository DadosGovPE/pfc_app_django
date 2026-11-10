# PFC — dashboard de avaliações abertas

Este registro descreve somente a nova superfície administrativa de avaliações.
O aplicativo existente gerencia cursos do Programa de Formação Continuada em Django.

## Plataforma e escopo confirmado

Web em Django, com JavaScript nos gráficos e filtros. O usuário solicitou uma cópia
próxima do painel de `seplagdev/analise_sentimento_pfc`, acessível pelo menu suspenso
ao clicar no nome do usuário, exclusivamente para o perfil ADMIN do PFC.
As demais telas e regras do aplicativo permanecem fora deste escopo.

## Referência visual e funcional

Referência: <https://gitlab.pe.gov.br/seplag/seplagdev/analise_sentimento_pfc>,
commit `c83a02f495d531fedd645e6d481db7adefa52550`, arquivo `painel_template.html`.
Preservar a ordem filtros, resumo, temas/pontos de atenção, evolução mensal,
cursos e comentários, as cores de sentimento, a tipografia e os filtros combinados.
A rota é `/dashboard/avaliacoes/`; o nome no menu é **Dashboard de Avaliações**.
Usuário autenticado e ativo com `role == "ADMIN"` acessa a página e sua atualização.

## Dados e atualização

A fonte confirmada pelo usuário é a consulta salva 33 do SQL Explorer do PFC.
O SQL foi lido no navegador e conferido por conexão somente leitura no banco em
09/11/2026: 1.769 avaliações, 315 comentários escritos e 81 nomes distintos de cursos.
Não existe upload de planilha nesta integração. O nome pessoal retornado pelo SQL
não é incluído nos dados do painel.

A partir de 10/11/2026, o modelo e a classificação permanecem no servidor de NLP da
Seplag (`http://192.168.4.102/sentimento/`). O PFC fornece os textos por uma API autenticada
e recebe as classificações prontas. Não há execução de NLP no servidor web do PFC.
O sincronizador externo inicia ambas as conexões, reaproveita classificações por hash e
publica um snapshot validado. A tela apenas exibe ou recarrega esse snapshot.
A integração exige um token dedicado; resultados incompletos ou de fonte alterada são
recusados, e reenvios idênticos são idempotentes. Instalação: `docs/painel-avaliacoes.md`.

## Evidência e limites de validação

Os 65 testes automatizados passaram usando SQLite isolado. A revisão visual desktop
e celular usou a base original (312 comentários/1.740 avaliações), em uma prévia
externa ao projeto; esses dados não são enviados como seed de produção.
Depois, a atualização completa pelo navegador leu a consulta real em uma conexão
somente leitura e publicou o resultado apenas no SQLite local: 1.769 avaliações,
315 comentários, 309 textos únicos classificados e 81 nomes de cursos. Os 312
comentários presentes na referência mantiveram os mesmos sentimentos. A segunda
atualização reaproveitou todas as classificações. O encoder foi baixado e seu SHA256
conferido antes do teste. A captura final de entrega apresenta os dados reais da
prévia local. Nenhuma migração foi aplicada ao banco de produção.

Em 10/11/2026 a arquitetura foi alterada para recepção de resultados externos. Os 73 testes
passaram. A máquina do PFC foi inspecionada somente em leitura: 1 CPU, 1.928 MiB de RAM,
Python 3.10.12, Django 4.2.14 e ausência dos pacotes NLP. Nenhum código ou serviço de
produção foi alterado durante essa inspeção. A execução antiga de NLP no próprio Django,
descrita acima como evidência histórica, foi removida do código atual.

O teste completo da integração externa publicou, em SQLite local, 1.786 avaliações,
317 comentários e 82 nomes de cursos, com 311 textos únicos classificados no cliente.
A segunda execução reaproveitou o cache e foi idempotente. Django permaneceu sem importar
as bibliotecas de NLP. As duas máquinas de produção permanecem sem alterações nesta etapa.

## Implantação concluída — 10/11/2026

A API e o dashboard foram publicados no servidor PFC (10.238.75.216), com migração
0109, estáticos e recarga do Gunicorn. A integração e a ação **Atualizar do PFC** foram
instaladas no container sentimento-web da LAB-01 (192.168.4.102), preservando o modelo.
A execução real atualizou os dois painéis com 1.786 avaliações, 317 comentários e
82 cursos; a segunda execução reaproveitou as 311 classificações únicas e foi idempotente.
O acesso ao dashboard pelo menu ADMIN foi conferido no navegador em produção.
Há backups para reversão; os procedimentos estão em docs/painel-avaliacoes.md.
