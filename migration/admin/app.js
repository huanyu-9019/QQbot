const $ = (id) => document.getElementById(id);
let csrf = '';
let role = 'readonly';
let settings = null;
let statusData = null;
let updateData = null;
const labels = { hermesApi: 'Hermes API', qqBridge: 'QQ 桥接', napcat: 'NapCat QQ', modelNotice: '模型公告服务' };
const featureInputs = [...document.querySelectorAll('[data-feature]')];

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    headers['X-CSRF-Token'] = csrf;
  }
  const response = await fetch(path, { credentials: 'same-origin', cache: 'no-store', ...options, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `请求失败（${response.status}）`);
  return payload;
}
const post = (path, value) => api(path, { method: 'POST', body: JSON.stringify(value) });
const show = (id, message, error = false) => { const el = $(id); el.textContent = message || ''; el.classList.toggle('error', error); el.classList.toggle('success', !error && !!message); };
const fmt = (value) => value === undefined || value === null ? '—' : String(value);

function loggedIn(value) {
  $('login-card').classList.toggle('hidden', value);
  $('app').classList.toggle('hidden', !value);
  $('top-actions').classList.toggle('hidden', !value);
  document.querySelectorAll('.write-only').forEach(el => {
    if (el.classList.contains('view')) el.classList.toggle('hidden', value && role !== 'admin');
    else el.classList.toggle('hidden', value && role !== 'admin');
  });
  document.querySelectorAll('[data-write]').forEach(el => el.classList.toggle('hidden', value && role !== 'admin'));
}
function selectView(name) {
  document.querySelectorAll('.view').forEach(el => el.classList.toggle('hidden', el.id !== `view-${name}`));
  document.querySelectorAll('.tab').forEach(el => el.classList.toggle('active', el.dataset.view === name));
  if (name === 'backups') loadBackups();
  if (name === 'updates') loadUpdates();
}
function renderProfile(data) {
  const fields = $('profile-fields'), relation = $('relationship-fields');
  fields.replaceChildren(); relation.replaceChildren();
  const p = data.portrait || {}, history = p.history || {}, native = data.native || {};
  const el = (tag, text, cls) => { const n = document.createElement(tag); n.textContent = text; if (cls) n.className = cls; return n; };
  const paragraph = (root, text, cls = '') => root.append(el('p', text, cls));
  const section = (root, title) => root.append(el('h4', title));
  const list = (root, values) => { const ul = el('ul', '', 'memory-list'); for (const v of values || []) ul.append(el('li', v)); root.append(ul); };
  paragraph(fields, p.name || '称呼还没有可靠记录', 'person-name');
  if (p.aliases?.length) paragraph(fields, '也用过这些称呼：' + p.aliases.join('、'), 'muted');
  section(fields, '我们之间');
  paragraph(fields, p.relationship?.description || '关系资料暂未读取成功。');
  paragraph(fields, p.relationship?.note || '先核对资料，不凭空补全关系。', 'muted');
  const attitude = p.relationship?.attitude || {};
  section(fields, '好感度与江生对 TA 的态度');
  const score = value => Number.isFinite(value) ? `${value}/100` : '未记录';
  const attitudeRows = [
    ['历史关系阶段', attitude.stage || '未记录'],
    ['好感度', score(attitude.affection)],
    ['熟悉度', score(attitude.familiarity)],
    ['信任度', score(attitude.trust)],
    ['关系边界', attitude.boundary || '未记录'],
  ];
  for (const [label, value] of attitudeRows) paragraph(fields, `${label}：${value}`);
  paragraph(fields, '这些数值和阶段来自旧系统的历史估算，不代表实时情绪或已确认关系；江生对这个人的实际态度，请结合下方真实来往片段判断。', 'muted');
  const saved = native.facts || [];
  section(fields, '后来记住的事');
  for (const fact of saved) {
    const item = el('article', '', 'memory-entry');
    paragraph(item, fact.detail || fact.value || '（内容为空）');
    paragraph(item, `${fact.category || '记忆'} · 保存于 ${formatTime(fact.updatedAt)}${fact.sourceCount != null ? ' · 依据 ' + fact.sourceCount + ' 条' : ''}`, 'muted');
    fields.append(item);
  }
  if (!saved.length) paragraph(fields, native.status === 'available' ? '还没有新系统已采纳的结构化记忆。下面的旧资料与聊天片段不会冒充新的学习成果。' : '新系统记忆暂时读取失败。', 'muted');
  const clues = el('details', '', 'memory-details');
  clues.append(el('summary', '迁入的个人线索 · 尚缺逐条原话依据'));
  for (const [key, title] of [['habits','聊天习惯'], ['preferences','兴趣和偏好线索'], ['routine','生活与作息'], ['boundaries','明确边界线索']]) {
    if (p[key]?.length) { section(clues, title); list(clues, p[key]); }
  }
  paragraph(clues, '保留旧资料供核对；后续明确更正和有来源的新记忆优先。群聊与私聊共用同一账号的经历，不按昵称合并不同人。', 'muted');
  fields.append(clues);
  if (history.status === 'available') {
    paragraph(relation, history.humanTurns ? `记录中最早的来往：${formatTime(history.firstAt)}；最近来往：${formatTime(history.lastAt)}。累计收录对方 ${history.humanTurns} 条消息，来自 ${(history.channels || []).map(x => x === 'private' ? '私聊' : '群聊').join('、')}。` : '尚未收录这位用户的真实对话。', 'muted');
    paragraph(relation, '以下选取最早与最近的对话片段，保留双方归属。它们是发生过的发言，玩笑、自述和旧回答仍需结合上下文判断，不能直接当作已确认事实。', 'muted');
    for (const item of history.excerpts || []) {
      const row = el('article', '', 'memory-entry');
      paragraph(row, `${item.speaker === 'human' ? (p.name || '对方') : '江生当时的回答'} · ${item.channel === 'private' ? '私聊' : '群聊'} · ${formatTime(item.at)}`, 'muted');
      row.append(el('blockquote', item.text)); relation.append(row);
    }
  } else paragraph(relation, '真实对话记录暂未读取成功，不能据此认定没有来往。', 'muted');
  const diagnostics = el('details', '', 'memory-details');
  diagnostics.append(el('summary', '历史提取与旧评分说明'));
  paragraph(diagnostics, '旧熟悉度、好感度、信任感由关键词和消息数计算，次数曾封顶100；单次情绪也会改变旧阶段。它们不再作为当前关系或共同经历展示。', 'muted');
  if (attitude.updatedAt) paragraph(diagnostics, '旧评分更新时间：' + formatTime(attitude.updatedAt), 'muted');
  if (p.review?.rejected?.length) paragraph(diagnostics, '已从可用资料中排除的疑似问句碎片：' + p.review.rejected.join('、'), 'muted');
  relation.append(diagnostics);
  $('profile-card').classList.remove('hidden');
}
function formatTime(value) {
  if (value === undefined || value === null || value === '') return '暂无记录';
  const n = Number(value);
  const d = Number.isFinite(n) ? new Date(Math.abs(n) < 1e11 ? n * 1000 : n) : new Date(value);
  return Number.isNaN(d.getTime()) ? '时间未识别' : d.toLocaleString();
}
function renderEvolution(data) {
  const state = $('evolution-state');
  const cards = $('evolution-cards');
  const routes = $('evolution-routes');
  cards.replaceChildren(); routes.replaceChildren();
  if (!data) { state.textContent = '两台服务器状态暂不可用，请等待下次刷新'; $('overview-primary').textContent='未核实'; $('model-primary').textContent='未核实'; return; }
  state.textContent = data.stale ? '状态数据已过期，正在等待 Codex 更新' : '状态更新于 ' + formatTime(data.generatedAt);
  const hosts = [
    ['Codex 服务器', data.codex, data.codex?.listening ? '正在监听' : '未确认监听'],
    ['QQ 机器人服务器', data.qq, data.qq?.canReply ? '回复链可用' : '回复链异常'],
  ];
  for (const [name, host, status] of hosts) {
    const card = document.createElement('article'); card.className = 'service-card';
    const title = document.createElement('strong'); title.textContent = name;
    const pill = document.createElement('span');
    const healthy = !data.stale && host?.online && (name === 'Codex 服务器' ? host.listening : host.canReply);
    pill.className = 'pill ' + (healthy ? 'ok' : 'bad'); pill.textContent = data.stale ? '状态过期' : status;
    const small = document.createElement('small');
    small.textContent = '可用内存 ' + (host?.memoryAvailableMiB ?? '—') + ' MiB · 磁盘剩余 ' + (host?.diskFreeGiB ?? '—') + ' GiB';
    card.append(title, pill, small); cards.append(card);
  }
  const qq = data.qq || {}; const codex = data.codex || {};
  $('evolution-reply').textContent = qq.lastDelivered ? '上次 QQ 确认送达：' + formatTime(qq.lastDelivered) + ' · AstrBot / 陪伴插件' : qq.lastReply ? '上次模型完成（含内部测试）：' + formatTime(qq.lastReply) : '尚无路由器成功回复记录';
  for (const route of qq.routes || []) {
    const item = document.createElement('div'); item.className = 'metric';
    const label = document.createElement('span'); label.textContent = route.name;
    const value = document.createElement('strong'); value.textContent = route.model + ' · ' + (route.available ? '文字可用' : '文字异常') + ' / ' + (route.visionAvailable ? '看图可用' : '看图异常');
    item.append(label, value); routes.append(item);
  }
  $('evolution-vision').textContent = data.stale ? '状态过期' : qq.canSeeImages ? '可识别图片' : '图片识别故障';
  $('evolution-fetch').textContent = formatTime(codex.lastFetch);
  $('evolution-iteration').textContent = formatTime(codex.lastIteration) + ' · ' + (codex.iterationStatus || '状态未知');
  const change = data.latestChange || {};
  $('evolution-change').textContent = (change.files?.join('、') || '暂无代码变更') + ' · ' + (change.status || '');
  $('evolution-reason').textContent = '最近学习结论：' + (codex.lastReason || '暂无');
  const actual = data.stale ? '状态已过期' : (qq.activeModel ? qq.activeProvider + ' / ' + qq.activeModel : '等待真实请求选路');
  for (const id of ['overview-primary','model-primary']) $(id).textContent = actual;
  const chain = (qq.routes || []).map(r => r.name + '（' + r.model + '）').join(' → ');
  for (const id of ['overview-fallback','model-fallback']) $(id).textContent = chain;
  const statusNames = {completed:'评估完成',evaluating:'评估中',failed:'评估失败',unknown:'尚无新状态'};
  const metrics = $('evolution-learning-metrics'); metrics.replaceChildren();
  if (qq.runtime === 'astrbot') { const p = document.createElement('p'); p.textContent = 'AstrBot ' + (qq.astrbot ? '运行中' : '异常') + ' · QQ ' + (qq.qqConnected ? '已连接' : '断开') + ' · 陪伴插件 ' + (qq.companionReady ? '已就绪' : '未就绪') + ' · 上次入站 ' + formatTime(qq.lastIncoming) + ' · 超时未回复 ' + (qq.unanswered || 0) + ' 条'; metrics.append(p); }
  for (const [name,value] of [['累计学习轮数',codex.iterationCount ?? '—'],['学习频率','每 30 分钟'],['日志检查频率','每 5 分钟'],['下次评估最早时间',formatTime(codex.nextIteration)],['本轮状态',statusNames[codex.learningStatus] || codex.learningStatus],['评估对话事件',codex.learningEvents ?? '—'],['评估开始',formatTime(codex.learningStarted)],['评估结束',formatTime(codex.learningFinished)]]) {
    const item=document.createElement('div');item.className='metric';
    const title=document.createElement('span');title.textContent=name;
    const content=document.createElement('strong');content.textContent=value;item.append(title,content);metrics.append(item);
  }
  const commits=$('evolution-commits');commits.replaceChildren();
  for (const row of codex.changes || []) {
    const item=document.createElement('article');item.className='history-entry';
    const title=document.createElement('strong');title.textContent=formatTime(row.at)+' · '+row.revision;
    const files=document.createElement('p');files.textContent=(row.files || []).map(f => f.file+'（新增 '+f.added+' / 删除 '+f.removed+' 行）').join('、');
    item.append(title);
    if ((row.files || []).length > 4) { const detail=document.createElement('details'); const summary=document.createElement('summary'); summary.textContent='展开 '+row.files.length+' 个文件的改动'; detail.append(summary,files); item.append(detail); } else { item.append(files); }
    for(const rule of row.summary || []) { const p=document.createElement('p');p.className='small muted';p.textContent=rule;item.append(p); }
    commits.append(item);
  }
  if (!commits.childElementCount) commits.textContent='暂无自动发布记录';
  const learning=$('evolution-learning');learning.replaceChildren();
  const kinds={code:'已发布代码',learning_record:'记录经验，未发布代码',failed:'评估失败'};
  for(const row of codex.learningHistory || []) {
    const item=document.createElement('article');item.className='history-entry';
    const title=document.createElement('strong');title.textContent='#'+row.iteration+' · '+formatTime(row.at)+' · '+(kinds[row.kind] || row.kind);
    const p=document.createElement('p');p.textContent=row.reason;item.append(title,p);learning.append(item);
  }
  if(!learning.childElementCount) learning.textContent='暂无学习记录';
}
function renderServices(data) {
  if (data.runtime === 'astrbot') { labels.hermesApi = 'AstrBot 江生'; labels.qqBridge = '聊天模型路由'; }
  const root = $('service-cards'); root.replaceChildren();
  Object.entries(data.services || {}).forEach(([key, service]) => {
    const card = document.createElement('article'); card.className = 'service-card';
    const title = document.createElement('strong'); title.textContent = labels[key] || key;
    const state = document.createElement('span'); state.className = `pill ${service.active ? 'ok' : 'bad'}`; state.textContent = service.active ? '运行中' : `异常：${fmt(service.state)}`;
    const sub = document.createElement('small'); sub.textContent = `状态 ${fmt(service.substate)} · 重启计数 ${fmt(service.restarts)}`;
    card.append(title, state, sub); root.append(card);
  });
  const metrics = data.metrics || {};
  const fields = [['系统负载', (metrics.load || []).join(' / ')], ['可用内存', `${fmt(metrics.memoryAvailableMiB)} / ${fmt(metrics.memoryTotalMiB)} MiB`], ['磁盘剩余', `${fmt(metrics.diskFreeGiB)} / ${fmt(metrics.diskTotalGiB)} GiB`], ['24 小时模型回退', metrics.modelFallbacks24h], ['24 小时恢复主模型', metrics.primaryRestores24h]];
  const box = $('metrics'); box.replaceChildren();
  fields.forEach(([name, value]) => { const item = document.createElement('div'); item.className = 'metric'; const n = document.createElement('span'); n.textContent = name; const v = document.createElement('strong'); v.textContent = fmt(value); item.append(n, v); box.append(item); });
  const model = data.model || {};
  $('overview-primary').textContent = model.primary === 'qq-chat' ? '自动路由，正在读取实际模型' : fmt(model.primary);
  $('overview-fallback').textContent = (model.fallback || []).join(' → ') || '未配置';
  $('last-check').textContent = `更新于 ${new Date(data.checkedAt).toLocaleString()}`;
}
function renderSettings(data) {
  const migrated = statusData?.runtime === 'astrbot';
  for (const selector of ['#model-select', '#check-hermes', '#apply-hermes', '#show-update-plan', '[data-feature]', '#proactive-enabled', '#proactive-idle-days', '#proactive-repeat-days']) {
    document.querySelectorAll(selector).forEach(el => { el.disabled = migrated; if (migrated) el.title = 'AstrBot 模式：由新配置和受控发布管理'; });
  }
  settings = data;
  $('persona-text').value = data.persona || '';
  $('persona-count').textContent = `${(data.persona || '').length} 字符`;
  featureInputs.forEach(input => { input.checked = Boolean(data.features?.[input.dataset.feature]); });
  const model = data.model || {};
  $('model-primary').textContent = model.primary === 'qq-chat' ? '自动路由，正在读取实际模型' : fmt(model.primary);
  $('model-fallback').textContent = (model.fallback || []).join(' → ') || '未配置';
  const select = $('model-select'); select.replaceChildren();
  (model.available || []).forEach(name => { const option = document.createElement('option'); option.value = name; option.textContent = name; select.append(option); });
  select.value = model.primary;
  $('model-warning').classList.toggle('hidden', !(model.fallback || []).includes(select.value));
  const proactive = data.proactive || { enabled: false, idleDays: 3, repeatDays: 7 };
  $('proactive-enabled').checked = Boolean(proactive.enabled);
  $('proactive-idle-days').value = proactive.idleDays;
  $('proactive-repeat-days').value = proactive.repeatDays;
}
async function refreshAll() {
  const [s, config] = await Promise.all([api('/api/status'), api('/api/settings')]);
  statusData = s; renderServices(s); renderSettings(config);
  try { renderEvolution(await api('/api/evolution')); } catch { renderEvolution(null); }
}
async function loadBackups() {
  try {
    const data = await api('/api/backups'); const root = $('backup-list'); root.replaceChildren();
    (data.items || []).forEach(item => {
      const card = document.createElement('article'); card.className = 'backup-item';
      const info = document.createElement('div'); const title = document.createElement('strong'); title.textContent = item.created || item.id;
      const small = document.createElement('small'); small.textContent = (item.files || []).join(' · '); info.append(title, small);
      card.append(info);
      if (role === 'admin') {
        const button = document.createElement('button'); button.className = 'button secondary'; button.textContent = '恢复'; button.addEventListener('click', async () => {
          if (!confirm(`恢复备份 ${item.id} 中的 ${item.files.join('、')}？当前配置会先另存备份，相关服务将重载。`)) return;
          try { await post('/api/backups/restore', { backupId: item.id, files: item.files }); toast('备份已恢复'); await refreshAll(); }
          catch (e) { toast(e.message, true); }
        }); card.append(button);
      }
      root.append(card);
    });
    if (!root.childElementCount) root.textContent = '目前没有可用备份。';
  } catch (e) { toast(e.message, true); }
}
function renderUpdates(data) {
  updateData = data;
  $('hermes-version').textContent = `当前版本：${fmt(data.hermesVersion)} · 更新状态：${fmt(data.hermesUpdate || '尚未检查')}`;
  const root = $('package-list'); root.replaceChildren();
  (data.apt || []).forEach(item => {
    const row = document.createElement('div'); row.className = 'package-row';
    const info = document.createElement('div'); const title = document.createElement('strong'); title.textContent = item.name;
    const small = document.createElement('small'); small.textContent = `${item.installed} → ${item.candidate} (${item.architecture})`; info.append(title, small);
    const button = document.createElement('button'); button.className = 'button secondary'; button.textContent = '安装此版本';
    button.addEventListener('click', async () => {
      button.disabled = true; button.textContent = '模拟中…';
      let plan;
      try { plan = await post('/api/updates/simulate', { package: item.name, candidate: item.candidate }); }
      catch (e) { show('update-result', e.message, true); button.disabled = false; button.textContent = '安装此版本'; return; }
      const summary = `安装 ${plan.package} ${plan.candidate}\n预计变更软件包：${plan.changedPackages}\n预计移除软件包：${plan.removedPackages}\n系统操作可能重启相关服务。`;
      if (!confirm(`${summary}\n\n现在取消可不做更改。`)) { button.disabled = false; button.textContent = '安装此版本'; return; }
      if (!confirm('再次确认：已创建可用的 ECS 快照，并同意按上述计划安装？')) { button.disabled = false; button.textContent = '安装此版本'; return; }
      try { const job = await post('/api/updates/apply', { kind: 'apt', package: item.name, candidate: item.candidate, confirm: true, snapshotConfirmed: true }); toast('系统更新已开始'); pollJob(job.id, 'update-result'); }
      catch (e) { show('update-result', e.message, true); }
      finally { button.disabled = false; button.textContent = '安装此版本'; }
    }); row.append(info, button); root.append(row);
  });
  if (!root.childElementCount) root.textContent = '没有检测到可升级软件包。';
}
async function loadUpdates() {
  try { renderUpdates(await api('/api/updates')); }
  catch (e) { $('hermes-version').textContent = e.message; }
}
async function pollJob(id, target) {
  for (let i = 0; i < 120; i++) {
    await new Promise(resolve => setTimeout(resolve, 1500));
    try {
      const job = await api(`/api/jobs/${id}`);
      if (job.state === 'completed') {
        const result = job.result || {};
        show(target, `已完成${result.hermesVersion ? ` · Hermes ${result.hermesVersion}` : ''}${result.hermesUpdate ? ` · ${result.hermesUpdate}` : ''}${result.apt ? ` · 软件包 ${result.apt.length} 项` : ''}${result.summaryLines !== undefined ? ` · 更新计划已生成（${result.summaryLines} 行）` : ''}${result.backupId ? ` · 备份 ${result.backupId}` : ''}`);
        if (target === 'update-result') await loadUpdates();
        return;
      }
      if (job.state === 'failed') { show(target, job.error || '操作失败', true); return; }
      show(target, job.state === 'queued' ? '等待执行…' : '正在执行…');
    } catch (e) { show(target, e.message, true); return; }
  }
  show(target, '仍在执行；稍后可刷新查看状态。', true);
}
function toast(message, error = false) { const el = $('toast'); el.textContent = message; el.classList.remove('hidden', 'error', 'success'); el.classList.add(error ? 'error' : 'success'); setTimeout(() => el.classList.add('hidden'), 4500); }

