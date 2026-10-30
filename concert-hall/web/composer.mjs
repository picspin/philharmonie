export const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const architectureChoices = [['EDA','事件驱动 / EDA'],['microkernel','Microkernel'],['DDD','领域驱动 / DDD']];
export const clone = x => structuredClone(x);
export function movement(id, chair, extra={}) {return {kind:'movement',id,chair,writes:[],outputs:[],timeout_sec:120,...extra};}
export function chapter(index, research=false) {
  const id='chapter-'+index;
  const verify = movement('verify','snare',{argv:['python3','evaluate.py'],outputs:['metric.json']});
  return {id,name:research?'渐进研究变奏':'实现与验证',form:research?'bach_variation':'mozart_sonata',depends_on:[],body:research ? {
    kind:'loop',id:'variations',edit_paths:['candidate.py'],metric:{path:'metric.json',key:'loss',direction:'min'},limits:{max_iterations:5,max_wall_sec:1800,max_consecutive_failures:2},baseline:clone(verify),body:{kind:'sequence',id:'candidate',children:[movement('implement','violin',{prompt:'Improve candidate.py against the locked SPEC.md. Use previous best metric and iteration feedback.',writes:['candidate.py']}),clone(verify)]}
  } : {kind:'sequence',id:'development',children:[movement('implement','violin',{prompt:'Implement this chapter against the locked SPEC.md. Set explicit file manifests in the score before running.'}),movement('verify','snare',{argv:['python3','-m','unittest','discover']})]}};
}
export function fresh(research=false) {
  return {schema_version:2,task:{id:'task-'+Date.now(),summary:research?'以可复现指标逐轮改进候选':'实现任务目标并验证契约',context:{deployment:'local',architecture:[],taste:['small verified changes',research?'ai4science':'coding']}},score:{id:'score-'+Date.now(),revision:'1',chapters:[chapter(1,research)]},chairs:{violin:{section:'violin_1',executor:'agent',allowed_toolsets:['terminal','file'],isolation:'shared',hall:'hermes'},snare:{section:'snare_drum',executor:'command',allowed_toolsets:['terminal','file'],isolation:'shared'}},ground_bass:['SPEC.md'],budget:{max_wall_sec:3600},parallelism:4};
}
