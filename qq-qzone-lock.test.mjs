import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,readFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawn} from 'node:child_process';
import {pathToFileURL} from 'node:url';
import {publicationDecision,recordPublicationAttempt,queuePublication,digestPublication} from './qq-qzone-lock.mjs';

test('all publication sources share a four-hour interval and three attempts per Shanghai day',()=>{
  const now=Date.parse('2026-11-07T08:00:00+08:00');
  let state=recordPublicationAttempt({},now);
  assert.equal(publicationDecision(state,now+5*60000).allowed,false);
  assert.equal(publicationDecision(state,now+4*3600000).allowed,true);
  state=recordPublicationAttempt(state,now+4*3600000);
  state=recordPublicationAttempt(state,now+8*3600000);
  assert.equal(publicationDecision(state,now+12*3600000).reason,'daily_limit');
  assert.equal(publicationDecision(state,Date.parse('2026-11-08T00:00:00+08:00')).allowed,true);
});
test('account cooldown prevents any attempts until its deadline',()=>{
  const now=Date.now();const state={publicationPolicy:{blockedUntil:now+86400000}};
  assert.equal(publicationDecision(state,now).reason,'account_cooldown');
  assert.equal(publicationDecision(state,now+86400000).allowed,true);
});
test('queued updates are bounded, deduplicated, and combined into a short digest',()=>{
  let state={};
  for(let i=0;i<60;i++)state=queuePublication(state,'update-'+i,'这是一条经过测试的日常更新记录，详细信息可以到管理台查看。',i);
  assert.equal(state.pendingDigest.length,50);
  state=queuePublication(state,'update-59','新的更新内容');
  assert.equal(state.pendingDigest.length,50);
  state=queuePublication(state,'route-new','聊天线路已切换，仍然可以正常聊天，系统会持续检查可用性。');
  const text=digestPublication(state,'当前更新');
  assert.ok(Array.from(text).length<=140);assert.match(text,/汇总/);assert.match(text,/线路/);
});

test('two concurrent publishers serialize their read-modify-write state', {skip:process.platform!=='linux'}, async t => {
  const dir=mkdtempSync(join(tmpdir(),'qzone-lock-'));
  t.after(()=>rmSync(dir,{recursive:true,force:true}));
  const state=join(dir,'state'); const script=join(dir,'worker.mjs');
  writeFileSync(state,'0');
  writeFileSync(script,`import {ensurePublicationLock} from ${JSON.stringify(new URL('./qq-qzone-lock.mjs',import.meta.url).href)};
import {readFileSync,writeFileSync} from 'node:fs';
ensurePublicationLock(${JSON.stringify(join(dir,'lock'))});
const n=Number(readFileSync(${JSON.stringify(state)},'utf8'));
await new Promise(r=>setTimeout(r,150));
writeFileSync(${JSON.stringify(state)},String(n+1));`);
  const run=()=>new Promise((resolve,reject)=>{
    const p=spawn(process.execPath,[script]);p.on('error',reject);p.on('exit',code=>code===0?resolve():reject(new Error('child exit '+code)));
  });
  await Promise.all([run(),run()]);
  assert.equal(readFileSync(state,'utf8'),'2');
});
