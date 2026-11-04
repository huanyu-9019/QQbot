import {readFileSync,readdirSync,lstatSync,writeFileSync,renameSync,unlinkSync,existsSync} from 'node:fs';
import {join,isAbsolute} from 'node:path';
import {createHash,randomUUID} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {fetchPublicBuffer,validatePublicUrl} from './qq-public-fetch.mjs';
import {normalizeImage} from './qq-media.mjs';

const digest=value=>createHash('sha256').update(value).digest('hex').slice(0,32);
const filenamePattern=/^([a-f0-9]{32})-([a-f0-9]{32})\.(jpg|gif)$/;
export function loadOnlineConfig(path=new URL('./qq-online-stickers.json',import.meta.url)){
 const c=JSON.parse(readFileSync(path,'utf8'));
 if(typeof c.enabled!=='boolean'||typeof c.networkEnabled!=='boolean'||typeof c.directory!=='string'||!isAbsolute(c.directory))throw new Error('BAD_ONLINE_STICKER_CONFIG');
 const bounds={queryTtlMs:[1000,86400000],imageTtlMs:[1000,604800000],maxCacheFiles:[1,200],maxCacheBytes:[2097152,209715200],maxSourceBytes:[1024,4194304],maxOutputBytes:[1024,4194304],maxPixels:[1,8000000],maxEdge:[128,1280],maxGifFrames:[1,120],maxCandidates:[1,12],searchMaxBytes:[1024,2097152],fetchTimeoutMs:[100,15000],totalTimeoutMs:[1000,30000]};
 for(const [key,[low,high]] of Object.entries(bounds))if(!Number.isInteger(c[key])||c[key]<low||c[key]>high)throw new Error('BAD_ONLINE_STICKER_CONFIG');
 if(c.maxCacheBytes<c.maxOutputBytes||c.imageTtlMs<c.queryTtlMs)throw new Error('BAD_ONLINE_STICKER_CONFIG');
 return Object.freeze(c);
}
export function memeKeyword(value){
 if(typeof value!=='string'||/[\r\n]/.test(value))return null;
 const q=value.trim().replace(/ +/g,' ');
 if(!q||Array.from(q).length>28||!/[\p{L}]/u.test(q)||!/^[\p{L}\p{N} _，,!?！？-]+$/u.test(q)||/\d{5,}|sk[-_]|AKIA|[a-f0-9]{20,}|[A-Za-z0-9]{24,}/i.test(q))return null;
 return q;
}
export function memeSelector(value){
 if(typeof value!=='string')return null;
 const selector=value.trim();
 if(/^@any$/i.test(selector))return '@any';
 if(/^@?[a-f0-9]{32}$/i.test(selector))return '@'+selector.replace(/^@/,'').toLowerCase();
 return memeKeyword(value);
}
export function parseSearchResults(bytes){
 const body=JSON.parse(bytes.toString('utf8'));
 if(!Array.isArray(body.list))throw new Error('SEARCH_UNAVAILABLE');
 const results=[];const seen=new Set();
 for(const item of body.list){
  const urls=[];
  for(const value of [item?.img,item?.thumb]){
   if(typeof value!=='string')continue;
   try{const safe=validatePublicUrl(value).href;if(!urls.includes(safe))urls.push(safe);}catch{}
  }
  if(!urls.length||seen.has(urls[0]))continue;
  seen.add(urls[0]);results.push({urls,key:digest(urls[0])});
 }
 return results;
}
export class StickerLibrary{
 constructor(mediaConfig,{onlineConfig=loadOnlineConfig(),fetcher=fetchPublicBuffer,normalize=normalizeImage,clock=Date.now,collection=null}={}){
  this.media=mediaConfig;this.config=onlineConfig;this.fetcher=fetcher;this.normalize=normalize;this.clock=clock;
  this.lastAttempt=new Map();this.recent=new Map();this.queries=new Map();this.status={reason:'none'};
  this.collection=collection;
 }
 get enabled(){return this.media.stickersEnabled&&this.config.enabled;}
 get networkEnabled(){return this.config.networkEnabled===true;}
 validateAssets(){
  if(!this.enabled||!this.networkEnabled)return;
  const item=lstatSync(this.config.directory);if(!item.isDirectory()||item.isSymbolicLink())throw new Error('BAD_STICKER_DIRECTORY');
  this.cleanup();
 }
 instructions(){
  if(!this.enabled)return '';
  return [
   this.networkEnabled?'你可以在私聊或群聊的轻松聊天里偶尔发一张网上的表情包，每次最多一张；认真技术、健康、安全求助不要主动附图。用户明确索要时尽量发。':'在私聊或群聊的轻松聊天里，接梗、调侃、表达情绪或回应别人表情时，优先配一张合适的收藏表情，每条最多一张；认真技术、健康、安全求助不要主动附图。用户明确索要时从收藏里挑选。',
   this.networkEnabled?'用末尾独立一行 [[MEME:短关键词:auto]] 表示配图，用户明确索要时用 [[MEME:短关键词:requested]]。关键词最多28字，不带会话原文、昵称、QQ号或私人信息。':'发送收藏表情时，末尾独立一行输出 [[MEME:图片编号:auto]]；用户明确索要表情时必须使用 requested 模式，即 [[MEME:图片编号:requested]]，不要只在文字里答应。图片编号必须从下方清单原样选择，格式为 @加摘要；不要把用户措辞或自行改写的标签当成编号。',
   this.networkEnabled?'系统会按关键词实时搜网络表情并发出真实图片；你不需要用 web_search 找表情，不指定图片网址或文件路径，不使用旧的 STICKER 标记，不向用户解释标记，也不说只能发自制蓝鲸图。可以只给文字，不必每句配图。':'表情只使用从聊天中收藏的图片，私聊与群聊全局共用。对方泛泛说发个表情、随便来一张，没有指定类型时，使用 [[MEME:@any:requested]] 从已有收藏挑一张；若指定了情绪或角色，从清单标签中选合适的编号，确实没有匹配才说明暂未收藏。不要擅自把泛泛索要理解为要求新收藏或等待别人发图。禁止为找表情使用 web_search、在线图片或图片链接，不先声称已经发送成功。用户表示不需要或禁止发图时不输出发图标记。',
   '回复形式可以自然变化，平时有文字，也偶尔只回一张表情。私聊和群聊里，对方没有待回答的问题，只是简短的反应、起哄、玩笑或斗嘴，而一张收藏表情本身已经能完整接住时，优先只回这张图，不额外凑一句文字、动作描述或笑话。此时整条回复仅输出一条 MEME 标记，不附文字、解释或 <QQ_SILENT>；没有明确索要用 auto，明确索要用 requested。用户明确说只要表情时，能选到合适的收藏就只发图。不要连续用表情代替所有聊天；具体问题、认真求助和需要说明的内容仍用文字回答，没有适合的收藏就自然用文字。群聊先判断是否应接话，不因可以只回图就额外插话；决定静默时仍按群聊规则静默。',
   this.collection?.catalog()||'',
  ].join('\n');
 }
 parse(answer){
  const value=String(answer).trim();
  const marker=value.match(/(?:^|\n)\[\[MEME:([^\]\r\n]{1,80}):(auto|requested)\]\]\s*$/);
  const id=marker?memeSelector(marker[1]):null;
  return {text:value.replace(/\[\[(?:MEME|STICKER):[^\]\r\n]*(?:\]\])?/g,'').trim(),id,mode:id?marker[2]:null};
 }
 files(){
  return readdirSync(this.config.directory).flatMap(name=>{
   const match=name.match(filenamePattern);if(!match)return [];
   const path=join(this.config.directory,name);const stat=lstatSync(path);
   return stat.isFile()&&!stat.isSymbolicLink()?[{path,query:match[1],hash:match[2],mtime:stat.mtimeMs,size:stat.size}]:[];
  });
 }
 cleanup(keepPath){
  const now=this.clock();const files=this.files().sort((a,b)=>Number(b.path===keepPath)-Number(a.path===keepPath)||b.mtime-a.mtime);
  let bytes=0,count=0;
  for(const file of files){
   if(now-file.mtime>this.config.imageTtlMs||count>=this.config.maxCacheFiles||bytes+file.size>this.config.maxCacheBytes)unlinkSync(file.path);
   else{count++;bytes+=file.size;}
  }
 }
 remember(scope,file,sourceKey){
  this.lastAttempt.set(scope,this.clock());if(this.lastAttempt.size>1000)this.lastAttempt.delete(this.lastAttempt.keys().next().value);
  const previous=this.recent.get(scope)||[];this.recent.set(scope,[...previous,{hash:file.hash,key:sourceKey}].slice(-3));
  if(this.recent.size>1000)this.recent.delete(this.recent.keys().next().value);
  this.status={reason:'success',source:file.source||'online'};
  return pathToFileURL(file.path).href;
 }
 fallbackText(reply){
  if(reply.mode!=='requested')return '';
  if(this.status.reason==='cooldown')return '刚发过表情，稍等一会儿再试。';
  if(this.status.reason==='disabled')return '表情包功能目前已关闭。';
  if(!this.networkEnabled||this.status.reason==='not_collected')return '收藏里暂时没有符合要求的表情，可以换个类型，或让我从已有的里面挑一张。';
  return '这次没找到能读取的网络表情，换个关键词试试。';
 }
 async select(task,reply){
  this.status={reason:'none'};
  if(!this.enabled){this.status={reason:'disabled'};return null;}
  const keyword=memeSelector(reply.id);if(!keyword)return null;
  const scope=task.kind==='group'?'group:'+task.groupId:'private:'+task.userId;
  const now=this.clock();const interval=reply.mode==='requested'?this.media.requestedStickerCooldownMs:this.media.automaticStickerCooldownMs;
  if(this.lastAttempt.has(scope)&&now-this.lastAttempt.get(scope)<interval){this.status={reason:'cooldown'};return null;}
  const recent=this.recent.get(scope)||[];
  const learned=this.collection?.find(keyword,recent.map(x=>x.hash),{allowRepeat:reply.mode==='requested'});
  if(learned)return this.remember(scope,learned,null);
  if(!this.networkEnabled||keyword.startsWith('@')){this.status={reason:'not_collected'};return null;}
  const query=keyword.endsWith('表情包')?keyword:keyword+' 表情包';const queryHash=digest(query);
  const previous=this.files().filter(x=>x.query===queryHash&&!recent.some(r=>r.hash===x.hash));
  const fast=previous.find(x=>now-x.mtime<this.config.queryTtlMs);
  if(fast)return this.remember(scope,fast,null);
  const end=Date.now()+this.config.totalTimeoutMs;
  const fetcher=(url,maxBytes)=>this.fetcher(url,{maxBytes,timeoutMs:Math.min(this.config.fetchTimeoutMs,Math.max(1,end-Date.now()))});
  try{
   let found=this.queries.get(queryHash);
   if(!found||now-found.at>this.config.queryTtlMs){
    const response=await fetcher('https://image.so.com/j?'+new URLSearchParams({q:query,sn:'0',pn:'10'}),this.config.searchMaxBytes);
    found={at:now,items:parseSearchResults(response.bytes)};this.queries.set(queryHash,found);
    if(this.queries.size>100)this.queries.delete(this.queries.keys().next().value);
   }
   for(const item of found.items.slice(0,this.config.maxCandidates)){
    if(recent.some(r=>r.key===item.key))continue;
    for(const url of item.urls){
     if(Date.now()>=end)break;
     try{
      const response=await fetcher(url,this.config.maxSourceBytes);
      if(!response.contentType.startsWith('image/'))continue;
      const c={...this.media,...this.config,pythonExecutable:this.media.pythonExecutable,preserveAnimation:true,normalizeTimeoutMs:Math.max(1,Math.min(this.config.fetchTimeoutMs,end-Date.now()))};
      const bytes=await this.normalize(response.bytes,c);
      if(bytes.length>this.config.maxOutputBytes)continue;
      const hash=digest(bytes);if(recent.some(r=>r.hash===hash))continue;
      const extension=bytes.subarray(0,3).toString()==='GIF'?'gif':bytes[0]===255&&bytes[1]===216?'jpg':null;
      if(!extension)continue;
      const path=join(this.config.directory,queryHash+'-'+hash+'.'+extension);
      if(existsSync(path)){if(lstatSync(path).isSymbolicLink())continue;}
      else{
       const temp=join(this.config.directory,'.'+randomUUID()+'.tmp');
       try{writeFileSync(temp,bytes,{flag:'wx',mode:0o640});renameSync(temp,path);}finally{if(existsSync(temp))unlinkSync(temp);}
      }
      this.cleanup(path);return this.remember(scope,{path,hash},item.key);
     }catch{}
    }
   }
  }catch{}
  const fallback=previous.find(x=>now-x.mtime<this.config.imageTtlMs);
  if(fallback)return this.remember(scope,fallback,null);
  this.status={reason:'unavailable'};return null;
 }
}
