import {spawn} from 'node:child_process';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {isAbsolute} from 'node:path';

export const name='philharmonie';
export const inject=['connection','llm'];
export const PREFIX='/api/philharmonie/';
const root=new URL('../',import.meta.url);
const sessionPattern=/^[A-Za-z0-9_-]{1,160}$/;
export function validateConfig(config) {
  if(config?.state?.startsWith('/REPLACE/'))throw Error('set an absolute Philharmonie state directory in the profile configuration');
  if(!config||!isAbsolute(config.state||''))throw Error('Philharmonie requires an absolute state directory');
  if(Boolean(config.root)===Boolean(config.demo))throw Error('choose exactly one of root or demo');
  if(config.root&&!isAbsolute(config.root))throw Error('root must be absolute');
  if(config.registry&&!isAbsolute(config.registry))throw Error('registry must be absolute');
  if(config.python!==undefined&&typeof config.python!=='string')throw Error('python must be a command/path');
  if(config.modelBindings!==undefined&&(!Array.isArray(config.modelBindings)||config.modelBindings.some(x=>!x||typeof x.id!=='string'||typeof x.provider!=='string'||typeof x.model!=='string')))throw Error('modelBindings requires id, provider and model');
  return config;
}
export class PythonBridge {
  constructor(config) {
    this.pending=new Map();this.counter=0;this.closed=false;this.buffer='';
    this.child=spawn(config.python||'python3',[fileURLToPath(new URL('./bridge.py',import.meta.url))],{stdio:['pipe','pipe','pipe']});
    this.child.stdout.setEncoding('utf8');
    this.child.stderr.on('data',()=>{}); // No provider/worker output in the host log.
    this.child.stdout.on('data',chunk=>{
      this.buffer+=chunk;
      if(this.buffer.length>8*1024*1024){this.dispose();return;}
      let end;
      while((end=this.buffer.indexOf('\n'))>=0){const line=this.buffer.slice(0,end);this.buffer=this.buffer.slice(end+1);try{const m=JSON.parse(line),p=this.pending.get(m.id);if(p){clearTimeout(p.timer);this.pending.delete(m.id);m.error?p.reject(Error(m.error)):p.resolve(m.value);}}catch{this.dispose();return;}}
    });
    const failed=()=>{this.closed=true;for(const p of this.pending.values()){clearTimeout(p.timer);p.reject(Error('Philharmonie bridge stopped; reload plugin to recover persisted runs'));}this.pending.clear();};
    this.child.on('error',failed);this.child.on('close',failed);this.child.stdin.on('error',failed);
    this.ready=this.call({operation:'init',config});
  }
  call(message) {
    if(this.closed)return Promise.reject(Error('Philharmonie bridge is closed'));
    return new Promise((resolve,reject)=>{
      const id=++this.counter;
      const timer=setTimeout(()=>{this.pending.delete(id);reject(Error('bridge response timed out; execution outcome may be uncertain; inspect history before starting another run'));},30000);
      this.pending.set(id,{resolve,reject,timer});
      this.child.stdin.write(JSON.stringify({...message,id})+'\n');
    });
  }
  dispose(){this.child.kill();this.closed=true;for(const p of this.pending.values()){clearTimeout(p.timer);p.reject(Error('plugin unloaded'));}this.pending.clear();}
}
export async function availableModels(llm,config) {
  const enabled=new Set();
  await Promise.all(llm.listProviders().map(async provider=>{
    try{const models=await llm.listModels(provider.id);for(const binding of config.modelBindings||[]){if(binding.provider===provider.id&&models.some(m=>m.id===binding.model))enabled.add(binding.id);}}
    catch{/* Missing provider inventory fails closed. */}
  }));
  return [...enabled];
}
export function validateRequest(body) {
  if(!body||typeof body!=='object'||Array.isArray(body)||Object.keys(body).some(x=>!['method','path','body','sessionId'].includes(x)))throw Error('invalid request fields');
  if(body.sessionId!=null&&!sessionPattern.test(body.sessionId))throw Error('invalid Session id');
  if(!['GET','POST'].includes(body.method)||typeof body.path!=='string'||!(/^(config|session|example|scores|runs|compile|binding|runs\/[a-f0-9]{32})$/).test(body.path))throw Error('unsupported route');
  if(body.body!=null&&(typeof body.body!=='object'||Array.isArray(body.body)))throw Error('invalid body');
  return body;
}
export function createHandler(config,{llm,bridge}) {
  return async request=>{
    try{
      if(!(request.headers.get('content-type')||'').startsWith('application/json'))return Response.json({error:'JSON required'},{status:415});
      const raw=await request.text();if(raw.length>1024*1024)return Response.json({error:'request too large'},{status:413});
      const body=validateRequest(JSON.parse(raw));
      await bridge.ready;
      const value=await bridge.call({...body,available:await availableModels(llm,config)});
      return Response.json(value,{headers:{'Cache-Control':'no-store'}});
    }catch(error){return Response.json({error:error.message},{status:400,headers:{'Cache-Control':'no-store'}});}
  };
}
export async function frameHtml() {
  let html=await readFile(new URL('concert-hall/web/index.html',root),'utf8');
  return html.replace('class="wordmark" href="/"','class="wordmark" href="#top"').replace('content="__TOKEN__"','content="host-owner-auth"').replace('href="/styles.css"','href="styles.css"').replace('src="/app.mjs"','src="frame.mjs"');
}
export async function apply(ctx,input) {
  const config=validateConfig(input),bridge=new PythonBridge(config);
  ctx.effect(()=>()=>bridge.dispose(),'philharmonie: Python bridge');
  await bridge.ready;
  const handler=createHandler(config,{llm:ctx.llm,bridge});
  const routes=[['request',['POST'],handler],['frame',['GET'],async()=>new Response(await frameHtml(),{headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'}})]];
  for(const file of ['styles.css','app.mjs','composer.mjs'])routes.push([file,['GET'],async()=>new Response(await readFile(new URL('concert-hall/web/'+file,root)),{headers:{'Content-Type':file.endsWith('.css')?'text/css':'text/javascript','Cache-Control':'no-store'}})]);
  routes.push(['frame.mjs',['GET'],async()=>new Response(await readFile(new URL('./frame.mjs',import.meta.url)),{headers:{'Content-Type':'text/javascript','Cache-Control':'no-store'}})]);
  for(const [path,methods,fetch] of routes)ctx.effect(()=>ctx.connection.fetch.register({path:PREFIX+path,methods,requestBody:'buffered',fetch}),'philharmonie: '+path);
}
