import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync, renameSync } from 'node:fs';
import { join } from 'node:path';

const DEFAULT = Object.freeze({ version: 1, familiarity: 0, trust: 30, affection: 10, boundary: '正常', stage: '刚认识', turns: 0, lastMood: '平静', milestones: [], updatedAt: 0 });
const clamp = value => Math.max(0, Math.min(100, Math.round(value)));
const idFor = userId => createHash('sha256').update(`user:${String(userId)}`).digest('hex');

function normalize(value) {
  const state = { ...DEFAULT, ...(value && typeof value === 'object' ? value : {}) };
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
  const pathFor = userId => join(directory, `${idFor(userId)}.json`);
  const get = task => {
    try { return normalize(JSON.parse(readFileSync(pathFor(task.userId), 'utf8'))); }
    catch (error) { if (error.code === 'ENOENT') return { ...DEFAULT }; throw new Error('RELATIONSHIP_STATE_INVALID'); }
  };
  const save = (userId, state) => {
    const path = pathFor(userId); const temp = `${path}.tmp-${process.pid}`;
    writeFileSync(temp, JSON.stringify(state), { mode: 0o600 }); renameSync(temp, path);
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
