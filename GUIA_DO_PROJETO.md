# Guia técnico do TagCheck

Estado documentado em 14/09/2026. Este guia descreve os arquivos e comportamentos atuais da Fase 2; não representa uma nova auditoria nem confirma o estado dos serviços publicados.

## 1. Projeto oficial

- Pasta: `E:\ROVIX_AUTOMATION\01_PRODUTOS\TAGCHECK_FASE2_CLEAN`.
- GitHub: https://github.com/robbertojustinno/TAG
- Remote: `origin`.
- Branch de trabalho: `fase-2/multiempresa`. Não trabalhar em `main` ou `master`.
- Backend: FastAPI, SQLAlchemy, PostgreSQL/SQLite, autenticação JWT e hashes Argon2.
- Frontend: HTML, CSS e JavaScript estáticos, sem etapa de build local.
- `admin/`: administração. `viewer/`: viewer específico atual, configuração versão 7.1.0. A raiz também contém um viewer V2 independente; seus arquivos não são os mesmos de `viewer/`.
- Os arquivos `render.yaml` existentes descrevem o site estático; não provisionam o backend e o PostgreSQL.

## 2. Ambiente e inicialização

Em PowerShell, na pasta oficial:

```powershell
Set-Location -LiteralPath 'E:\ROVIX_AUTOMATION\01_PRODUTOS\TAGCHECK_FASE2_CLEAN'
git branch --show-current
git status --short
# Apenas se ainda não existir ambiente virtual:
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

Configure as variáveis no processo que iniciará o backend. `.env.example` é somente um modelo: o aplicativo não carrega `.env` automaticamente. Um novo terminal não herda variáveis definidas em outro terminal já aberto.

| Variável | Uso atual |
| --- | --- |
| `DATABASE_URL` | Conexão SQLAlchemy obrigatória; PostgreSQL ou SQLite |
| `ADMIN_USERNAME` | Identificação do login administrativo legado |
| `ADMIN_PASSWORD` | Credencial administrativa legada, também usada na migração |
| `ADMIN_EMAIL` | Opcional; identidade estável do administrador migrado; padrão definido em `backend/main.py` |
| `ADMIN_TOKEN` | Chave de assinatura exclusiva do servidor, com pelo menos 32 caracteres; não é o token de sessão do navegador |
| `CLOUDINARY_CLOUD_NAME` | Configuração de upload no servidor |
| `CLOUDINARY_API_KEY` | Configuração de upload no servidor |
| `CLOUDINARY_API_SECRET` | Segredo de upload no servidor |
| `TAGCHECK_BROWSER_EXECUTABLE` | Opcional, caminho do navegador nos testes Playwright |

Para fornecer valores sem gravá-los neste guia ou digitá-los como literais no histórico do PowerShell:

```powershell
function Set-PrivateProcessVariable([string]$Name) {
    $value = Read-Host "Informe $Name" -AsSecureString
    $plain = [System.Net.NetworkCredential]::new('', $value).Password
    [Environment]::SetEnvironmentVariable($Name, $plain, 'Process')
    Remove-Variable plain, value
}
Set-PrivateProcessVariable DATABASE_URL
Set-PrivateProcessVariable ADMIN_USERNAME
Set-PrivateProcessVariable ADMIN_PASSWORD
Set-PrivateProcessVariable ADMIN_TOKEN
Set-PrivateProcessVariable CLOUDINARY_CLOUD_NAME
Set-PrivateProcessVariable CLOUDINARY_API_KEY
Set-PrivateProcessVariable CLOUDINARY_API_SECRET
# Se necessário, antes da primeira migração:
Set-PrivateProcessVariable ADMIN_EMAIL
```

Os valores ficam no ambiente do processo, acessíveis ao backend. Não imprima nem publique esse ambiente. Use valores exclusivos de desenvolvimento para testes locais.

### Banco e backend

Formato ilustrativo, sem conexão real: `postgresql://<usuario>:<valor-protegido>@<host>:<porta>/<banco>`. Caracteres reservados dos componentes precisam de codificação de URL. O backend normaliza o prefixo `postgres://` para `postgresql://`.

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

