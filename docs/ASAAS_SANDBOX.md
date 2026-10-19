# Asaas — preparação em Sandbox

A integração publicada nesta etapa opera exclusivamente em `https://api-sandbox.asaas.com/v3`. Não há endpoint de produção nem alteração de acesso real por pagamento simulado.

## Configuração do servidor

No serviço Render `tagcheck-fase2-hml-api`, configurar somente pelo mecanismo seguro de variáveis de ambiente:

- `ASAAS_SANDBOX_API_KEY`: chave da conta Sandbox. A conta e a chave de produção não substituem as de Sandbox.
- `ASAAS_SANDBOX_WEBHOOK_TOKEN`: segredo aleatório de pelo menos 32 caracteres, diferente da chave da API.

Não salvar esses valores no repositório, no frontend ou no chat.

Na conta Sandbox, cadastrar um webhook para:

`https://tagcheck-fase2-hml-api.onrender.com/webhooks/asaas/sandbox`

Usar o mesmo segredo como token de autenticação. Selecionar eventos de cobranças, incluindo criação, confirmação, recebimento, atraso, estorno, exclusão e chargeback. O receptor autentica `asaas-access-token`, consulta a cobrança diretamente no Asaas e confere cliente, assinatura e valor. Identificadores de eventos processados são persistidos para impedir processamento repetido. Notificações de cobrança de assinaturas desconhecidas são ignoradas. Não são aceitos dados de cartão no TagCheck.

## Fluxo no Super Admin

1. Abrir Pagamentos — Asaas (testes).
2. Selecionar empresa, informar mensalidade e forma de pagamento, salvar o plano.
3. Para disponibilizar os meios habilitados na fatura, selecionar Cliente escolhe na fatura (`UNDEFINED`). Também é possível limitar a boleto, Pix ou cartão.
4. Informar CPF/CNPJ válido para testes e primeiro vencimento; gerar assinatura de teste.
5. Consultar faturas e abrir a página de pagamento hospedada pelo Asaas.
6. Simular o pagamento pelo Sandbox. A confirmação aparece como `paid_simulated`; não converte o cliente real nem altera o prazo de teste.
7. Em caso de erro de comunicação, usar Conciliar assinatura. Uma assinatura já iniciada não pode ser criada novamente. Se a conciliação não encontrar o resultado, o estado fica `needs_review`; verificar o painel antes de uma correção operacional, evitando repetição automática.

A chave e o webhook ainda precisam ser configurados pelo titular. Os testes locais usam respostas simuladas e não demonstram conectividade com uma conta Asaas.

## Fora desta etapa

Não há cobrança de produção, ativação automática de acesso real, política de inadimplência, cancelamento de assinatura pela interface ou mudanças de valor de assinatura existente. Essas funções devem ser concluídas e validadas antes da venda automatizada. O botão manual Ativar assinatura do cadastro de empresas continua separado do Asaas e não cobra valores.

Referências oficiais consultadas: https://docs.asaas.com/reference/criar-nova-assinatura ; https://docs.asaas.com/reference/listar-cobrancas-de-uma-assinatura ; https://docs.asaas.com/docs/sobre-os-webhooks ; https://docs.asaas.com/docs/cobrancas-via-cartao-de-credito .
