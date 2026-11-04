import {readFileSync} from 'node:fs';
import {lookup as dnsLookup} from 'node:dns/promises';
import {isIP} from 'node:net';
import https from 'node:https';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

export class MediaError extends Error {
  constructor(code) { super(code); this.code=code; }
}

export function loadMediaConfig(path=new URL('./qq-media-config.json',import.meta.url)) {
  const c=JSON.parse(readFileSync(path,'utf8'));
  for(const key of ['imagesEnabled','stickersEnabled']) if(typeof c[key]!=='boolean') throw new MediaError('BAD_CONFIG');
  const bounds={maxImages:[1,4],maxSourceBytes:[1024,16777216],maxPixels:[1,20000000],maxEdge:[128,2048],maxOutputBytes:[1024,2097152],downloadTimeoutMs:[1000,30000],normalizeTimeoutMs:[1000,20000],automaticStickerCooldownMs:[1000,3600000],requestedStickerCooldownMs:[1000,3600000]};
  for(const [k,[low,high]] of Object.entries(bounds)) if(!Number.isInteger(c[k])||c[k]<low||c[k]>high) throw new MediaError('BAD_CONFIG');
  if(typeof c.pythonExecutable!=='string'||!c.pythonExecutable.startsWith('/')||typeof c.stickerDirectory!=='string'||!c.stickerDirectory.startsWith('/')) throw new MediaError('BAD_CONFIG');
  return Object.freeze(c);
}

export function parseIncoming(segments,{kind,mentioned},config) {
  const text=segments.filter(x=>x.type==='text').map(x=>String(x.data?.text??'')).join('').trim();
  const pictures=segments.filter(x=>x.type==='image'||x.type==='mface');
  if(!pictures.length) return {text,imageUrls:[]};
  if(!config.imagesEnabled) return {text,imageUrls:[],error:'IMAGES_DISABLED'};
  if(pictures.length>config.maxImages) return {text,imageUrls:[],error:'TOO_MANY_IMAGES'};
  const imageUrls=pictures.map(x=>typeof x.data?.url==='string'?x.data.url:'');
  if(imageUrls.some(x=>!x)) return {text,imageUrls:[],error:'IMAGE_URL_UNAVAILABLE'};
  const defaultText = text || (pictures.every(x => x.type === 'mface' || Number(x.data?.sub_type) === 1)
    ? '对方发来一个表情，仅作聊天语气参考。'
    : '对方发来了一张图片，仅作聊天语气参考。');
  const collectibleIndexes=pictures.flatMap((x,index)=>x.type==='mface'||Number(x.data?.sub_type)===1?[index]:[]);
  const mediaKind = pictures.every(x => x.type === 'mface' || Number(x.data?.sub_type) === 1) ? 'sticker' : 'image';
  return {text:defaultText,imageUrls,mediaKind,collectibleIndexes,imageIndexes:pictures.map((_x,index)=>index)};
}

const hosts=new Set(['multimedia.nt.qq.com.cn','gchat.qpic.cn','c2cpicdw.qpic.cn','p.qpic.cn','gxh.vip.qq.com','q.qlogo.cn']);
export function validateImageUrl(value) {
  let url;
  try { url=new URL(value); } catch { throw new MediaError('UNTRUSTED_IMAGE_URL'); }
  if(!hosts.has(url.hostname)||!['https:','http:'].includes(url.protocol)||url.username||url.password||url.hash||url.port) throw new MediaError('UNTRUSTED_IMAGE_URL');
  // QQ still emits signed HTTP links for the same HTTPS-capable image CDN.
  url.protocol='https:';
  return url;
}

export function isPublicAddress(address) {
  if(isIP(address)===6) return /^[23][0-9a-f]{3}:/i.test(address);
  if(isIP(address)!==4) return false;
  const [a,b,c]=address.split('.').map(Number);
  if(a===0||a===10||a===127||a>=224||a===169&&b===254||a===172&&b>=16&&b<=31||a===192&&b===168||a===100&&b>=64&&b<=127||a===198&&(b===18||b===19)) return false;
  if(a===192&&b===0||a===198&&b===51&&c===100||a===203&&b===0&&c===113) return false;
  return true;
}

function openHttps(url,addresses,timeoutMs) {
  return new Promise((resolve,reject)=>{
    const chosen=addresses.find(x=>x.family===4)||addresses[0];
    const request=https.request(url,{
      method:'GET',headers:{'User-Agent':'QQ-Hermes-Images/1.0','Accept':'image/*'},
      lookup:(_host,options,callback)=>options?.all?callback(null,[chosen]):callback(null,chosen.address,chosen.family),
    });
    const timer=setTimeout(()=>request.destroy(new MediaError('IMAGE_DOWNLOAD_TIMEOUT')),timeoutMs);
    request.on('error',()=>{clearTimeout(timer);reject(new MediaError('IMAGE_DOWNLOAD_FAILED'));});
    request.on('response',response=>{
      response.once('close',()=>clearTimeout(timer));
      resolve({status:response.statusCode,headers:response.headers,body:response});
    });
    request.end();
  });
}

