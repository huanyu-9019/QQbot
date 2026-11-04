import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, readdirSync, rmSync, statSync, utimesSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createConversationAudit } from './qq-conversation-audit.mjs';

test('records bounded incoming and delivered events with hashed sessions', () => {
  const directory = mkdtempSync(join(tmpdir(), 'qq-audit-'));
  try {
    const audit = createConversationAudit({ directory, sessionSalt: 'test-salt', now: () => 1700000000000 });
    const turnId = audit.recordIncoming({ sessionKey: 'qq:private:123456', kind: 'private', text: 'hello'.repeat(300) });
    audit.recordDelivered({ sessionKey: 'qq:private:123456', kind: 'private', text: 'hi', turnId });
    const file = join(directory, readdirSync(directory)[0]);
    const rows = readFileSync(file, 'utf8').trim().split('\n').map(JSON.parse);
    assert.equal(rows.length, 2);
    assert.equal(rows[0].direction, 'incoming');
    assert.equal(rows[1].direction, 'delivered');
    assert.equal(rows[0].text.length, 1200);
    assert.match(rows[0].sessionHash, /^[a-f0-9]{64}$/);
    assert.equal(rows[0].sessionKey, undefined);
    assert.equal(rows[0].turnId, rows[1].turnId);
    if (process.platform !== 'win32') assert.equal(statSync(file).mode & 0o777, 0o600);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('persists a private salt so session hashes survive process restarts', () => {
  const directory = mkdtempSync(join(tmpdir(), 'qq-audit-'));
  const saltFile = join(directory, '.salt');
  try {
    const first = createConversationAudit({ directory, saltFile, now: () => 1700000000000 });
    first.recordIncoming({ sessionKey: 'qq:private:123456', kind: 'private', text: 'hello' });
    const firstRow = JSON.parse(readFileSync(join(directory, '2023-11-14.jsonl'), 'utf8').trim());
    const second = createConversationAudit({ directory, saltFile, now: () => 1700000000000 });
    second.recordIncoming({ sessionKey: 'qq:private:123456', kind: 'private', text: 'again' });
    const rows = readFileSync(join(directory, '2023-11-14.jsonl'), 'utf8').trim().split('\n').map(JSON.parse);
    assert.equal(rows[1].sessionHash, firstRow.sessionHash);
    assert.equal(statSync(saltFile).mode & 0o777, process.platform === 'win32' ? statSync(saltFile).mode & 0o777 : 0o600);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('prunes audit files older than seven days', () => {
  const directory = mkdtempSync(join(tmpdir(), 'qq-audit-'));
  try {
    const audit = createConversationAudit({ directory, sessionSalt: 'test-salt', now: () => 1700000000000 });
    audit.recordIncoming({ sessionKey: 'qq:private:123456', kind: 'private', text: 'old' });
    const file = join(directory, readdirSync(directory)[0]);
    const old = new Date(1700000000000);
    utimesSync(file, old, old);
    audit.prune(1700000000000 + 8 * 24 * 60 * 60 * 1000);
    assert.deepEqual(readdirSync(directory), []);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
