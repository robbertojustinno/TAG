const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..');
function runtime(language,blocked=false){
 const storage=new Map(),listeners={};
 const context={URL,Intl,Date,console,location:{href:'https://example.invalid/manutencao/?lang='+language,replace(url){this.href=url;}},localStorage:{getItem(k){if(blocked)throw Error();return storage.get(k)||null;},setItem(k,v){if(blocked)throw Error();storage.set(k,v);}},document:{baseURI:'https://example.invalid/',documentElement:{},title:'Manutenção Preventiva · TagCheck',addEventListener(k,v){listeners[k]=v;},querySelector(){return null;},querySelectorAll(){return [];}},confirm:()=>true};
 context.window=context;vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(root,'admin/locale.js'),'utf8'),context);return {context,listeners};
}
test('English and Spanish translate preventive labels, errors and dynamic messages',()=>{
 for(const [lang,label]of [['en','Preventive maintenance'],['es','Mantenimiento preventivo']]){
  const {context:c}=runtime(lang);
  assert.equal(c.tcL('Manutenção preventiva'),label);
  assert.notEqual(c.tcL('Importar planilha atualizada'),'Importar planilha atualizada');
  const message=c.tcL('Linha 12: código PREV-007 já pertence a outra TAG. Confira a planilha.');
  assert.match(message,/12/);assert.match(message,/PREV-007/);assert.ok(!message.startsWith('Linha'));
  const multiline=c.tcL('Planilha com erros. Nenhum dado foi gravado.\nLinha 8: a última execução possui histórico. Atualize-a por Registrar execução.');
  assert.ok(!multiline.includes('Nenhum dado'));assert.ok(!multiline.includes('Linha 8'));
 }
});
test('HTML labels translate without changing submitted values, user data or markup',()=>{
 const {context:c}=runtime('en');
 const render=vm.runInContext('(data)=>tcH`<label>Equipamento<input value="${data}"></label><p>${data}</p><option>Conforme</option>`',c);
 const html=render('Pressão');
 assert.match(html,/>Equipment</);assert.match(html,/value="Pressão"/);assert.match(html,/<p>Pressão<\/p>/);
 assert.match(html,/<option value="Conforme">Compliant<\/option>/);
 assert.equal(c.tcH('<button title="Histórico">Histórico</button>'),'<button title="History">History</button>');
});
test('Portuguese stays original and server English errors have Portuguese/Spanish labels',()=>{
 const {context:c}=runtime('pt');assert.equal(c.tcL('Manutenção preventiva'),'Manutenção preventiva');
 assert.equal(c.tcL('Invalid or expired session'),'Sessão inválida ou expirada');
 assert.equal(c.tcL('Instrumento PARTICULAR-123'),'Instrumento PARTICULAR-123');
});
test('Navigation retains selected language even with blocked local storage',()=>{
 const {context:c,listeners}=runtime('es',true);
 assert.equal(new URL(c.TAGCHECK_I18N.url('tagueamento/')).searchParams.get('lang'),'es');
 assert.equal(c.TAGCHECK_I18N.formatDate('2026-11-04'),'4/11/2026');
 listeners.DOMContentLoaded();assert.equal(c.document.title,'Mantenimiento Preventivo · TagCheck');
});
test('Admin and Viewer use the same catalogs and updated language resources',()=>{
 assert.equal(fs.readFileSync(path.join(root,'admin/locale.js'),'utf8'),fs.readFileSync(path.join(root,'viewer/locale.js'),'utf8'));
 for(const f of ['admin/index.html','admin/manutencao/index.html','admin/tagueamento/index.html','viewer/index.html']){
  const html=fs.readFileSync(path.join(root,f),'utf8');assert.match(html,/locale\.js\?v=(?:20261104-complete|20261112-equipment-status)"/);
  assert.ok(html.indexOf('locale.js')<html.indexOf('app.js'));
 }
});
