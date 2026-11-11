// Local, opt-in event instrumentation. This module never executes a hook.
export const motifs = Object.freeze({
  start:       {notes:[392,523,659], rank:3},
  complete:    {notes:[523,659,784,1046], rank:8},
  failure:     {notes:[233,220,174], rank:9},
  pause:       {notes:[440,440], rank:3},
  resume:      {notes:[440,587], rank:3},
  cancel:      {notes:[392,294], rank:7},
  keep:        {notes:[523,659,784], rank:5},
  discard:     {notes:[493,440], rank:4},
  crash:       {notes:[207,196], rank:7},
  hook_pass:   {notes:[784,1046], rank:4},
  hook_block:  {notes:[294,277], rank:10},
  step:        {notes:[659], rank:1},
  saved:       {notes:[523], rank:2},
});

export function eventCue(event, detailed=false) {
  if(event.type==='loop_decision')return ['keep','discard','crash'].includes(event.decision)?event.decision:null;
  if(event.type==='hook_result')return ({pass:'hook_pass',fail:'failure',blocked:'hook_block'})[event.outcome]||null;
  return ({run_completed:'complete',run_failed:'failure',manual_reconciliation:'hook_block',step_failed:'crash',...(detailed?{step_completed:'step'}:{})})[event.type]||null;
}

// One cursor, not an ever-growing event cache. Selecting history seeds silently.
export class RunMusic {
  constructor(play){this.play=play;this.id=null;this.cursor=0;this.status=null;this.detailed=false;}
  begin(id){this.id=id;this.cursor=0;this.status='created';}
  observe(id,run,family){
    const events=run.events||[];
    if(id!==this.id){this.id=id;this.cursor=events.length;this.status=run.status;return;}
    const cues=events.slice(this.cursor).map(e=>eventCue(e,this.detailed));
    if(this.status!==run.status)cues.push(({paused:'pause',running:this.status==='paused'?'resume':null,cancelled:'cancel',completed:'complete',failed:'failure',needs_reconciliation:'hook_block'})[run.status]);
    this.cursor=events.length;this.status=run.status;
    // A fast loop can finish between polls: keep the most significant cue,
    // rather than replaying a queue of old sounds over the current state.
    const cue=cues.filter(c=>motifs[c]).sort((a,b)=>motifs[b].rank-motifs[a].rank)[0];
    if(cue)this.play(cue,family);
  }
}

export class SoundDesk {
  constructor({createContext=()=>new (globalThis.AudioContext||globalThis.webkitAudioContext)(),visible=()=>!globalThis.document?.hidden,now=()=>performance.now()}={}){
    this.createContext=createContext;this.visible=visible;this.now=now;
    this.enabled=false;this.volume=.18;this.context=null;this.voices=new Set();this.last=-Infinity;this.rank=0;
  }
  async enable(){
    try{
      if(!this.context||this.context.state==='closed'){this.context=this.createContext();this.master=null;}
      if(!this.master){this.master=this.context.createGain();this.master.connect(this.context.destination);}
      await this.context.resume();
      if(this.context.state!=='running')throw Error('Audio suspended');
      this.enabled=true;this.master.gain.value=this.volume;return true;
    }catch{this.disable();return false;}
  }
  hush(){for(const node of this.voices){try{node.stop();}catch{/* Already ended. */}}this.voices.clear();}
  disable(){this.enabled=false;this.hush();if(this.master)this.master.gain.value=0;}
  setVolume(value){this.volume=Number.isFinite(value)?Math.min(.35,Math.max(0,value)):0;if(this.master)this.master.gain.value=this.enabled?this.volume:0;}
  play(cue,family='coding'){
    const motif=typeof cue==='string'&&Object.hasOwn(motifs,cue)?motifs[cue]:null;
    if(!motif||!this.enabled||!this.visible()||!this.volume||this.context?.state!=='running')return false;
    const now=this.now();
    if(now-this.last<700){if(motif.rank<=this.rank)return false;this.hush();}
    this.last=now;this.rank=motif.rank;
    try{
      motif.notes.forEach((frequency,index)=>{
        const node=this.context.createOscillator(),gain=this.context.createGain();
        const start=this.context.currentTime+index*.095,end=start+.14;
        node.type=family==='ai4science'?'sine':'triangle';node.frequency.value=frequency;
        gain.gain.setValueAtTime(0,start);gain.gain.linearRampToValueAtTime(.3,start+.008);gain.gain.exponentialRampToValueAtTime(.001,end);
        node.connect(gain);gain.connect(this.master);this.voices.add(node);
        node.onended=()=>{this.voices.delete(node);node.disconnect();gain.disconnect();};
        node.start(start);node.stop(end+.01);
      });
      return true;
    }catch{this.disable();return false;}
  }
  dispose(){this.disable();void this.context?.close().catch(()=>{});}
}
