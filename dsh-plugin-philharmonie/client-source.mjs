// The build wraps this dependency-free source in DSH's closure-factory protocol.
export const PANEL_ID='philharmonie.concert-hall';
export const inject=['slots','layout'];
export function install(React,ctx) {
  let selectedSession=null;
  const listeners=new Set();
  const select=session=>{selectedSession=session;for(const f of listeners)f();ctx.layout.selectPanel(PANEL_ID);};
  function Panel(){
    const session=React.useSyncExternalStore(f=>{listeners.add(f);return()=>listeners.delete(f);},()=>selectedSession,()=>null);
    const url=new URL('api/philharmonie/frame',document.baseURI);if(session)url.searchParams.set('sessionId',session);
    return React.createElement('iframe',{key:session||'global',src:url.href,title:'Philharmonie Concert Hall',style:{width:'100%',height:'100%',minHeight:'400px',border:0,display:'block',paddingTop:'var(--dsh-frame-top-clearance, 0px)'},referrerPolicy:'same-origin'});
  }
  function Header({sessionId}) {
    const [label,setLabel]=React.useState('Concert Hall');
    React.useEffect(()=>{
      let alive=true;const controller=new AbortController();
      const pull=async()=>{try{const response=await fetch(new URL('api/philharmonie/request',document.baseURI),{method:'POST',credentials:'same-origin',signal:controller.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({method:'GET',path:'session',sessionId})});if(!response.ok)throw Error('unavailable');const data=await response.json();if(alive)setLabel(data.binding?`${data.binding.program.task.summary.slice(0,22)} · ${data.run?.status||'已关联'}`:'Concert Hall · 未关联');}catch{if(alive)setLabel('Concert Hall · 状态不可用');}};
      void pull();const timer=setInterval(pull,3000);return()=>{alive=false;controller.abort();clearInterval(timer);};
    },[sessionId]);
    return React.createElement('button',{type:'button',title:'打开乐团大厅；保留当前 DSH 会话',onClick:()=>select(sessionId),style:{font:'inherit',maxWidth:'180px',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap',border:'1px solid currentColor',borderRadius:'5px',background:'transparent',color:'inherit',padding:'3px 8px',cursor:'pointer'}},'♮ '+label);
  }
  const Icon=({size=20})=>React.createElement('span',{'aria-hidden':true,style:{fontSize:size}},'♮');
  ctx.slots.inject('main',()=>ctx.slots.register({name:'main',key:PANEL_ID},Panel));
  ctx.slots.inject('sidebar.panellist',()=>ctx.slots.register({name:'sidebar.panellist',id:PANEL_ID,label:()=> 'Concert Hall',order:50},Icon));
  ctx.slots.inject('conversation.session.header.actions',()=>ctx.slots.register({name:'conversation.session.header.actions',id:'philharmonie.open-hall',order:50},Header));
  ctx.effect(()=>()=>listeners.clear(),'philharmonie: panel subscriptions');
  return {select};
}
