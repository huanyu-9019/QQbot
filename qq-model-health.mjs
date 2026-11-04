import {readFileSync} from 'node:fs';
import {deepSeekReply,validCompletion} from './qq-model-fallback.mjs';
const env=readFileSync('/home/hermes/.hermes/.env','utf8');
const key=env.split(/\r?\n/).filter(x=>x.startsWith('API_SERVER_KEY=')).at(-1)?.slice(15).trim();
const messages=[{role:'user',content:'这是隔离的服务健康测试，不执行工具，不发送QQ消息，只回复：OK'}];
const status={primary:false,deepseek:false,reply:false,napcat:false};
try {
 status.napcat=await new Promise(resolve=>{
  const ws=new WebSocket('ws://127.0.0.1:3001');const echo='health-'+Date.now();
  const timer=setTimeout(()=>{ws.close();resolve(false)},5000);
  ws.addEventListener('open',()=>ws.send(JSON.stringify({action:'get_login_info',params:{},echo})));
  ws.addEventListener('message',event=>{try{const j=JSON.parse(event.data);if(j.echo===echo){clearTimeout(timer);ws.close();resolve(j.status==='ok'&&j.retcode===0)}}catch{}});
  ws.addEventListener('error',()=>{clearTimeout(timer);resolve(false)});
 });
}catch{}
try {
 const r=await fetch('http://127.0.0.1:8642/v1/chat/completions',{method:'POST',headers:{Authorization:'Bearer '+key,'Content-Type':'application/json','X-Hermes-Session-Key':'qq:health:'+Date.now()},body:JSON.stringify({model:'hermes-agent',messages}),signal:AbortSignal.timeout(35000)});
 status.primary=r.ok&&validCompletion(await r.json());
}catch{}
try {status.deepseek=Boolean(await deepSeekReply(messages));}catch{}
status.reply=(status.primary||status.deepseek)&&status.napcat;
console.log(JSON.stringify(status));
