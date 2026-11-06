import {spawnSync} from 'node:child_process';

export const PUBLICATION_INTERVAL_MS = 4 * 60 * 60 * 1000;
export const PUBLICATION_DAILY_LIMIT = 3;
export function shanghaiDay(now) {
  return new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(now));
}
export function publicationDecision(state, now = Date.now()) {
  const policy = state.publicationPolicy || {};
  if (Number(policy.blockedUntil || 0) > now) return {allowed:false,reason:'account_cooldown',nextAttemptAt:policy.blockedUntil};
  const next = Number(policy.lastAttemptAt || 0) + PUBLICATION_INTERVAL_MS;
  if (next > now) return {allowed:false,reason:'global_interval',nextAttemptAt:next};
  if (policy.day === shanghaiDay(now) && Number(policy.attempts || 0) >= PUBLICATION_DAILY_LIMIT) {
    // The daily counter resets at Shanghai midnight; retain the four-hour spacing too.
    const midnight = Date.parse(shanghaiDay(now) + 'T00:00:00+08:00') + 86400000;
    return {allowed:false,reason:'daily_limit',nextAttemptAt:Math.max(next,midnight)};
  }
  return {allowed:true,reason:'due'};
}
export function recordPublicationAttempt(state, now = Date.now()) {
  const previous = state.publicationPolicy || {};
  return {...state,publicationPolicy:{...previous,lastAttemptAt:now,day:shanghaiDay(now),
    attempts:previous.day === shanghaiDay(now) ? Number(previous.attempts || 0) + 1 : 1}};
}
export function queuePublication(state, id, text, now = Date.now()) {
  const queue = Array.isArray(state.pendingDigest) ? state.pendingDigest : [];
  return {...state,pendingDigest:[...queue.filter(row=>row.id!==id),{id,text:String(text || ''),at:now}].slice(-50)};
}
export function digestPublication(state, current) {
  const rows=(state.pendingDigest || []).filter(row=>row.text);
  if (rows.length <= 1) return current;
  const latest = new Map();
  for (const row of rows) {
    const category = /route|model|budget/.test(row.id) ? '线路' : /health|server|space/.test(row.id) ? '状态' : '更新';
    latest.set(category,row.text);
  }
  const summaries=[...latest].map(([category,text])=>category+'：'+Array.from(text).slice(0,34).join(''));
  return Array.from('最近运行与更新汇总：'+summaries.join('；')+'。详细记录保存在管理台。').slice(0,140).join('');
}

export function ensurePublicationLock(lockPath) {
  if (process.platform !== 'linux') throw new Error('QQ空间发布锁需要 Linux');
  if (process.env.QQ_QZONE_LOCK_HELD === lockPath) return;
  const result=spawnSync('/usr/bin/flock',['--exclusive','--wait','40',lockPath,process.execPath,...process.argv.slice(1)],{
    stdio:'inherit',env:{...process.env,QQ_QZONE_LOCK_HELD:lockPath},
  });
  process.exit(result.status ?? 1);
}