A importação do backend executa a migração automaticamente. Confira o destino do banco antes de iniciar. Endpoints locais: `http://127.0.0.1:8000/health` e `http://127.0.0.1:8000/docs`.

Para executar somente a migração, com o ambiente configurado:

```powershell
.\.venv\Scripts\python.exe backend/migrate_multiempresa.py
```

### Frontend

Para testes manuais, ajuste localmente `API_BASE_URL` em `admin/config.js` e `viewer/config.js` para `http://127.0.0.1:8000`. Ajuste `VIEWER_BASE_URL` em `admin/config.js` para `http://127.0.0.1:8080/viewer/`. Se usar o viewer da raiz, ajuste também `config.js` da raiz. Os arquivos de Admin e Viewer atualmente apontam para serviços publicados; não os use inadvertidamente para gravar dados de teste.

Em outro terminal na raiz:

```powershell
.\.venv\Scripts\python.exe -m http.server 8080 --bind 127.0.0.1
```

- Admin: `http://127.0.0.1:8080/admin/`.
- Viewer: `http://127.0.0.1:8080/viewer/`.
- Viewer V2 da raiz: `http://127.0.0.1:8080/`.

Esse servidor é apenas local e serve arquivos da pasta. Não o exponha na rede. Não publique ajustes locais de URL por acidente. Se uma alteração visual não aparecer, verifique o cache e o service worker do viewer correspondente no navegador.

## 3. Estrutura de dados

`Empresa → Unidade → Equipamento`

Um equipamento sempre pertence a uma empresa; a unidade é opcional. Também existe `Empresa → Equipamento` sem unidade.

| Modelo | Tabela | Responsabilidade |
| --- | --- | --- |
| `Company` | `companies` | Empresa, nome, slug único, estado ativo e data de criação |
| `User` | `users` | Usuário com e-mail único, hash de senha, estado ativo e indicador `is_superadmin` |
| `UserCompany` | `user_companies` | Vínculo único usuário/empresa, papel e estado ativo |
| `Unit` | `units` | Unidade de uma empresa; slug único dentro daquela empresa |
| `Equipment` | `tagcheck_equipment` | Equipamento com empresa obrigatória e unidade opcional, TAG, foto e dados técnicos |

`Equipment.company_id` referencia `Company`; `Equipment.unit_id` referencia `Unit`. A API verifica se a unidade pertence à empresa da sessão. As FKs individuais não substituem essa verificação de correspondência entre empresas. A TAG permanece globalmente única, inclusive entre empresas.

A migração em `backend/migrate_multiempresa.py` cria a Empresa Padrão, migra a identidade administrativa e associa equipamentos legados sem empresa à Empresa Padrão. Preserva os registros e IDs existentes. No PostgreSQL usa transação e advisory lock; a repetição é idempotente. Não há migração reversa automática implementada.

## 4. Login, empresa ativa e permissões

O Admin envia e-mail e senha para `POST /auth/login`. Com um vínculo ativo, recebe uma sessão da empresa. Com vários vínculos ativos, recebe uma credencial temporária de seleção e deve chamar `POST /auth/select-company`. Sem empresa permitida, o login é negado. `GET /auth/me` informa o contexto autenticado.

A seleção dura até 5 minutos e a sessão até 8 horas. O login legado por `ADMIN_USERNAME` continua disponível e se restringe à Empresa Padrão. Não confundir o nome de exibição de um usuário com sua identidade por e-mail.

Papéis de `UserCompany`: `company_admin`, `supervisor`, `operator` e `viewer`. Operador pode criar/editar equipamentos; exclusão exige supervisor ou administrador da empresa. Viewer tem leitura. A gestão de unidades exige administrador da empresa ou Super Admin. A autorização efetiva é implementada em `backend/tenancy.py` e `backend/admin_api.py`.

