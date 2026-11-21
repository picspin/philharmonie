// Observe the real browser Web Audio graph; do not replace its implementation.
(() => {
  window.__audioProbe={nodes:0,states:[]};
  const Audio=window.AudioContext||window.webkitAudioContext;
  if(!Audio)return;
  const original=Audio.prototype.createOscillator;
  Audio.prototype.createOscillator=function(...args){
    const result=original.apply(this,args);
    window.__audioProbe.nodes++;window.__audioProbe.states.push(this.state);
    return result;
  };
})();
