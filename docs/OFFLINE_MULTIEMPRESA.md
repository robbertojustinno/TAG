# TagCheck V2 — Arquitetura offline multiempresa

## Regra de isolamento

O modo offline segue a mesma fronteira de segurança da V2: **uma empresa por contexto ativo**.

Fluxo:

`Usuário autenticado → Empresa selecionada → armazenamento offline exclusivo da empresa → fila de sincronização → API da sessão`.

Cada empresa usa um banco IndexedDB fisicamente separado no navegador:

- `tagcheck_offline_company_10`
- `tagcheck_offline_company_20`
- `tagcheck_offline_company_30`

Nenhuma consulta offline percorre bancos de outras empresas.

## Cadastro offline

Quando a API não está acessível e existe uma sessão válida já autenticada:

1. o formulário é validado normalmente;
2. o cadastro e a foto são gravados no IndexedDB da empresa ativa;
3. o registro recebe `local_id`, `company_id`, `user_id`, data/hora e `pending_sync`;
4. a interface mostra o número de cadastros aguardando envio;
5. ao recuperar a conexão, a fila é enviada usando o token da sessão atual.

A API continua sendo a autoridade. O cliente **não escolhe a empresa de destino durante a sincronização**: o backend deriva a empresa do token/sessão, como já ocorre na V2.

## Troca de empresa

Troca de empresa exige conexão. Em modo offline a empresa ativa fica bloqueada no contexto que foi validado online. Isso impede cadastrar em uma empresa e sincronizar acidentalmente em outra.

## Sessão e segurança

O contexto offline é mantido apenas em `sessionStorage` e respeita a expiração do JWT. Se a sessão expirar, novos cadastros offline não são aceitos até novo login online.

Dados de fila permanecem no banco local da empresa para não perder trabalho, mas só sincronizam quando a mesma empresa estiver autenticada novamente.

## Estados

- `pending_sync`: aguardando conexão;
- `syncing`: envio em andamento;
- `sync_error`: API rejeitou o item; permanece para correção/reenvio;
- removido da fila: sincronização confirmada pelo servidor.

## Cache

Listas de ativos, unidades e categorias são armazenadas como snapshots por empresa para consulta durante uma queda de conexão. Respostas autenticadas da API nunca são colocadas no Service Worker.

## Garantias de não mistura

1. banco IndexedDB separado por `company_id`;
2. cada linha da fila repete e valida `company_id`;
3. contexto offline vinculado à empresa selecionada;
4. sincronização usa apenas a sessão autenticada atual;
5. backend mantém a regra existente de derivar `company_id` do token;
6. TAG pode se repetir em empresas diferentes, mas continua única dentro da mesma empresa.