### Super Admin

É o indicador `User.is_superadmin`, não um papel de `UserCompany`. A interface fica em `admin/superadmin.js`, integrada ao Admin. Permite gerir empresas, usuários, estados ativos e vínculos pelas rotas `/companies`, `/users` e `/users/{id}/companies`. Continua precisando de vínculo/empresa ativa para operar no contexto de equipamentos e unidades. A migração cria o administrador legado como Super Admin quando essa identidade ainda não existe; não promove automaticamente qualquer usuário já existente com o mesmo e-mail.

### Viewer público da Empresa Padrão

Leituras sem autenticação são limitadas à Empresa Padrão ativa. O viewer público não oferece acesso anônimo aos equipamentos das demais empresas. O QR não concede autorização. Os viewers podem exibir cache local ou conteúdo mínimo do QR como fallback; isso não confirma dados atuais no banco.

## 5. Mapa rápido: QUERO ALTERAR → ARQUIVO

| QUERO ALTERAR | ARQUIVO |
| --- | --- |
| Logo do Admin | `admin/public/logo.png`; referência em `admin/index.html` |
| Logo do Viewer | `viewer/public/logo.png`; referência em `viewer/index.html` |
| Logo do viewer da raiz | `public/icons/icon.svg`; referência em `index.html` |
| Nome do sistema | `admin/index.html`, traduções `brandTitle` em `admin/app.js`, `admin/config.js`; no viewer, `viewer/index.html`, `viewer/config.js`, `viewer/manifest.webmanifest`; equivalentes da raiz para o V2 |
| Cores | Variáveis de `:root` em `admin/styles.css`, `viewer/styles.css` ou `styles.css` da raiz |
| Tamanhos de logo, fontes, cartões e espaçamento | Seletores, medidas e media queries nos mesmos arquivos CSS |
| URL da API | `admin/config.js`, `viewer/config.js`; `config.js` apenas para o viewer da raiz |
| URL de abertura do Viewer pelo Admin | `VIEWER_BASE_URL` em `admin/config.js` |
| Conexão com o banco | Variável de processo `DATABASE_URL`; consumo em `backend/main.py` e `backend/migrate_multiempresa.py` |
| Modelos e estrutura do banco | `backend/models.py`, `backend/migrate_multiempresa.py` |
| Login e seleção de empresa | `admin/app.js`, `backend/admin_api.py`, `backend/tenancy.py`, `backend/passwords.py` |
| Empresas, usuários e vínculos | `admin/superadmin.js`, `backend/admin_api.py`, `backend/models.py` |
| Unidades | `backend/admin_api.py`, `backend/models.py`; carregamento e seleção no Admin em `admin/app.js` |
| Equipamentos e filtro por unidade | `backend/main.py`, `backend/models.py`, `admin/app.js` |
| QR e conteúdo do QR | `backend/main.py` (rota `qr-payload` e geração), `admin/app.js` (abertura do viewer), `viewer/app.js` (leitura); `app.js` para o V2 |
| PDF e tamanho das etiquetas | `equipment_pdf_labels` e rotas PDF em `backend/main.py`; acionamento em `admin/app.js` |
| Cache/PWA | `viewer/sw.js`, `viewer/manifest.webmanifest`; equivalentes na raiz para o V2 |
| Dependências | `backend/requirements.txt`, `tests/requirements.txt` |

## 6. Arquivos críticos e testes locais

Não alterar sem backup e revisão: `backend/models.py`, `backend/migrate_multiempresa.py`, `backend/main.py`, `backend/tenancy.py`, `backend/admin_api.py`, `backend/passwords.py`, `admin/app.js`, `admin/superadmin.js`, `viewer/app.js`, `app.js`, configurações de API, service workers, manifests, arquivos `render.yaml` e listas de dependências. Inclua os assets originais no backup antes de substituir logos. Preserve separadamente o banco e as configurações privadas; Git não cobre esses dados.

