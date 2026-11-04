/* Uses the existing authenticated company context. No credentials or tenant data persisted here. */
(() => {
 'use strict';
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const planFields=[['code','Código da atividade','text',true,'PREV-001'],['equipment_id','Equipamento / TAG','asset',true],['equipment_label','Descrição do equipamento no plano','text'],['workshop','Oficina','text',false,'UNIDADE 6'],['location','Local','text',false,'Reator 4.2'],['equipment_type','Tipo','text',false,'PT100'],['activity','Atividade resumida','text',true,'Aferição'],['responsible','Responsável / Equipe','text',true,'Equipe de instrumentação'],['last_execution','Última execução','date'],['interval_days','Intervalo (dias)','number',true,'7'],['first_due','Primeiro vencimento (sem execução anterior)','date'],['component','Componente / Sistema','text'],['procedure','Procedimento / Atividade detalhada','textarea'],['acceptance','Critério de aceitação','textarea'],['duration_minutes','Tempo previsto (minutos)','number'],['resources','Ferramentas / Materiais','textarea'],['qualification','Qualificação / Equipe','text'],['shutdown','Parada necessária','text'],['protections','Bloqueio / PT / Proteções','textarea'],['reference','Referência técnica','text'],['notes','Observações','textarea'],['active','Plano ativo','checkbox']];
 const executionFields=[['work_order','Ordem de serviço','text',true,'OS-2026-001'],['started_at','Início','datetime-local',true],['finished_at','Término','datetime-local',true],['executor','Executante','text',true],['result','Resultado / Valor medido','textarea',true],['conformity','Conformidade','select',true,['Conforme','Não conforme','Não aplicável']],['anomaly','Anomalia / Ação necessária','textarea'],['materials','Materiais utilizados','textarea'],['corrective_order','OS corretiva vinculada','text'],['release','Condição final','select',true,['Liberado','Liberado com restrição','Não liberado']],['released_by','Responsável pela liberação','text',true],['notes','Observações','textarea']];
 let activeDialog=null;
 window.openMaintenance=async function(){
  if(!state.authToken||!state.companyId)return;
  activeDialog?.remove();
  const company=state.companyId, token=state.authToken;
  const editor=state.isSuperadmin||['company_admin','supervisor'].includes(state.role);
  const executor=editor||state.role==='operator';
  const d=document.createElement('section');activeDialog=d;d.className='maintenance-page';
  d.innerHTML=tcH`<header class="mp-head"><div><span class="mp-eyebrow">TAGCHECK · GESTÃO DE ATIVOS</span><h1>Manutenção preventiva</h1><p>${esc(state.companyName)} · Planejamento, controle e rastreabilidade</p></div><button type="button" data-close aria-label="Voltar aos ativos">← Voltar aos ativos</button></header><div class="mp-content"><div class="mp-notice" role="status">Carregando registros da empresa…</div><div class="mp-stats"></div><div class="mp-toolbar"><label>Buscar<input type="search" id="mpSearch" placeholder="TAG, equipamento, oficina ou atividade"></label><label>Situação<select id="mpStatus"><option value="">Todas as situações</option>${['Atrasada','Vence hoje','Próximos 7 dias','Programada','Sem programação','Inativo'].map(s=>tcH`<option value="${esc(s)}">${esc(tcL(s))}</option>`).join('')}</select></label><button type="button" id="mpNew" ${editor?'':'hidden'}>+ Novo plano</button><button type="button" id="mpImport" ${editor?'':'hidden'}>Importar planilha atualizada</button><button type="button" id="mpExport">Exportar CSV</button><button type="button" id="mpRefresh">Atualizar</button></div><div class="mp-table-wrap"><table><thead><tr>${['Atividade / TAG','Equipamento','Oficina / Local / Tipo','Responsável','Intervalo','Próxima data','Situação','Ações'].map(s=>tcH`<th>${esc(tcL(s))}</th>`).join('')}</tr></thead><tbody></tbody></table></div><section class="mp-form-panel" hidden></section></div>`;
  app.replaceChildren(d);document.title=tcL('Manutenção Preventiva · TagCheck');
  const notice=d.querySelector('.mp-notice'), panel=d.querySelector('.mp-form-panel');let plans=[],equipment=[],shown=[];
  const current=()=>d.isConnected&&state.companyId===company&&state.authToken===token;
  const guard=setInterval(()=>{if(!current()){clearInterval(guard);d.remove();}},500);
  d.querySelector('[data-close]').onclick=()=>{clearInterval(guard);location.assign(window.TAGCHECK_I18N.url(new URL('../',location.href).href));};
  const message=(s,error=false)=>{notice.textContent=tcL(s);notice.classList.toggle('mp-error',error);};
  async function api(path,method='GET',body){
   if(!current())throw Error(tcL('A empresa ou sessão mudou. Abra novamente.'));
   const response=await fetchWithTimeout(buildUrl(CONFIG.API_BASE_URL,'/maintenance'+path),{method,headers:getAuthHeaders({'Content-Type':'application/json'}),...(body?{body:JSON.stringify(body)}:{})});
   if(!current())throw Error(tcL('A empresa ou sessão mudou.'));
   const result=await response.json();if(!response.ok)throw Error(typeof result.detail==='string'?result.detail:'Confira os campos e tente novamente.');return result;
  }
  const date=v=>v?new Date(v+'T12:00:00').toLocaleDateString(window.TAGCHECK_I18N.locale):'—';
  function draw(){
   const q=d.querySelector('#mpSearch').value.toLocaleLowerCase(),status=d.querySelector('#mpStatus').value;
   shown=plans.filter(p=>(!status||p.status===status)&&[p.code,p.tag,p.equipment_name,p.workshop,p.location,p.equipment_type,p.activity,p.responsible].join(' ').toLocaleLowerCase().includes(q));
   d.querySelector('.mp-stats').innerHTML=[['Planos ativos',plans.filter(p=>p.active).length],['Atrasadas',plans.filter(p=>p.status==='Atrasada').length],['Vencem em até 7 dias',plans.filter(p=>['Vence hoje','Próximos 7 dias'].includes(p.status)).length],['Sem programação',plans.filter(p=>p.status==='Sem programação').length]].map(([k,v])=>tcH`<article><strong>${v}</strong><span>${esc(tcL(k))}</span></article>`).join('');
   d.querySelector('tbody').innerHTML=shown.length?shown.map(p=>tcH`<tr><td><a class="mp-plan-link" href="#plano-${p.id}" data-sheet="${p.id}" aria-label="${esc(tcL('Abrir formulário'))} ${esc(p.code)}">${esc(p.code)}</a><br>${esc(p.tag)}<br><small>${esc(p.activity)}</small></td><td>${esc(p.equipment_name)}</td><td>${esc(p.workshop||'—')}<br><small>${esc(p.location)} · ${esc(p.equipment_type)}</small></td><td>${esc(p.responsible)}</td><td>${p.interval_days} dias</td><td>${date(p.next_due)}<br><small>${p.days_remaining===null?'':p.days_remaining+' '+tcL('dia(s)')}</small></td><td><span class="mp-badge ${p.status==='Atrasada'?'mp-late':''}">${esc(tcL(p.status))}</span></td><td><div class="mp-actions"><button data-edit="${p.id}">${tcL(editor?'Editar':'Detalhes')}</button>${executor&&p.active?tcH`<button data-execute="${p.id}">Registrar execução</button>`:''}<button data-history="${p.id}">Histórico</button></div></td></tr>`).join(''):tcH('<tr><td colspan="8">Nenhum plano encontrado. Cadastre um equipamento no TagCheck e crie seu primeiro plano.</td></tr>');
  }
  async function load(){try{[plans,equipment]=await Promise.all([api('/plans'),api('/equipment')]);draw();message('Dados da empresa atual. Os intervalos e critérios devem seguir os manuais e procedimentos aplicáveis.');}catch(e){message(e.message,true);}}
  function field([key,label,type,required,example],data){
   const value=key==='status'?tcL(data[key]??''):(data[key]??'');let control;const common=`name="${key}" ${required?'required':''} ${example&&typeof example==='string'?`placeholder="${esc(tcL('Ex.:'))} ${esc(tcL(example))}"`:''}`;
   if(type==='asset')control=tcH`<select ${common}><option value="">Selecione o equipamento</option>${equipment.map(e=>tcH`<option value="${e.id}" ${e.id===value?'selected':''}>${esc(e.tag)} — ${esc(e.name)}</option>`).join('')}</select>`;
   else if(type==='select')control=tcH`<select ${common}><option value="">Selecione</option>${example.map(s=>tcH`<option value="${esc(s)}" ${s===value?'selected':''}>${esc(tcL(s))}</option>`).join('')}</select>`;
   else if(type==='readonly')control=tcH`<input ${common} readonly value="${esc(value)}" aria-readonly="true">`;
   else if(type==='textarea')control=tcH`<textarea ${common} maxlength="4000" rows="3">${esc(value)}</textarea>`;
   else control=tcH`<input ${common} type="${type}" ${type==='number'?'min="'+(key==='interval_days'?1:0)+'" step="1"':''} ${type==='checkbox'?(value?'checked':''):`value="${esc(value)}"`} ${type==='text'?'maxlength="2000"':''}>`;
   return tcH`<label>${esc(tcL(label))}${required?' *':''}${control}</label>`;
  }
  function form(plan={},execution=false){
   const fields=execution?executionFields:planFields;const readonly=!execution&&!editor;
   panel.hidden=false;panel.innerHTML=tcH`<h2>${tcL(execution?'Registrar execução':plan.id?(readonly?'Detalhes do plano':'Editar plano'):'Novo plano')}</h2><p>${esc(plan.tag||'')} ${esc(plan.equipment_name||'')} · Campos com * são obrigatórios.</p><form><fieldset ${readonly?'disabled':''}><div class="mp-grid">${fields.map(f=>field(f,{active:true,...plan})).join('')}</div></fieldset><p class="mp-form-message" role="alert"></p>${readonly?'':tcH('<button type="submit">Salvar registro</button>')} <button type="button" data-cancel>Fechar formulário</button></form>`;
   panel.scrollIntoView({behavior:'smooth',block:'start'});panel.querySelector('[data-cancel]').onclick=()=>panel.hidden=true;
   const f=panel.querySelector('form');
   if(!execution){if(plan.id)f.elements.equipment_id.disabled=true;f.elements.equipment_id.onchange=()=>{const e=equipment.find(e=>e.id===Number(f.elements.equipment_id.value));if(e)for(const k of ['workshop','location','equipment_type'])f.elements[k].value=e[k];};}
   f.onsubmit=async ev=>{ev.preventDefault();const button=f.querySelector('[type=submit]');if(!button)return;button.disabled=true;
    try{const body={};for(const [k,,type] of fields){let v=f.elements[k].value;if(type==='checkbox')v=f.elements[k].checked;else if(type==='number'||type==='asset')v=v===''?null:Number(v);else if(type==='date')v=v||null;else if(type==='datetime-local')v=new Date(v).toISOString();body[k]=v;}
     if(plan.id)body.revision=plan.revision;
     await api(execution?`/plans/${plan.id}/executions`:plan.id?`/plans/${plan.id}`:'/plans',execution||!plan.id?'POST':'PUT',body);
     panel.hidden=true;await load();message('Registro salvo. O cronograma foi atualizado.');
    }catch(e){panel.querySelector('.mp-form-message').textContent=tcL(e.message);}finally{button.disabled=false;}
   };
  }

  function sheetForm(plan) {
   const fields=[
    ['code','Código atividade','text',true],['tag','TAG','readonly'],
    ['equipment_label','Equipamento','text',true],['workshop','OFICINA','text'],
    ['location','LOCAL','text'],['equipment_type','TIPO','text'],
    ['activity','Atividade resumida','text',true],['responsible','Responsável','text',true],
    ['last_execution','Última execução','date'],['interval_days','Intervalo (dias)','number',true],
    ['next_due','Próxima data','readonly'],['days_remaining','Dias restantes','readonly'],
    ['status','Situação','readonly'],['notes','Observações','textarea']
   ];
   const data={...plan,equipment_label:plan.equipment_label||plan.equipment_name,next_due:date(plan.next_due)};
   panel.hidden=false;panel.id='plano-'+plan.id;
   panel.innerHTML=tcH`<h2>Formulário da planilha · ${esc(plan.code)}</h2><p>Mesmos campos do Cronograma. Próxima data, dias restantes e situação são calculados automaticamente.</p><form><fieldset ${editor?'':'disabled'}><div class="mp-grid mp-sheet-grid">${fields.map(f=>field(f,data)).join('')}</div></fieldset><p class="mp-form-message" role="alert"></p>${editor?tcH('<button type="submit">Salvar alterações</button>'):''} <button type="button" data-cancel>Fechar formulário</button></form>`;
   const f=panel.querySelector('form');
   panel.querySelector('[data-cancel]').onclick=()=>{panel.hidden=true;};
   panel.scrollIntoView({behavior:'smooth',block:'start'});
   f.elements.code.focus({preventScroll:true});
   function calculate(){
    let due=plan.first_due||'';
    const last=f.elements.last_execution.value, interval=Number(f.elements.interval_days.value);
    if(last&&Number.isInteger(interval)&&interval>0){
     const value=new Date(last+'T00:00:00Z');value.setUTCDate(value.getUTCDate()+interval);due=value.toISOString().slice(0,10);
    }else if(last){due='';}
    const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
    const part=type=>parts.find(p=>p.type===type).value;
    const today=part('year')+'-'+part('month')+'-'+part('day');
    const days=due?Math.round((Date.parse(due+'T00:00:00Z')-Date.parse(today+'T00:00:00Z'))/86400000):null;
    f.elements.next_due.value=date(due);
    f.elements.days_remaining.value=days===null?'':String(days);
    f.elements.status.value=tcL(!plan.active?'Inativo':days===null?'Sem programação':days<0?'Atrasada':days===0?'Vence hoje':days<=7?'Próximos 7 dias':'Programada');
   }
   f.elements.last_execution.oninput=calculate;f.elements.interval_days.oninput=calculate;
   f.onsubmit=async event=>{
    event.preventDefault();if(!editor)return;
    const button=f.querySelector('[type=submit]');button.disabled=true;
    try {
     const body={};for(const [key] of planFields)if(key in plan)body[key]=plan[key];
     for(const [key,,type] of fields)if(type!=='readonly')body[key]=type==='number'?Number(f.elements[key].value):type==='date'?(f.elements[key].value||null):f.elements[key].value;
     body.revision=plan.revision;
     await api('/plans/'+plan.id,'PUT',body);
     panel.hidden=true;await load();message('Alterações salvas no formulário e no cronograma.');
    }catch(error){panel.querySelector('.mp-form-message').textContent=tcL(error.message);}
    finally{button.disabled=false;}
   };
  }

  function importSpreadsheet(){
   if(!editor)return;
   panel.hidden=false;panel.innerHTML=tcH`<h2>Importar planilha atualizada</h2><p>Envie o Cronograma em .xls ou .xlsx (até 8 MB / 2.000 atividades). A conferência usa TAG e código da atividade somente nesta empresa. Linhas ausentes da planilha não excluem registros.</p><form id="mpUploadForm"><label>Planilha atualizada<input type="file" accept=".xls,.xlsx" required></label><p>Instrumentos existentes serão reutilizados. Os campos do plano presentes na planilha serão atualizados; os demais dados e o histórico serão preservados.</p><button type="submit">Conferir planilha</button> <button type="button" data-upload-cancel>Cancelar</button></form><div class="mp-import-result" role="status"></div>`;
   panel.scrollIntoView({behavior:'smooth',block:'start'});
   const form=panel.querySelector('form'),input=form.querySelector('input'),result=panel.querySelector('.mp-import-result');let preview=null,selected=null;
   panel.querySelector('[data-upload-cancel]').onclick=()=>{selected=null;preview=null;panel.hidden=true;};
   input.onchange=()=>{preview=null;selected=null;result.replaceChildren();};
   async function upload(path,file,previewToken){
    if(!current())throw Error(tcL('A empresa ou sessão mudou. Abra novamente.'));
    const body=new FormData();body.append('file',file);if(previewToken)body.append('preview_token',previewToken);
    const response=await fetchWithTimeout(buildUrl(CONFIG.API_BASE_URL,'/maintenance/import/'+path),{method:'POST',headers:getAuthHeaders(),body});
    if(!current())throw Error(tcL('A empresa ou sessão mudou.'));
    const data=await response.json();if(!response.ok){const detail=data.detail;throw Error(typeof detail==='string'?detail:detail?.errors?[detail.message,...detail.errors].join('\n'):'Não foi possível conferir a planilha. Verifique os dados e tente novamente.');}return data;
   }
   const summary=s=>tcH`<div class="mp-import-summary">${[['Atividades',s.activities],['Instrumentos já cadastrados',s.existing_instruments],['Instrumentos novos',s.new_instruments],['Planos novos',s.new_plans],['Planos a atualizar',s.updated_plans],['Planos sem alteração',s.unchanged_plans]].map(([label,n])=>tcH`<span><strong>${n}</strong> ${esc(tcL(label))}</span>`).join('')}</div>`;
   form.onsubmit=async event=>{
    event.preventDefault();selected=input.files[0];preview=null;if(!selected)return;
    const button=form.querySelector('[type=submit]');button.disabled=true;input.disabled=true;result.textContent=tcL('Conferindo instrumentos e atividades…');
    try{
     preview=await upload('preview',selected);
     result.innerHTML=tcH`<h3>Confira antes de importar</h3>${summary(preview.summary)}<p>${preview.ignored_rows} linha(s) vazia(s) ignorada(s). A prévia vale por 10 minutos.</p>${preview.errors.length?tcH`<div class="mp-error"><p>Corrija os conflitos abaixo. Nenhum dado foi gravado.</p><ul>${preview.errors.map(e=>tcH`<li>${esc(e)}</li>`).join('')}</ul></div>`:''}<div class="mp-table-wrap"><table><thead><tr><th>Linha</th><th>Código</th><th>TAG</th><th>Equipamento</th><th>Instrumento</th><th>Plano</th></tr></thead><tbody>${preview.items.map(i=>tcH`<tr><td>${i.row}</td><td>${esc(i.code)}</td><td>${esc(i.tag)}</td><td>${esc(i.equipment_name)}</td><td>${esc(tcL(i.instrument))}</td><td>${esc(tcL(i.action))}</td></tr>`).join('')}</tbody></table></div>${preview.preview_token?tcH('<p><button type="button" data-apply-import>Confirmar importação</button></p>'):''}`;
     const apply=result.querySelector('[data-apply-import]');if(apply)apply.onclick=async()=>{
      apply.disabled=true;button.disabled=true;input.disabled=true;
      try{const saved=await upload('apply',selected,preview.preview_token);selected=null;preview=null;panel.hidden=true;await load();message(tcF`Importação concluída: ${saved.summary.new_instruments} instrumento(s) novo(s), ${saved.summary.new_plans} plano(s) novo(s), ${saved.summary.updated_plans} atualizado(s) e ${saved.summary.unchanged_plans} sem alteração.`);}
      catch(error){preview=null;selected=null;result.textContent=tcL(error.message);button.disabled=false;input.disabled=false;}
     };
    }catch(error){result.textContent=tcL(error.message);}finally{button.disabled=false;input.disabled=false;}
   };
  }

  async function history(plan){try{const rows=await api(`/plans/${plan.id}/executions`);panel.hidden=false;panel.innerHTML=tcH`<h2>Histórico · ${esc(plan.code)} · ${esc(plan.tag)}</h2><p>Registros preservados com o plano vigente na execução.</p>${rows.length?rows.map(r=>tcH`<details><summary>${esc(r.work_order)} · ${esc(r.executor)} · ${new Date(r.finished_at).toLocaleString(window.TAGCHECK_I18N.locale)} · ${esc(tcL(r.release))}</summary><dl>${executionFields.map(([k,l])=>tcH`<dt>${esc(tcL(l))}</dt><dd>${esc(['conformity','release'].includes(k)?tcL(r[k]||'—'):(r[k]||'—'))}</dd>`).join('')}<dt>Atividade no momento da execução</dt><dd>${esc(r.plan_snapshot.activity)}</dd><dt>Vencimento previsto à época</dt><dd>${date(r.plan_snapshot.next_due)}</dd><dt>Registrado em</dt><dd>${esc(r.created_at)}</dd></dl></details>`).join(''):tcH('<p>Nenhuma execução registrada.</p>')}<button data-dismiss>Fechar histórico</button>`;panel.querySelector('[data-dismiss]').onclick=()=>panel.hidden=true;panel.scrollIntoView({behavior:'smooth'});}catch(e){message(e.message,true);}}
  d.querySelector('tbody').onclick=ev=>{const link=ev.target.closest('[data-sheet]');if(link){ev.preventDefault();const plan=plans.find(p=>p.id===Number(link.dataset.sheet));if(plan)sheetForm(plan);return;}const b=ev.target.closest('button');if(!b)return;const id=Number(b.dataset.edit||b.dataset.execute||b.dataset.history),p=plans.find(p=>p.id===id);if(!p)return;if(b.dataset.history)history(p);else form(p,!!b.dataset.execute);};
  d.querySelector('#mpImport').onclick=importSpreadsheet;
  d.querySelector('#mpSearch').oninput=draw;d.querySelector('#mpStatus').onchange=draw;d.querySelector('#mpNew').onclick=()=>form();d.querySelector('#mpRefresh').onclick=()=>{panel.hidden=true;load();};
  d.querySelector('#mpExport').onclick=()=>{const fields=[['code','Código atividade'],['tag','TAG'],['equipment_name','Equipamento'],['workshop','OFICINA'],['location','LOCAL'],['equipment_type','TIPO'],['activity','Atividade resumida'],['responsible','Responsável'],['last_execution','Última execução'],['interval_days','Intervalo (dias)'],['next_due','Próxima data'],['days_remaining','Dias restantes'],['status','Situação'],['notes','Observações']];const cell=v=>'"'+String(v??'').replace(/^(?=[\s]*[=+@\-]|[\t\r\n])/,"'").replace(/"/g,'""')+'"';const csv='\uFEFF'+[fields.map(([,l])=>cell(tcL(l))).join(';'),...shown.map(p=>fields.map(([k])=>cell(k==='status'?tcL(p[k]):p[k])).join(';'))].join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='TagCheck_Manutencao_Preventiva.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  await load();
 };
 document.getElementById('maintenanceButton').onclick=()=>location.assign(window.TAGCHECK_I18N.url(new URL('manutencao/',document.baseURI).href));
})();
