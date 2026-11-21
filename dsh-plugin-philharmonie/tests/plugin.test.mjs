import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import vm from 'node:vm';
import {PythonBridge,createHandler,validateConfig,validateRequest,availableModels,frameHtml,apply} from '../index.mjs';
import {install,PANEL_ID} from '../client-source.mjs';

const temp=()=>mkdtemp(join(tmpdir(),'phil-dsh-test-'));
const request=(body)=>new Request('http://localhost/api/philharmonie/request',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});
const llm={listProviders:()=>[{id:'local'}],listModels:async()=>[{id:'coder'}]};
test('config and wire inputs reject browser path selection and unsafe identities',()=>{
 assert.throws(()=>validateConfig({demo:true,state:'/REPLACE/WITH/state'}));
 assert.throws(()=>validateConfig({root:'relative',state:'/tmp/state'}));
 assert.throws(()=>validateConfig({root:'/tmp/root',demo:true,state:'/tmp/state'}));
 assert.throws(()=>validateRequest({method:'GET',path:'../../etc/passwd'}));
 assert.throws(()=>validateRequest({method:'GET',path:'config',root:'/etc'}));
 assert.throws(()=>validateRequest({method:'POST',path:'binding',sessionId:'../escape'}));
});
test('active Host model catalog requires explicit runtime model binding and fails closed',async()=>{
 assert.deepEqual(await availableModels(llm,{modelBindings:[{id:'hall-model',provider:'local',model:'coder'}]}),['hall-model']);
 assert.deepEqual(await availableModels(llm,{modelBindings:[{id:'missing',provider:'local',model:'no'}]}),[]);
 assert.deepEqual(await availableModels({listProviders:()=>[{id:'bad'}],listModels:async()=>{throw Error('offline');}},{modelBindings:[{id:'x',provider:'bad',model:'coder'}]}),[]);
});
test('persistent Host bridge composes, binds multiple Sessions and returns real runner decisions',async()=>{
 const state=await temp(),config={state,demo:true},bridge=new PythonBridge(config);
 try{
  await bridge.ready;
  const handler=createHandler(config,{llm,bridge});
  async function call(method,path,body,sessionId='session-one'){
   const r=await handler(request({method,path,body,sessionId}));const data=await r.json();assert.equal(r.status,200,JSON.stringify(data));return data;
  }
  const program=await call('GET','example');
  const compiled=await call('POST','compile',{program});assert.equal(compiled.ready,true);assert.equal(compiled.admit,false);
  await call('POST','binding',{program});await call('POST','binding',{program},'session-two');
  const started=await call('POST','runs',{program});
  let result;const deadline=Date.now()+10000;
  do{await new Promise(r=>setTimeout(r,60));result=await call('GET','runs/'+started.id);}while(!['completed','failed'].includes(result.status)&&Date.now()<deadline);
  assert.equal(result.status,'completed');assert.deepEqual(result.events.filter(e=>e.type==='loop_decision').map(e=>e.decision),['keep','crash','keep','discard']);
  assert.equal((await call('GET','session',undefined,'session-two')).run.id,started.id);
  assert.equal((await call('GET','session',undefined,'unbound')).binding,null);
  // Restart preserves binding and run identity, without replay.
  bridge.dispose();await new Promise(resolve=>bridge.child.once('close',resolve));
  const again=new PythonBridge(config);try{await again.ready;const data=await again.call({method:'GET',path:'session',sessionId:'session-one'});assert.equal(data.run.id,started.id);}finally{again.dispose();await new Promise(resolve=>again.child.once('close',resolve));}
 }finally{bridge.dispose();await rm(state,{recursive:true,force:true});}
});
test('browser cannot select filesystem paths or arbitrary Host operations',async()=>{
 const handler=createHandler({}, {llm,bridge:{ready:Promise.resolve(),call:()=>{throw Error('must not dispatch');}}});
 const r=await handler(request({method:'GET',path:'config',state:'/etc'}));assert.equal(r.status,400);
 const large=await handler(new Request('http://localhost/x',{method:'POST',headers:{'content-type':'application/json'},body:' '.repeat(1024*1024+1)}));assert.equal(large.status,413);
});
test('official additive slots register and dispose without replacing header or conversation',()=>{
 const entries=[],effects=[],selected=[];
 const ctx={slots:{inject:(_name,f)=>f(),register:(options,component)=>{entries.push({options,component});return()=>{};}},layout:{selectPanel:id=>selected.push(id)},effect:f=>effects.push(f())};
 const api=install({},ctx);api.select('session-one');assert.deepEqual(selected,[PANEL_ID]);
 assert.deepEqual(entries.map(e=>e.options.name),['main','sidebar.panellist','conversation.session.header.actions']);
 assert.equal(entries[1].options.label(),'Concert Hall');assert.equal(entries[2].options.id,'philharmonie.open-hall');
 for(const dispose of effects)dispose?.();
});
test('packaged client speaks the official closure-factory protocol and shares React',async()=>{
 let row;vm.runInNewContext(await readFile(new URL('../client.js',import.meta.url),'utf8'),{window:{__ModuleLoader__:{load:x=>row=x}}});
 assert.equal(row.id,'dsh-plugin-philharmonie');let requested;const face=row.factory(id=>{requested=id;return {};});
 const ctx={slots:{inject:()=>{}},effect:()=>{}};assert.equal(face.apply(ctx),undefined,'Cordis apply must not return the private controller object');assert.equal(requested,'react');assert.deepEqual([...face.inject],['slots','layout']);
});
test('frame assets are document-relative and Host routes have owned lifecycle disposers',async()=>{
 const html=await frameHtml();assert.match(html,/src="frame.mjs"/);assert.match(html,/href="styles.css"/);assert.doesNotMatch(html,/__TOKEN__/);
 const state=await temp(),routes=[],cleanup=[];
 const ctx={llm,connection:{fetch:{register:route=>{routes.push(route);return()=>{};}}},effect:f=>cleanup.push(f())};
 try{await apply(ctx,{state,demo:true});assert.equal(routes.length,7);assert.ok(routes.every(r=>r.path.startsWith('/api/philharmonie/')));assert.ok(routes.find(r=>r.path.endsWith('/request')).methods.includes('POST'));}
 finally{for(const f of cleanup)await f?.();await rm(state,{recursive:true,force:true});}
});
