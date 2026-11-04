import test from 'node:test';
import assert from 'node:assert/strict';
import { appendRecent } from './qq-memory.mjs';

test('recent context keeps both user and Jiangsheng turns', () => {
  const data = { recent: [{ speaker: '龟仙人', user: '现在几点了' }] };
  appendRecent(data, '江生', '现在是北京时间 2026年11月3日 16:53。');
  assert.deepEqual(data.recent.at(-1), { speaker: '江生', user: '现在是北京时间 2026年11月3日 16:53。' });
});
