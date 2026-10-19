/* Asaas sandbox billing management. Credentials remain server-side. */
window.TAGCHECK_BILLING = {
  async mount(host, companies, request, escape) {
    const status = await request('/superadmin/billing/status');
    const states = {draft:'Plano em preparação',creating:'Criação em andamento',awaiting_payment:'Aguardando pagamento',paid_simulated:'Pagamento de teste recebido',needs_review:'Revisão necessária'};
    const types = {UNDEFINED:'Cliente escolhe na fatura',BOLETO:'Boleto',PIX:'Pix',CREDIT_CARD:'Cartão'};
    const money = value => new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(Number(value||0));
    const paymentStatus = {RECEIVED:'Recebido',CONFIRMED:'Confirmado',PENDING:'Pendente',OVERDUE:'Vencido',REFUNDED:'Estornado',RECEIVED_IN_CASH:'Recebido em dinheiro'};
    const dateLabel = value => /^\d{4}-\d{2}-\d{2}$/.test(value||'') ? value.split('-').reverse().join('/') : value||'—';
    host.classList.add('billing-workspace');
    host.innerHTML = `<div class="billing-heading"><div><p class="section-kicker">GESTÃO FINANCEIRA</p><h3>Pagamentos</h3><p class="subtle">Planos, assinaturas e faturas por empresa.</p></div><span class="status-pill billing-test-badge">Ambiente de testes</span></div>
      <div class="billing-connections"><span class="status-pill ${status.api_configured?'status-ok':'status-danger'}">${status.api_configured?'API conectada':'API não configurada'}</span><span class="status-pill ${status.webhook_configured?'status-ok':'status-danger'}">${status.webhook_configured?'Confirmações configuradas':'Confirmações pendentes'}</span></div>
      <p class="billing-notice">Sem cobranças reais. Pagamentos simulados não alteram o acesso dos clientes.</p>
      <div class="billing-selector"><label for="billingCompany">Selecione a empresa</label><select id="billingCompany" class="input"><option value="">Escolha uma empresa</option>${companies.map(c=>`<option value="${c.id}">${escape(c.name)}</option>`).join('')}</select></div>
      <div id="billingDetails"><div class="billing-empty">Selecione uma empresa para consultar ou configurar seu plano.</div></div>`;
    const select = host.querySelector('#billingCompany'), details = host.querySelector('#billingDetails');
    let generation = 0;
    const load = async () => {
      const version = ++generation, id = select.value;
      if (!id) {details.innerHTML='<div class="billing-empty">Selecione uma empresa para consultar ou configurar seu plano.</div>';return;}
      details.textContent='Carregando plano…';
      try {
        const plan=await request(`/companies/${id}/billing`);
        if(version!==generation)return;
        const editable=!plan||plan.state==='draft', subscribed=!!plan?.subscription_id;
        details.innerHTML=`<div class="billing-summary"><div><span class="subtle">Situação da assinatura</span><h4>${escape(states[plan?.state]||plan?.state||'Sem plano cadastrado')}</h4>${plan?.last_payment_status?`<span class="subtle">Último pagamento: ${escape(paymentStatus[plan.last_payment_status]||plan.last_payment_status)}</span>`:''}</div><div><span class="subtle">Mensalidade</span><strong>${plan?money(plan.monthly_value):'—'}</strong></div><div><span class="subtle">Forma de pagamento</span><strong>${escape(types[plan?.billing_type]||'A definir')}</strong></div><button id="billingRefresh" type="button" class="outline-button">Atualizar</button></div>
          <div class="billing-setup" ${subscribed?'hidden':''}>
            <section class="billing-box"><h4><span class="billing-step">1</span> Configure o plano</h4><p class="subtle">Defina o valor mensal e a forma de pagamento.</p><form id="billingPlanForm" class="billing-form"><label>Mensalidade (R$)<input class="input" name="monthly_value" type="number" min="0.01" max="100000" step="0.01" required value="${escape(String(plan?.monthly_value||''))}" ${editable?'':'disabled'}></label><label>Forma de pagamento<select class="input" name="billing_type" ${editable?'':'disabled'}>${Object.entries(types).map(([key,value])=>`<option value="${key}" ${plan?.billing_type===key?'selected':''}>${value}</option>`).join('')}</select></label><button class="primary-button" ${editable?'':'disabled'}>Salvar plano</button></form></section>
            <section class="billing-box"><h4><span class="billing-step">2</span> Gere a assinatura</h4><p class="subtle">Salve o plano antes de criar a assinatura de teste.</p><form id="billingSubscribeForm" class="billing-form"><label>CPF ou CNPJ do pagador<input class="input" name="cpf_cnpj" inputmode="numeric" placeholder="Somente números" pattern="([0-9]{11}|[0-9]{14})" required autocomplete="off" ${status.api_configured&&plan?.state==='draft'?'':'disabled'}></label><label>Primeiro vencimento<input class="input" name="next_due_date" type="date" required ${status.api_configured&&plan?.state==='draft'?'':'disabled'}></label><button class="primary-button" ${status.api_configured&&plan?.state==='draft'?'':'disabled'}>Gerar assinatura de teste</button></form></section>
          </div>
          <section class="billing-box billing-invoices"><div class="billing-heading"><div><h4>Faturas</h4><p class="subtle">Consulte as cobranças desta assinatura.</p></div><button type="button" id="billingPayments" class="secondary-button" ${status.api_configured&&subscribed?'':'disabled'}>Consultar faturas</button></div><div id="billingInvoices" class="billing-empty">${subscribed?'Clique em Consultar faturas para carregar as cobranças.':'As faturas ficam disponíveis após gerar a assinatura.'}</div></section>
          <details class="billing-tools"><summary>Ferramentas de conciliação</summary><p class="subtle">Use se a criação da assinatura não tiver sido confirmada. A conciliação consulta o Asaas.</p><button type="button" id="billingReconcile" class="outline-button" ${status.api_configured&&plan?'':'disabled'}>Conciliar assinatura</button></details><p id="billingFeedback" role="status" aria-live="polite"></p>`;
        const run=async(button,action)=>{button.disabled=true;const feedback=details.querySelector('#billingFeedback');feedback.textContent='Processando…';try{await action();if(version===generation&&feedback.isConnected)feedback.textContent='Consulta concluída.';}catch(e){if(version===generation&&feedback.isConnected)feedback.textContent=e.message;}finally{if(button.isConnected)button.disabled=false;}};
        details.querySelector('#billingRefresh').onclick=load;
        details.querySelector('#billingPlanForm').onsubmit=e=>{e.preventDefault();const f=e.currentTarget;run(f.querySelector('button'),async()=>{await request(`/companies/${id}/billing`,'PUT',{monthly_value:f.elements.monthly_value.value,billing_type:f.elements.billing_type.value});await load();});};
        details.querySelector('#billingSubscribeForm').onsubmit=e=>{e.preventDefault();if(!confirm('Criar assinatura no ambiente de TESTES do Asaas, sem cobrança real?'))return;const f=e.currentTarget,payload={cpf_cnpj:f.elements.cpf_cnpj.value,next_due_date:f.elements.next_due_date.value};f.elements.cpf_cnpj.value='';run(f.querySelector('button'),async()=>{await request(`/companies/${id}/billing/subscribe`,'POST',payload);await load();});};
        details.querySelector('#billingReconcile').onclick=e=>run(e.currentTarget,async()=>{await request(`/companies/${id}/billing/reconcile`,'POST',{});await load();});
        details.querySelector('#billingPayments').onclick=e=>run(e.currentTarget,async()=>{
          const payments=await request(`/companies/${id}/billing/payments`);if(version!==generation)return;
          details.querySelector('#billingInvoices').classList.remove('billing-empty');
          details.querySelector('#billingInvoices').innerHTML=payments.length?`<div class="table-wrap"><table><thead><tr><th>Vencimento</th><th>Valor</th><th>Situação</th><th>Fatura</th></tr></thead><tbody>${payments.map(p=>{let link='—';try{const u=new URL(p.invoice_url);if(u.protocol==='https:'&&(u.hostname==='asaas.com'||u.hostname.endsWith('.asaas.com')))link=`<a class="outline-button" href="${escape(u.href)}" target="_blank" rel="noopener noreferrer">Abrir fatura</a>`;}catch{}return `<tr><td>${escape(dateLabel(p.due_date))}</td><td>${money(p.value)}</td><td>${escape(paymentStatus[p.status]||p.status||'—')}</td><td>${link}</td></tr>`;}).join('')}</tbody></table></div>`:'<p class="billing-empty">Nenhuma fatura gerada ainda.</p>';
        });
      } catch(e) {if(version===generation)details.textContent=e.message;}
    };
    select.onchange=load;
  }
};
