import {loadInteractionConfig} from './qq-interaction-config.mjs';
export class TypingNudges {
 constructor({config=loadInteractionConfig().typing,clock=Date.now,setTimer=setTimeout,clearTimer=clearTimeout,isBusy=()=>false,connected=()=>false,enqueue=()=>false}={}){
  Object.assign(this,{config,clock,setTimer,clearTimer,isBusy,connected,enqueue});this.states=new Map();
 }
 cancel(state){
  if(state.timer!==null)this.clearTimer(state.timer);
  state.timer=null;state.controller?.abort();state.controller=null;state.revision++;state.typing=false;
 }
 message(task){
  if(!this.config.enabled||task.kind!=='private')return;
  const key='qq:private:'+task.userId;
  let state=this.states.get(key);
  if(!state){state={timer:null,revision:0,lastAttempt:null};this.states.set(key,state);}
  this.cancel(state);state.lastMessage=this.clock();
  while(this.states.size>this.config.maxScopes){const key=this.states.keys().next().value;this.cancel(this.states.get(key));this.states.delete(key);}
 }
 receive(event){
  if(event.post_type!=='notice'||event.notice_type!=='notify'||event.sub_type!=='input_status')return false;
  if(!this.config.enabled||Number(event.group_id||0)!==0)return true;
  const userId=String(event.user_id??''),selfId=String(event.self_id??'');
  if(!/^[1-9]\d*$/.test(userId)||!/^\d+$/.test(selfId)||userId===selfId)return true;
  const key='qq:private:'+userId,state=this.states.get(key);
  if(!state||this.clock()-state.lastMessage>=this.config.activeWindowMs)return true;
  if(Number(event.event_type)!==1){this.cancel(state);return true;}
  state.typing=true;state.lastInput=this.clock();if(state.timer!==null)return true;
  state.timer=this.setTimer(()=>{
   state.timer=null;
   if(!state.typing||!this.connected()||this.isBusy()||this.clock()-state.lastMessage>=this.config.activeWindowMs||state.lastAttempt!==null&&this.clock()-state.lastAttempt<this.config.cooldownMs)return;
   state.controller=new AbortController();state.lastAttempt=this.clock();
   const task={kind:'private',trigger:'typing',typingKey:key,typingRevision:state.revision,userId,sessionKey:key+':typing',text:'对方正在输入，还没有发出新消息。',signal:state.controller.signal,timeoutMs:Math.max(1,this.config.signalTtlMs-(this.clock()-state.lastInput))};
   this.enqueue(task);
  },this.config.delayMs);
  return true;
 }
 isCurrent(task){
  const state=this.states.get(task.typingKey);
  return !!(state&&state.typing&&state.revision===task.typingRevision&&!task.signal.aborted&&this.connected()&&this.clock()-state.lastMessage<this.config.activeWindowMs&&this.clock()-state.lastInput<this.config.signalTtlMs);
 }
 close(){for(const state of this.states.values())this.cancel(state);}
}
export function typingText(answer){
 const text=String(answer??'');if(text.includes('<QQ_SILENT>'))return '';
 return Array.from(text.replace(/\[\[[^\]\r\n]*(?:\]\])?/g,'').replace(/\s+/g,' ').trim()).slice(0,80).join('');
}
