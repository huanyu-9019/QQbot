import { existsSync, readFileSync, writeFileSync, renameSync, chmodSync } from 'node:fs';

const OFFSET = 8 * 60 * 60 * 1000;
const DAY = 24 * 60 * 60 * 1000;
const CN = { 零: 0, 一: 1, 二: 2, 两: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9, 十: 10 };

function numberValue(value) {
  if (/^\d+$/.test(value)) return Number(value);
  if (value.length === 1) return CN[value] ?? NaN;
  if (value === '十') return 10;
  if (value.startsWith('十')) return 10 + (CN[value[1]] ?? 0);
  if (value.endsWith('十')) return (CN[value[0]] ?? 0) * 10;
  return (CN[value[0]] ?? 0) * 10 + (CN[value[2]] ?? CN[value[1]] ?? 0);
}

function shanghaiParts(now) {
  const d = new Date(now + OFFSET);
  return { year: d.getUTCFullYear(), month: d.getUTCMonth(), day: d.getUTCDate() };
}

function toShanghaiDate({ year, month, day, hour, minute }) {
  return Date.UTC(year, month, day, hour, minute) - OFFSET;
}

function parseTime(text) {
  const match = text.match(/(凌晨|早上|上午|中午|下午|晚上|晚间)?\s*([0-9一二两三四五六七八九十]{1,3})(?:\s*[点时:]\s*(半|[0-9]{1,2})\s*分?)?/);
  if (!match) return null;
  let hour = numberValue(match[2]);
  const minute = match[3] === '半' ? 30 : match[3] ? Number(match[3]) : 0;
  if (!Number.isInteger(hour) || hour > 23 || minute > 59) return null;
  const part = match[1] || '';
  if ((part === '下午' || part === '晚上' || part === '晚间') && hour < 12) hour += 12;
  if (part === '中午' && hour < 11) hour += 12;
  if (part === '凌晨' && hour === 12) hour = 0;
  return { hour, minute, raw: match[0], index: match.index };
}

function parseDate(text, now) {
  const base = shanghaiParts(now);
  const absolute = text.match(/(20\d{2})[年\/-](\d{1,2})[月\/-](\d{1,2})日?/);
  if (absolute) return { year: Number(absolute[1]), month: Number(absolute[2]) - 1, day: Number(absolute[3]), raw: absolute[0] };
  if (/后天/.test(text)) return { ...base, day: base.day + 2, raw: '后天' };
  if (/明天/.test(text)) return { ...base, day: base.day + 1, raw: '明天' };
  if (/今天/.test(text) || /今晚/.test(text)) return { ...base, raw: '今天' };
  return { ...base, raw: '' };
}

function parseRepeat(text) {
  if (/每(?:天|日)/.test(text)) return { type: 'daily' };
  const match = text.match(/每周\s*([一二三四五六日天1-7])/);
  if (match) return { type: 'weekly', weekday: match[1] === '日' || match[1] === '天' ? 0 : match[1] === '一' ? 1 : match[1] === '二' ? 2 : match[1] === '三' ? 3 : match[1] === '四' ? 4 : match[1] === '五' ? 5 : match[1] === '六' ? 6 : Number(match[1]) % 7 };
  return null;
}

function cleanTitle(text, time, date, repeat) {
  let title = text.replace(/^\s*(?:提醒我|提醒一下我|请提醒我)\s*/, '').trim();
  if (title === text.trim()) {
    const marker = text.indexOf('提醒我');
    if (marker >= 0) title = text.slice(marker + 3).trim();
  }
  if (time) title = title.replace(time.raw, '');
  if (date?.raw) title = title.replace(date.raw, '');
  if (repeat) title = title.replace(/每(?:天|日)|每周\s*[一二三四五六日天1-7]/, '');
  return title.replace(/[，,、]/g, ' ').replace(/\s+/g, ' ').trim();
}

export function parseReminderCommand(text, now = Date.now()) {
  const input = String(text || '').trim();
  if (/^(?:我的)?提醒(?:列表|记录)?$|^有哪些提醒|^(?:查|查询)(?:看)?(?:一下)?(?:我的)?提醒/.test(input)) return { type: 'list' };
  const cancel = input.match(/^(?:取消|删除|停止)提醒\s*(\d+)?/);
  if (cancel) return { type: 'cancel', id: cancel[1] ? Number(cancel[1]) : null };
  if (!/提醒/.test(input) || (!/提醒我|请提醒|提醒一下/.test(input) && !/(?:明天|后天|今天|每周|每天|每日|[0-9一二两三四五六七八九十]+\s*分钟?后|[0-9一二两三四五六七八九十]+\s*小时?后)/.test(input))) return { type: 'none' };
  const relative = input.match(/([0-9一二两三四五六七八九十]+)\s*(分钟?|小时?)后/);
  if (relative) {
    const amount = numberValue(relative[1]) * (relative[2].startsWith('小时') ? 60 : 1);
    const marker = input.indexOf('提醒我');
    const title = marker >= 0 ? input.slice(marker + 3).trim() : '';
    if (!title) return { type: 'error', message: '还缺提醒内容，比如“2分钟后提醒我喝水”。' };
    return { type: 'create', title: title.replace(/[，,、]/g, ' ').trim(), dueAt: now + amount * 60 * 1000, repeat: null };
  }
  const repeat = parseRepeat(input);
  const date = parseDate(input, now);
  const time = parseTime(input);
  if (!time) return { type: 'error', message: '请告诉我具体时间，例如“明天下午三点提醒我开会”。' };
  let dueAt = toShanghaiDate({ ...date, hour: time.hour, minute: time.minute });
  if (repeat?.type === 'weekly' && !date.raw) {
    while (new Date(dueAt + OFFSET).getUTCDay() !== repeat.weekday || dueAt <= now) dueAt += DAY;
  } else if (repeat?.type === 'daily' && dueAt <= now) {
    do { dueAt += DAY; } while (dueAt <= now);
  }
  if (dueAt <= now && !repeat) return { type: 'error', message: '这个时间已经过去了，请换一个未来的时间。' };
  const title = cleanTitle(input, time, date, repeat);
  if (!title) return { type: 'error', message: '还缺提醒内容，例如“明天下午三点提醒我开会”。' };
  return { type: 'create', title, dueAt, repeat };
}