Os arquivos `tests/test_migration.py`, `tests/test_multiempresa.py`, `tests/test_units.py`, `tests/test_equipment_units.py` e `tests/test_equipment_unit_filter.py` são pontos de partida para testes locais. As fixtures atuais usam SQLite temporário e uploads simulados. Arquivos novos de experimentação devem ficar fora dos caminhos publicados, de preferência em uma pasta temporária externa. `.env.example` pode orientar configuração, mas nunca receber valores privados. CSS, HTML e configurações versionadas não são descartáveis: faça experiências em branch/cópia local e revise o diff.

### PostgreSQL de teste

O banco de teste é `tagcheck_fase2_test`. Configure `DATABASE_URL` por entrada privada usando host, porta e usuário autorizados para esse banco. Antes de migrar, confira somente o nome do destino, sem imprimir a URL:

```powershell
.\.venv\Scripts\python.exe -c "import os; from sqlalchemy import create_engine,text; e=create_engine(os.environ['DATABASE_URL'].replace('postgres://','postgresql://',1)); c=e.connect(); n=c.scalar(text('SELECT current_database()')); assert n=='tagcheck_fase2_test', 'Banco incorreto'; print(n); c.close(); e.dispose()"
.\.venv\Scripts\python.exe backend/migrate_multiempresa.py
.\.venv\Scripts\python.exe backend/migrate_multiempresa.py
```

Depois inicie o backend com esse mesmo ambiente. Use usuários, empresas e equipamentos fictícios. Upload manual de equipamento usa a configuração real de upload do processo: use um ambiente de desenvolvimento apropriado.

A validação anterior passou nesse PostgreSQL real em schemas temporários: 25 testes focados de API, migração nova/legada, FKs, constraints, índices, idempotência e rollback. Os schemas foram removidos; o `public` ficou vazio naquele momento. O executor dessa validação foi temporário e não está versionado. Os testes existentes não passam a usar PostgreSQL apenas por definir `DATABASE_URL`, pois suas fixtures a substituem por SQLite. Repetir a integração PostgreSQL exige um executor isolado equivalente; os dois comandos acima verificam a execução repetida da migração, não reproduzem toda aquela validação.

### Testes rápidos

Instale as dependências de teste quando necessário:

```powershell
.\.venv\Scripts\python.exe -m pip install -r tests/requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_migration.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_units.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_equipment_units.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_equipment_unit_filter.py -v
```

Escolha somente os módulos relacionados à mudança. Esses comandos são testes locais, não validação do PostgreSQL publicado.

### Testes completos

