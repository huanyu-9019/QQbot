import { randomInt } from 'node:crypto';
import { readFileSync, writeFileSync, renameSync, chmodSync } from 'node:fs';
import { enqueueTask } from './qq-task-queue.mjs';

const DAY_MS = 24 * 60 * 60 * 1000;
const SHANGHAI_OFFSET_MS = 8 * 60 * 60 * 1000;
const CONFIG_PATH = '/home/hermes/qq-proactive-config.json';
const STATE_PATH = '/home/hermes/qq-proactive-state.json';
function readConfig() {
  const config = JSON.parse(readFileSync(CONFIG_PATH, 'utf8'));
  if (!config || typeof config !== 'object' || Array.isArray(config) ||
      typeof config.enabled !== 'boolean' ||
      !Number.isInteger(config.idleDays) || config.idleDays < 1 || config.idleDays > 14 ||
      !Number.isInteger(config.repeatDays) || config.repeatDays < 1 || config.repeatDays > 30 ||
      Object.keys(config).some(key => !['enabled', 'idleDays', 'repeatDays'].includes(key))) {
    throw new Error('BAD_PROACTIVE_CONFIG');
  }
  return config;
}

function shanghaiDay(now) {
  const shifted = new Date(now + SHANGHAI_OFFSET_MS);
  const year = shifted.getUTCFullYear();
  const month = shifted.getUTCMonth() + 1;
  const day = shifted.getUTCDate();
  const key = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  const start = Date.UTC(year, month - 1, day) - SHANGHAI_OFFSET_MS;
  return { key, start, end: start + DAY_MS };
}

function loadState() {
  try {
    const parsed = JSON.parse(readFileSync(STATE_PATH, 'utf8'));
    if (parsed?.version === 1 && parsed.sessions && typeof parsed.sessions === 'object' && !Array.isArray(parsed.sessions)) {
      return { sessions: parsed.sessions, operational: true };
    }
    console.error('主动互动状态格式无效，已暂停主动消息');
    return { sessions: Object.create(null), operational: false };
  } catch (error) {
    if (error.code === 'ENOENT') return { sessions: Object.create(null), operational: true };
    console.error('主动互动状态读取失败，已暂停主动消息');
    return { sessions: Object.create(null), operational: false };
  }
}

function saveState(sessions) {
  const temp = `${STATE_PATH}.tmp-${process.pid}`;
  writeFileSync(temp, JSON.stringify({ version: 1, sessions }), { encoding: 'utf8', mode: 0o600 });
  chmodSync(temp, 0o600);
  renameSync(temp, STATE_PATH);
}

function validSessionKey(key) {
  return /^qq:(?:private|group):[0-9]+$/.test(key);
}

function validEntry(entry) {
  return entry && Number.isFinite(entry.lastActivityAt) &&
    (entry.lastIdleQueuedAt === null || Number.isFinite(entry.lastIdleQueuedAt)) &&
    (entry.dailyQueuedDay === null || typeof entry.dailyQueuedDay === 'string') &&
    typeof entry.dayKey === 'string' && Number.isFinite(entry.dailyAt) &&
    (entry.dailyEligible === undefined || typeof entry.dailyEligible === 'boolean');
}