function formatShanghaiTime(timestamp) {
  const d = new Date(timestamp + OFFSET);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-${String(d.getUTCDate()).padStart(2, '0')} ${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}`;
}

function dueText(reminder) {
  const title = reminder.title;
  const variants = [
    `到时间啦，记得${title}。`,
    `喂，之前让你记的“${title}”，现在该做了。`,
    `时间到了，去处理一下：${title}。`,
  ];
  return variants[(Number(reminder.id) - 1) % variants.length];
}

export function handleReminderCommand(task, scheduler, now = Date.now()) {
  const parsed = parseReminderCommand(task.text, now);
  const owner = { userId: task.userId, sessionKey: task.sessionKey };
  if (parsed.type === 'none') return null;
  if (parsed.type === 'error') return parsed.message;
  if (parsed.type === 'create') {
    const result = scheduler.create({ ...task, ...parsed });
    return result.ok
      ? `行，记上了。${result.reminder.title}，到点我叫你${result.reminder.repeat ? '，之后按这个时间重复。' : '。'}`
      : result.message;
  }
  if (parsed.type === 'cancel') {
    const result = scheduler.cancel(owner, parsed.id);
    return result.ok ? `好，${result.reminder.title}这条我不再提醒了。` : '没找到对应的提醒，你再看看编号？';
  }
  const reminders = scheduler.list(owner);
  return reminders.length
    ? reminders.map(r => `${r.id}、${r.title}（${formatShanghaiTime(r.dueAt)}${r.repeat ? '，重复' : ''}）`).join('；')
    : '这里暂时没留提醒。';
}

function readState(path) {
  try {
    const state = JSON.parse(readFileSync(path, 'utf8'));
    if (state?.version === 1 && Array.isArray(state.reminders)) return state;
  } catch (error) {
    if (error.code === 'ENOENT') return { version: 1, nextId: 1, reminders: [] };
    throw new Error('REMINDER_STATE_INVALID');
  }
}

export function createReminderScheduler({ path, send, now = () => Date.now(), intervalMs = 60_000 }) {
  const state = readState(path);
  let closed = false;
  const pending = new Map();
  const persist = () => {
    const temp = `${path}.tmp-${process.pid}`;
    writeFileSync(temp, JSON.stringify(state), { mode: 0o600 });
    chmodSync(temp, 0o600);
    renameSync(temp, path);
  };
  const create = data => {
    if (!/^\d+$/.test(String(data.userId)) || !/^qq:(?:private|group):\d+$/.test(data.sessionKey) || !data.title || !Number.isFinite(data.dueAt)) return { ok: false, message: '提醒信息无效。' };
    const reminder = { id: state.nextId++, userId: String(data.userId), kind: data.kind, groupId: String(data.groupId || ''), sessionKey: data.sessionKey, title: data.title.slice(0, 200), dueAt: data.dueAt, repeat: data.repeat || null, createdAt: now() };
    state.reminders.push(reminder); persist(); return { ok: true, reminder };
  };
  const list = owner => state.reminders.filter(r => r.userId === String(owner.userId) && r.sessionKey === owner.sessionKey).map(r => ({ ...r }));
  const cancel = (owner, id) => {
    const index = state.reminders.findIndex(r => r.userId === String(owner.userId) && r.sessionKey === owner.sessionKey && (!id || r.id === Number(id)));
    if (index < 0) return { ok: false };
    const [removed] = state.reminders.splice(index, 1); persist(); return { ok: true, reminder: removed };
  };
  const tick = () => {
    const current = now();
    for (const r of state.reminders) {
      if (r.dueAt > current || pending.has(r.id)) continue;
      const echo = send({ kind: r.kind, userId: r.userId, groupId: r.groupId, sessionKey: r.sessionKey, text: dueText(r) }, r.id);
      if (echo) pending.set(r.id, echo);
    }
  };
  const timer = setInterval(tick, intervalMs);
  if (!existsSync(path)) persist();
  const delivery = (echo, ok) => {
    const entry = [...pending.entries()].find(([, value]) => value === echo);
    if (!entry) return false;
    const [id] = entry;
    pending.delete(id);
    if (!ok) return true;
    const index = state.reminders.findIndex(r => r.id === id);
    if (index < 0) return true;
    const reminder = state.reminders[index];
    if (!reminder.repeat) state.reminders.splice(index, 1);
    else {
      do { reminder.dueAt += DAY; } while (reminder.dueAt <= now());
      if (reminder.repeat.type === 'weekly') { while (new Date(reminder.dueAt + OFFSET).getUTCDay() !== reminder.repeat.weekday) reminder.dueAt += DAY; }
    }
    persist();
    return true;
  };
  return { create, list, cancel, tick, delivery, close: () => { closed = true; pending.clear(); clearInterval(timer); }, isClosed: () => closed };
}
