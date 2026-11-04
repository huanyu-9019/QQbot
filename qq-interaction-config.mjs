import {readFileSync} from 'node:fs';
export function loadInteractionConfig(path=new URL('./qq-interaction-config.json',import.meta.url)){
 const config=JSON.parse(readFileSync(path,'utf8'));
 const bounds={queue:{maxPending:[1,100],priorityBurst:[1,100]},typing:{delayMs:[1000,30000],cooldownMs:[60000,3600000],activeWindowMs:[60000,3600000],signalTtlMs:[5000,60000],maxScopes:[1,1000]},recentImages:{ttlMs:[10000,3600000],maxScopes:[1,200],maxCachedBytes:[1048576,33554432]},group:{replyCooldownMs:[10000,600000],decisionIntervalMs:[1000,60000]}};
 for(const [name,fields] of Object.entries(bounds)){
  const c=config[name];if(!c||typeof c.enabled!=='boolean')throw new Error('BAD_INTERACTION_CONFIG');
  for(const [key,[min,max]] of Object.entries(fields))if(!Number.isInteger(c[key])||c[key]<min||c[key]>max)throw new Error('BAD_INTERACTION_CONFIG');
  Object.freeze(c);
 }
 if(typeof config.queue.coalesceGroupText!=='boolean')throw new Error('BAD_INTERACTION_CONFIG');
 if(config.queue.priorityLane!==undefined&&typeof config.queue.priorityLane!=='boolean')throw new Error('BAD_INTERACTION_CONFIG');
 if(config.typing.signalTtlMs<=config.typing.delayMs)throw new Error('BAD_INTERACTION_CONFIG');
 if(config.group.replyCooldownMs<config.group.decisionIntervalMs)throw new Error('BAD_INTERACTION_CONFIG');
 return Object.freeze(config);
}
