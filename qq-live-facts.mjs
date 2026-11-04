const TIME_RE = /^(?:江生[，,、 ]*)?(?:请问|帮我)?(?:查一下|查查|看一下|告诉我)?(?:现在|北京时间)?(?:几点|时间)(?:了)?[？?。!！ ]*$/i;
const DATE_RE = /^(?:江生[，,、 ]*)?(?:请问|帮我)?(?:查一下|查查|看一下|告诉我)?(?:今天|当前日期|日期)(?:是)?(?:几号|几月几号|哪天)?[？?。!！ ]*$/i;

function formatParts(date) {
  const parts = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: 'numeric', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: false }).formatToParts(date);
  return Object.fromEntries(parts.filter(x => x.type !== 'literal').map(x => [x.type, x.value]));
}

export function liveFactReply(text, now = new Date()) {
  const value = String(text ?? '').trim();
  const p = formatParts(now);
  if (TIME_RE.test(value)) return `现在是北京时间 ${p.year}年${p.month}月${p.day}日 ${p.hour.padStart(2, '0')}:${p.minute}。`;
  if (DATE_RE.test(value)) return `今天是${p.year}年${p.month}月${p.day}日。`;
  return null;
}
