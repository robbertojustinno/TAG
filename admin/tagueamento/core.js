(function(root){
'use strict';
const normalize=v=>String(v||'').trim().toUpperCase();
const code=(v,label)=>{const s=normalize(v);if(!/^[A-Z0-9_-]{1,20}$/.test(s))throw Error(label+': use até 20 letras sem acentos, números, hífen ou sublinhado.');return s;};
const tag=v=>{const s=normalize(v);if(!/^[A-Z0-9_-]{1,80}$/.test(s))throw Error('Identificação inválida (máximo de 80 caracteres).');return s;};
const types={R:'Reator / misturador',TK:'Tanque',B:'Bomba',COMP:'Compressor',EQ:'Outro equipamento'};
const quantities={P:'Pressão',T:'Temperatura',F:'Vazão',L:'Nível'};
const functions={I:'Indicação',T:'Transmissão',C:'Controle',IC:'Indicação e controle',IA:'Indicação e alarme'};
function addWorkshop(state,d,id){
 const value=code(d.code,'Código da oficina');
 if(!String(d.name||'').trim())throw Error('Informe o nome da oficina.');
 if(state.workshops.some(x=>x.code===value))throw Error('Essa oficina já existe.');
 return {...state,workshops:[...state.workshops,{id,code:value,name:d.name.trim(),tag:value}]};
}
function addSubsection(state,d,id){
 const workshop=state.workshops.find(x=>x.id===d.workshopId);if(!workshop)throw Error('Selecione a oficina.');
 const value=code(d.code,'Código da subseção');
 if(!String(d.name||'').trim())throw Error('Informe o nome da subseção.');
 if(state.subsections.some(x=>x.workshopId===workshop.id&&x.code===value))throw Error('Essa subseção já existe nesta oficina.');
 return {...state,subsections:[...state.subsections,{id,workshopId:workshop.id,code:value,name:d.name.trim(),tag:workshop.code+'-'+value}]};
}
function equipmentTag(state,d){
 const sub=state.subsections.find(x=>x.id===d.subsectionId);if(!sub)throw Error('Cadastre e selecione primeiro a subseção.');
 if(!types[d.type])throw Error('Selecione o tipo de equipamento.');
 const prefix=sub.tag+'-'+d.type;let n=1;
 const used=new Set(state.equipments.map(x=>x.tag));
 while(used.has(prefix+String(n).padStart(3,'0')))n++;
 return tag(prefix+String(n).padStart(3,'0'));
}
function unique(state,company,value){if([...state.equipments,...state.instruments].some(x=>normalize(x.company)===normalize(company)&&normalize(x.tag)===value))throw Error('Essa tag já existe nesta empresa.');}
function addEquipment(state,d,id){
 if(!String(d.name||'').trim())throw Error('Informe o nome do equipamento.');
 const sub=state.subsections.find(x=>x.id===d.subsectionId);
 const value=equipmentTag(state,d);unique(state,'LOCAL',value);
 return {...state,equipments:[...state.equipments,{...d,company:'LOCAL',unit:sub.tag,area:sub.code,workshopId:sub.workshopId,tag:value,id,createdAt:new Date().toISOString()}]};
}
function nextLoop(state,company){let n=1;const used=new Set(state.instruments.filter(x=>normalize(x.company)===normalize(company)).map(x=>Number(x.loop)));while(used.has(n))n++;return String(n).padStart(3,'0');}
function instrumentTag(state,d){
 const eq=state.equipments.find(x=>x.id===d.equipmentId);if(!eq)throw Error('Cadastre e selecione primeiro o equipamento.');
 if(!quantities[d.quantity]||!functions[d.function])throw Error('Selecione grandeza e função.');
 const loop=d.loopMode==='existing'?String(d.loop||'').trim():nextLoop({...state,instruments:state.instruments.filter(x=>x.equipmentId===eq.id)},eq.company);
 if(!/^[0-9]{1,6}$/.test(loop))throw Error('Informe uma malha de 1 a 6 algarismos.');
 if(d.loopMode==='existing'&&!state.instruments.some(x=>x.equipmentId===eq.id&&x.quantity===d.quantity&&x.loop===loop))throw Error('Selecione uma malha existente da mesma grandeza.');
 return {tag:tag(eq.tag+'-'+d.quantity+d.function+loop.padStart(3,'0')),loop,eq};
}
function addInstrument(state,d,id){
 if(!String(d.description||'').trim())throw Error('Informe a descrição do instrumento.');
 const proposed=instrumentTag(state,d);unique(state,proposed.eq.company,proposed.tag);
 const {company,unit,area}=proposed.eq;
 return {...state,instruments:[...state.instruments,{...d,id,tag:proposed.tag,loop:proposed.loop,company,unit,area,parent:proposed.eq.tag,createdAt:new Date().toISOString()}]};
}
function updateRecord(state,kind,id,d){
 if(!['workshops','subsections','equipments','instruments'].includes(kind))throw Error('Tipo inválido.');
 const old=state[kind].find(x=>x.id===id);if(!old)throw Error('Registro não encontrado.');
 let next={...state,[kind]:state[kind].filter(x=>x.id!==id)};
 if(kind==='workshops')next=addWorkshop(next,d,id);
 if(kind==='subsections')next=addSubsection(next,d,id);
 if(kind==='equipments'){
  if(!String(d.name||'').trim())throw Error('Informe o nome do equipamento.');
  if(old.subsectionId===d.subsectionId&&old.type===d.type)next={...next,equipments:[...next.equipments,{...old,name:d.name.trim()}]};
  else next=addEquipment(next,d,id);
 }
 if(kind==='instruments'){
  if(!String(d.description||'').trim())throw Error('Informe a descrição do instrumento.');
  if(d.loopMode==='keep'){
   if(d.equipmentId!==old.equipmentId)throw Error('Ao mover o instrumento, selecione nova malha ou uma malha do destino.');
   const eq=state.equipments.find(x=>x.id===d.equipmentId);
   if(!quantities[d.quantity]||!functions[d.function])throw Error('Selecione grandeza e função.');
   const value=tag(eq.tag+'-'+d.quantity+d.function+String(old.loop).padStart(3,'0'));unique(next,eq.company,value);
   next={...next,instruments:[...next.instruments,{...old,...d,tag:value,loop:old.loop}]};
  }else next=addInstrument(next,d,id);
 }
 next[kind]=state[kind].map(x=>x.id===id?{...old,...next[kind].find(y=>y.id===id),updatedAt:new Date().toISOString()}:x);
 if(kind==='workshops')next.subsections=next.subsections.map(sub=>sub.workshopId===id?{...sub,tag:next.workshops.find(w=>w.id===id).tag+'-'+sub.code}:sub);
 next.equipments=next.equipments.map(eq=>{
  const sub=next.subsections.find(x=>x.id===eq.subsectionId),before=state.subsections.find(x=>x.id===eq.subsectionId);
  if(!sub)return eq;
  const value=before&&eq.tag.startsWith(before.tag+'-')?tag(sub.tag+eq.tag.slice(before.tag.length)):eq.tag;
  return {...eq,tag:value,workshopId:sub.workshopId,unit:sub.tag,area:sub.code};
 });
 next.instruments=next.instruments.map(i=>{
  const eq=next.equipments.find(x=>x.id===i.equipmentId),before=state.equipments.find(x=>x.id===i.equipmentId);
  if(!eq||!before)return i;
  return {...i,parent:eq.tag,unit:eq.unit,area:eq.area,tag:i.tag.startsWith(before.tag+'-')?tag(eq.tag+i.tag.slice(before.tag.length)):i.tag};
 });
 const seen=new Set();for(const x of [...next.subsections,...next.equipments,...next.instruments]){const key=(x.company||'LOCAL')+':'+x.tag;if(seen.has(key))throw Error('A alteração geraria uma tag duplicada.');seen.add(key);}
 return next;
}
function deleteRecord(state,kind,id){
 if(!['workshops','subsections','equipments','instruments'].includes(kind)||!state[kind].some(x=>x.id===id))throw Error('Registro não encontrado.');
 const children={workshops:['subsections','workshopId'],subsections:['equipments','subsectionId'],equipments:['instruments','equipmentId']}[kind];
 if(children&&state[children[0]].some(x=>x[children[1]]===id))throw Error('Este registro possui vínculos. Exclua ou mova primeiro os itens vinculados.');
 return {...state,[kind]:state[kind].filter(x=>x.id!==id)};
}
function migrate(old){const state={version:2,equipments:[],instruments:[]};for(const r of old){let eq=state.equipments.find(x=>x.tag===normalize(r.parent)&&x.unit===normalize(r.unit)&&x.area===normalize(r.area));if(!eq){eq={id:'legacy-eq-'+state.equipments.length,company:'LEGADO',unit:normalize(r.unit),area:normalize(r.area),name:r.equipment,tag:normalize(r.parent),type:'EQ'};state.equipments.push(eq);}state.instruments.push({...r,company:'LEGADO',equipmentId:eq.id});}return state;}
function csv(state){const fields=['tipo','empresa','unidade','area','tag','descricao','equipamento_id','tag_equipamento','grandeza','funcao','malha'];const rows=[...state.equipments.map(e=>['Equipamento',e.company,e.unit,e.area,e.tag,e.name,e.id,'','','','']),...state.instruments.map(i=>['Instrumento',i.company,i.unit,i.area,i.tag,i.description,i.equipmentId,i.parent,i.quantity,i.function,i.loop])];const q=v=>'"'+String(v??'').replace(/^[=+@\-\t\r]/,"'$&").replaceAll('"','""')+'"';return '\uFEFF'+[fields,...rows].map(r=>r.map(q).join(';')).join('\r\n');}
function parseCSV(text){
 if(typeof text!=='string'||text.length>5000000)throw Error('CSV inválido ou maior que 5 MB.');
 text=text.replace(/^\uFEFF/,'');
 const first=text.split(/\r?\n/,1)[0],delimiter=first.includes(';')?';':first.includes('\t')?'\t':',';
 const rows=[];let row=[],field='',quoted=false,closed=false;
 for(let i=0;i<text.length;i++){
  const c=text[i];
  if(quoted){if(c==='"'){if(text[i+1]==='"'){field+='"';i++;}else{quoted=false;closed=true;}}else field+=c;continue;}
  if(c==='"'){if(field||closed)throw Error('Aspas inválidas no CSV.');quoted=true;continue;}
  if(c===delimiter||c==='\n'||c==='\r'){row.push(field);field='';closed=false;if(c!==delimiter){if(c==='\r'&&text[i+1]==='\n')i++;if(row.some(v=>v.trim()))rows.push(row);row=[];}continue;}
  if(closed)throw Error('Conteúdo inválido após aspas no CSV.');field+=c;
 }
 if(quoted)throw Error('Aspas não fechadas no CSV.');
 row.push(field);if(row.some(v=>v.trim()))rows.push(row);
 if(rows.length<2)throw Error('O CSV não contém registros.');
 const headers=rows.shift().map(h=>h.trim().toLowerCase());
 const required=['tipo','unidade','area','tag','descricao','equipamento_id','tag_equipamento','grandeza','funcao','malha'];
 if(new Set(headers).size!==headers.length||required.some(h=>!headers.includes(h)))throw Error('Use o modelo exportado pelo Tagueamento: faltam colunas obrigatórias ou há colunas repetidas.');
 if(rows.length>10000)throw Error('Importe até 10.000 linhas por arquivo.');
 return rows.map((values,index)=>{if(values.length!==headers.length)throw Error('Quantidade de colunas inválida na linha '+(index+2)+'.');return {...Object.fromEntries(headers.map((h,i)=>[h,values[i].trim()])),line:index+2};});
}
function importCSV(current,text,idFactory){
 const rows=parseCSV(text),next=JSON.parse(JSON.stringify(current)),created={workshops:0,subsections:0,equipments:0,instruments:0};let skipped=0;
 const fail=(r,msg)=>{throw Error('Linha '+r.line+': '+msg);};
 const equipmentRows=rows.filter(r=>normalize(r.tipo)==='EQUIPAMENTO'),instrumentRows=rows.filter(r=>normalize(r.tipo)==='INSTRUMENTO');
 for(const r of rows){if(!['EQUIPAMENTO','INSTRUMENTO'].includes(normalize(r.tipo)))fail(r,'Tipo deve ser Equipamento ou Instrumento.');if(!r.descricao||r.descricao.length>120)fail(r,'Informe descrição de até 120 caracteres.');}
 const references=new Map();
 for(const r of equipmentRows){
  const subtag=normalize(r.unidade),subcode=normalize(r.area),value=tag(r.tag);
  if(!subcode||!subtag.endsWith('-'+subcode))fail(r,'Unidade e área não identificam a subseção.');
  const workshopCode=code(subtag.slice(0,-subcode.length-1),'Oficina');code(subcode,'Subseção');
  if(value.slice(0,subtag.length+1)!==subtag+'-')fail(r,'Tag não corresponde à subseção.');
  const match=value.slice(subtag.length+1).match(/^(R|TK|B|COMP|EQ)([0-9]{3,6})$/);
  if(!match||Number(match[2])<1)fail(r,'Tipo ou número do equipamento inválido.');
  let workshop=next.workshops.find(w=>w.code===workshopCode);
  if(!workshop){workshop={id:idFactory(),code:workshopCode,tag:workshopCode,name:workshopCode};next.workshops.push(workshop);created.workshops++;}
  let sub=next.subsections.find(s=>s.tag===subtag);
  if(!sub){sub={id:idFactory(),workshopId:workshop.id,code:subcode,tag:subtag,name:subcode};next.subsections.push(sub);created.subsections++;}
  if(sub.workshopId!==workshop.id||sub.code!==subcode)fail(r,'Subseção existente possui outro vínculo.');
  let eq=next.equipments.find(e=>e.tag===value);
  if(eq){if(eq.name!==r.descricao||eq.subsectionId!==sub.id||eq.type!==match[1])fail(r,'Tag já cadastrada com dados diferentes. Edite o cadastro antes de importar.');skipped++;}
  else{eq={id:idFactory(),name:r.descricao,subsectionId:sub.id,workshopId:workshop.id,type:match[1],company:'LOCAL',unit:subtag,area:subcode,tag:value};unique(next,'LOCAL',value);next.equipments.push(eq);created.equipments++;}
  if(r.equipamento_id){const prev=references.get(r.equipamento_id);if(prev&&prev.id!==eq.id)fail(r,'Identificador de equipamento repetido com tags diferentes.');references.set(r.equipamento_id,eq);}
 }
 for(const r of instrumentRows){
  const fromId=references.get(r.equipamento_id)||next.equipments.find(e=>e.id===r.equipamento_id),fromTag=next.equipments.find(e=>e.tag===normalize(r.tag_equipamento)),eq=fromTag||fromId;
  if(!eq||!r.tag_equipamento||eq.tag!==normalize(r.tag_equipamento)||(fromId&&fromId.id!==eq.id))fail(r,'Equipamento vinculado não encontrado ou identificadores inconsistentes.');
  if(normalize(r.unidade)!==eq.unit||normalize(r.area)!==eq.area)fail(r,'Localização não corresponde ao equipamento.');
  const q=normalize(r.grandeza),f=normalize(r.funcao);
  if(!quantities[q]||!functions[f]||!/^\d{1,6}$/.test(r.malha)||Number(r.malha)<1)fail(r,'Grandeza, função ou malha inválida.');
  const loop=r.malha.padStart(3,'0'),value=tag(r.tag);
  if(value!==eq.tag+'-'+q+f+loop)fail(r,'Tag do instrumento não corresponde ao equipamento, à função e à malha.');
  const existing=next.instruments.find(i=>i.tag===value);
  if(existing){if(existing.description!==r.descricao||existing.equipmentId!==eq.id||existing.quantity!==q||existing.function!==f||Number(existing.loop)!==Number(loop))fail(r,'Instrumento existente com dados diferentes.');skipped++;continue;}
  unique(next,'LOCAL',value);next.instruments.push({id:idFactory(),description:r.descricao,equipmentId:eq.id,company:'LOCAL',unit:eq.unit,area:eq.area,parent:eq.tag,quantity:q,function:f,loop,tag:value});created.instruments++;
 }
 return {state:next,created,skipped,rows:rows.length};
}

const api={parseCSV,importCSV,updateRecord,deleteRecord,addWorkshop,addSubsection,normalize,types,quantities,functions,equipmentTag,addEquipment,nextLoop,instrumentTag,addInstrument,migrate,csv};if(typeof module!=='undefined')module.exports=api;else root.Tagging=api;
})(globalThis);
