const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync(path.join(__dirname, '../admin/app.js'), 'utf8');
function extract(name) {
  const match = new RegExp('(?:async )?function '+name+'\\(').exec(source);
  assert(match, name);
  const rest = source.slice(match.index);
  const next = /\n(?:async )?function \w+\(/.exec(rest);
  return next ? rest.slice(0, next.index) : rest;
}
async function run() {
  const requests=[], submitted=[], opened=[];
  const tab={opener:'old',close(){this.closed=true;}};
  const context={
    state:{authToken:'test-session'},
    CONFIG:{API_BASE_URL:'https://api.example.invalid',ENDPOINTS:{login:'/auth/login',list:'/equipment',byTag:'/equipment/tag/:tag'},STORAGE_KEYS:{lastSearch:'test'}},
    t:x=>x, normalizeItem:x=>x, localStorage:{setItem(){}}, crypto:{randomUUID:()=> 'test-tab'},
    window:{open:(url,target)=>{opened.push({url,target});return tab;}},
    document:{body:{appendChild(){}},getElementById:()=>({}),createElement(type){return {type,appendChild(input){this.input=input;},submit(){submitted.push(this);},remove(){this.removed=true;}};}}
  };
  context.fetchWithTimeout=async(url,options)=>{
    requests.push({url,options});
    let body=url.endsWith('/auth/login')?{token:'test-session',username:'legacy'}:
      url.endsWith('/pdf-access')?{token:'test-short-pdf'}:
      url.includes('/tag/')?{id:1,tag:'OLD',name:'Old'}:[{id:1,tag:'OLD',name:'Old'}];
    return {ok:true,json:async()=>body};
  };
  vm.createContext(context);
  for(const name of ['normalizeText','buildUrl','getAuthHeaders','loginAdmin','loadItems','searchByTag','openEquipmentPdf']) vm.runInContext(extract(name),context);
  const login=await context.loginAdmin('legacy','test-password');
  assert.equal(login.username,'legacy');
  assert.deepEqual(JSON.parse(requests[0].options.body),{username:'legacy',password:'test-password'});
  await context.loadItems();
  await context.searchByTag('OLD');
  for(const request of requests.slice(1)) assert.equal(request.options.headers.Authorization,'Bearer test-session');
  await context.openEquipmentPdf();
  assert.equal(opened[0].url,'about:blank');
  assert.equal(tab.opener,null);
  assert.equal(submitted[0].method,'POST');
  assert.equal(submitted[0].action,'https://api.example.invalid/equipment/pdf');
  assert.equal(submitted[0].input.name,'pdf_token');
  assert.equal(submitted[0].input.value,'test-short-pdf');
  assert.equal(submitted[0].target,opened[0].target);
  assert(!submitted[0].action.includes('token'));
  assert.equal(requests.at(-1).options.headers.Authorization,'Bearer test-session');
  const count=requests.length;
  context.window.open=()=>null;
  await context.openEquipmentPdf();
  assert.equal(requests.length,count);
  console.log('Admin: legacy login, authenticated reads, PDF POST/new tab and popup handling passed.');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
