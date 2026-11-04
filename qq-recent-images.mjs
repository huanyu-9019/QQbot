import {loadInteractionConfig} from './qq-interaction-config.mjs';
import {prepareImages,validateImageUrl} from './qq-media.mjs';
export class RecentImages {
 constructor(media,{config=loadInteractionConfig().recentImages,clock=Date.now,prepare=prepareImages}={}){
  this.media=media;this.config=config;this.clock=clock;this.prepare=prepare;this.entries=new Map();
 }
 get enabled(){return this.config.enabled&&this.media.imagesEnabled;}
 usable(ref,task){return this.enabled&&ref?.scope===task.sessionKey&&this.clock()-ref.at>=0&&this.clock()-ref.at<this.config.ttlMs;}
 prune(){
  for(const [key,ref] of this.entries)if(this.clock()-ref.at>=this.config.ttlMs){ref.image=null;this.entries.delete(key);}
 }
 observe(task){
  if(!this.enabled||!task.sessionKey)return;
  this.prune();
  if(task.mediaError){const ref=this.entries.get(task.sessionKey);if(ref)ref.image=null;this.entries.delete(task.sessionKey);return;}
  if(task.imageUrls?.length){
   let url;try{url=validateImageUrl(task.imageUrls.at(-1)).href;}catch{const ref=this.entries.get(task.sessionKey);if(ref)ref.image=null;this.entries.delete(task.sessionKey);return;}
   const previous=this.entries.get(task.sessionKey);if(previous)previous.image=null;
   const ref={scope:task.sessionKey,url,at:this.clock(),image:null,fastFollowupUsed:false};
   this.entries.delete(task.sessionKey);this.entries.set(task.sessionKey,ref);task.incomingImageRef=ref;
   while(this.entries.size>this.config.maxScopes){const key=this.entries.keys().next().value;this.entries.get(key).image=null;this.entries.delete(key);}
  }else{
   const ref=this.entries.get(task.sessionKey);if(this.usable(ref,task))task.recentImageRef=ref;
  }
 }
 cache(ref,image){
  this.prune();
  if(!this.enabled||!ref||this.entries.get(ref.scope)!==ref||typeof image!=='string'||!image.startsWith('data:image/jpeg;base64,'))return;
  ref.image=Buffer.byteLength(image)<=this.config.maxCachedBytes?image:null;
  let bytes=0;for(const item of [...this.entries.values()].reverse())if(item.image){bytes+=Buffer.byteLength(item.image);if(bytes>this.config.maxCachedBytes)item.image=null;}
 }
 async resolve(task){
  const ref=task.recentImageRef;if(!this.usable(ref,task))return [];
  if(ref.image)return [ref.image];
  const images=await this.prepare([ref.url],this.media);
  if(!this.usable(ref,task))return [];
  this.cache(ref,images.at(-1));return images.slice(-1);
 }
 instructions(task){
  if(task.images?.length||task.imageUrls?.length||!this.usable(task.recentImageRef,task))return '';
  return '当前文字消息没有附图，但同一聊天前面有一张近期图片可查看。若用户指代上图、刚才的图片、图中内容，或当前问题需要看那张图才能准确回答，请仅输出 [[LOOK_RECENT_IMAGE]]，系统会取该消息到达前最近的那张图片给你查看。不要凭文字猜测画面；与图片无关的闲聊直接正常回答，不输出这个标记。不从其他聊天找图，不联网搜图。';
 }
 allowFastFollowup(task){
  const ref=task.recentImageRef;
  if(task.kind!=='private'||task.imageUrls?.length||!this.usable(ref,task)||ref.fastFollowupUsed)return false;
  ref.fastFollowupUsed=true;return true;
 }
}
