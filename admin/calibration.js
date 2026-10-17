const CERT_FIELDS = {"document_type": "Tipo de documento", "certificate_number": "Número do certificado / CIE", "issue_date": "Data de emissão", "laboratory": "Laboratório emissor", "requester": "Solicitante", "procedure": "Procedimento / método", "temperature": "Temperatura ambiente", "humidity": "Umidade relativa", "observations": "Observações / falha constatada", "conclusion": "Conclusão / condição técnica", "approved_by": "Responsável / signatário informado", "approval_date": "Data da aprovação informada"};
const CERT_TABLES = {"standards": {"identification": "Padrão utilizado", "serial": "Série", "certificate": "Certificado", "laboratory": "Laboratório", "calibration_date": "Calibração", "valid_until": "Validade"}, "results": {"reference": "Entrada", "input_unit": "Grandeza", "indicated": "Valor de saída", "output_unit": "Tipo de saída", "low": "Baixo", "high": "Alto", "uncertainty": "Incerteza (U)", "k": "k"}};
const CERT_POINT_FIELDS = {"span_accuracy": "Exatidão do intervalo (%)", "reading_accuracy": "Exatidão das leituras (%)", "declared_accuracy": "Exatidão declarada", "plus_minus": "Mais / menos", "input_range": "Faixa de entrada", "output_range": "Faixa de saída"};

// Exemplos visuais orientam o preenchimento sem inserir dados no registro.
const CERT_EXAMPLES = {
 certificate_number:'Ex.: CAL-2026-001',issue_date:'Ex.: 16/10/2026',laboratory:'Ex.: Laboratório de Metrologia',requester:'Ex.: Empresa solicitante',procedure:'Ex.: Procedimento PC-001',temperature:'Ex.: 23 °C',humidity:'Ex.: 50 %',observations:'Ex.: Instrumento sem danos aparentes',conclusion:'Ex.: Conforme o critério de aceitação',approved_by:'Ex.: Nome do responsável',approval_date:'Ex.: 16/10/2026',
 span_accuracy:'Ex.: 1 %',reading_accuracy:'Ex.: 0,5 %',declared_accuracy:'Ex.: ±0,02 kgf/cm²',plus_minus:'Ex.: 0,02 kgf/cm²',input_range:'Ex.: 0 a 2 kgf/cm²',output_range:'Ex.: 0 a 2 kgf/cm²',
 tag:'Ex.: TESTE-A-001',name:'Ex.: Manômetro da linha de ar',manufacturer:'Ex.: Fabricante do instrumento',model:'Ex.: Modelo do instrumento',serial_number:'Ex.: SN-001234',equipment_type:'Ex.: Manômetro',sector:'Ex.: Utilidades',location:'Ex.: Linha de ar comprimido',status:'Ex.: Ativo',calibration_date:'Ex.: 16/10/2026',next_calibration_date:'Ex.: 16/10/2027'
};
const CERT_TABLE_EXAMPLES = {
 standards:{identification:'Ex.: Manômetro padrão',serial:'Ex.: PAD-001',certificate:'Ex.: CAL-PAD-2026-001',laboratory:'Ex.: Laboratório emissor',calibration_date:'Ex.: 16/10/2026',valid_until:'Ex.: 16/10/2027'},
 results:{reference:'Ex.: 1,00',input_unit:'Ex.: kgf/cm²',indicated:'Ex.: 1,01',output_unit:'Ex.: kgf/cm²',low:'Ex.: 0,99',high:'Ex.: 1,03',uncertainty:'Ex.: 0,005',k:'Ex.: 2'}
};

