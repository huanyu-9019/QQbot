import { chmodSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { createHmac, randomBytes } from 'node:crypto';
import { join } from 'node:path';

const DAY_MS = 24 * 60 * 60 * 1000;
const MIN_MESSAGES = 30;

export function safeStyleInstructions(learner, task, log = console.error) {
  try { return learner?.instructions(task) ?? ''; }
  catch { log('群聊风格暂不可用'); return ''; }
}

export function groupStyleContext(task, instructions) {
  return task?.kind === 'group' && typeof instructions === 'string' ? instructions : '';
}

function safeChmod(path, mode) {
  if (process.platform !== 'win32') chmodSync(path, mode);
}

function features(text) {
  const value = String(text ?? '').trim();
  const length = Array.from(value).length;
  return {
    messages: 1,
    chars: length,
    short: length <= 18 ? 1 : 0,
    questions: /[?？]/u.test(value) ? 1 : 0,
    exclamations: /[!！]/u.test(value) ? 1 : 0,
    ellipses: /(?:…{1,}|\.{2,})/u.test(value) ? 1 : 0,
    emoji: /\p{Extended_Pictographic}/u.test(value) ? 1 : 0,
    laughter: /(?:哈{2,}|呵呵|笑死|绷不住|233|hhh|草)/iu.test(value) ? 1 : 0,
    casual: /(?:欸|诶|哎|嘛|呗|喂|欸|耶)/u.test(value) ? 1 : 0,
  };
}

function addCounts(target, source) {
  for (const key of Object.keys(source)) target[key] = (target[key] ?? 0) + source[key];
}

function safeState(state) {
  return state && typeof state === 'object' && state.version === 1 && state.groups && typeof state.groups === 'object'
    ? state
    : { version: 1, groups: {} };
}

export function createGroupStyleLearning({
  directory = `${process.env.HOME}/.local/share/qq-group-style`,
  salt,
  saltFile,
  now = Date.now,
  retentionDays = 14,
} = {}) {
  if (!directory) throw new TypeError('group style directory is required');
  mkdirSync(directory, { recursive: true, mode: 0o700 });
  safeChmod(directory, 0o700);
  const statePath = join(directory, 'style.json');
  let secret = salt;
  if (saltFile) {
    mkdirSync(join(saltFile, '..'), { recursive: true, mode: 0o700 });
    try {
      secret = readFileSync(saltFile, 'utf8').trim();
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
      secret = randomBytes(32).toString('hex');
      writeFileSync(saltFile, `${secret}\n`, { encoding: 'utf8', mode: 0o600, flag: 'wx' });
    }
    safeChmod(saltFile, 0o600);
  }
  if (!secret) throw new TypeError('group style salt is required');

  const groupHash = sessionKey => createHmac('sha256', secret).update(String(sessionKey)).digest('hex');
  function readState() {
    try {
      return safeState(JSON.parse(readFileSync(statePath, 'utf8')));
    } catch (error) {
      if (error.code === 'ENOENT') return { version: 1, groups: {} };
      throw error;
    }
  }
  function saveState(state) {
    const temp = `${statePath}.${process.pid}.tmp`;
    writeFileSync(temp, `${JSON.stringify(state)}\n`, { encoding: 'utf8', mode: 0o600, flag: 'wx' });
    safeChmod(temp, 0o600);
    renameSync(temp, statePath);
    safeChmod(statePath, 0o600);
  }
  function trimBuckets(group, date) {
    const cutoff = Math.floor(date / DAY_MS) * DAY_MS - (retentionDays - 1) * DAY_MS;
    for (const day of Object.keys(group)) {
      const timestamp = Date.parse(`${day}T00:00:00Z`);
      if (!Number.isFinite(timestamp) || timestamp < cutoff) delete group[day];
    }
  }
  function recentCounts(group, date) {
    const cutoff = Math.floor(date / DAY_MS) * DAY_MS - (retentionDays - 1) * DAY_MS;
    const total = {};
    for (const [day, counts] of Object.entries(group)) {
      const timestamp = Date.parse(`${day}T00:00:00Z`);
      if (Number.isFinite(timestamp) && timestamp >= cutoff) addCounts(total, counts);
    }
    return total;
  }

  return {
    observe({ kind, direction = 'incoming', sessionKey, text } = {}) {
      if (kind !== 'group' || direction !== 'incoming' || !sessionKey || !String(text ?? '').trim()) return false;
      const date = new Date(now());
      const day = date.toISOString().slice(0, 10);
      const state = readState();
      for (const [key, existing] of Object.entries(state.groups)) {
        trimBuckets(existing, date.getTime());
        if (!Object.keys(existing).length) delete state.groups[key];
      }
      const id = groupHash(sessionKey);
      const group = state.groups[id] ??= {};
      trimBuckets(group, date.getTime());
      const bucket = group[day] ??= {};
      const next = features(text);
      if ((bucket.messages ?? 0) >= 300) return false;
      addCounts(bucket, next);
      saveState(state);
      return true;
    },
    instructions({ kind, sessionKey } = {}) {
      if (kind !== 'group' || !sessionKey) return '';
      const date = new Date(now());
      const state = readState();
      const group = state.groups[groupHash(sessionKey)];
      if (!group) return '';
      trimBuckets(group, date.getTime());
      const total = recentCounts(group, date.getTime());
      if ((total.messages ?? 0) < MIN_MESSAGES) {
        return '';
      }
      const n = total.messages;
      const avg = total.chars / n;
      const descriptors = [avg <= 18 ? '平均偏短，常用短句' : avg >= 60 ? '平均偏长，常用完整句' : '句子长度中等'];
      if (avg <= 18) descriptors.push('本群闲聊回复优先一句收住，不另发气氛补句或无必要的追问；具体问题仍须答清');
      if (total.questions / n >= 0.25) descriptors.push('提问较常见');
      if (total.exclamations / n >= 0.25) descriptors.push('感叹语气较常见');
      if (total.ellipses / n >= 0.2) descriptors.push('停顿和省略较常见');
      if (total.emoji / n >= 0.2) descriptors.push('表情符号较常见');
      if (total.laughter / n >= 0.2) descriptors.push('轻松笑声语气较常见');
      if (total.casual / n >= 0.2) descriptors.push('口语语气词较常见');
      return `【群聊表达统计】近${retentionDays}天至少有${n}条群消息样本：${descriptors.join('；')}。自然贴合群体节奏即可，不要套用统计标签、复用成员原句或刻意模仿某个成员。`;
    },
  };
}
