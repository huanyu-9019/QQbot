import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, writeFileSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { parseReminderCommand, handleReminderCommand, createReminderScheduler } from './qq-reminders.mjs';

const NOW = Date.parse('2026-11-02T10:00:00Z'); // 18:00 Shanghai

test('parses a Shanghai-time one-off reminder', () => {
  const result = parseReminderCommand('明天下午三点提醒我开会', NOW);
  assert.equal(result.type, 'create');
  assert.equal(result.title, '开会');
  assert.equal(result.dueAt, Date.parse('2026-11-03T07:00:00Z'));
  assert.equal(result.repeat, null);
});

test('recognizes half-hour times and leaves ordinary reminder discussion to the model', () => {
  const half = parseReminderCommand('明天下午三点半提醒我开会', NOW);
  assert.equal(half.dueAt, Date.parse('2026-11-03T07:30:00Z'));
  assert.equal(parseReminderCommand('提醒功能怎么样', NOW).type, 'none');
});

test('parses relative minute reminders and the plain query wording', () => {
  const relative = parseReminderCommand('2分钟后提醒我喝水', NOW);
  assert.equal(relative.type, 'create');
  assert.equal(relative.dueAt, NOW + 2 * 60 * 1000);
  const chinese = parseReminderCommand('两分钟后提醒我喝水', NOW);
  assert.equal(chinese.type, 'create');
  assert.equal(chinese.dueAt, NOW + 2 * 60 * 1000);
  const ten = parseReminderCommand('十分钟后提醒我休息', NOW);
  assert.equal(ten.dueAt, NOW + 10 * 60 * 1000);
  assert.equal(parseReminderCommand('查询提醒', NOW).type, 'list');
});

test('parses weekly recurrence and handles create, query, and cancel commands', () => {
  const weekly = parseReminderCommand('每周一早上九点提醒我交周报', NOW);
  assert.equal(weekly.type, 'create');
  assert.equal(weekly.title, '交周报');
  assert.equal(new Date(weekly.dueAt + 8 * 60 * 60 * 1000).getUTCDay(), 1);
  const dir = mkdtempSync(join(tmpdir(), 'qq-reminders-'));
  const scheduler = createReminderScheduler({ path: join(dir, 'state.json'), now: () => NOW, send() {}, intervalMs: 60000 });
  const task = { userId: '42', kind: 'private', groupId: '', sessionKey: 'qq:private:42', text: '明天下午三点提醒我交周报' };
  assert.match(handleReminderCommand(task, scheduler, NOW), /记上了/);
  assert.match(handleReminderCommand({ ...task, text: '查一下我的提醒' }, scheduler, NOW), /交周报/);
  assert.match(handleReminderCommand({ ...task, text: '取消提醒' }, scheduler, NOW), /不再提醒/);
  assert.match(handleReminderCommand({ ...task, text: '查我的提醒' }, scheduler, NOW), /没留提醒/);
  scheduler.close();
  rmSync(dir, { recursive: true });
});

test('persists and routes due reminders to the originating session', () => {
  const sent = [];
  const dir = mkdtempSync(join(tmpdir(), 'qq-reminders-'));
  const scheduler = createReminderScheduler({
    path: join(dir, 'state.json'),
    now: () => NOW,
    send: task => { sent.push(task); return 'echo-1'; },
    intervalMs: 60_000,
  });
  const created = scheduler.create({ userId: '42', kind: 'group', groupId: '99', sessionKey: 'qq:group:99', title: '开会', dueAt: NOW });
  assert.equal(created.ok, true);
  scheduler.tick();
  assert.equal(sent[0].kind, 'group');
  assert.equal(sent[0].groupId, '99');
  assert.match(sent[0].text, /开会/);
  assert.doesNotMatch(sent[0].text, /^提醒：/);
  assert.equal(scheduler.list({ userId: '42', sessionKey: 'qq:group:99' }).length, 1);
  scheduler.delivery('echo-1', true);
  assert.equal(scheduler.list({ userId: '42', sessionKey: 'qq:group:99' }).length, 0);
  scheduler.close();
  rmSync(dir, { recursive: true });
});

test('restores reminders after restart and isolates list and cancel by user and session', () => {
  const dir = mkdtempSync(join(tmpdir(), 'qq-reminders-'));
  const path = join(dir, 'state.json');
  const owner = { userId: '42', kind: 'group', groupId: '99', sessionKey: 'qq:group:99' };
  let scheduler = createReminderScheduler({ path, now: () => NOW, send() {}, intervalMs: 60000 });
  const { reminder } = scheduler.create({ ...owner, title: '开会', dueAt: NOW + 3600000 });
  scheduler.close();
  scheduler = createReminderScheduler({ path, now: () => NOW, send() {}, intervalMs: 60000 });
  assert.equal(scheduler.list(owner).length, 1);
  assert.equal(scheduler.list({ ...owner, userId: '43' }).length, 0);
  assert.equal(scheduler.list({ ...owner, sessionKey: 'qq:group:100' }).length, 0);
  assert.equal(scheduler.cancel({ ...owner, userId: '43' }, reminder.id).ok, false);
  assert.equal(scheduler.cancel(owner, reminder.id).ok, true);
  scheduler.close();
  rmSync(dir, { recursive: true });
});

test('advances a daily reminder past missed occurrences', () => {
  const dir = mkdtempSync(join(tmpdir(), 'qq-reminders-'));
  const sent = [];
  let current = NOW;
  let echo = 0;
  const scheduler = createReminderScheduler({ path: join(dir, 'state.json'), now: () => current, send: task => { sent.push(task); return `echo-${++echo}`; }, intervalMs: 60000 });
  scheduler.create({ userId: '42', kind: 'private', sessionKey: 'qq:private:42', title: '吃药', dueAt: NOW, repeat: { type: 'daily' } });
  current += 3 * 24 * 60 * 60 * 1000 + 1;
  scheduler.tick();
  assert.equal(sent.length, 1);
  scheduler.delivery('echo-1', true);
  assert.equal(scheduler.list({ userId: '42', sessionKey: 'qq:private:42' })[0].dueAt, Date.parse('2026-11-06T10:00:00Z'));
  scheduler.close();
  rmSync(dir, { recursive: true });
});

test('does not advance recurring reminders until QQ delivery is confirmed', () => {
  const dir = mkdtempSync(join(tmpdir(), 'qq-reminders-'));
  const sent = [];
  const scheduler = createReminderScheduler({ path: join(dir, 'state.json'), now: () => NOW, send: task => { sent.push(task); return 'echo-fail'; }, intervalMs: 60000 });
  scheduler.create({ userId: '42', kind: 'private', sessionKey: 'qq:private:42', title: '吃药', dueAt: NOW, repeat: { type: 'daily' } });
  scheduler.tick();
  scheduler.delivery('echo-fail', false);
  assert.equal(scheduler.list({ userId: '42', sessionKey: 'qq:private:42' })[0].dueAt, NOW);
  scheduler.close();
  rmSync(dir, { recursive: true });
});

test('fails closed on a corrupt state file instead of overwriting it', () => {
  const dir = mkdtempSync(join(tmpdir(), 'qq-reminders-'));
  const path = join(dir, 'state.json');
  writeFileSync(path, '{broken');
  assert.throws(() => createReminderScheduler({ path, now: () => NOW, send() {}, intervalMs: 60000 }));
  assert.equal(readFileSync(path, 'utf8'), '{broken');
  rmSync(dir, { recursive: true });
});
