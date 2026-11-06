import {readFileSync} from 'node:fs';
export function validCompletion(result) {
 const c=result?.choices?.[0];
 return !['error','cancelled','length'].includes(c?.finish_reason) && typeof c?.message?.content==='string' && Boolean(c.message.content.trim());
}
export async function withLastFallback(primary,backup) {
 try {return await primary();} catch {return await backup();}
}
function containsImage(messages) {
 return messages.some(message=>Array.isArray(message.content)&&message.content.some(part=>part?.type==='image_url'||part?.type==='input_image'));
}
export async function routedVisionReply(messages,{signal,routerConfig,fetchImpl=fetch}={}) {
 const config=routerConfig??JSON.parse(readFileSync('/home/hermes/.hermes/chat-routing.json','utf8'));
 if(typeof config.localKey!=='string'||!config.localKey)throw Error('vision router unavailable');
 const base=typeof config.base==='string'?config.base:'http://127.0.0.1:8650/v1';
 const response=await fetchImpl((base.endsWith('/')?base.slice(0,-1):base)+'/chat/completions',{
  method:'POST',headers:{Authorization:'Bearer '+config.localKey,'Content-Type':'application/json'},
  body:JSON.stringify({model:'qq-chat',messages,stream:false}),
  signal:signal?AbortSignal.any([signal,AbortSignal.timeout(30000)]):AbortSignal.timeout(30000),
 });
 if(!response.ok)throw Error('vision router HTTP '+response.status);
 const result=await response.json();if(!validCompletion(result))throw Error('vision router incomplete reply');
 const answer=result.choices[0].message.content.trim();
 const lowerAnswer=answer.toLowerCase();
 if(containsImage(messages)&&['看不到','看不见','无法查看','不能查看',"can't see","can't view",'cannot see','cannot view',"don't have access to the image"].some(term=>lowerAnswer.includes(term)))throw Error('vision route returned an image access failure');
 return answer;
}
export async function deepSeekReply(messages,{signal,routerConfig,fetchImpl=fetch}={}) {
 // Text and images share the configured provider order and cached health state.
 return routedVisionReply(messages,{signal,routerConfig,fetchImpl});
}
