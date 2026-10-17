# Entrega de acesso ao cliente

1. Após a contratação, o responsável ROVIX recebe os dados da empresa e de seu administrador.
2. Em Super Admin → Cadastrar cliente e administrador, informa uma nova empresa (ou seleciona uma empresa existente ainda sem administrador) e define a senha inicial.
3. O sistema cria empresa, usuário e vínculo de administrador na mesma transação. Não há criação parcial se um dado estiver duplicado.
4. O cliente entra em https://tagcheck.com.br/ com e-mail e senha inicial. A troca de senha é obrigatória antes de obter a sessão de acesso aos dados.
5. Em sua empresa, o administrador cria unidades e usuários, com os perfis Supervisor, Operador e Somente leitura. O cadastro de empresas e administradores iniciais continua exclusivo do Superadmin.

## Senha esquecida

O login oferece “Esqueci minha senha”. A solicitação não confirma publicamente se o e-mail existe. O administrador encontra solicitações de seus usuários em Administração → Recuperação de senha; o Superadmin atende as solicitações de administradores e de identidades compartilhadas entre empresas.

Antes de liberar um link, o responsável verifica a identidade por um canal conhecido. O link pode ser copiado e entregue ao titular pelo canal de suporte. **Não há envio automático por e-mail**: nenhum provedor de correio foi configurado para este recurso.

Os links expiram em 30 minutos, são de uso único e ficam apenas como digest no banco. Reemitir um link revoga os anteriores. O titular define uma nova senha sem fornecer a antiga. A troca invalida as sessões antigas. A conta técnica inicial, cuja credencial é gerenciada na infraestrutura, exige recuperação pelo responsável técnico; os administradores comerciais usam o fluxo normal.

A recuperação não altera empresa, perfil ou permissões. Um administrador de empresa não pode recuperar contas globais, de outras empresas ou de outros administradores. Solicitações são limitadas por e-mail e origem; o banco guarda digests de origem e e-mail, sem IP em texto.
