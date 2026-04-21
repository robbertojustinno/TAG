# TagCheck Viewer V2

Projeto separado, leve e profissional para **consulta** de instrumentos por **QR** ou **TAG**, em **modo somente leitura**.

## O que a V2 melhora

- Corrige a estratégia de cache do service worker para reduzir problemas de conteúdo antigo em outro navegador
- Suporte a abertura direta por URL com `?tag=...` ou `?id=...`
- Consulta manual por TAG
- Scanner QR com fallback híbrido
- Entrada manual do conteúdo do QR para testes
- Painel de saúde da API
- Consulta recente com cache local
- Botão de atualizar dados do instrumento
- PWA instalável no celular

## Passo 1 — apontar para seu backend

Edite `config.js`:

```js
API_BASE_URL: 'https://SEU-BACKEND-AQUI.onrender.com'
```

Troque pelo backend real do TagCheck Admin/API.

## Passo 2 — testar localmente

```bash
python -m http.server 8080
```

Depois abra:

```txt
http://localhost:8080
```

## Deploy no Render

Como Static Site.

- Build Command: vazio
- Publish Directory: `.`

## QR aceito

- Link com TAG
- Link com ID
- JSON
- Texto híbrido `TAG:...|NOME:...|SERIAL:...`
- Texto simples com TAG

## Observação

Esta V2 já foi preparada para ser evoluída depois para integração 100% no padrão real do seu backend.
