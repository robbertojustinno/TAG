# Administração independente por empresa — Fase 2

Implementado exclusivamente em `fase-2/multiempresa`. Não altera a Fase 1 nem configurações de conexão. Nenhuma migração foi executada em banco publicado durante este trabalho.

## Permissões e experiência

- Somente `User.is_superadmin = true` acessa empresas, usuários e vínculos globais. A API normal não aceita o campo `is_superadmin`, nem mesmo no cadastro global. A interface não oferece promoção.
- `company_admin` aparece como **Administrador** e acessa **Administração**, com identidade visual, usuários e acesso à gestão existente de equipamentos e unidades. Os demais perfis não acessam essa área.
- Criação local permite somente `supervisor`, `operator` e `viewer`. Alterar administradores exige suporte global. O proprietário define o administrador pelo vínculo global.
- Contexto local vem exclusivamente da sessão validada. Payload com `company_id` é rejeitado; query/header divergente recebe 403. Nenhum seletor novo foi introduzido: um vínculo ativo entra diretamente; contas com vários vínculos mantêm a seleção apenas entre seus vínculos autorizados.
- Listas locais não retornam privilégios globais, identificadores de empresa ou usuários sem vínculo local. Contas de Super Admin são omitidas da lista local.
- Ativar/desativar localmente modifica `UserCompany.active`, preservando a identidade global e os vínculos de outras empresas. Nome, e-mail e senha de identidades com outros vínculos (inclusive inativos) só podem ser alterados pelo suporte global. Essa restrição impede efeitos sobre outro cliente; a mensagem ao cliente não revela os outros vínculos.
- Não foram modificados usuários existentes, incluindo `admin@tagcheck.local`, Demo e Empresa Padrão. A migração mantém a política anterior de bootstrap e não promove contas existentes. A conta administrativa de produção não foi consultada neste trabalho.

## Endpoints novos

| Método | Caminho | Permissão |
| --- | --- | --- |
| GET | `/company` | Administrador da empresa; identidade da sessão |
| GET, POST | `/company/users` | Administrador da empresa; listagem/criação local |
| PATCH | `/company/users/{user_id}` | Administrador da empresa; nome, e-mail, perfil e vínculo locais |
| POST | `/company/users/{user_id}/reset-password` | Administrador da empresa; identidade exclusiva da empresa |
| GET | `/company/logo` | Qualquer sessão ativa; imagem da própria empresa |
| POST, DELETE | `/company/logo` | Administrador da empresa; logo da sessão |
| GET, POST, DELETE | `/companies/{company_id}/logo` | Somente Super Admin |

`PATCH /companies/{company_id}` passa a aceitar `admin_email`, `email_domains` e `email_exceptions`, exclusivamente para Super Admin. O painel global oferece **Identidade e e-mails** em cada empresa. `GET /auth/me` passa a retornar `logo_url`.

## Banco e logos

Migração aditiva e idempotente em `migrate_multiempresa.py`, dentro da transação existente, acrescenta seis colunas opcionais em `companies`:

- `logo_url` (VARCHAR 300): rota relativa autenticada e versão aleatória.
- `logo_data` (BYTEA no PostgreSQL / BLOB no SQLite): imagem validada, carregada sob demanda pelo ORM.
- `logo_mime` (VARCHAR 30).
- `admin_email` (VARCHAR 254).
- `email_domains` e `email_exceptions` (TEXT com listas JSON).

O armazenamento usa o banco já configurado para a Fase 2. Não usa filesystem público, disco efêmero, Cloudinary ou recursos da Fase 1 para logos. Backups do banco incluem as logos. Substituição e remoção são transacionais, sem arquivos órfãos. O custo máximo é 2 MB por empresa, além do armazenamento do banco.

Upload multipart usa somente o campo `file`. Aceita PNG, JPG/JPEG e WEBP, até 2 MB. Confere extensão, MIME e conteúdo decodificável, rejeita SVG, arquivos vazios e imagens acima de 16 milhões de pixels; reencoda a imagem, removendo metadados, animação e conteúdo anexado. O resultado também respeita 2 MB. A leitura exige autenticação, retorna `no-store` e não expõe URLs públicas. O frontend obtém a imagem com Bearer e exibe um URL de objeto, sem pôr tokens na URL.

A logo é atualizada no cabeçalho sem novo login. O Viewer autenticado carrega a logo da sessão e a limpa ao sair. Sem logo, permanece a identidade padrão TagCheck. A prévia só altera a imagem publicada após **Salvar logo**.

## Domínios

Super Admin configura um ou mais domínios exatos, normalizados para minúsculas, e exceções por endereço de e-mail. Subdomínio não é aceito implicitamente. A validação ocorre na criação local e na alteração de e-mail; mudanças de nome/perfil e login de usuários existentes continuam funcionando. Lista de domínios vazia mantém cadastro sem restrição para compatibilidade de migração. Configure a política no painel global antes de delegar o cadastro quando quiser exigir domínio.

## Validação local

99 testes aprovados, sem contar reexecuções, distribuídos pelos seguintes módulos/casos:

| Testes | Quantidade |
| --- | ---: |
| `test_company_admin.py` | 14 |
| `test_multiempresa.py` | 23 |
| `test_superadmin_management_api.py` | 4 |
| `test_migration.py` | 4 |
| `test_units.py` | 4 |
| `test_admin_login_browser.py` | 6 |
| `test_company_admin_browser.py` | 3 |
| `test_superadmin_browser.py` | 12 |
| `test_roles_viewer_browser.py` (inclui casos herdados de login) | 17 |
| `test_stabilization.py`: `test_health_and_login`, `test_protected_write` | 2 |
| `test_legacy_rotation.py` | 8 |
| `admin_contract.test.js`, `service_worker.test.js` | 2 |

Inclui IDOR bidirecional, URL/query/header/payload, usuários e senhas de outra empresa, alteração de vínculo local, restrição de perfis, bloqueio de promoção, domínios/exceções, migração de estrutura anterior e preservação de privilégios, arquivos inválidos, logos autenticadas e operações reais no navegador. Também executados `node --check` nos quatro scripts alterados e `git diff --check`.

Os módulos Python foram executados em processos separados, usando SQLite temporário; browser com Playwright/Chromium. Não foi executada a suíte inteira. Os 12 casos de Super Admin e 17 de Viewer incluem execuções focadas dos casos acrescentados, além dos módulos existentes.

## Limitações operacionais

- PostgreSQL publicado e dados atuais não foram acessados. A migração será aplicada pela inicialização existente do backend no banco configurado para a Fase 2; validar o destino e ter backup antes da atualização operacional.
- Acesso público legado da Empresa Padrão permanece como já implementado. O isolamento autenticado continua usando `company_id` da sessão.
- Não há upload público de logo, editor de imagem, recuperação por e-mail ou alteração local de senha/nome de identidades compartilhadas. Redefinição usa nova senha definida pelo administrador autorizado.
- A estrutura existente para contas vinculadas a mais de uma empresa foi preservada; somente vínculos autorizados aparecem nessa seleção. Não foi introduzida listagem global para clientes.
