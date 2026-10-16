const CERT_FIELDS = {"document_type": "Tipo de documento", "certificate_number": "Número do certificado / CIE", "issue_date": "Data de emissão", "laboratory": "Laboratório emissor", "requester": "Solicitante", "requester_address": "Endereço do solicitante", "contractor": "Contratante", "contractor_address": "Endereço do contratante", "asset_number": "Patrimônio", "building": "Edifício", "equipment_id": "ID do equipamento", "document_id": "ID do documento", "frequency": "Frequência de calibração", "sensor_id": "Identificação do sensor", "sensor_type": "Tipo de sensor", "sensor_length": "Comprimento do sensor", "sensor_diameter": "Diâmetro do sensor", "compensation": "Compensação", "indication_range": "Faixa de indicação", "division": "Valor de divisão", "group_number": "Número do grupo", "group_name": "Nome do grupo", "span_accuracy": "Exatidão do intervalo (%)", "reading_accuracy": "Exatidão da leitura (%)", "declared_accuracy": "Exatidão declarada", "plus_minus": "Mais / menos", "input_range": "Faixa de entrada", "output_range": "Faixa de saída", "procedure": "Procedimento / método", "temperature": "Temperatura ambiente", "humidity": "Umidade relativa", "stabilization": "Tempo de estabilização (com unidade)", "readings": "Leituras por ponto", "evaluated_range": "Faixa avaliada", "uncertainty_note": "Declaração de incerteza", "observations": "Observações / falha constatada", "limitations": "Restrições e notas do certificado", "gaps": "Pendências / dados não informados", "conclusion": "Conclusão / condição técnica", "decision_rule": "Regra de decisão / critério de aceitação", "approved_by": "Responsável / signatário informado", "approval_date": "Data da aprovação informada"};
const CERT_TABLES = {"standards": {"identification": "Padrão utilizado", "serial": "Série", "certificate": "Certificado", "laboratory": "Laboratório", "calibration_date": "Calibração", "valid_until": "Validade"}, "results": {"reference": "Referência / entrada", "input_unit": "Unidade de entrada", "indicated": "Indicação / saída", "output_unit": "Unidade de saída", "low": "Limite baixo", "high": "Limite alto", "error": "Erro declarado", "uncertainty": "Incerteza expandida", "k": "k", "neff": "neff", "immersion": "Imersão"}};

window.openCalibration = function(prefix) {
 const target = prefix === 'create' ? state.createForm : state.editDraft;
 const record = structuredClone(target.calibration_record || {});
 const dialog = document.createElement('dialog');
 dialog.style.cssText='width:min(1100px,94vw);max-height:90vh;overflow:auto;border:0;border-radius:14px;padding:24px';
 const field = (key,label,value) => key === 'document_type' ? `<label>${escapeHtml(label)}<select class="input" data-cert="document_type">${['','Certificado de calibração','Carta de inspeção'].map(option=>`<option ${option===(value || '')?'selected':''}>${option}</option>`).join('')}</select></label>` : `<label>${escapeHtml(label)}<input class="input" data-cert="${key}" value="${escapeHtml(value || '')}"></label>`;
 dialog.innerHTML = `<h2>Certificado e leituras do instrumento</h2><p>Preencha os dados do certificado e os valores lidos. Use a mesma unidade para referência e indicação. Carta de inspeção registra falhas, sem avaliação de calibração.</p><div class="grid-2">${Object.entries(CERT_FIELDS).map(([k,l])=>field(k,l,record[k])).join('')}</div><h3>Critério metrológico do instrumento</h3>${metrologyHtml('certificate',target)}<p>Erro = indicação − referência. A verificação usa |erro| ≤ EMA, sem considerar incerteza. A incerteza, k e neff devem vir do certificado ou de avaliação própria.</p><div id="certTables"></div><button type="button" id="certCalculate">Calcular erros e avaliar pontos</button><div id="certFeedback" role="status"></div><button type="button" id="certSave">Aplicar ao cadastro</button> <button type="button" id="certCancel">Cancelar</button>`;
 document.body.append(dialog);
 function tables() {
  dialog.querySelector('#certTables').innerHTML=Object.entries(CERT_TABLES).map(([kind,columns])=>`<h3>${kind==='results'?'Pontos de medição':'Padrões utilizados'}</h3>${(record[kind] || []).map((row,i)=>`<fieldset><legend>${i+1}</legend><div class="grid-2">${Object.entries(columns).map(([k,l])=>`<label>${escapeHtml(l)}<input class="input" data-table="${kind}" data-row="${i}" data-key="${k}" value="${escapeHtml(row[k] || '')}"></label>`).join('')}</div><button type="button" data-remove="${kind}" data-index="${i}">Remover linha</button></fieldset>`).join('')}<button type="button" data-add="${kind}">Adicionar ${kind==='results'?'ponto':'padrão'}</button>`).join('');
 }
 tables();
 dialog.addEventListener('input',e=>{const el=e.target;if(el.dataset.table)record[el.dataset.table][Number(el.dataset.row)][el.dataset.key]=el.value;});
 dialog.addEventListener('click',e=>{const el=e.target;if(el.dataset.add){const k=el.dataset.add;record[k] ||= [];if(record[k].length<100){record[k].push({});tables();}}if(el.dataset.remove){record[el.dataset.remove].splice(Number(el.dataset.index),1);tables();}});
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
 dialog.querySelector('#certSave').onclick=()=>{
  dialog.querySelectorAll('[data-cert]').forEach(el=>record[el.dataset.cert]=el.value.trim());
  target.calibration_record=record;Object.assign(target,readMetrology('certificate'));
  dialog.close();dialog.remove();renderApp();
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
