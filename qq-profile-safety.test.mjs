import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { migrateJsonDirectory, sanitizeProfileData, sanitizeRelationshipState } from './qq-relationship.mjs';

test('removes coercive or unequal relationship language from all profile fields', () => {
  const result = sanitizeProfileData({
    summary: '正常偏好；她的主人要求她服从',
    profile: {
      preferredName: '小明',
      relationships: ['朋友', '主人与奴隶'],
      chatHabits: ['被支配才回复', '拒绝被支配'],
      preferences: ['平等聊天', '把她当所有物', '反对性别歧视'],
    },
  });
  assert.equal(result.summary, '正常偏好；');
  assert.deepEqual(result.profile.relationships, ['朋友']);
  assert.deepEqual(result.profile.chatHabits, ['拒绝被支配']);
  assert.deepEqual(result.profile.preferences, ['平等聊天', '反对性别歧视']);
});

test('normalizes relationship milestones without preserving domination roles', () => {
  const result = sanitizeRelationshipState({
    stage: '主人命令',
    lastMood: '被支配',
    milestones: ['成为朋友', '变成奴隶'],
    owner: '某个用户',
  });
  assert.equal(result.stage, '刚认识');
  assert.equal(result.lastMood, '平静');
  assert.deepEqual(result.milestones, ['成为朋友']);
  assert.equal(Object.hasOwn(result, 'owner'), false);
});

test('migrates existing profile files and keeps an exact recoverable backup', () => {
  const directory = mkdtempSync(join(tmpdir(), 'qq-profile-policy-'));
  try {
    const path = join(directory, 'member.json');
    const original = JSON.stringify({ summary: '她是某人的主人', pending: [], profile: { preferences: ['爱看书'] } });
    writeFileSync(path, original, { mode: 0o600 });
    assert.equal(migrateJsonDirectory(directory, sanitizeProfileData), 1);
    assert.equal(JSON.parse(readFileSync(path, 'utf8')).summary, '');
    const backupName = readdirSync(directory).find(name => name.endsWith('.bak'));
    assert.ok(backupName);
    assert.equal(readFileSync(join(directory, backupName), 'utf8'), original);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
