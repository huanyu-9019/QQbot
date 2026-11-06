import { createHash } from 'node:crypto';
import { chmodSync, copyFileSync, mkdirSync, readFileSync, readdirSync, writeFileSync, renameSync } from 'node:fs';
import { join } from 'node:path';

const UNEQUAL_SOURCE = '主人|奴隶|主仆|奴役|支配|服从|所有物|所有者|占有|低人一等|高人一等|不平等|剥夺人权|没有人权|无条件听命|强迫服从|人身控制|人身自由受限|剥夺自由|剥夺权利|霸凌|虐待|压迫|剥削|性别歧视|种族歧视|阶级歧视|human rights violation|slave owner|master and slave|enslavement';
const UNEQUAL_RELATIONSHIP = new RegExp(UNEQUAL_SOURCE, 'u');
const UNEQUAL_RELATIONSHIP_GLOBAL = new RegExp(UNEQUAL_SOURCE, 'gu');

export function containsUnequalRelationship(value) {
  const text = String(value || '');
  return [...text.matchAll(new RegExp(UNEQUAL_SOURCE, 'giu'))].some(match => {
    const prefix = text.slice(Math.max(0, match.index - 12), match.index);
    return !/(?:没有|不受|不因|不把|拒绝|反对|不允许|禁止|不要|不应|不该|不得|避免|反抗|摆脱|no\s+|not\s+|never\s+|without\s+|against\s+)/iu.test(prefix);
  });
}

export function sanitizeText(value, fallback = '') {
  const safeParts = String(value || '').split(/(?<=[。！？!?；;\n])/u).filter(part => !containsUnequalRelationship(part));
  return safeParts.join('').replace(UNEQUAL_RELATIONSHIP_GLOBAL, '').replace(/\s{2,}/g, ' ').trim() || fallback;
}

function safeList(values) {
  return [...new Set((Array.isArray(values) ? values : [])
    .filter(value => typeof value === 'string' && !containsUnequalRelationship(value))
    .map(value => value.trim().slice(0, 160)).filter(Boolean))].slice(-20);
}

function cleanProfileList(values, kind) {
  const result = [];
  for (const value of Array.isArray(values) ? values : []) {
    if (typeof value !== 'string') continue;
    let item = value.trim().replace(/\s+/gu, ' ').slice(0, 160);
    if (!item || item.length < 2) continue;
    if (kind === 'preferences' && (/^(?:我|你|他|她|吗|啊|谁|什么|哪个|的人)$/u.test(item) || /[？?]$/u.test(item) || /名字一样|吃什么|我[，,].*(?:不喜欢|喜欢你)/u.test(item))) continue;
    if (kind === 'relationships') {
      if (/宠物|所有物|主人|奴隶|支配|服从|我的老公|用户的老公|江生(?:喜欢|不喜欢)|迪宏是/iu.test(item)) continue;
      item = item.replace(/[（(].*?[）)]/gu, '').trim();
      if (/老公|老婆|男朋友|女朋友|情侣/iu.test(item)) item = '情侣';
    }
    if (!result.includes(item)) result.push(item);
  }
  return result.slice(-12);
}

export function sanitizeProfileData(data) {
  const source = data && typeof data === 'object' ? data : {};
  const profile = source.profile && typeof source.profile === 'object' ? source.profile : {};
  return {
    ...source,
    summary: sanitizeText(source.summary, ''),
    profile: {
      preferredName: sanitizeText(profile.preferredName, ''),
      privateNickname: sanitizeText(profile.privateNickname, ''),
      groupNicknames: profile.groupNicknames && typeof profile.groupNicknames === 'object'
        ? Object.fromEntries(Object.entries(profile.groupNicknames).map(([key, value]) => [key, sanitizeText(value, '')]).filter(([, value]) => value))
        : {},
      relationships: cleanProfileList(profile.relationships, 'relationships'),
      chatHabits: cleanProfileList(profile.chatHabits, 'chatHabits'),
      preferences: cleanProfileList(profile.preferences, 'preferences'),
    },
  };
}

export function sanitizeRelationshipState(value) {
  const source = value && typeof value === 'object' ? value : {};
  const state = Object.fromEntries(['version', 'familiarity', 'trust', 'affection', 'boundary', 'stage', 'turns', 'lastMood', 'milestones', 'updatedAt']
    .filter(key => Object.hasOwn(source, key)).map(key => [key, source[key]]));
  if (containsUnequalRelationship(state.stage)) state.stage = '刚认识';
  else state.stage = sanitizeText(state.stage, '刚认识');
  if (containsUnequalRelationship(state.lastMood)) state.lastMood = '平静';
  else state.lastMood = sanitizeText(state.lastMood, '平静');
  state.milestones = safeList(state.milestones).slice(-8);
  return state;
}

