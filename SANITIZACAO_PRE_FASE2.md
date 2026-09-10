# Saneamento pre Fase 2 — 2026-09-10

## Estado
Alteracoes locais aplicadas e testadas. Nenhum commit, branch, tag ou push criado.
Master continua em cbf91e798390bfc090684d505ed9e3e29222137a.
Snapshot bloqueado: fsck --full ainda falha por dois blobs historicos ausentes.

## Seguranca
- backend/id.txt permanece local, intacto e ignorado; removido somente do indice Git.
- ADMIN_PASSWORD e ADMIN_TOKEN nao possuem mais defaults. Todas as variaveis do
  .env.example sao obrigatorias. ADMIN_TOKEN e chave de assinatura interna (32+ caracteres).
- Login fornece sessao bearer assinada com duracao de 8 horas; nunca fornece a chave
  ADMIN_TOKEN. Senha, usuario ou chave alterados invalidam sessoes existentes.
- Admin guarda a sessao em sessionStorage, elimina o login antigo em localStorage e
  encerra a sessao local ao receber 401. Logout remove a sessao do navegador; uma copia
  roubada continua valida ate expirar ou ate rotacao das credenciais no servidor.
- O antigo authToken em admin/config.js era uma CHAVE DE ARMAZENAMENTO, nao um segredo.
- Endpoints admin corrigidos de /api/equipment para /equipment, conforme a API existente.
- Configuracao externa nao foi alterada. Rotacionar credenciais Cloudinary expostas e
  qualquer senha/token administrativo antigo utilizado. Nao republicar esses valores.
- .env.example nao e carregado automaticamente; injetar variaveis no processo backend.
- Banco PostgreSQL e upload Cloudinary reais nao foram usados nos testes.
- Historico antigo ainda contem segredos. Sanitizar a ponta nao sanitiza seus ancestrais.

## Recuperacao Git nao destrutiva
Clone mirror independente do origin em H:/TAGCHECK/tagcheck-origin-recovery-20260910.git.
Leitura binaria via cat-file e gravacao hash-object -w de quatro objetos ausentes,
com verificacao de igualdade do identificador. Nenhum objeto local foi removido.
O clone remoto passou fsck --full.
Os objetos restantes sao:
- d455846b53e0b37c0ee6b156b904d7e6f5cd2d5c — tag-main-textos.zip
- f0200559a004de2bed5bdd22716e3b3eec127e84 — imagens/anexos.zip
Nao constam do clone integral remoto; tentativa de fetch direto do primeiro foi recusada
com not our ref. Nenhuma limpeza de refs/reflogs/objetos foi executada.
As tres linhas master, origin/master e origin/main nao possuem objetos ausentes.
merge-base master origin/main agora termina com codigo 1: nao ha ancestral comum.

## Master e main
origin/master 6401810cc278b3745da6ca587601b85ead40adea: parser QR hibrido, alteracao de
apresentacao e substituicao da tabela de dados tecnicos por JSON. O parser corrigido ja
estava no arquivo local; preservado com suas melhorias. Nao aplicado o restante do commit.
origin/main 3216afa8be1b75d0ee800b0f3cbf06128e7b22aa: resposta streaming explicitada no
endpoint PDF e QR menor (0.62/0.58). Streaming ja estava no codigo local. QR menor fica
como candidato posterior, sujeito a validacao de impressao/leitura. Estilos e cache
tambem diferem. Nao houve merge entre historicos independentes.
Corrigida expressao local que tentava chamar um float no calculo do QR; mantidas
dimensoes master (0.75/0.70). Restaurados logo admin e dois icones ausentes do viewer.

## Validacao
Testes em ambiente isolado, SQLite temporario e credenciais aleatorias de teste:
configuracao ausente; importacao/inicializacao; health; login; token distinto por login;
segredo de assinatura nao retornado; rejeicao de token fixo/adulterado/expirado;
escrita protegida; geracao de PDF com equipamento; dependencias declaradas.
Seis casos de QR e analise sintatica de todos os oito arquivos JavaScript.
Referencias literais locais nos tres HTML principais verificadas.
Nenhum arquivo preexistente perdido; backend/id.txt privado preservado.
Backup original: 706 hashes conferidos sem divergencia, inclusive .git.

## Proximo passo
Recuperar os dois ZIPs historicos de outra copia confiavel, ou decidir explicitamente
como isolar o historico danificado sem perda. Definir tratamento do historico com
credenciais antes de publicar. Nenhuma implementacao multiempresa realizada.
