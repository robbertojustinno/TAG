const fs=require('fs'), path=require('path'), vm=require('vm'), assert=require('assert');
(async()=>{
  for(const file of ['sw.js','viewer/sw.js']){
    const handlers={}; let cacheCalls=0,network=0,response;
    const context={URL, self:{location:{origin:'https://example.invalid'},addEventListener:(name,fn)=>handlers[name]=fn},
      caches:{match:async()=>{cacheCalls++; return {cached:true};}},
      fetch:async()=>{network++;return {private:true};}};
    vm.createContext(context);
    vm.runInContext(fs.readFileSync(path.join(process.env.TAGCHECK_TEST_ROOT || path.join(__dirname,'..'),file),'utf8'),context);
    handlers.fetch({request:{method:'GET',url:'https://example.invalid/equipment',headers:{has:name=>name.toLowerCase()==='authorization'}},respondWith:value=>response=value});
    assert.deepEqual(await response,{private:true},file);
    assert.equal(cacheCalls,0,file+' must not read a shared cache for a session request');
    assert.equal(network,1);
    // The established anonymous offline path remains available.
    handlers.fetch({request:{method:'GET',url:'https://example.invalid/equipment',headers:{has:()=>false}},respondWith:value=>response=value});
    assert.deepEqual(await response,{cached:true});
  }
  console.log('Service workers: authenticated network-only and anonymous legacy cache passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
