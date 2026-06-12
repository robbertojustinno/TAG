TAGCheck Campo Offline

Como usar:
1. Publique esta pasta como Static Site no Render ou abra via servidor local.
2. Acesse com HTTPS no celular e instale como app.
3. Com internet, informe API, usuário e senha do TAGCheck e clique em Entrar e salvar token.
4. Vá ao campo sem sinal, cadastre instrumentos e tire fotos. Tudo fica salvo no aparelho.
5. Ao voltar o sinal, clique em Sincronizar pendentes.

Endpoint usado:
POST /equipment para criar.
Se a TAG já existir, o app usa GET /equipment/tag/{tag} e PUT /equipment/{id} para atualizar.

Importante:
- Câmera/PWA funcionam melhor em HTTPS.
- Não limpe os dados do navegador antes de sincronizar.
- Use Exportar pendentes JSON como backup antes de grandes campanhas.
