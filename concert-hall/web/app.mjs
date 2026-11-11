import {esc, architectureChoices, clone, chapter, fresh} from './composer.mjs';
const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name="hall-token"]').content;
const forms = {custom:'自由序曲',mozart_sonata:'Mozart · Sonata',beethoven_symphony:'Beethoven · Symphony',bach_fugue:'Bach · Fugue',bach_variation:'Bach · Progressive variation',brahms_variation:'Brahms · Variation'};
let config, program, compiled = null, revision = 0, runId = '', busy = false, sourceDirty = false, runStatus = null;
function error(message='') { $('error').hidden = !message; $('error').textContent = message; }
async function api(path, body) {
  if(globalThis.philharmonieTransport)return globalThis.philharmonieTransport(path,body);
  const response = await fetch('/api/'+path, {headers:{'X-Hall-Token':token,...(body?{'Content-Type':'application/json'}:{})},method:body?'POST':'GET',body:body?JSON.stringify(body):undefined});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}
function changed() {
  revision++; sourceDirty=false; compiled = null; $('consent').checked = false;
  $('compile-result').textContent = '有未编译的修改。';
  $('source').value = JSON.stringify(program,null,2); renderGraph(); renderStart();
}
function context() { return program.task.context ||= {}; }
function resetRun() {
  runId='';runStatus=null;$('run-state').textContent='未启动';$('decisions').replaceChildren();$('events').replaceChildren();
  $('run-note').textContent='当前任务尚未选择运行。';$('runs').innerHTML='<option value="">选择运行</option>';
}
function adopt(p) {
  const different=program?.task.id!==p.task.id;
  program=clone(p);if(different)resetRun();changed();renderEditor();renderRoster();
  if(config)void refreshRuns().catch(e=>error(e.message));
}
function renderEditor() {
  $('task').value=program.task.summary;
  $('deployment').value=context().deployment||'local';
  $('taste').value=(context().taste||[]).join(', ');
  $('family').value=(context().taste||[]).includes('ai4science')?'ai4science':'coding';
  $('architectures').innerHTML=architectureChoices.map(([key,label])=>`<label class="chip"><input type="checkbox" value="${key}" ${context().architecture?.includes(key)?'checked':''}>${label}</label>`).join('');
  $('architectures').querySelectorAll('input').forEach(input=>input.onchange=()=>{context().architecture=[...$('architectures').querySelectorAll(':checked')].map(x=>x.value);changed();});
  $('chapter-count').textContent=String(program.score.chapters.length).padStart(2,'0');
  $('chapters').innerHTML=program.score.chapters.map((c,i)=>`<article class="chapter"><span class="number">${String(i+1).padStart(2,'0')}</span><div><input aria-label="章节 ${i+1} 名称" data-name="${i}" value="${esc(c.name)}"><select data-form="${i}" aria-label="章节 ${i+1} 曲式">${Object.entries(forms).map(([id,label])=>`<option value="${id}" ${id===c.form?'selected':''}>${label}</option>`).join('')}${!forms[c.form]?`<option selected>${esc(c.form)}</option>`:''}</select><small>${esc(c.body.kind)} · ${esc(c.id)}${c.depends_on.length?' · after '+esc(c.depends_on.join(', ')):''}</small></div><button class="icon" data-remove="${i}" aria-label="删除章节 ${i+1}" ${program.score.chapters.length===1?'disabled':''}>×</button></article>`).join('');
  $('chapters').querySelectorAll('[data-name]').forEach(input=>input.oninput=()=>{program.score.chapters[+input.dataset.name].name=input.value;changed();});
  $('chapters').querySelectorAll('[data-form]').forEach(select=>select.onchange=()=>{program.score.chapters[+select.dataset.form].form=select.value;changed();});
  $('chapters').querySelectorAll('[data-remove]').forEach(button=>button.onclick=()=>{const [removed]=program.score.chapters.splice(+button.dataset.remove,1);for(const c of program.score.chapters)c.depends_on=c.depends_on.filter(d=>d!==removed.id);changed();renderEditor();});
}
function tree(node) {
  const chair=node.chair ? program.chairs[node.chair] : null;
  const children=node.kind==='loop'?[node.baseline,node.body]:node.children||[];
  return `<li class="tree-${esc(node.kind)}"><div><span class="node-kind">${esc(node.kind)}</span><b>${esc(node.id)}</b>${chair?`<small>${esc(node.chair)} / ${esc(chair.section)}</small>`:''}${node.kind==='loop'?`<small>≤ ${node.limits.max_iterations} variations · ${esc(node.metric.key)} ${esc(node.metric.direction)} · keep / discard / crash</small>`:''}</div>${children.length?`<ul>${children.map(tree).join('')}</ul>`:''}</li>`;
}
function renderGraph() {
  $('ribbon-title').textContent=program?`${program.score.id} · ${program.score.chapters.length} chapters`:'Concert Hall';
  $('ribbon-status').textContent=compiled ? (compiled.ready?'已编译 · 可执行':'已编译 · 路由未就绪') : '草稿 · 未编译';
  if (!program)return;
  $('graph').innerHTML=`<div class="score-graph">${program.score.chapters.map(c=>`<article><p class="eyebrow">${esc(forms[c.form]||c.form)}</p><h3>${esc(c.name)}</h3><p class="muted">${c.depends_on.length?'← '+esc(c.depends_on.join(', ')):'序章 / 无章节依赖'}</p><ul class="tree">${tree(c.body)}</ul></article>`).join('<span class="chapter-arrow" aria-hidden="true">→</span>')}</div>`;
}
function renderRoster() {
  $('roster').innerHTML=Object.entries(program.chairs).map(([id,c])=>{
    const tier=config.tiers[c.section];const route=compiled?.chairs[id]?.routing;
    const models=config.registry.models.filter(m=>m.enabled!==false && (m.tiers.includes(tier)||(config.registry.fallbacks?.[tier]||[]).some(t=>m.tiers.includes(t))));
    return `<div class="chair"><div><b>${esc(id)}</b><span>${esc(c.section)} · ${esc(c.isolation)}</span><small>${esc(tier)}</small></div>${c.executor==='command'?'<span class="pill">0 token · local</span>':`<select data-chair="${esc(id)}" aria-label="${esc(id)} 模型"><option value="">Auto · ${esc(route?.assigned_model||'待解析')}</option>${models.map(m=>`<option value="${esc(m.id)}" ${c.model===m.id?'selected':''}>${esc(m.id)}</option>`).join('')}${c.model&&!models.some(m=>m.id===c.model)?`<option selected value="${esc(c.model)}">${esc(c.model)} · 不兼容</option>`:''}</select>`}</div>`;
  }).join('');
  $('roster').querySelectorAll('select').forEach(select=>select.onchange=()=>{const c=program.chairs[select.dataset.chair];if(select.value)c.model=select.value;else delete c.model;changed();});
}
function renderStart() {
  $('bind-session').disabled=busy||sourceDirty||!config?.sessionId;
  $('start').disabled=busy||sourceDirty||!compiled?.ready||!$('consent').checked;
  const terminal=['completed','failed','cancelled'].includes(runStatus);
  for(const name of ['pause','resume','cancel'])$(name).disabled=busy||!runId||!runStatus||terminal;
  if(runStatus==='paused')$('pause').disabled=true;
  if(!['paused','needs_reconciliation'].includes(runStatus))$('resume').disabled=true;
}
async function action(fn) {
  if(busy)return;busy=true;error();renderStart();
  try{await fn();}catch(e){error(e.message);}finally{busy=false;renderStart();}
}
async function compile() {
  if(sourceDirty)throw new Error('请先应用 JSON 编辑，再编译。');
  const current=revision;const result=await api('compile',{program});
  if(current!==revision)throw new Error('曲谱在编译期间已修改，请重新编译。');
  compiled=result;$('compile-result').textContent=result.ready?'编译通过。请审阅执行范围后确认启动。':result.diagnostics.join('；');renderGraph();renderRoster();
}
async function library() {
  const scores=await api('scores');
  $('library').innerHTML=scores.length?scores.map((s,i)=>`<button data-score="${i}">${esc(s.program.task.summary)}<small>${esc(s.program.score.id)}</small></button>`).join(''):'<p class="muted">保存你的第一份曲谱。</p>';
  $('library').querySelectorAll('button').forEach(b=>b.onclick=()=>adopt(scores[+b.dataset.score].program));
}
async function refreshRuns() {
  const taskId=program.task.id;
  const allRuns=await api('runs');if(taskId!==program.task.id)return;
  const runs=allRuns.filter(r=>r.task.id===taskId);
  $('runs').innerHTML='<option value="">选择运行</option>'+runs.map(r=>`<option value="${r.id}" ${r.id===runId?'selected':''}>${esc(r.task.summary)} · ${esc(r.status)}</option>`).join('');
  if(!runId&&runs.length){runId=runs.at(-1).id;$('runs').value=runId;}
  if(runId)await inspect();
}
async function inspect() {
  const id=runId;const run=await api('runs/'+id);if(id!==runId)return;
  runStatus=run.status;$('run-state').textContent=run.status;renderStart();
  $('run-note').textContent=run.error|| (run.status==='needs_reconciliation'?'执行结果尚不确定。等待 worker 回执后恢复；如无法取得回执，请按文档在 CLI 核对，界面不会自动重放。':'运行 '+id+' · '+run.status);
  const decisions=run.events.filter(e=>e.type==='loop_decision');
  $('decisions').innerHTML=decisions.map(e=>`<div class="decision ${esc(e.decision)}"><span>${esc(e.address)} · #${e.iteration}</span><b>${esc(e.decision)}</b><small>metric ${esc(e.metric??'—')} / best ${esc(e.best_metric)}${e.error?' · '+esc(e.error):''}</small></div>`).join('');
  $('events').innerHTML=run.events.slice(-100).map(e=>`<li><b>${esc(e.type)}</b> ${esc(e.address||'')} <small>${new Date(e.time*1000).toLocaleTimeString()}</small></li>`).join('');
}
$('bind-session').onclick=()=>action(async()=>{
  if(sourceDirty)throw Error('请先应用 JSON 编辑。');
  const current=revision;const result=await api('binding',{program});config.binding=result.binding;
  if(current!==revision)throw Error('已关联先前版本；曲谱已修改，请重新关联。');
  $('session-label').textContent=`当前任务已关联至 DSH Session: ${config.sessionId}`;
});
$('task').oninput=()=>{program.task.summary=$('task').value;changed();};
$('deployment').onchange=()=>{context().deployment=$('deployment').value;changed();};
$('taste').onchange=()=>{context().taste=[...new Set($('taste').value.split(',').map(s=>s.trim()).filter(Boolean))];changed();};
$('family').onchange=()=>{const t=context().taste||[];context().taste=[...t.filter(x=>!['coding','ai4science'].includes(x)),$('family').value];changed();};
$('new').onclick=()=>adopt(fresh($('family').value==='ai4science'));
$('add').onclick=()=>{let n=program.score.chapters.length+1;while(program.score.chapters.some(c=>c.id==='chapter-'+n))n++;const c=chapter(n,$('family').value==='ai4science');c.depends_on=[program.score.chapters.at(-1).id];program.score.chapters.push(c);program.chairs.violin ||= fresh().chairs.violin;program.chairs.snare ||= fresh().chairs.snare;changed();renderEditor();renderRoster();};
$('source').oninput=()=>{sourceDirty=true;compiled=null;$('consent').checked=false;$('compile-result').textContent='有未应用的 JSON 编辑，请先应用。';renderGraph();renderStart();};
$('apply').onclick=()=>action(async()=>{const p=JSON.parse($('source').value);await api('compile',{program:p});adopt(p);});
$('compile').onclick=()=>action(compile);
$('save').onclick=()=>action(async()=>{if(sourceDirty)throw new Error('请先应用 JSON 编辑。');await api('scores',{program});await library();$('compile-result').textContent='曲谱已保存。';});
$('example').onclick=()=>action(async()=>{adopt(await api('example'));$('compile-result').textContent=config.demo?'Bach 离线示例：命令已配套当前 demo 根目录。':'此示例需要 candidate.py 和 SPEC.py；请确认目标目录已包含对应文件。';});
$('consent').onchange=renderStart;
$('start').onclick=()=>action(async()=>{if(!compiled?.ready||!$('consent').checked)return;const result=await api('runs',{program});runId=result.id;$('consent').checked=false;await refreshRuns();});
for(const name of ['pause','resume','cancel'])$(name).onclick=()=>action(async()=>{await api('runs/'+runId,{action:name});await inspect();});
$('runs').onchange=()=>{runId=$('runs').value;if(runId)void action(inspect);};
async function boot() {
  config=await api('config');$('mode').textContent=config.demo?'离线演示 · 真实本地执行':'本地任务目录';$('root').textContent='任务目录：'+config.root;
  $('session-binding').hidden=!config.embedded;
  $('session-label').textContent=config.sessionId?`DSH Session: ${config.sessionId}`:'从 DSH 会话头部打开大厅后，可显式关联任务。';
  $('bind-session').disabled=!config.sessionId;
  adopt(config.binding?.program||(config.demo?await api('example'):fresh()));await library();await refreshRuns();
  setInterval(()=>{if(!busy)refreshRuns().catch(e=>error(e.message));},2000);
}
boot().catch(e=>error(e.message));
