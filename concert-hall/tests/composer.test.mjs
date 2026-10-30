import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {fresh,chapter,architectureChoices,esc,clone} from '../web/composer.mjs';
const root=fileURLToPath(new URL('../../',import.meta.url));
function compile(program) {
  const result=spawnSync('python3',['-c',"import sys,json;sys.path.insert(0,'scripts');from compile_score import compile_program;print(json.dumps(compile_program(json.loads(sys.argv[1]),draft=True)))",JSON.stringify(program)],{cwd:root,timeout:5000,encoding:'utf8'});
  if(result.status!==0)throw new Error(result.stderr);
  return JSON.parse(result.stdout);
}
test('Coding template compiles as an unresolved agent draft, never fake-ready',()=>{
  const p=compile(fresh());assert.equal(p.ready,false);assert.equal(p.admit,false);assert.equal(p.chairs.violin.routing.assigned_model,null);
});
test('AI4Science template produces a bounded baseline/body loop and declared metric',()=>{
  const p=compile(fresh(true));const body=p.chapters[0].body;
  assert.equal(body.kind,'loop');assert.equal(body.metric.key,'loss');assert.deepEqual(body.edit_paths,['candidate.py']);assert.ok(body.limits.max_iterations>0);
});
test('EDA combines with DDD and serverless without changing role/model contracts',()=>{
  const p=fresh();p.task.context={deployment:'serverless',architecture:['EDA','DDD'],taste:['contract first']};
  const c=compile(p);assert.deepEqual(c.source.task.context.architecture,['EDA','DDD']);assert.equal(c.chairs.violin.section,'violin_1');
  assert.match(architectureChoices.find(([key])=>key==='EDA')[1],/事件驱动/);
});
test('Mixed chapters survive compiler dependency ordering',()=>{
  const p=fresh();const variation=chapter(2,true);variation.depends_on=[p.score.chapters[0].id];p.score.chapters.push(variation);
  const c=compile(p);assert.deepEqual(c.chapters.map(x=>x.form),['mozart_sonata','bach_variation']);
});
test('Independent template copies do not share mutable candidate manifests',()=>{
  const p=fresh(true),copy=clone(p);copy.score.chapters[0].body.edit_paths.push('other.py');assert.deepEqual(p.score.chapters[0].body.edit_paths,['candidate.py']);
});
test('User-controlled graph and event text is escaped for text and attribute contexts',()=>{
  const escaped=esc('<img src=x onerror="alert(1)"> & \'');assert.equal(escaped,'&lt;img src=x onerror=&quot;alert(1)&quot;&gt; &amp; &#39;');
});
