const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const code = fs.readFileSync('admin/app.js', 'utf8').split('const CONFIG =')[0];
const elements = {};
const state = {createForm: {}, editDraft: {}};
const sandbox = {state, document: {getElementById: id => elements[id]}, escapeHtml: value => String(value).replaceAll('<','&lt;')};
vm.createContext(sandbox);
vm.runInContext(code, sandbox);
for (const prefix of ['create','edit']) {
  const html = sandbox.metrologyHtml(prefix, {range_min:0, resolution:0, measurand:'<text>'});
  assert.equal((html.match(/<input /g) || []).length,8);
  assert(html.includes('value="0"'));
  assert(html.includes('&lt;text>'));
  const keys=['measurand','measurement_unit','range_min','range_max','accuracy_class','resolution','ema','reading_contribution'];
  for (const id of [...keys.map(k=>prefix+'Metro_'+k), prefix+'CalculateEma',prefix+'MetroFeedback']) {
    elements[id]={value:'', handlers:{}, addEventListener(event,callback){this.handlers[event]=callback;}};
  }
  sandbox.bindMetrology(prefix);
  elements[prefix+'Metro_range_min'].value='0';
  elements[prefix+'Metro_range_max'].value='630';
  elements[prefix+'Metro_accuracy_class'].value='2,0';
  elements[prefix+'CalculateEma'].handlers.click();
  assert.equal(elements[prefix+'Metro_ema'].value,'12,6');
  const draft = prefix === 'create' ? state.createForm : state.editDraft;
  assert.equal(draft.ema,'12,6');
  elements[prefix+'Metro_ema'].value='9,5';
  elements[prefix+'Metro_ema'].handlers.input();
  assert.equal(draft.ema,'9,5');
  elements[prefix+'Metro_range_min'].value='';
  elements[prefix+'CalculateEma'].handlers.click();
  assert.equal(elements[prefix+'Metro_ema'].value,'9,5');
  assert(elements[prefix+'MetroFeedback'].textContent.includes('válida'));
}
console.log('Metrology UI: create/edit, zero, escaping, decimal comma, calculation, manual override and invalid range passed.');
