import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { createRelationshipStore, sanitizeProfileData } from './qq-relationship.mjs';

test('cleans noisy profile fragments and deduplicates relationship facts', () => {
  const cleaned = sanitizeProfileData({
    summary: '用户喜欢聊天。',
    profile: {
      preferredName: '环宇',
      relationships: ['情侣', '情侣（用户要求互称老公）', '情侣', '江生是我的宠物'],
      chatHabits: ['晚上聊天', '晚上聊天'],
      preferences: ['我', '吗', '喜欢篮球', '喜欢篮球', '的人名字一样，你的名字'],
    },
  });
  assert.deepEqual(cleaned.profile.relationships, ['情侣']);
  assert.deepEqual(cleaned.profile.chatHabits, ['晚上聊天']);
  assert.deepEqual(cleaned.profile.preferences, ['喜欢篮球']);
});

test('keeps relationship state shared by user id and persists it', () => {
  const dir = mkdtempSync(join(process.cwd(), 'relationship-test-'));
  const store = createRelationshipStore(join(dir, 'states'));
  const task = { userId: '42', text: '谢谢你，帮大忙了' };
  const before = store.get(task);
  assert.equal(before.stage, '刚认识');
  const after = store.observe(task);
  assert.ok(after.familiarity > before.familiarity);
  assert.ok(after.trust > before.trust);
  assert.ok(after.affection > before.affection);
  assert.ok(after.milestones.includes('第一次收到明确的感谢'));
  const reloaded = createRelationshipStore(join(dir, 'states'));
  assert.deepEqual(reloaded.get({ userId: '42' }), after);
  assert.deepEqual(reloaded.get({ userId: '43' }), before);
  rmSync(dir, { recursive: true });
});

test('sets a guarded boundary after clear hostility and clamps values', () => {
  const dir = mkdtempSync(join(process.cwd(), 'relationship-test-'));
  const store = createRelationshipStore(join(dir, 'states'));
  const state = store.observe({ userId: '42', text: '滚开，别再烦我' });
  assert.equal(state.boundary, '需要保持距离');
  assert.ok(state.trust < 30);
  assert.ok(state.affection < 10);
  assert.match(state.stage, /陌生|保持距离/);
  rmSync(dir, { recursive: true });
});

test('renders a short private context without exposing ids', () => {
  const dir = mkdtempSync(join(process.cwd(), 'relationship-test-'));
  const store = createRelationshipStore(join(dir, 'states'));
  store.observe({ userId: '42', text: '我们聊了好一阵了，谢谢' });
  const context = store.context({ userId: '42' });
  assert.match(context, /熟悉度|信任感|关系阶段/);
  assert.doesNotMatch(context, /42/);
  rmSync(dir, { recursive: true });
});
