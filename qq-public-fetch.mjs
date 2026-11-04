import {lookup as dnsLookup} from 'node:dns/promises';
import {isIP} from 'node:net';
import https from 'node:https';
import {isPublicAddress} from './qq-media.mjs';

export class PublicFetchError extends Error {
 constructor(code){super(code);this.code=code;}
}
export function validatePublicUrl(value){
 let url;try{url=new URL(value);}catch{throw new PublicFetchError('UNSAFE_URL');}
 if(!['https:','http:'].includes(url.protocol)||url.username||url.password||url.port||url.hash||isIP(url.hostname.replace(/^\[|\]$/g,'')))throw new PublicFetchError('UNSAFE_URL');
 url.protocol='https:';
 return url;
}
function abortable(promise,signal){
 return new Promise((resolve,reject)=>{
  const aborted=()=>reject(new PublicFetchError('NETWORK_TIMEOUT'));
  if(signal.aborted)return aborted();
  signal.addEventListener('abort',aborted,{once:true});
  Promise.resolve(promise).then(resolve,reject).finally(()=>signal.removeEventListener('abort',aborted));
 });
}
function openHttps(url,addresses,signal){
 return new Promise((resolve,reject)=>{
  const chosen=addresses.find(x=>x.family===4)||addresses[0];
  const request=https.request(url,{method:'GET',agent:false,signal,
   headers:{'User-Agent':'Mozilla/5.0','Accept':'image/*,application/json,text/plain;q=0.8'},
   lookup:(_hostname,options,callback)=>options?.all?callback(null,[chosen]):callback(null,chosen.address,chosen.family),
  });
  request.once('error',()=>reject(new PublicFetchError(signal.aborted?'NETWORK_TIMEOUT':'DOWNLOAD_FAILED')));
  request.once('response',response=>resolve({status:response.statusCode,headers:response.headers,body:response}));
  request.end();
 });
}
export async function fetchPublicBuffer(value,{maxBytes,timeoutMs},{lookup=dnsLookup,open=openHttps}={}){
 const controller=new AbortController();
 const timer=setTimeout(()=>controller.abort(),timeoutMs);
 let activeBody;
 try{
  return await abortable((async()=>{
   let url=validatePublicUrl(value);
   for(let hop=0;hop<4;hop++){
    const addresses=await abortable(lookup(url.hostname,{all:true}),controller.signal);
    if(!addresses.length||addresses.some(x=>!isPublicAddress(x.address)))throw new PublicFetchError('UNSAFE_URL');
    const response=await abortable(open(url,addresses,controller.signal),controller.signal);
    activeBody=response.body;
    if([301,302,303,307,308].includes(response.status)){
     response.body.destroy?.();
     if(!response.headers.location)throw new PublicFetchError('DOWNLOAD_FAILED');
     url=validatePublicUrl(new URL(response.headers.location,url).href);continue;
    }
    if(response.status!==200)throw new PublicFetchError('DOWNLOAD_FAILED');
    const declared=Number(response.headers['content-length']||0);
    if(!Number.isFinite(declared)||declared<0||declared>maxBytes)throw new PublicFetchError('TOO_LARGE');
    const parts=[];let size=0;
    for await(const part of response.body){
     size+=part.length;if(size>maxBytes)throw new PublicFetchError('TOO_LARGE');parts.push(part);
    }
    if(!size)throw new PublicFetchError('EMPTY_DOWNLOAD');
    return {bytes:Buffer.concat(parts,size),contentType:String(response.headers['content-type']||'').split(';')[0].toLowerCase()};
   }
   throw new PublicFetchError('TOO_MANY_REDIRECTS');
  })(),controller.signal);
 }catch(error){throw error instanceof PublicFetchError?error:new PublicFetchError('DOWNLOAD_FAILED');}
 finally{clearTimeout(timer);controller.abort();activeBody?.destroy?.();}
}
