import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, readdirSync, rmSync, statSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createGroupStyleLearning, groupStyleContext, safeStyleInstructions } from './qq-group-style.mjs';

function fixture(t, options = {}) {
  const directory = mkdtempSync(join(tmpdir(), 'qq-group-style-'));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  return { directory, learner: createGroupStyleLearning({ directory, salt: 'test-salt', ...options }) };
}

test('learns only aggregate style counts from incoming group messages', t => {
  const { directory, learner } = fixture(t);
  for (let i = 0; i < 30; i++) {
    learner.observe({ kind: 'group', direction: 'incoming', sessionKey: 'qq:group:123456', text: '笑死了！今天也太离谱了吧' });
  }
  const instructions = learner.instructions({ kind: 'group', sessionKey: 'qq:group:123456' });
  assert.match(instructions, /群聊表达统计/);
  assert.match(instructions, /短句/);
  assert.doesNotMatch(instructions, /123456|笑死了|离谱/);
  const stored = readFileSync(join(directory, readdirSync(directory)[0]), 'utf8');
  assert.doesNotMatch(stored, /123456|笑死了|离谱/);
  if (process.platform !== 'win32') assert.equal(statSync(join(directory, readdirSync(directory)[0])).mode & 0o777, 0o600);
});

test('does not learn from private, delivered, or non-group events', t => {
  const { learner } = fixture(t);
  for (const event of [
    { kind: 'private', direction: 'incoming', sessionKey: 'private', text: '哈哈哈哈' },
    { kind: 'group', direction: 'delivered', sessionKey: 'group', text: '哈哈哈哈' },
  ]) learner.observe(event);
  assert.equal(learner.instructions({ kind: 'group', sessionKey: 'group' }), '');
});

test('requires enough messages and isolates learned profiles by group', t => {
  const { learner } = fixture(t);
  for (let i = 0; i < 29; i++) {
    learner.observe({ kind: 'group', direction: 'incoming', sessionKey: 'group-a', text: '嗯？' });
  }
  assert.equal(learner.instructions({ kind: 'group', sessionKey: 'group-a' }), '');
  learner.observe({ kind: 'group', direction: 'incoming', sessionKey: 'group-a', text: '嗯？' });
  assert.notEqual(learner.instructions({ kind: 'group', sessionKey: 'group-a' }), '');
  assert.equal(learner.instructions({ kind: 'group', sessionKey: 'group-b' }), '');
});

test('forgets style evidence older than the rolling retention window', t => {
  let now = Date.UTC(2026, 10, 5);
  const { learner } = fixture(t, { now: () => now, retentionDays: 14 });
  for (let i = 0; i < 30; i++) {
    learner.observe({ kind: 'group', direction: 'incoming', sessionKey: 'group-a', text: '嗯？' });
  }
  assert.notEqual(learner.instructions({ kind: 'group', sessionKey: 'group-a' }), '');
  now += 15 * 24 * 60 * 60 * 1000;
  assert.equal(learner.instructions({ kind: 'group', sessionKey: 'group-a' }), '');
});

test('adds learned style context only to that group response prompt', () => {
  const style = '【群聊表达统计】常用短句。';
  assert.equal(groupStyleContext({ kind: 'group' }, style), style);
  assert.equal(groupStyleContext({ kind: 'private' }, style), '');
});

test('optional style failures return empty context instead of blocking chat', () => {
  assert.equal(safeStyleInstructions({ instructions() { throw new Error('broken state'); } }, {kind:'group'}, () => {}), '');
});

test('new group activity removes expired silent groups from disk', t => {
  let now = Date.UTC(2026,10,5,12);
  const {directory,learner} = fixture(t,{now:()=>now});
  learner.observe({kind:'group',sessionKey:'old',text:'你好'});
  now += 20 * 86400000;
  learner.observe({kind:'group',sessionKey:'new',text:'你好'});
  const state = JSON.parse(readFileSync(join(directory,'style.json'),'utf8'));
  assert.equal(Object.keys(state.groups).length,1);
});
