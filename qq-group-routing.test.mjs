import test from 'node:test';
import assert from 'node:assert/strict';
import { isDirectGroupMessage } from './qq-group-routing.mjs';

test('treats mentions and explicit names as directed group messages', () => {
  assert.equal(isDirectGroupMessage({ mentioned: true, text: '在吗' }), true);
  assert.equal(isDirectGroupMessage({ mentioned: false, text: '江生你怎么看' }), true);
  assert.equal(isDirectGroupMessage({ mentioned: false, text: '林夏，帮我看看' }), true);
});

test('does not treat ordinary group chatter as directed', () => {
  assert.equal(isDirectGroupMessage({ mentioned: false, text: '今天吃什么' }), false);
  assert.equal(isDirectGroupMessage({ mentioned: false, text: '有人知道这个吗' }), false);
});
