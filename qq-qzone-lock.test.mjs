import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,readFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawn} from 'node:child_process';
import {pathToFileURL} from 'node:url';

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