export async function downloadQQImage(value,config,{lookup=dnsLookup,open=openHttps}={}) {
  let url=validateImageUrl(value);
  for(let hop=0;hop<4;hop++) {
    let addresses;
    try { addresses=await lookup(url.hostname,{all:true}); } catch { throw new MediaError('IMAGE_DOWNLOAD_FAILED'); }
    if(!addresses.length||addresses.some(x=>!isPublicAddress(x.address))) throw new MediaError('UNTRUSTED_IMAGE_URL');
    let response;
    try { response=await open(url,addresses,config.downloadTimeoutMs); } catch(error) { throw error instanceof MediaError?error:new MediaError('IMAGE_DOWNLOAD_FAILED'); }
    if([301,302,303,307,308].includes(response.status)) {
      response.body.destroy?.();
      if(!response.headers.location) throw new MediaError('IMAGE_DOWNLOAD_FAILED');
      url=validateImageUrl(new URL(response.headers.location,url).href);
      continue;
    }
    if(response.status!==200) {response.body.destroy?.();throw new MediaError('IMAGE_DOWNLOAD_FAILED');}
    const declared=Number(response.headers['content-length']||0);
    if(!Number.isFinite(declared)||declared>config.maxSourceBytes) {response.body.destroy?.();throw new MediaError('IMAGE_TOO_LARGE');}
    const parts=[];let size=0;
    try {
      for await(const part of response.body) {
        size+=part.length;
        if(size>config.maxSourceBytes) throw new MediaError('IMAGE_TOO_LARGE');
        parts.push(part);
      }
    } catch(error) {response.body.destroy?.();throw error instanceof MediaError?error:new MediaError('IMAGE_DOWNLOAD_FAILED');}
    if(!size) throw new MediaError('INVALID_IMAGE');
    return Buffer.concat(parts,size);
  }
  throw new MediaError('IMAGE_DOWNLOAD_FAILED');
}

export function normalizeImage(bytes,config) {
  return new Promise((resolve,reject)=>{
    const args=[fileURLToPath(new URL('./qq-image-normalize.py',import.meta.url)),String(config.maxSourceBytes),String(config.maxPixels),String(config.maxEdge),String(config.maxOutputBytes)];
    if(config.preserveAnimation)args.push('--keep-gif',String(config.maxGifFrames));
    const child=spawn(config.pythonExecutable,args,{stdio:['pipe','pipe','pipe']});
    const parts=[];let count=0,code='INVALID_IMAGE',settled=false;
    const finish=(error,value)=>{if(settled)return;settled=true;clearTimeout(timer);error?reject(error):resolve(value);};
    const timer=setTimeout(()=>{child.kill('SIGKILL');finish(new MediaError('IMAGE_PROCESS_TIMEOUT'));},config.normalizeTimeoutMs);
    child.stdout.on('data',part=>{count+=part.length;if(count>config.maxOutputBytes){child.kill('SIGKILL');finish(new MediaError('IMAGE_TOO_LARGE'));}else parts.push(part);});
    child.stderr.on('data',data=>{const name=data.toString('utf8').trim();if(['INVALID_IMAGE','IMAGE_TOO_LARGE','IMAGE_DIMENSIONS_TOO_LARGE'].includes(name))code=name;});
    child.on('error',()=>finish(new MediaError('IMAGE_PROCESS_UNAVAILABLE')));
    child.on('close',status=>status===0&&count?finish(null,Buffer.concat(parts,count)):finish(new MediaError(code)));
    child.stdin.on('error',()=>{});
    child.stdin.end(bytes);
  });
}

export async function prepareImages(urls,config,{download=downloadQQImage,normalize=normalizeImage}={}) {
  if(!config.imagesEnabled) throw new MediaError('IMAGES_DISABLED');
  if(urls.length>config.maxImages) throw new MediaError('TOO_MANY_IMAGES');
  const images=[];let total=0;
  for(const url of urls) {
    const raw=await download(url,{...config,maxSourceBytes:config.maxSourceBytes-total});
    total+=raw.length;
    if(total>config.maxSourceBytes) throw new MediaError('IMAGE_TOO_LARGE');
    const jpeg=await normalize(raw,config);
    images.push('data:image/jpeg;base64,'+jpeg.toString('base64'));
  }
  return images;
}

export function userContent(task) {
  if(!task.images?.length) return task.text;
  return [{type:'text',text:task.text},...task.images.map(url=>({type:'image_url',image_url:{url}}))];
}

export function mediaErrorMessage(code) {
  const messages={IMAGES_DISABLED:'图片识别目前已关闭，请发文字给我。',TOO_MANY_IMAGES:'一次最多看两张图片，请分开发。',IMAGE_TOO_LARGE:'图片太大了，请压缩后重发（每次图片合计不超过 8 MB）。',IMAGE_DIMENSIONS_TOO_LARGE:'图片分辨率太高，请缩小后重发。',IMAGE_URL_UNAVAILABLE:'这张图的下载地址没取到，请重新发一次原图。',UNTRUSTED_IMAGE_URL:'这张图片的来源无法读取，请直接上传 QQ 图片。'};
  return messages[code]||'这张图暂时没读到，请稍后重新发一下。';
}
