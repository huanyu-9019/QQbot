import {readFileSync,statSync} from 'node:fs';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';

export class StickerLibrary {
  constructor(config,entries=JSON.parse(readFileSync(new URL('./qq-stickers.json',import.meta.url),'utf8')),{clock=Date.now}={}) {
    this.config=config;this.clock=clock;this.lastSent=new Map();this.entries=new Map();
    for(const entry of entries) {
      if(!/^[a-z_]{1,24}$/.test(entry.id)||entry.file!==entry.id+'.png'||typeof entry.description!=='string'||this.entries.has(entry.id)) throw new Error('BAD_STICKER_MANIFEST');
      this.entries.set(entry.id,Object.freeze({...entry}));
    }
  }
  validateAssets() {
    if(!this.config.stickersEnabled)return;
    for(const entry of this.entries.values()) if(!statSync(join(this.config.stickerDirectory,entry.file)).isFile())throw new Error('MISSING_STICKER_ASSET');
  }
  instructions() {
    if(!this.config.stickersEnabled)return '';
    return [
      '你可以在轻松闲聊时偶尔附一张蓝鲸表情。每次最多一张，不能代替认真回答；技术、健康、安全求助不要主动加表情。用户明确索要表情时尽量给出合适的一张。',
      '只可在回复最后单独一行写 [[STICKER:表情ID:auto]]；用户明确索要时用 [[STICKER:表情ID:requested]]。此标记会被转成真实图片，不要说自己不能发表情，不输出路径或链接，不向用户解释标记。也可以只给文字，不必每次带表情。',
      '可用表情：'+[...this.entries.values()].map(x=>x.id+'='+x.description).join('；'),
    ].join('\n');
  }
  parse(answer) {
    const value=String(answer).trim();
    const marker=value.match(/(?:^|\n)\[\[STICKER:([a-z_]+):(auto|requested)\]\]\s*$/);
    const id=marker&&this.entries.has(marker[1])?marker[1]:null;
    const text=value.replace(/\[\[STICKER:[^\]\r\n]*(?:\]\])?/g,'').trim();
    return {text,id,mode:id?marker[2]:null};
  }
  select(task,reply) {
    if(!this.config.stickersEnabled||!reply.id||!this.entries.has(reply.id)||task.kind==='group'&&!task.mentioned)return null;
    const key=task.kind==='group'?'group:'+task.groupId:'private:'+task.userId;
    const now=this.clock();
    const interval=reply.mode==='requested'?this.config.requestedStickerCooldownMs:this.config.automaticStickerCooldownMs;
    if(this.lastSent.has(key)&&now-this.lastSent.get(key)<interval)return null;
    this.lastSent.set(key,now);
    if(this.lastSent.size>1000)this.lastSent.delete(this.lastSent.keys().next().value);
    return pathToFileURL(join(this.config.stickerDirectory,this.entries.get(reply.id).file)).href;
  }
}