export function migrateJsonDirectory(directory, sanitize) {
  let migrated = 0;
  for (const name of readdirSync(directory)) {
    if (!name.endsWith('.json')) continue;
    const path = join(directory, name);
    let original;
    try { original = readFileSync(path, 'utf8'); } catch { continue; }
    let parsed;
    try { parsed = JSON.parse(original); } catch { continue; }
    const next = JSON.stringify(sanitize(parsed));
    if (next === JSON.stringify(parsed)) continue;
    const backup = `${path}.before-equality-policy-${Date.now()}.bak`;
    copyFileSync(path, backup);
    chmodSync(backup, 0o600);
    writeFileSync(path, next, { mode: 0o600 });
    migrated++;
  }
  return migrated;
}

const DEFAULT = Object.freeze({ version: 1, familiarity: 0, trust: 30, affection: 10, boundary: '正常', stage: '刚认识', turns: 0, lastMood: '平静', milestones: [], updatedAt: 0 });
const clamp = value => Math.max(0, Math.min(100, Math.round(value)));
const idFor = userId => createHash('sha256').update(`user:${String(userId)}`).digest('hex');

function normalize(value) {
  const state = sanitizeRelationshipState({ ...DEFAULT, ...(value && typeof value === 'object' ? value : {}) });
  for (const key of ['familiarity', 'trust', 'affection', 'turns']) state[key] = clamp(Number(state[key]) || 0);
  if (!['正常', '需要保持距离'].includes(state.boundary)) state.boundary = '正常';
  state.stage = String(state.stage || DEFAULT.stage).slice(0, 20);
  state.lastMood = String(state.lastMood || DEFAULT.lastMood).slice(0, 30);
  state.milestones = Array.isArray(state.milestones) ? state.milestones.filter(x => typeof x === 'string').slice(-8) : [];
  return state;
}

function stageFor(state) {
  if (state.boundary === '需要保持距离') return '保持距离';
  if (state.familiarity >= 70 && state.trust >= 70) return '很熟';
  if (state.familiarity >= 35 && state.trust >= 45) return '熟悉';
  return state.familiarity >= 10 ? '认识一阵了' : '刚认识';
}

function classify(text) {
  const input = String(text || '');
  if (/(?:滚开|闭嘴|别烦我|去死|傻逼|脑残)/.test(input)) return 'hostile';
  if (/(?:谢谢|辛苦|帮大忙|你真好|靠谱|喜欢你|想你)/.test(input)) return 'warm';
  if (/(?:对不起|抱歉|打扰了)/.test(input)) return 'repair';
  return 'neutral';
}

export function createRelationshipStore(directory = '/home/hermes/qq-relationship') {
  mkdirSync(directory, { recursive: true, mode: 0o700 });
  migrateJsonDirectory(directory, sanitizeRelationshipState);
  const pathFor = userId => join(directory, `${idFor(userId)}.json`);
  const get = task => {
    try { return normalize(JSON.parse(readFileSync(pathFor(task.userId), 'utf8'))); }
    catch (error) { if (error.code === 'ENOENT') return { ...DEFAULT }; throw new Error('RELATIONSHIP_STATE_INVALID'); }
  };
  const save = (userId, state) => {
    const path = pathFor(userId); const temp = `${path}.tmp-${process.pid}`;
    writeFileSync(temp, JSON.stringify(sanitizeRelationshipState(state)), { mode: 0o600 }); renameSync(temp, path);
  };
  const observe = task => {
    const state = get(task); const kind = classify(task.text);
    const previousStage = state.stage;
    state.turns = clamp(state.turns + 1);
    state.familiarity = clamp(state.familiarity + 1);
    if (kind === 'warm') { state.trust = clamp(state.trust + 2); state.affection = clamp(state.affection + 2); state.lastMood = '有点开心'; }
    if (kind === 'repair') { state.trust = clamp(state.trust + 1); state.boundary = '正常'; state.lastMood = '平静'; }
    if (kind === 'hostile') { state.trust = clamp(state.trust - 8); state.affection = clamp(state.affection - 5); state.boundary = '需要保持距离'; state.lastMood = '不太舒服'; }
    state.stage = stageFor(state);
    if (kind === 'warm' && !state.milestones.includes('第一次收到明确的感谢')) state.milestones.push('第一次收到明确的感谢');
    if (previousStage !== state.stage) state.milestones.push(`关系阶段变为${state.stage}`);
    state.milestones = state.milestones.slice(-8);
    state.updatedAt = Date.now(); save(task.userId, state); return state;
  };
  const context = task => {
    const state = get(task);
    const growth = state.milestones.length ? `；互动经历=${state.milestones.join('、')}` : '';
    return `关系状态（仅用于调整语气，不要向用户报数）：关系阶段=${state.stage}；熟悉度=${state.familiarity}/100；信任感=${state.trust}/100；好感度=${state.affection}/100；边界=${state.boundary}；当前情绪=${state.lastMood}${growth}。`;
  };
  return { get, observe, context };
}
