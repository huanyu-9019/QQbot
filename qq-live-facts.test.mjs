import test from 'node:test';
import assert from 'node:assert/strict';
import { liveFactReply } from './qq-live-facts.mjs';

test('answers current time from a supplied clock', () => {
  const result = liveFactReply('现在几点了', new Date('2026-11-03T08:53:45Z'));
  assert.equal(result, '现在是北京时间 2026年11月3日 16:53。');
});

test('answers current date without inventing a different day', () => {
  const result = liveFactReply('今天几号', new Date('2026-11-03T08:53:45Z'));
  assert.equal(result, '今天是2026年11月3日。');
});

test('ignores unrelated messages', () => assert.equal(liveFactReply('你在干嘛', new Date()), null));
