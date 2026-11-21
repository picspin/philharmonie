import test from 'node:test';
import assert from 'node:assert/strict';
import {RunMusic,SoundDesk,eventCue} from '../web/sound.mjs';

test('only declared outcomes produce a hook or decision cue',()=>{
  assert.equal(eventCue({type:'hook_result',outcome:'pass'}),'hook_pass');
  assert.equal(eventCue({type:'hook_result',outcome:'blocked'}),'hook_block');
  assert.equal(eventCue({type:'hook_result',outcome:'fail'}),'failure');
  assert.equal(eventCue({type:'hook_result',outcome:'pending'}),null);
  assert.equal(eventCue({type:'step_completed'}),null);
  assert.equal(eventCue({type:'step_completed'},true),'step');
  assert.equal(eventCue({type:'loop_decision',decision:'crash'}),'crash');
});
test('history selection is silent and repeated polling never replays events',()=>{
  const calls=[],music=new RunMusic((...args)=>calls.push(args));
  const history={status:'completed',events:[{type:'run_completed'}]};
  music.observe('old',history,'coding');music.observe('old',history,'coding');
  assert.deepEqual(calls,[]);
  music.begin('new');
  const running={status:'running',events:[{type:'loop_decision',decision:'keep'}]};
  music.observe('new',running,'ai4science');music.observe('new',running,'ai4science');
  assert.deepEqual(calls,[['keep','ai4science']]);
  music.observe('old',history,'coding');music.observe('new',running,'coding');
  assert.equal(calls.length,1);
});
test('a poll burst coalesces to its most significant event, including status-only controls',()=>{
  const calls=[],music=new RunMusic(c=>calls.push(c));music.begin('r');
  const events=[{type:'loop_decision',decision:'keep'},{type:'loop_decision',decision:'discard'},{type:'step_failed'}];
  music.observe('r',{status:'running',events});assert.deepEqual(calls,['crash']);
  music.observe('r',{status:'paused',events});music.observe('r',{status:'paused',events});
  music.observe('r',{status:'running',events});
  music.observe('r',{status:'completed',events:[...events,{type:'run_completed'}]});
  assert.deepEqual(calls,['crash','pause','resume','complete']);
});
function fixture(){
  const nodes=[];let time=1000,visible=true;
  const gain=()=>({gain:{value:0,setValueAtTime(){},linearRampToValueAtTime(){},exponentialRampToValueAtTime(){}},connect(){},disconnect(){}});
  const ctx={state:'suspended',currentTime:1,destination:{},createGain:gain,
    async resume(){this.state='running';},async close(){this.state='closed';},
    createOscillator(){const node={frequency:{value:0},connect(){},disconnect(){},start(){},stop(){this.stopped=true;}};nodes.push(node);return node;}};
  const desk=new SoundDesk({createContext:()=>ctx,now:()=>time,visible:()=>visible});
  return {desk,nodes,ctx,advance:()=>time+=1000,hide:()=>{visible=false;}};
}
test('opt-in, browser availability, visibility and volume all gate synthesis',async()=>{
  const {desk,nodes,hide,advance}=fixture();assert.equal(desk.play('start'),false);assert.equal(desk.context,null);
  assert.equal(await desk.enable(),true);assert.equal(desk.play('start','ai4science'),true);
  assert.ok(nodes.every(n=>n.type==='sine'));advance();hide();assert.equal(desk.play('complete'),false);
  desk.disable();assert.ok(nodes.every(n=>n.stopped));assert.equal(desk.play('failure'),false);
  const noAudio=new SoundDesk({createContext:()=>{throw Error('unsupported');}});assert.equal(await noAudio.enable(),false);
  const zero=fixture();await zero.desk.enable();zero.desk.setVolume(NaN);assert.equal(zero.desk.play('start'),false);
});
test('rapid cues cannot build a backlog, and higher-priority failure interrupts lower-priority notes',async()=>{
  const {desk,nodes}=fixture();await desk.enable();desk.play('keep');
  const count=nodes.length;assert.equal(desk.play('step'),false);assert.equal(nodes.length,count);
  assert.equal(desk.play('failure'),true);assert.ok(nodes.slice(0,count).every(n=>n.stopped));
  assert.equal(desk.play('__proto__'),false);assert.equal(desk.enabled,true);
  desk.dispose();assert.equal(desk.enabled,false);
});
