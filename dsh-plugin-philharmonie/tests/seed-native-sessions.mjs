// Seed closed recordings through the installed official persistence provider.
// The browser still uses the real Host, projections, sidebar and Session slots.
// No LLM calls, mocked services, or direct edits to the Host's live stores.
import {createRequire} from 'node:module';
import {realpathSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
const require=createRequire(realpathSync(process.env.DSH_BIN));
const load=name=>import(pathToFileURL(require.resolve(name)).href);
const {Context}=await load('@deepseek-ai/cordis');
const persistence=await load('@deepseek-ai/dsh-session-persistence-jsonl');
const {SESSION_FORMAT_VERSION}=await load('@deepseek-ai/dsh-session');
const [root,cwd]=process.argv.slice(2);
const ctx=new Context();
try {
  await ctx.plugin(persistence,{root});
  for(const [suffix,text] of [['a','Inspect Bach task alpha.'],['b','Inspect Bach task beta.']]) {
    const id='phil-native-session-'+suffix,now=Date.now()-1000;
    const handle=await ctx.sessionPersistence.create({version:SESSION_FORMAT_VERSION,id,createdAt:now,cwd,isSeeded:false,delegationDepth:0});
    try {
      await handle.append([
        {type:'turn/start',time:now,data:{turn:1}},
        {type:'user/message',time:now+1,surfaceOp:'append',data:{role:'user',id:'native-message-'+suffix,source:{kind:'user',rpcId:'native-request-'+suffix},content:[{type:'text',text}]}},
        {type:'session/title',time:now+2,data:{title:'Philharmonie session '+suffix.toUpperCase(),messageSeqs:[],source:{kind:'user'}}},
        {type:'turn/end',time:now+3,data:{turn:1,reason:{kind:'completed'}}},
      ]);
    } finally {await handle.close();}
  }
} finally {await ctx.fiber.dispose();}