const CERT_HELP = {
 document_type:'Selecione certificado de calibração ou carta de inspeção. A carta registra falhas sem avaliar a calibração.',certificate_number:'Identificador do documento emitido pelo laboratório.',issue_date:'Data em que o documento foi emitido.',laboratory:'Nome do laboratório ou entidade responsável pelo documento.',requester:'Empresa ou pessoa que solicitou o serviço.',procedure:'Código ou descrição do método usado na calibração ou inspeção.',temperature:'Temperatura ambiente registrada durante o serviço. Informe também a unidade.',humidity:'Umidade relativa registrada durante o serviço, em porcentagem.',observations:'Registre observações relevantes ou a falha constatada.',conclusion:'Transcreva a conclusão técnica do documento. O exemplo não representa uma aprovação.',approved_by:'Nome do responsável ou signatário que consta no documento; não substitui assinatura.',approval_date:'Data de aprovação que consta no documento.',
 span_accuracy:'Percentual de exatidão relativo ao intervalo, conforme a especificação do instrumento.',reading_accuracy:'Percentual de exatidão relativo ao valor lido, conforme a especificação.',declared_accuracy:'Especificação de exatidão declarada pelo fabricante ou laboratório, com a unidade.',plus_minus:'Parcela adicional indicada com sinal ± na especificação. Informe valor e unidade.',input_range:'Intervalo da grandeza aplicada na entrada, com a unidade.',output_range:'Intervalo do sinal ou indicação de saída, com a unidade.',
 tag:'Identificação do instrumento no cadastro selecionado.',name:'Descrição do instrumento cadastrada na plataforma.',manufacturer:'Fabricante registrado no cadastro do instrumento.',model:'Modelo registrado no cadastro do instrumento.',serial_number:'Número de série registrado no cadastro.',equipment_type:'Tipo do instrumento registrado no cadastro.',sector:'Setor ao qual o instrumento está vinculado.',location:'Local de instalação informado no cadastro.',status:'Condição cadastrada para o instrumento.',calibration_date:'Última calibração informada no cadastro.',next_calibration_date:'Data prevista para a próxima calibração no cadastro.'
};
const CERT_TABLE_HELP = {
 standards:{identification:'Identificação do padrão usado na medição.',serial:'Número de série do padrão.',certificate:'Número do certificado do padrão.',laboratory:'Laboratório que calibrou o padrão.',calibration_date:'Data da calibração do padrão.',valid_until:'Prazo de validade ou próxima calibração definida para o padrão.'},
 results:{reference:'Valor de referência aplicado ao instrumento.',input_unit:'Unidade da entrada aplicada. Para calcular o erro diretamente, use a mesma unidade da saída.',indicated:'Valor efetivamente lido no instrumento.',output_unit:'Unidade do valor de saída ou indicação. Use a mesma unidade da entrada para comparar diretamente.',low:'Limite inferior calculado como valor de saída menos EMA, quando as unidades coincidem.',high:'Limite superior calculado como valor de saída mais EMA, quando as unidades coincidem.',uncertainty:'Incerteza expandida U do ponto, na unidade do resultado. Copie do certificado ou de avaliação própria.',k:'Fator de abrangência associado à incerteza U. Informe o valor do certificado; não presuma que seja 2.'}
};
window.openCalibration = function(prefix, selected = null, instrumentOptions = null) {
 const target = selected || (prefix === 'create' ? state.createForm : state.editDraft);
 const companyId = state.companyId;
 const record = structuredClone(target.calibration_record || {});
 if(!record.results?.length) record.results=[{input_unit:target.measurement_unit || '',output_unit:target.measurement_unit || ''}];
 const dialog = document.createElement('dialog');
 dialog.className = 'calibration-dialog';
 const field = (key,label,value) => key === 'document_type' ? `<label>${fieldHelp(label,CERT_HELP[key])}<select class="input" data-cert="document_type">${['','Certificado de calibração','Carta de inspeção'].map(option=>`<option ${option===(value || '')?'selected':''}>${option}</option>`).join('')}</select></label>` : `<label>${fieldHelp(label,CERT_HELP[key])}<input class="input" data-cert="${key}" placeholder="${escapeHtml(CERT_EXAMPLES[key] || '')}" value="${escapeHtml(value || '')}"></label>`;
 dialog.innerHTML = `<h2>Certificado e leituras do instrumento</h2><label>${fieldHelp("Selecionar instrumento cadastrado","Escolha um instrumento da empresa atual para carregar os dados existentes e inserir as novas leituras.")}<select id="certInstrument" class="input"><option value="">${prefix === 'edit' ? 'Usar o cadastro em edição' : 'Usar o novo cadastro'}</option></select></label><p id="certInstrumentStatus" role="status">Carregando instrumentos da empresa…</p><div class="grid-2 calibration-summary">${[['tag','TAG'],['name','Descrição'],['manufacturer','Fabricante'],['model','Modelo'],['serial_number','Número de série'],['equipment_type','Tipo'],['sector','Setor'],['location','Localização'],['status','Status'],['calibration_date','Última calibração'],['next_calibration_date','Próxima calibração']].map(([key,label])=>`<label>${fieldHelp(label,CERT_HELP[key])}<input class="input" readonly placeholder="${escapeHtml(CERT_EXAMPLES[key] || '')}" value="${escapeHtml(target[key] || '')}"></label>`).join('')}</div><p>Preencha os dados do certificado e os valores lidos. Use a mesma unidade para referência e indicação. Carta de inspeção registra falhas, sem avaliação de calibração.</p><div class="grid-2">${Object.entries(CERT_FIELDS).map(([k,l])=>field(k,l,record[k])).join('')}</div><h3>Critério metrológico do instrumento</h3>${metrologyHtml('certificate',target)}<p>Erro = indicação − referência. A verificação usa |erro| ≤ EMA, sem considerar incerteza. A incerteza e k devem vir do certificado ou de avaliação própria.</p><h3>Parâmetros dos pontos de medição</h3><div class="grid-2">${Object.entries(CERT_POINT_FIELDS).map(([k,l])=>field(k,l,record[k])).join('')}</div><div id="certTables"></div><button type="button" id="certCalculate">Calcular limites, erros e avaliar pontos</button><div id="certFeedback" role="status"></div><button type="button" id="certClearReadings">Limpar leituras para nova medição</button> <button type="button" id="certSave">${selected ? "Salvar no instrumento selecionado" : "Aplicar ao cadastro"}</button> <button type="button" id="certCancel">Cancelar</button>`;
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
  const cell=(kind,row,i,k,label)=>{
   const attrs=`class="input" aria-label="${escapeHtml(label)} — linha ${i+1}" data-table="${kind}" data-row="${i}" data-key="${k}" title="${escapeHtml(CERT_TABLE_HELP[kind]?.[k] || label)}"`;
   if(kind === 'results' && ['input_unit','output_unit'].includes(k)) {
    const value=String(row[k] ?? '');
    const options=[...new Set([...METROLOGY_OPTIONS.measurement_unit, target.measurement_unit, ...((record.results || []).flatMap(point=>[point.input_unit,point.output_unit]))].filter(Boolean))];
    return `<select ${attrs}><option value="">Selecione…</option>${options.map(option=>`<option value="${escapeHtml(option)}" ${option===value?'selected':''}>${escapeHtml(option)}</option>`).join('')}</select>`;
   }
   return `<input ${attrs} placeholder="${escapeHtml(CERT_TABLE_EXAMPLES[kind]?.[k] || '')}" value="${escapeHtml(row[k] ?? '')}">`;
  };
  dialog.querySelector('#certTables').innerHTML=Object.entries(CERT_TABLES).map(([kind,columns])=>{
   const rows=record[kind] || [];
   if(kind==='results') return `<h3>Pontos de medição</h3><p class="muted">Em Grandeza, informe a unidade da entrada (ex.: kgf/cm², °C, bar). Baixo e Alto = valor de saída ± EMA, na mesma unidade.</p><div class="table-wrap calibration-points"><table><thead><tr>${Object.entries(columns).map(([k,label])=>`<th>${fieldHelp(label,CERT_TABLE_HELP[kind][k])}</th>`).join('')}<th>Ação</th></tr></thead><tbody>${rows.map((row,i)=>`<tr>${Object.entries(columns).map(([k,label])=>`<td>${cell(kind,row,i,k,label)}</td>`).join('')}<td><button type="button" data-remove="results" data-index="${i}" aria-label="Remover ponto ${i+1}">Remover</button></td></tr>`).join('')}</tbody></table></div><button type="button" data-add="results">Adicionar ponto</button>`;
   return `<h3>Padrões utilizados</h3>${rows.map((row,i)=>`<fieldset><legend>${i+1}</legend><div class="grid-2">${Object.entries(columns).map(([k,label])=>`<label>${fieldHelp(label,CERT_TABLE_HELP[kind][k])}${cell(kind,row,i,k,label)}</label>`).join('')}</div><button type="button" data-remove="${kind}" data-index="${i}">Remover linha</button></fieldset>`).join('')}<button type="button" data-add="standards">Adicionar padrão</button>`;
  }).join('');
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
   if(!inspection&&Number.isFinite(ind)&&Number.isFinite(ema)&&ema>=0&&unit===b){r.low=String(Number((ind-ema).toFixed(10)));r.high=String(Number((ind+ema).toFixed(10)));}
   if(![ref,ind].every(Number.isFinite)||!a||a!==b)return `Ponto ${i+1}: informe números e unidades iguais.`;
   const error=Number((ind-ref).toFixed(10));
   return `Ponto ${i+1}: erro ${error} ${r.output_unit}. ${!inspection&&Number.isFinite(ema)&&ema>=0&&unit===b?(Math.abs(error)<=ema?'Conforme':'Não conforme'):'Não avaliado: confira EMA, unidade e tipo do documento.'}`;
  }).join(' | ');
  tables();
 };
 dialog.querySelector('#certClearReadings').onclick=()=>{
  (record.results || []).forEach(row=>{row.indicated='';row.error='';row.low='';row.high='';});
  tables();dialog.querySelector('#certFeedback').textContent='Leituras limpas nesta janela. As referências e os demais dados foram mantidos.';
 };
 dialog.querySelector('#certSave').onclick=async()=>{
  if (state.companyId !== companyId) { status.textContent='A empresa ativa mudou. Feche e abra a janela novamente.';return; }

  dialog.querySelectorAll('[data-cert]').forEach(el=>record[el.dataset.cert]=el.value.trim());
  record.results=(record.results || []).filter(row=>Object.entries(row).some(([key,value])=>!['input_unit','output_unit'].includes(key)&&String(value || '').trim()));
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