Requer Python com dependências de teste, Node.js e Chromium/Chrome/Edge. Playwright aceita `TAGCHECK_BROWSER_EXECUTABLE`; alternativamente instale Chromium:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
# Executa cada módulo em processo separado, incluindo scripts de navegador:
Get-ChildItem -LiteralPath tests -Filter 'test_*.py' | Sort-Object Name | ForEach-Object {
    & .\.venv\Scripts\python.exe $_.FullName
    if ($LASTEXITCODE -ne 0) { throw "Falha: $($_.Name)" }
}
$jsTests = @(Get-ChildItem -LiteralPath tests -Filter '*.test.js' | ForEach-Object { $_.FullName })
node --test @jsTests
if ($LASTEXITCODE -ne 0) { throw 'Falha nos testes JavaScript' }
```

A execução separada evita compartilhar o estado das fixtures entre módulos. A suíte completa está documentada para uso futuro; não foi executada para criar este guia.

## 7. Backup

Escolha uma pasta de backup fora do projeto e fora da publicação web. Para preservar o histórico Git e os arquivos versionados do commit atual:

```powershell
$backupDir = Read-Host 'Pasta externa para backup'
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
git status --short
git bundle create (Join-Path $backupDir "tagcheck-$stamp.bundle") --all
git archive --format=zip --output=(Join-Path $backupDir "tagcheck-$stamp.zip") HEAD
```

Bundle e ZIP não incluem alterações sem commit nem arquivos ignorados. Copie separadamente qualquer trabalho local necessário. Preserve configurações privadas em armazenamento protegido, nunca dentro do repositório ou do site. Imagens hospedadas externamente precisam de backup próprio; o banco guarda suas referências.

Para PostgreSQL, use `pg_dump` instalado e informe os dados de conexão por parâmetros sem senha literal; `-W` solicita a senha de forma interativa:

```powershell
$pgHost = Read-Host 'Host do banco'
$pgPort = Read-Host 'Porta do banco'
$pgUser = Read-Host 'Usuario do banco'
$pgDatabase = Read-Host 'Nome do banco confirmado'
$dumpPath = Join-Path $backupDir "tagcheck-db-$stamp.dump"
pg_dump -h $pgHost -p $pgPort -U $pgUser -W -d $pgDatabase -Fc -f $dumpPath
if ($LASTEXITCODE -ne 0) { throw 'Backup do banco falhou' }
pg_restore --list $dumpPath
```

Confira o resultado e teste a restauração em um banco separado. Listar o dump não comprova sozinho que a restauração funciona.

## 8. Rollback

Para desfazer um commit publicado, com árvore de trabalho limpa e na branch correta, preserve o histórico:

```powershell
git switch fase-2/multiempresa
git status --short
git log -5 --oneline
$commitToRevert = Read-Host 'SHA do commit a reverter'
git revert $commitToRevert
# Após revisar e validar o resultado:
git push origin HEAD:refs/heads/fase-2/multiempresa
```

Não usar `reset --hard` ou push forçado como rotina de rollback. Reverter código não restaura dados nem desfaz a migração do banco. Para rollback de banco, interrompa gravações, faça backup do estado atual e restaure um dump compatível em um banco vazio separado:

```powershell
$restoreDatabase = Read-Host 'Banco vazio separado para restauracao'
pg_restore -h $pgHost -p $pgPort -U $pgUser -W -d $restoreDatabase --exit-on-error --no-owner --no-privileges $dumpPath
```

Depois de validar os dados e a compatibilidade com o código, ajuste `DATABASE_URL` no ambiente e reinicie o backend. Lembre que iniciá-lo executará sua migração. Não restaure por cima de um banco em uso sem um plano específico.

## 9. Pontos críticos de segurança

- Nunca colocar credenciais, conexões privadas, chaves de assinatura ou valores de upload em HTML, JavaScript, Git, logs ou PDFs.
- A empresa efetiva vem do contexto autenticado. Preserve filtros de empresa em leitura, alteração, exclusão, QR, PDF e unidades; não confiar em IDs enviados pelo navegador.
- Preserve a validação de unidade da mesma empresa na API, além das FKs do banco.
- Usuário, empresa e vínculo precisam estar ativos. A sessão revalida permissões; não substituir isso por controles apenas visuais.
- Senhas ficam como hashes Argon2. A identidade administrativa do ambiente é autoritativa na migração: alterar sua credencial pode atualizar o hash e invalidar sessões anteriores.
- Tokens de sessão, seleção e PDF têm propósitos separados. O acesso temporário ao PDF dura até 120 segundos; não reutilizá-lo como sessão nem colocá-lo na URL.
- `is_superadmin` concede administração global; conceda somente a usuários apropriados. O isolamento de equipamentos continua vinculado à empresa selecionada.
- A Empresa Padrão é pública para leitura anônima enquanto ativa. Não colocar nela dados que devam exigir login.
- CORS está configurado com origens amplas e sem credenciais de cookie em `backend/main.py`; CORS não substitui autenticação. Use HTTPS na publicação e preserve o tratamento seguro de respostas e tokens.
- O frontend e seus caches são acessíveis ao usuário. Preserve escape de conteúdo e proteção contra injeção; não inserir HTML arbitrário de dados cadastrados.
