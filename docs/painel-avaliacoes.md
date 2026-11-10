# Avaliações do PFC — operação e implantação

Publicado nos dois servidores em 10/11/2026.

## Uso

1. Acesse http://192.168.4.102/sentimento/ e entre com o login já usado nesse painel.
2. Clique em **Atualizar do PFC** e depois em **Buscar, classificar e publicar**.
3. A LAB-01 consulta a API do PFC, classifica apenas os comentários novos/alterados e
   atualiza os dois painéis. O modelo continua na LAB-01.
4. No PFC, acesse **nome do usuário → Dashboard de Avaliações** ou
   https://www.pfc.seplag.pe.gov.br/dashboard/avaliacoes/ . A tela exige perfil ADMIN.
   **Recarregar painel** apenas consulta a última análise publicada.

A ação também pode ser aberta diretamente em
http://192.168.4.102/sentimento/sincronizar-pfc .
O upload de planilha foi preservado como operação legada do painel da LAB;
para buscar a fonte oficial e atualizar os dois painéis, use **Atualizar do PFC**.
A execução é manual, sem agendamento periódico criado nesta implantação.

Na LAB, o mesmo fluxo completo pode ser executado por SSH:

```console
cd /home/igpe01/projetos/analise_sentimento_pfc
docker compose exec -T web python -c "from app.pfc_sync import executar; executar()"
```

## Arquitetura e autenticação

- PFC: `GET /api/avaliacoes/fonte/` lê a consulta salva 33 do SQL Explorer.
- LAB: usa o classificador original e seu cache, sem instalar NLP no PFC.
- PFC: `POST /api/avaliacoes/resultados/` recebe e publica a análise validada.
- LAB: prepara os dados locais antes do envio e publica o painel/XLSX após a confirmação do PFC.

As duas rotas exigem um token dedicado em `Authorization: Bearer ...`.
O segredo foi configurado somente nos ambientes dos dois serviços, com arquivos `.env`
restritos, e não consta deste guia, do código, dos pacotes ou das capturas.
O cliente utiliza a URL HTTPS pública do PFC, alcançável pela LAB-01.
O PFC não precisa iniciar conexões com a LAB nem acessar o Hugging Face.

A fonte contém os IDs necessários, curso, datas e comentário; o nome pessoal retornado
pelo SQL não é exposto nessa API nem no dashboard. A publicação confere o hash da fonte,
a versão do modelo, a data e exatamente uma classificação por texto não vazio.
Resultados incompletos, inválidos, mais antigos ou de uma fonte alterada são recusados.
Reenvios idênticos são idempotentes. Se os dados mudarem durante a análise, o cliente
busca a fonte novamente e reaproveita as classificações já feitas.

O cache da LAB fica em `dados/pfc/classificacoes.json`, com hashes e classificações,
sem duplicar os comentários. É salvo atomicamente a cada lote e invalidado quando o
arquivo treinado muda. Os snapshots do painel ficam em `dados/atual` e `dados/anterior`.

## Instalação realizada

### PFC — 10.238.75.216

- Aplicativo: `/var/pfc_app_django`; Python 3.10.12, Django 4.2.14.
- API, dashboard, entrada no menu ADMIN e token publicados.
- Migração `0109_painelavaliacoes` aplicada e estáticos coletados.
- Gunicorn recarregado; Gunicorn e Nginx ativos.
- PyTorch, sentence-transformers e scikit-learn continuam ausentes nesse ambiente.
- Nginx do PFC na porta 8000. A porta 80 atende outra aplicação de API/logs.

### LAB-01 — 192.168.4.102

- Projeto: `/home/igpe01/projetos/analise_sentimento_pfc`.
- Serviço: `sentimento-web`, em Docker Compose, publicado pelo gateway em `/sentimento/`.
- Adicionados `sincronizar_pfc.py`, `app/pfc_sync.py` e a ação de atualização no painel.
- O classificador, o arquivo treinado e o volume/cache dos pesos foram preservados.
- Somente o serviço de sentimento foi reconstruído/recriado; o gateway teve recarga
  de configuração após validação. O container está saudável.

Para futuras instalações, os nomes das variáveis são:

```dotenv
PFC_AVALIACOES_SYNC_TOKEN=<segredo-exclusivo-com-no-minimo-32-caracteres>
PFC_API_URL=https://www.pfc.seplag.pe.gov.br/
```

`PFC_AVALIACOES_QUERY_ID=33` pode ser configurado no PFC.
O POST tem limite de 2 MiB; confira também o limite do gateway caso o conjunto cresça.
O cliente independente aceita `--projeto-classificador`, `--pfc-url` e `--cache`.
Para atualizar também o painel local da LAB, prefira a ação web ou `app.pfc_sync.executar`.

## Validação

- 73 testes do projeto Django e 7 testes adicionais da integração LAB passaram.
- Primeira sincronização real: **1.786 avaliações, 317 comentários, 82 nomes de cursos**.
- **311 textos únicos** classificados com o modelo original.
- Segunda execução: nenhum texto novo para classificar e resposta `alterado: false`.
- Snapshot local da LAB e snapshot no banco do PFC conferidos com os mesmos totais.
- Acesso em produção pelo menu do usuário conferido no navegador.
- API sem token retorna 401; telas sem login redirecionam para autenticação.

## Backups e reversão

PFC: `/var/backups/pfc-sync-20261110T102755`.
Contém os arquivos anteriores, `.env` e um manifesto dos arquivos novos.
Restaure os arquivos correspondentes e recarregue o Gunicorn para reverter o código.
A tabela nova guarda apenas o snapshot do painel; preserve os dados ao planejar uma reversão.

LAB: `/home/igpe01/projetos/analise_sentimento_pfc/dados/deploy-backups/20261110T102909`.
Contém os arquivos anteriores, `.env`, manifesto e identificação da imagem anterior.
A imagem anterior foi preservada com a tag
`analise_sentimento_pfc-web:backup-20261110102909`.
Para reversão, restaure os arquivos/ambiente e a imagem anterior e recrie somente `web`.
Os volumes `dados` e `huggingface` devem ser preservados.

O código da integração está versionado neste repositório em `integracoes/pfc_sync/`.
`servidor_nlp/integracao.patch` registra as alterações pontuais aplicadas ao projeto
original da LAB. O remoto do PFC é `https://github.com/DadosGovPE/pfc_app_django.git`.
O repositório GitLab do classificador não foi atualizado por esta publicação.
