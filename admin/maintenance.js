/* Uses the existing authenticated company context. No credentials or tenant data persisted here. */
(() => {
 'use strict';
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const planFields=[['code','Código da atividade','text',true,'PREV-001'],['equipment_id','Equipamento / TAG','asset',true],['workshop','Oficina','text',false,'UNIDADE 6'],['location','Local','text',false,'Reator 4.2'],['equipment_type','Tipo','text',false,'PT100'],['activity','Atividade resumida','text',true,'Aferição'],['responsible','Responsável / Equipe','text',true,'Equipe de instrumentação'],['last_execution','Última execução','date'],['interval_days','Intervalo (dias)','number',true,'7'],['first_due','Primeiro vencimento (sem execução anterior)','date'],['component','Componente / Sistema','text'],['procedure','Procedimento / Atividade detalhada','textarea'],['acceptance','Critério de aceitação','textarea'],['duration_minutes','Tempo previsto (minutos)','number'],['resources','Ferramentas / Materiais','textarea'],['qualification','Qualificação / Equipe','text'],['shutdown','Parada necessária','text'],['protections','Bloqueio / PT / Proteções','textarea'],['reference','Referência técnica','text'],['notes','Observações','textarea'],['active','Plano ativo','checkbox']];
 const executionFields=[['work_order','Ordem de serviço','text',true,'OS-2026-001'],['started_at','Início','datetime-local',true],['finished_at','Término','datetime-local',true],['executor','Executante','text',true],['result','Resultado / Valor medido','textarea',true],['conformity','Conformidade','select',true,['Conforme','Não conforme','Não aplicável']],['anomaly','Anomalia / Ação necessária','textarea'],['materials','Materiais utilizados','textarea'],['corrective_order','OS corretiva vinculada','text'],['release','Condição final','select',true,['Liberado','Liberado com restrição','Não liberado']],['released_by','Responsável pela liberação','text',true],['notes','Observações','textarea']];
 let activeDialog=null;
 window.openMaintenance=async function(){
  if(!state.authToken||!state.companyId)return;
  activeDialog?.close();activeDialog?.remove();
  const company=state.companyId, token=state.authToken;
  const editor=state.isSuperadmin||['company_admin','supervisor'].includes(state.role);
  const executor=editor||state.role==='operator';
  const d=document.createElement('dialog');activeDialog=d;d.className='maintenance-page';
  d.innerHTML=`<header class="mp-head"><div><span class="mp-eyebrow">TAGCHECK · GESTÃO DE ATIVOS</span><h1>Manutenção preventiva</h1><p>${esc(state.companyName)} · Planejamento, controle e rastreabilidade</p></div><button type="button" data-close aria-label="Fechar manutenção">Fechar ×</button></header><div class="mp-content"><div class="mp-notice" role="status">Carregando registros da empresa…</div><div class="mp-stats"></div><div class="mp-toolbar"><label>Buscar<input type="search" id="mpSearch" placeholder="TAG, equipamento, oficina ou atividade"></label><label>Situação<select id="mpStatus"><option value="">Todas as situações</option>${['Atrasada','Vence hoje','Próximos 7 dias','Programada','Sem programação','Inativo'].map(s=>`<option>${s}</option>`).join('')}</select></label><button type="button" id="mpNew" ${editor?'':'hidden'}>+ Novo plano</button><button type="button" id="mpExport">Exportar CSV</button><button type="button" id="mpRefresh">Atualizar</button></div><div class="mp-table-wrap"><table><thead><tr>${['Atividade / TAG','Equipamento','Oficina / Local / Tipo','Responsável','Intervalo','Próxima data','Situação','Ações'].map(s=>`<th>${s}</th>`).join('')}</tr></thead><tbody></tbody></table></div><section class="mp-form-panel" hidden></section></div>`;
  document.body.append(d);d.showModal();
  const notice=d.querySelector('.mp-notice'), panel=d.querySelector('.mp-form-panel');let plans=[],equipment=[],shown=[];
  const current=()=>d.isConnected&&state.companyId===company&&state.authToken===token;
  const guard=setInterval(()=>{if(!current()){clearInterval(guard);d.close();d.remove();}},500);
  d.addEventListener('close',()=>{clearInterval(guard);d.remove();},{once:true});d.querySelector('[data-close]').onclick=()=>d.close();
  const message=(s,error=false)=>{notice.textContent=s;notice.classList.toggle('mp-error',error);};
  async function api(path,method='GET',body){
   if(!current())throw Error('A empresa ou sessão mudou. Abra novamente.');
   const response=await fetchWithTimeout(buildUrl(CONFIG.API_BASE_URL,'/maintenance'+path),{method,headers:getAuthHeaders({'Content-Type':'application/json'}),...(body?{body:JSON.stringify(body)}:{})});
   if(!current())throw Error('A empresa ou sessão mudou.');
   const result=await response.json();if(!response.ok)throw Error(typeof result.detail==='string'?result.detail:'Confira os campos e tente novamente.');return result;
  }
  const date=v=>v?new Date(v+'T12:00:00').toLocaleDateString('pt-BR'):'—';
  function draw(){
   const q=d.querySelector('#mpSearch').value.toLocaleLowerCase(),status=d.querySelector('#mpStatus').value;
   shown=plans.filter(p=>(!status||p.status===status)&&[p.code,p.tag,p.equipment_name,p.workshop,p.location,p.equipment_type,p.activity,p.responsible].join(' ').toLocaleLowerCase().includes(q));
   d.querySelector('.mp-stats').innerHTML=[['Planos ativos',plans.filter(p=>p.active).length],['Atrasadas',plans.filter(p=>p.status==='Atrasada').length],['Vencem em até 7 dias',plans.filter(p=>['Vence hoje','Próximos 7 dias'].includes(p.status)).length],['Sem programação',plans.filter(p=>p.status==='Sem programação').length]].map(([k,v])=>`<article><strong>${v}</strong><span>${k}</span></article>`).join('');
   d.querySelector('tbody').innerHTML=shown.length?shown.map(p=>`<tr><td><strong>${esc(p.code)}</strong><br>${esc(p.tag)}<br><small>${esc(p.activity)}</small></td><td>${esc(p.equipment_name)}</td><td>${esc(p.workshop||'—')}<br><small>${esc(p.location)} · ${esc(p.equipment_type)}</small></td><td>${esc(p.responsible)}</td><td>${p.interval_days} dias</td><td>${date(p.next_due)}<br><small>${p.days_remaining===null?'':p.days_remaining+' dia(s)'}</small></td><td><span class="mp-badge ${p.status==='Atrasada'?'mp-late':''}">${esc(p.status)}</span></td><td><div class="mp-actions"><button data-edit="${p.id}">${editor?'Editar':'Detalhes'}</button>${executor&&p.active?`<button data-execute="${p.id}">Registrar execução</button>`:''}<button data-history="${p.id}">Histórico</button></div></td></tr>`).join(''):'<tr><td colspan="8">Nenhum plano encontrado. Cadastre um equipamento no TagCheck e crie seu primeiro plano.</td></tr>';
  }
  async function load(){try{[plans,equipment]=await Promise.all([api('/plans'),api('/equipment')]);draw();message('Dados da empresa atual. Os intervalos e critérios devem seguir os manuais e procedimentos aplicáveis.');}catch(e){message(e.message,true);}}
  function field([key,label,type,required,example],data){
   const value=data[key]??'';let control;const common=`name="${key}" ${required?'required':''} ${example&&typeof example==='string'?`placeholder="Ex.: ${esc(example)}"`:''}`;
   if(type==='asset')control=`<select ${common}><option value="">Selecione o equipamento</option>${equipment.map(e=>`<option value="${e.id}" ${e.id===value?'selected':''}>${esc(e.tag)} — ${esc(e.name)}</option>`).join('')}</select>`;
   else if(type==='select')control=`<select ${common}><option value="">Selecione</option>${example.map(s=>`<option ${s===value?'selected':''}>${esc(s)}</option>`).join('')}</select>`;
   else if(type==='textarea')control=`<textarea ${common} maxlength="4000" rows="3">${esc(value)}</textarea>`;
   else control=`<input ${common} type="${type}" ${type==='number'?'min="'+(key==='interval_days'?1:0)+'" step="1"':''} ${type==='checkbox'?(value?'checked':''):`value="${esc(value)}"`} ${type==='text'?'maxlength="2000"':''}>`;
   return `<label>${label}${required?' *':''}${control}</label>`;
  }
  function form(plan={},execution=false){
   const fields=execution?executionFields:planFields;const readonly=!execution&&!editor;
   panel.hidden=false;panel.innerHTML=`<h2>${execution?'Registrar execução':plan.id?(readonly?'Detalhes do plano':'Editar plano'):'Novo plano'}</h2><p>${esc(plan.tag||'')} ${esc(plan.equipment_name||'')} · Campos com * são obrigatórios.</p><form><fieldset ${readonly?'disabled':''}><div class="mp-grid">${fields.map(f=>field(f,{active:true,...plan})).join('')}</div></fieldset><p class="mp-form-message" role="alert"></p>${readonly?'':'<button type="submit">Salvar registro</button>'} <button type="button" data-cancel>Fechar formulário</button></form>`;
   panel.scrollIntoView({behavior:'smooth',block:'start'});panel.querySelector('[data-cancel]').onclick=()=>panel.hidden=true;
   const f=panel.querySelector('form');
   if(!execution){if(plan.id)f.elements.equipment_id.disabled=true;f.elements.equipment_id.onchange=()=>{const e=equipment.find(e=>e.id===Number(f.elements.equipment_id.value));if(e)for(const k of ['workshop','location','equipment_type'])f.elements[k].value=e[k];};}
   f.onsubmit=async ev=>{ev.preventDefault();const button=f.querySelector('[type=submit]');if(!button)return;button.disabled=true;
    try{const body={};for(const [k,,type] of fields){let v=f.elements[k].value;if(type==='checkbox')v=f.elements[k].checked;else if(type==='number'||type==='asset')v=v===''?null:Number(v);else if(type==='date')v=v||null;else if(type==='datetime-local')v=new Date(v).toISOString();body[k]=v;}
     if(plan.id)body.revision=plan.revision;
     await api(execution?`/plans/${plan.id}/executions`:plan.id?`/plans/${plan.id}`:'/plans',execution||!plan.id?'POST':'PUT',body);
     panel.hidden=true;await load();message('Registro salvo. O cronograma foi atualizado.');
    }catch(e){panel.querySelector('.mp-form-message').textContent=e.message;}finally{button.disabled=false;}
   };
  }
  async function history(plan){try{const rows=await api(`/plans/${plan.id}/executions`);panel.hidden=false;panel.innerHTML=`<h2>Histórico · ${esc(plan.code)} · ${esc(plan.tag)}</h2><p>Registros preservados com o plano vigente na execução.</p>${rows.length?rows.map(r=>`<details><summary>${esc(r.work_order)} · ${esc(r.executor)} · ${new Date(r.finished_at).toLocaleString('pt-BR')} · ${esc(r.release)}</summary><dl>${executionFields.map(([k,l])=>`<dt>${l}</dt><dd>${esc(r[k]||'—')}</dd>`).join('')}<dt>Atividade no momento da execução</dt><dd>${esc(r.plan_snapshot.activity)}</dd><dt>Vencimento previsto à época</dt><dd>${date(r.plan_snapshot.next_due)}</dd><dt>Registrado em</dt><dd>${esc(r.created_at)}</dd></dl></details>`).join(''):'<p>Nenhuma execução registrada.</p>'}<button data-dismiss>Fechar histórico</button>`;panel.querySelector('[data-dismiss]').onclick=()=>panel.hidden=true;panel.scrollIntoView({behavior:'smooth'});}catch(e){message(e.message,true);}}
  d.querySelector('tbody').onclick=ev=>{const b=ev.target.closest('button');if(!b)return;const id=Number(b.dataset.edit||b.dataset.execute||b.dataset.history),p=plans.find(p=>p.id===id);if(!p)return;if(b.dataset.history)history(p);else form(p,!!b.dataset.execute);};
  d.querySelector('#mpSearch').oninput=draw;d.querySelector('#mpStatus').onchange=draw;d.querySelector('#mpNew').onclick=()=>form();d.querySelector('#mpRefresh').onclick=()=>{panel.hidden=true;load();};
  d.querySelector('#mpExport').onclick=()=>{const fields=[['code','Código atividade'],['tag','TAG'],['equipment_name','Equipamento'],['workshop','OFICINA'],['location','LOCAL'],['equipment_type','TIPO'],['activity','Atividade resumida'],['responsible','Responsável'],['last_execution','Última execução'],['interval_days','Intervalo (dias)'],['next_due','Próxima data'],['days_remaining','Dias restantes'],['status','Situação'],['notes','Observações']];const cell=v=>'"'+String(v??'').replace(/^(?=[\s]*[=+@\-]|[\t\r\n])/,"'").replace(/"/g,'""')+'"';const csv='\uFEFF'+[fields.map(([,l])=>cell(l)).join(';'),...shown.map(p=>fields.map(([k])=>cell(p[k])).join(';'))].join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='TagCheck_Manutencao_Preventiva.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  await load();
 };
 document.getElementById('maintenanceButton').onclick=()=>openMaintenance();
})();
