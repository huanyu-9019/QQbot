import { readFileSync, writeFileSync, renameSync } from 'node:fs';
import { persona } from './qq-memory.mjs';
import { assertSearchOnlyAccess } from './qq-search-policy.mjs';
import { spawnSync } from 'node:child_process';
import { ensurePublicationLock } from './qq-qzone-lock.mjs';

// All publishing paths use the same account and lock, including manual root calls.
if (process.getuid?.() === 0) {
  const result = spawnSync('/usr/sbin/runuser', ['-u','hermes','--',process.execPath,...process.argv.slice(1)], {
    stdio: 'inherit', env: {...process.env, HOME:'/home/hermes'},
  });
  process.exit(result.status ?? 1);
}
ensurePublicationLock('/home/hermes/.config/qq-hermes/qzone-publish.lock');

const mode = process.argv[2] ?? '--dry-run';
if (!['--dry-run', '--test-private', '--publish', '--publish-update'].includes(mode)) {
  throw new Error('未知模式');
}
const updateId = mode === '--publish-update' ? process.argv[3] : '';
if (mode === '--publish-update' && (process.argv.length !== 4 || !/^[a-z0-9][a-z0-9-]{2,63}$/i.test(updateId))) {
  throw new Error('更新发布需要有效且稳定的更新编号');
}

const home = '/home/hermes';
const statePath = home + '/qq-qzone-state.json';
const api = 'http://127.0.0.1:8642';
const today = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
}).format(new Date());

function readState() {
  try {
    return JSON.parse(readFileSync(statePath, 'utf8'));
  } catch (error) {
    if (error.code === 'ENOENT') return {};
    throw error;
  }
}

function saveState(state) {
  const temp = statePath + '.' + process.pid + '.tmp';
  writeFileSync(temp, JSON.stringify(state, null, 2) + '\n', { mode: 0o600, flag: 'wx' });
  renameSync(temp, statePath);
}

function withUpdateAttempt(state, attempt) {
  const publishedUpdates = state.publishedUpdates && typeof state.publishedUpdates === 'object' && !Array.isArray(state.publishedUpdates)
    ? state.publishedUpdates
    : {};
  return { ...state, publishedUpdates: { ...publishedUpdates, [updateId]: attempt } };
}

function apiKey() {
  const env = readFileSync(home + '/.hermes/.env', 'utf8');
  const line = env.split(/\r?\n/).filter(x => x.startsWith('API_SERVER_KEY=')).at(-1);
  const key = line?.slice('API_SERVER_KEY='.length).trim();
  if (!key) throw new Error('Hermes API 密钥未配置');
  return key;
}

async function generate(recent) {
  const headers = { Authorization: 'Bearer ' + apiKey() };
  await assertSearchOnlyAccess(api, headers);

  const system = [persona, "你在自己的 QQ 空间发原创说说。沿用Grok妩媚、腹黑、机灵的口吻，可以写一个让成年人会心一笑的大胆双关或反撩；有具体语境和意外包袱，别写空泛情话、露骨色情或重复旧梗。说说是公开内容，不针对真实群友或陌生人调情；不提个人信息、现实地点、联系方式或账号，不写政治、广告或惊吓内容。不使用 emoji、颜文字、网址、@、话题标签。只输出说说正文。"].join("\n");
  const previous = recent.length
    ? '最近发过这些，请换切入点和包袱，别重复：\n' + recent.map(x => x.content).join('\n')
    : '这是第一条，不需要承接以前的内容。';

  for (let attempt = 0; attempt < 2; attempt++) {
    const response = await fetch(api + '/v1/chat/completions', {
      method: 'POST',
      headers: {
        ...headers,
        'Content-Type': 'application/json',
        'X-Hermes-Session-Key': 'qq-qzone-' + today + '-' + attempt,
      },
      body: JSON.stringify({
        model: 'hermes-agent',
        messages: [
          { role: 'system', content: system },
          { role: 'user', content: previous + '\n写一条今天可以公开发布的 QQ 空间说说，25 到 110 字，1 到 3 句。写得机灵、妩媚、有点坏，最好有一处意想不到的成人双关；别写露骨内容，别加标题。' },
        ],
      }),
      signal: AbortSignal.timeout(120000),
    });
    if (!response.ok) throw new Error('Hermes 生成失败：HTTP ' + response.status);
    const result = await response.json();
    const choice = result.choices?.[0];
    if (choice?.finish_reason === 'error' || choice?.finish_reason === 'cancelled') {
      throw new Error('Hermes 本轮未完成');
    }
    const content = String(choice?.message?.content ?? '').trim().replace(/^["“]|["”]$/g, '');
    const length = Array.from(content).length;
    if (length >= 25 && length <= 140 &&
        !/https?:\/\/|www\.|@|#|<QQ_SILENT>|(?:\d[\s-]?){7,}/i.test(content) &&
        !recent.some(x => x.content === content)) {
      return content;
    }
  }
  throw new Error('两次生成均未通过长度或内容检查');
}

