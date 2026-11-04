import test from 'node:test';
import assert from 'node:assert/strict';
import {withLastFallback,validCompletion} from './qq-model-fallback.mjs';
test('failed primary uses the final provider',async()=>{
 assert.equal(await withLastFallback(async()=>{throw Error('down')},async()=> 'backup'), 'backup');
});
test('empty or error completions are unhealthy',()=>{
 assert.equal(validCompletion({choices:[{finish_reason:'error',message:{content:'x'}}]}),false);
 assert.equal(validCompletion({choices:[{finish_reason:'stop',message:{content:''}}]}),false);
 assert.equal(validCompletion({choices:[{finish_reason:'stop',message:{content:'OK'}}]}),true);
});
