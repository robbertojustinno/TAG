const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync(require('path').join(__dirname, '../viewer/app.js'), 'utf8');
const start = source.indexOf('function parseHybridText(');
const end = source.indexOf('async function resolveQrContent', start);
const context = {
  normalizeText: value => String(value || '').trim(),
  safeJsonParse: value => { try { return JSON.parse(value); } catch { return null; } },
  CONFIG: {QR_PARSE_KEYS: ['tag','codigo','code']}, URL
};
vm.createContext(context);
vm.runInContext(source.slice(start,end), context);
for (const input of ['TAGCHECK | MODO HIBRIDO\nTAG: 6 BOM RDX\nNOME: Manom',
 'TAGCHECK | MODO HIBRIDO\rTAG: 6 BOM RDX\rNOME: Manom',
 'TAG=6 BOM RDX|NOME=Manom', '{"tag":"6 BOM RDX"}',
 'https://example.invalid/?tag=6%20BOM%20RDX']) {
 assert.strictEqual(context.parseHybridText(input).tag,'6 BOM RDX');
}
assert.strictEqual(context.parseHybridText(''),null);
console.log('QR: 6 cases passed.');