async function sendQzone(content, visibility) {
  const ws = new WebSocket('ws://127.0.0.1:3001');
  const echo = 'qzone-' + Date.now() + '-' + process.pid;
  try {
    const reply = await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => { ws.close(); reject(new Error('NapCat 响应超时，发布结果待核实')); }, 30000);
      ws.addEventListener('open', () => {
        ws.send(JSON.stringify({
          action: 'send_qzone_msg',
          params: { content, images: [], ugc_right: visibility },
          echo,
        }));
      });
      ws.addEventListener('message', event => {
        let value;
        try { value = JSON.parse(event.data); } catch { return; }
        if (value.echo !== echo) return;
        clearTimeout(timeout);
        resolve(value);
      });
      ws.addEventListener('error', () => {
        clearTimeout(timeout);
        reject(new Error('NapCat WebSocket 连接失败，发布结果待核实'));
      });
    });
    if (reply.status !== 'ok' || reply.retcode !== 0 || !reply.data?.tid) {
      throw new Error('NapCat 发说说失败：retcode=' + String(reply.retcode));
    }
    return String(reply.data.tid);
  } finally {
    ws.close();
  }
}

const state = readState();
if (mode === '--publish' && state.lastAttempt?.date === today) {
  console.log('今天已有公开发布记录或待核实记录，跳过');
  process.exit(0);
}
if (updateId && state.publishedUpdates?.[updateId]) {
  console.log('此更新编号已有发布记录或待核实记录，跳过');
  process.exit(0);
}

const recent = Array.isArray(state.recent) ? state.recent.slice(-7) : [];
const supplied = (mode === '--publish' || updateId) && !process.stdin.isTTY
  ? readFileSync(0, 'utf8').trim()
  : '';
if (updateId && !supplied) throw new Error('更新发布必须提供已审核的说说正文');
const content = supplied || await generate(recent);
if (supplied) {
  const length = Array.from(supplied).length;
  if (length < 25 || length > 140 ||
      /https?:\/\/|www\.|@|#|<QQ_SILENT>|(?:\d[\s-]?){7,}/i.test(supplied) ||
      recent.some(x => x.content === supplied)) {
    throw new Error('指定文案未通过长度或内容检查');
  }
}
if (mode === '--dry-run') {
  console.log(content);
  process.exit(0);
}

if (mode === '--publish' || updateId) {
  const pending = { date: today, status: 'pending' };
  saveState(updateId
    ? { ...withUpdateAttempt(state, pending), recent }
    : { ...state, lastAttempt: pending, recent });
}
const visibility = mode === '--test-private' ? 64 : 1;
const tid = await sendQzone(content, visibility);
if (mode === '--test-private') {
  console.log(JSON.stringify({ visibility: 'private', tid, content }));
} else {
  const recentNext = [...recent, { date: today, content }].slice(-7);
  const sent = { date: today, status: 'sent', tid };
  saveState(updateId
    ? { ...withUpdateAttempt(state, sent), recent: recentNext }
    : { ...state, lastAttempt: sent, recent: recentNext });
  console.log(updateId ? '已公开发布功能更新' : '已公开发布今日说说');
}