export function createProactiveScheduler({ queue, queueConfig, activeSessions, isConnected, processQueue }) {
  const config = readConfig();
  const loaded = loadState();
  const sessions = loaded.sessions;
  let stopped = false;
  let operational = loaded.operational;

  function prepareDay(entry, now) {
    const { key, start } = shanghaiDay(now);
    if (entry.dayKey === key) return false;
    entry.dayKey = key;
    entry.dailyAt = start + randomInt(0, DAY_MS);
    entry.dailyQueuedDay = null;
    entry.dailyEligible = false;
    return true;
  }

  function persist() {
    try {
      saveState(sessions);
    } catch {
      operational = false;
      console.error('主动互动状态保存失败，已暂停主动消息');
    }
  }

  function observe(task) {
    if (stopped || !operational || !config.enabled || !validSessionKey(task.sessionKey)) return;
    const now = Date.now();
    let entry = sessions[task.sessionKey];
    if (!entry || !validEntry(entry)) {
      entry = { lastActivityAt: now, lastIdleQueuedAt: null, dayKey: '', dailyAt: 0, dailyQueuedDay: null, dailyEligible: false };
      sessions[task.sessionKey] = entry;
    }
    entry.lastActivityAt = now;
    prepareDay(entry, now);
    if (now <= entry.dailyAt) entry.dailyEligible = true;
    persist();
  }

  function makeTask(sessionKey, reason) {
    const match = /^qq:(private|group):([0-9]+)$/.exec(sessionKey);
    if (!match) return null;
    const kind = match[1] === 'group' ? 'group' : 'private';
    const id = match[2];
    return {
      kind,
      userId: kind === 'private' ? id : 'grok-proactive',
      groupId: kind === 'group' ? id : '',
      sessionKey,
      text: reason === 'idle'
        ? '请自然地接着本会话的聊天背景，主动和对方打个招呼或问候近况，简短、具体，不要提及定时或提醒。无需搜索或使用任何工具。'
        : '请结合本会话近期聊天背景，主动开启一个轻松自然的话题，简短地问候一下，不要提及定时或提醒。无需搜索或使用任何工具。',
      mentioned: false,
      mentionOnly: false,
      trigger: reason === 'idle' ? 'proactive-idle' : 'proactive-daily',
    };
  }

  function tick() {
    if (stopped || !operational || !config.enabled || !isConnected()) return;
    const now = Date.now();
    let changed = false;
    for (const [sessionKey, entry] of Object.entries(sessions)) {
      if (!validSessionKey(sessionKey) || !validEntry(entry)) continue;
      if (prepareDay(entry, now)) changed = true;
      if (activeSessions.has(sessionKey) || queue.some(task => task.sessionKey === sessionKey && task.trigger?.startsWith('proactive'))) continue;

      const idleDue = now - entry.lastActivityAt >= config.idleDays * DAY_MS &&
        (entry.lastIdleQueuedAt === null || now - entry.lastIdleQueuedAt >= config.repeatDays * DAY_MS);
      const { key, start } = shanghaiDay(now);
      const dailyDue = !idleDue && entry.dayKey === key && entry.dailyQueuedDay !== key &&
        now >= entry.dailyAt && entry.dailyEligible && entry.lastActivityAt >= start &&
        now - entry.lastActivityAt < DAY_MS;
      if (!idleDue && !dailyDue) continue;

      const reason = idleDue ? 'idle' : 'daily';
      const task = makeTask(sessionKey, reason);
      if (!task) continue;
      const result = enqueueTask(queue, task, queueConfig);
      if (!result.accepted) continue;
      if (idleDue) entry.lastIdleQueuedAt = now;
      else entry.dailyQueuedDay = key;
      changed = true;
      console.log('QQ 主动互动入队：', JSON.stringify({ kind: task.kind, reason }));
      void processQueue();
    }
    if (changed) persist();
  }

  let startupChanged = false;
  for (const [key, entry] of Object.entries(sessions)) {
    if (!validSessionKey(key) || !validEntry(entry)) {
      delete sessions[key];
      startupChanged = true;
      continue;
    }
    if (entry.dailyEligible === undefined) {
      const { key, start } = shanghaiDay(Date.now());
      entry.dailyEligible = entry.dayKey === key && entry.lastActivityAt >= start && entry.lastActivityAt <= entry.dailyAt;
      startupChanged = true;
    }
    if (prepareDay(entry, Date.now())) startupChanged = true;
  }
  if (startupChanged && Object.keys(sessions).length) persist();
  const timer = setInterval(tick, 60_000);
  tick();

  return {
    observe,
    close() {
      stopped = true;
      clearInterval(timer);
    },
    status() {
      return { enabled: config.enabled, trackedSessions: Object.keys(sessions).length };
    },
  };
}

