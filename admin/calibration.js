const CERT_FIELDS = {"document_type": "Tipo de documento", "certificate_number": "Número do certificado / CIE", "issue_date": "Data de emissão", "laboratory": "Laboratório emissor", "requester": "Solicitante", "procedure": "Procedimento / método", "temperature": "Temperatura ambiente", "humidity": "Umidade relativa", "observations": "Observações / falha constatada", "conclusion": "Conclusão / condição técnica", "approved_by": "Responsável / signatário informado", "approval_date": "Data da aprovação informada"};
const CERT_TABLES = {"standards": {"identification": "Padrão utilizado", "serial": "Série", "certificate": "Certificado", "laboratory": "Laboratório", "calibration_date": "Calibração", "valid_until": "Validade"}, "results": {"reference": "Referência / entrada", "input_unit": "Unidade de entrada", "indicated": "Indicação / saída", "output_unit": "Unidade de saída", "uncertainty": "Incerteza expandida", "k": "k"}};

window.openCalibration = function(prefix, selected = null, instrumentOptions = null) {
 const target = selected || (prefix === 'create' ? state.createForm : state.editDraft);
 const companyId = state.companyId;
 const record = structuredClone(target.calibration_record || {});
 const dialog = document.createElement('dialog');
 dialog.className = 'calibration-dialog';
 const field = (key,label,value) => key === 'document_type' ? `<label>${escapeHtml(label)}<select class="input" data-cert="document_type">${['','Certificado de calibração','Carta de inspeção'].map(option=>`<option ${option===(value || '')?'selected':''}>${option}</option>`).join('')}</select></label>` : `<label>${escapeHtml(label)}<input class="input" data-cert="${key}" value="${escapeHtml(value || '')}"></label>`;
 dialog.innerHTML = `<h2>Certificado e leituras do instrumento</h2><label>Selecionar instrumento cadastrado<select id="certInstrument" class="input"><option value="">${prefix === 'edit' ? 'Usar o cadastro em edição' : 'Usar o novo cadastro'}</option></select></label><p id="certInstrumentStatus" role="status">Carregando instrumentos da empresa…</p><div class="grid-2 calibration-summary">${[['tag','TAG'],['name','Descrição'],['manufacturer','Fabricante'],['model','Modelo'],['serial_number','Número de série'],['equipment_type','Tipo'],['sector','Setor'],['location','Localização'],['status','Status'],['calibration_date','Última calibração'],['next_calibration_date','Próxima calibração']].map(([key,label])=>`<label>${label}<input class="input" readonly value="${escapeHtml(target[key] || '')}"></label>`).join('')}</div><p>Preencha os dados do certificado e os valores lidos. Use a mesma unidade para referência e indicação. Carta de inspeção registra falhas, sem avaliação de calibração.</p><div class="grid-2">${Object.entries(CERT_FIELDS).map(([k,l])=>field(k,l,record[k])).join('')}</div><h3>Critério metrológico do instrumento</h3>${metrologyHtml('certificate',target)}<p>Erro = indicação − referência. A verificação usa |erro| ≤ EMA, sem considerar incerteza. A incerteza e k devem vir do certificado ou de avaliação própria.</p><div id="certTables"></div><button type="button" id="certCalculate">Calcular erros e avaliar pontos</button><div id="certFeedback" role="status"></div><button type="button" id="certClearReadings">Limpar leituras para nova medição</button> <button type="button" id="certSave">${selected ? "Salvar no instrumento selecionado" : "Aplicar ao cadastro"}</button> <button type="button" id="certCancel">Cancelar</button>`;
 document.body.append(dialog);
 const selector = dialog.querySelector('#certInstrument');
 const status = dialog.querySelector('#certInstrumentStatus');
 async function loadInstrumentOptions() {
  try {
   let items = instrumentOptions;
   if (!items) {
    const response = await fetchWithTimeout(buildUrl(CONFIG.API_BASE_URL, '/equipment'), {headers:getAuthHeaders({Accept:'application/json'})});
    if (!response.ok) throw new Error('Não foi possível carregar os instrumentos.');
    items = (await response.json()).map(normalizeItem);
   }
   if (!dialog.isConnected || state.companyId !== companyId) return;
   items = items.filter(item=>!item.offline_pending);
   selector.innerHTML += items.map(item=>`<option value="${Number(item.id)}">${escapeHtml(item.tag)} — ${escapeHtml(item.name)}</option>`).join('');
   selector.value = selected ? String(selected.id) : '';
   status.textContent = selected ? 'Dados do instrumento carregados. Confira os campos e insira as leituras; dados ainda não cadastrados continuam em branco.' : 'Selecione um instrumento para carregar seus dados e o certificado já salvo.';
   selector.onchange = () => {
    const item = items.find(row=>String(row.id) === selector.value) || null;
    dialog.close();dialog.remove();openCalibration(prefix,item,items);
   };
  } catch (error) { if(dialog.isConnected) status.textContent = error.message; }
 }
 loadInstrumentOptions();
 function tables() {
  dialog.querySelector('#certTables').innerHTML=Object.entries(CERT_TABLES).map(([kind,columns])=>`<h3>${kind==='results'?'Pontos de medição':'Padrões utilizados'}</h3>${(record[kind] || []).map((row,i)=>`<fieldset><legend>${i+1}</legend><div class="grid-2">${Object.entries(columns).map(([k,l])=>`<label>${escapeHtml(l)}<input class="input" data-table="${kind}" data-row="${i}" data-key="${k}" value="${escapeHtml(row[k] || '')}"></label>`).join('')}</div><button type="button" data-remove="${kind}" data-index="${i}">Remover linha</button></fieldset>`).join('')}<button type="button" data-add="${kind}">Adicionar ${kind==='results'?'ponto':'padrão'}</button>`).join('');
 }
 tables();
 dialog.addEventListener('input',e=>{const el=e.target;if(el.dataset.table)record[el.dataset.table][Number(el.dataset.row)][el.dataset.key]=el.value;});
 dialog.addEventListener('click',e=>{const el=e.target;if(el.dataset.add){const k=el.dataset.add;record[k] ||= [];if(record[k].length<100){record[k].push(k === 'results' ? {input_unit:readMetrology('certificate').measurement_unit,output_unit:readMetrology('certificate').measurement_unit} : {});tables();}}if(el.dataset.remove){record[el.dataset.remove].splice(Number(el.dataset.index),1);tables();}});
 const num=v=>v.trim()===''?NaN:Number(v.replace(',','.').replace(/%$/,'').trim());
 dialog.querySelector('#certificateCalculateEma').onclick=()=>{
  const vals=readMetrology('certificate'),lo=num(vals.range_min),hi=num(vals.range_max),cl=num(vals.accuracy_class);
  if([lo,hi,cl].every(Number.isFinite)&&hi>=lo&&cl>=0)dialog.querySelector('#certificateMetro_ema').value=String(Number(((hi-lo)*cl/100).toFixed(10)));
  else dialog.querySelector('#certificateMetroFeedback').textContent='Informe faixa e classe percentual válidas.';
 };
 dialog.querySelector('#certCalculate').onclick=()=>{
  const vals=readMetrology('certificate'),ema=num(vals.ema),unit=vals.measurement_unit.trim().toLowerCase();
  const inspection=dialog.querySelector('[data-cert="document_type"]').value.trim().toLowerCase()==='carta de inspeção';
  dialog.querySelector('#certFeedback').textContent=(record.results || []).map((r,i)=>{
   const ref=num(r.reference || ''),ind=num(r.indicated || ''),a=(r.input_unit || '').trim().toLowerCase(),b=(r.output_unit || '').trim().toLowerCase();
   if(![ref,ind].every(Number.isFinite)||!a||a!==b)return `Ponto ${i+1}: informe números e unidades iguais.`;
   const error=Number((ind-ref).toFixed(10));
   return `Ponto ${i+1}: erro ${error} ${r.output_unit}. ${!inspection&&Number.isFinite(ema)&&ema>=0&&unit===b?(Math.abs(error)<=ema?'Conforme':'Não conforme'):'Não avaliado: confira EMA, unidade e tipo do documento.'}`;
  }).join(' | ');
 };
 dialog.querySelector('#certClearReadings').onclick=()=>{
  (record.results || []).forEach(row=>{row.indicated='';row.error='';});
  tables();dialog.querySelector('#certFeedback').textContent='Leituras limpas nesta janela. As referências e os demais dados foram mantidos.';
 };
 dialog.querySelector('#certSave').onclick=async()=>{
  if (state.companyId !== companyId) { status.textContent='A empresa ativa mudou. Feche e abra a janela novamente.';return; }

  dialog.querySelectorAll('[data-cert]').forEach(el=>record[el.dataset.cert]=el.value.trim());
  const metrology = readMetrology('certificate');
  if (selected) {
   const button=dialog.querySelector('#certSave');button.disabled=true;
   try {
    const form=new FormData();
    ['tag','name','equipment_type','sector','location','manufacturer','model','serial_number','calibration_date','next_calibration_date','status','notes'].forEach(key=>form.append(key,selected[key] ?? ''));
    Object.entries(metrology).forEach(([key,value])=>form.append(key,value));
    form.append('calibration_record',JSON.stringify(record));
    await updateEquipment(selected.id,form);
    if(state.editingId === selected.id && state.editDraft) {Object.assign(state.editDraft,metrology,{calibration_record:record});}
    dialog.close();dialog.remove();await loadItems();renderApp('<div class="notice success">Certificado e leituras salvos no instrumento selecionado.</div>');
   } catch(error) {status.textContent='Falha ao salvar: '+error.message;button.disabled=false;}
  } else {
   target.calibration_record=record;Object.assign(target,metrology);
   dialog.close();dialog.remove();renderApp();
  }
 };
 dialog.querySelector('#certCancel').onclick=()=>{dialog.close();dialog.remove();};
 dialog.addEventListener('cancel',()=>dialog.remove());dialog.showModal();
};
window.downloadMasterReport = async function(id) {
 try {
 const response=await fetchWithTimeout(`${CONFIG.API_BASE_URL}/equipment/${id}/master-report-pdf`,{headers:getAuthHeaders()});
 if(!response.ok)throw new Error('Não foi possível gerar o relatório mestre.');
 const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download='relatorio-mestre.pdf';a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);
 }catch(e){alert(e.message);}
};
