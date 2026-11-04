import {readFileSync} from 'node:fs';
export function validCompletion(result) {
 const c=result?.choices?.[0];
 return !['error','cancelled','length'].includes(c?.finish_reason) && typeof c?.message?.content==='string' && Boolean(c.message.content.trim());
}
export async function withLastFallback(primary,backup) {
 try {return await primary();} catch {return await backup();}
}
export async function deepSeekReply(messages,{signal}={}) {
 const env=readFileSync('/home/hermes/.hermes/.env','utf8');
 const key=env.split(/\r?\n/).filter(x=>x.startsWith('DEEPSEEK_API_KEY=')).at(-1)?.slice('DEEPSEEK_API_KEY='.length).trim();
 if(!key)throw Error('DeepSeek key missing');
 const safeMessages=messages.map(m=>({...m,content:Array.isArray(m.content)?m.content.filter(x=>x.type==='text').map(x=>x.text).join('\n'):m.content}));
 const r=await fetch('https://api.deepseek.com/chat/completions',{
 method:'POST',headers:{Authorization:'Bearer '+key,'Content-Type':'application/json'},
 body:JSON.stringify({model:'deepseek-flash',messages:safeMessages,stream:false,max_tokens:512,thinking:{type:'disabled'}}),
 signal:signal?AbortSignal.any([signal,AbortSignal.timeout(30000)]):AbortSignal.timeout(30000)});
 if(!r.ok)throw Error('DeepSeek HTTP '+r.status);
 const j=await r.json();if(!validCompletion(j))throw Error('DeepSeek incomplete reply');
 return j.choices[0].message.content.trim();
}
