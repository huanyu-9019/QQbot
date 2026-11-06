import test from 'node:test';
import assert from 'node:assert/strict';
import {withLastFallback,validCompletion,deepSeekReply} from './qq-model-fallback.mjs';
test('failed primary uses the final provider',async()=>{
 assert.equal(await withLastFallback(async()=>{throw Error('down')},async()=> 'backup'), 'backup');
});
test('empty or error completions are unhealthy',()=>{
 assert.equal(validCompletion({choices:[{finish_reason:'error',message:{content:'x'}}]}),false);
 assert.equal(validCompletion({choices:[{finish_reason:'stop',message:{content:''}}]}),false);
 assert.equal(validCompletion({choices:[{finish_reason:'stop',message:{content:'OK'}}]}),true);
});
test('text fallback uses the ordered router instead of bypassing to official DeepSeek',async()=>{
 const answer=await deepSeekReply([{role:'user',content:'hello'}],{
  routerConfig:{localKey:'local-secret'},envText:'DEEPSEEK_API_KEY=unavailable',
  fetchImpl:async(url)=>{
   assert.equal(url,'http://127.0.0.1:8650/v1/chat/completions');
   return new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:'hello back'}}]}),{status:200});
  },
 });
 assert.equal(answer,'hello back');
});
test('image fallback preserves image content and uses the vision router',async()=>{
 const image='data:image/jpeg;base64,AA==';let sent;
 const messages=[{role:'user',content:[{type:'text',text:'What is in this image?'},{type:'image_url',image_url:{url:image}}]}];
 const answer=await deepSeekReply(messages,{routerConfig:{base:'http://127.0.0.1:8650/v1',localKey:'local-secret'},fetchImpl:async(url,options)=>{
  sent={url,body:JSON.parse(options.body),authorization:options.headers.Authorization};
  return new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:'A blue shape.'}}]}),{status:200});
 }});
 assert.equal(answer,'A blue shape.');
 assert.equal(sent.url,'http://127.0.0.1:8650/v1/chat/completions');
 assert.equal(sent.body.messages[0].content[1].image_url.url,image);
 assert.equal(sent.authorization,'Bearer local-secret');
});
test('image fallback refuses to send pictures through the text-only official route',async()=>{
 const messages=[{role:'user',content:[{type:'text',text:'Look'},{type:'image_url',image_url:{url:'data:image/jpeg;base64,AA=='}}]}];
 await assert.rejects(()=>deepSeekReply(messages,{routerConfig:{base:'http://127.0.0.1:8650/v1',localKey:'local-secret'},fetchImpl:async()=>new Response('{}',{status:503})}));
});
test('image fallback treats a model claiming it cannot see the image as unhealthy',async()=>{
 const messages=[{role:'user',content:[{type:'text',text:'What is this?'},{type:'image_url',image_url:{url:'data:image/jpeg;base64,AA=='}}]}];
 await assert.rejects(()=>deepSeekReply(messages,{routerConfig:{localKey:'local-secret'},fetchImpl:async()=>new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:'I cannot see the image.'}}]}),{status:200})}),/image access failure/);
});