$('login-form').addEventListener('submit', async event => {
  event.preventDefault(); show('login-error', '');
  try { const data = await post('/api/login', { password: $('login-password').value }); csrf = data.csrf; role = data.role || 'readonly'; $('login-password').value = ''; loggedIn(true); selectView('overview'); await refreshAll(); }
  catch (e) { show('login-error', e.message, true); }
});
setInterval(async () => { if (!$('app').classList.contains('hidden')) { try { renderEvolution(await api('/api/evolution')); } catch { renderEvolution(null); } } }, 30000);
$('refresh-all').addEventListener('click', async () => { try { await refreshAll(); toast('状态已刷新'); } catch (e) { toast(e.message, true); } });
document.querySelectorAll('.tab').forEach(tab => tab.addEventListener('click', () => selectView(tab.dataset.view)));
$('profile-form').addEventListener('submit', async event => {
  event.preventDefault();
  const qq = $('profile-qq').value.trim();
  try { renderProfile(await api(`/api/profile?qq=${encodeURIComponent(qq)}`)); show('profile-result', '档案已读取，仅供查看。'); }
  catch (e) { $('profile-card').classList.add('hidden'); show('profile-result', e.message, true); }
});
$('persona-text').addEventListener('input', () => { $('persona-count').textContent = `${$('persona-text').value.length} 字符`; });
$('save-persona').addEventListener('click', async () => {
  const value = $('persona-text').value;
  if (!value.trim() || value.length > 200000) return show('persona-result', '内容不能为空，且最多 200 KB。', true);
  if (!confirm('保存当前人格并重载 QQ 桥接？系统会先备份现有内容。')) return;
  try { const result = await post('/api/persona', { persona: value }); show('persona-result', `已保存并重载聊天服务 · 备份 ${result.backupId}`); }
  catch (e) { show('persona-result', e.message, true); }
});
$('save-features').addEventListener('click', async () => {
  const values = Object.fromEntries(featureInputs.map(input => [input.dataset.feature, input.checked]));
  if (!confirm('应用这些能力开关并重载 QQ 桥接？')) return;
  try { const result = await post('/api/features', { features: values }); show('features-result', `已应用 · 备份 ${result.backupId}`); }
  catch (e) { show('features-result', e.message, true); }
});
$('model-select').addEventListener('change', () => $('model-warning').classList.toggle('hidden', !(settings?.model?.fallback || []).includes($('model-select').value)));
$('save-model').addEventListener('click', async () => {
  const name = $('model-select').value;
  if (!confirm(`将 ${name} 设为主模型并重载 Hermes API？`)) return;
  try { const result = await post('/api/model', { model: name }); show('model-result', `已切换至 ${result.model} · 备份 ${result.backupId}`); await refreshAll(); }
  catch (e) { show('model-result', e.message, true); }
});
document.querySelectorAll('.restart').forEach(button => button.addEventListener('click', async () => {
  if (!confirm(`重载 ${statusData?.runtime === 'astrbot' ? 'AstrBot 江生' : (button.dataset.service === 'hermes-api' ? 'Hermes API' : 'QQ 桥接')}？`)) return;
  try { await post('/api/services/restart', { service: button.dataset.service }); show('service-result', '服务已恢复运行。'); await refreshAll(); }
  catch (e) { show('service-result', e.message, true); }
}));
$('refresh-backups').addEventListener('click', loadBackups);
$('check-hermes').addEventListener('click', async () => { try { const job = await post('/api/updates/check', {}); show('update-result', '正在检查 AstrBot 与 Ubuntu 更新…'); pollJob(job.id, 'update-result'); } catch (e) { show('update-result', e.message, true); } });
$('refresh-packages').addEventListener('click', async () => { try { const data = await api('/api/updates'); renderUpdates(data); toast('更新列表已刷新'); } catch (e) { show('update-result', e.message, true); } });
$('show-update-plan').addEventListener('click', async () => { try { const job = await post('/api/updates/plan', {}); show('update-result', '正在生成只读更新计划…'); pollJob(job.id, 'update-result'); } catch (e) { show('update-result', e.message, true); } });
$('apply-hermes').addEventListener('click', async () => {
  if (!confirm('执行 Hermes 自带备份并更新 Hermes Agent？更新完成后会重载 Hermes API。')) return;
  if (!confirm('再次确认更新 Hermes Agent？')) return;
  try { const job = await post('/api/updates/apply', { kind: 'hermes', confirm: true }); show('update-result', 'Hermes 更新已开始…'); pollJob(job.id, 'update-result'); }
  catch (e) { show('update-result', e.message, true); }
});
$('save-proactive').addEventListener('click', async () => {
  const proactive = {
    enabled: $('proactive-enabled').checked,
    idleDays: Number($('proactive-idle-days').value),
    repeatDays: Number($('proactive-repeat-days').value),
  };
  if (!Number.isInteger(proactive.idleDays) || proactive.idleDays < 1 || proactive.idleDays > 14 ||
      !Number.isInteger(proactive.repeatDays) || proactive.repeatDays < 1 || proactive.repeatDays > 30) {
    return show('proactive-result', '沉寂天数需为 1–14，重复间隔需为 1–30。', true);
  }
  if (!confirm(`应用主动互动设置？每天随机一次（含凌晨）；${proactive.idleDays} 天未互动后提醒，之后每 ${proactive.repeatDays} 天最多提醒一次。群聊同样适用。`)) return;
  try {
    const result = await post('/api/proactive', { proactive });
    show('proactive-result', `设置已保存并重载聊天服务 · 备份 ${result.backupId}`);
  } catch (e) { show('proactive-result', e.message, true); }
});
$('password-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (!confirm('修改管理员口令并结束当前会话？')) return;
  const currentPassword = $('current-password').value, newPassword = $('new-password').value;
  try { await post('/api/password', { currentPassword, newPassword }); csrf = ''; loggedIn(false); show('login-error', '口令已更新，请使用新口令登录。'); $('password-form').reset(); }
  catch (e) { show('password-result', e.message, true); }
});

(async () => {
  try { const data = await api('/api/session'); csrf = data.csrf; role = data.role || 'readonly'; loggedIn(true); await refreshAll(); }
  catch { loggedIn(false); }
})();
