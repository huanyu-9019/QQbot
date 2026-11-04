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


export function currentFactsContext(now = new Date()) {
  const p = formatParts(now);
  return [
    `本轮可信时钟：北京时间 ${p.year}年${p.month}月${p.day}日 ${p.hour.padStart(2, '0')}:${p.minute}（Asia/Shanghai）。今天、今年、去年均以此为准；不要用模型知识中的日期或历史对话里的日期代替。`,
    '时效事实规则：回答当前版本、价格、新闻、政策、赛事、人物现职、产品是否发布或上市、近期事件及用户要求查证的问题时，必须先用 web_search 核实再给结论，调用格式为 {"query":"与当前问题相关的非空公开搜索词","limit":3}，query 不能为空，也不要误用 search 或 search_queries 字段；不能凭训练记忆断言。追问“去年吗”“现在呢”“出了吗”也要沿用前文主题进行核实，不能丢失话题。',
    '历史聊天、长期记忆以及自己以前说过的话都不是实时事实依据；发现自己前面说错就简短纠正，不能为了保持一致而重复错误。',
    '核对搜索摘要和网页的发布日期、事件发生日期及适用地区；搜索排名靠前不等于最新。优先相关官方公告，区分发布、开售、传闻和计划。查到的只有旧数据就明确说是哪年的，不包装成当前数据；搜索失败或结果不足就说暂时没核实，不能说“查过了”或编造。',
    '自然聊天与基础知识无需联网；核实事实不改变简短自然的回复风格。',
  ].join('\n');
}


export function requiresFreshFacts(text) {
  const t = String(text ?? '').trim();
  if (/发布|上市|开售|版本|价格|多少钱|新闻|热点|天气|汇率|股价|政策|首相|总统|现任|任职|赛果|比分|查一下|查查|查证|核实|搜一下|搜索|联网/.test(t)) return true;
  if (/^(?:去年|今年|现在|目前|最新|最近|今天)(?:吗|呢)[？?。!！ ]*$/.test(t)) return true;
  return /(?:现在|目前|最新|最近|今年|今天).*(?:谁|什么|哪|多少|怎样|怎么样|如何|出了|出没|有没)|(?:出了|出没)(?:吗|有|了)/.test(t);
}

export function hasFreshSearchEvidence(result) {
  const output = result?.output ?? [];
  const calls = new Set(output.filter(x => x.type === 'function_call' && x.name === 'web_search').map(x => x.call_id));
  return output.some(x => {
    if (x.type !== 'function_call_output' || !calls.has(x.call_id)) return false;
    try {
      const raw = typeof x.output === 'string' ? x.output : JSON.stringify(x.output);
      const json = raw.match(/\{[\s\S]*\}/)?.[0];
      const data = JSON.parse(json ?? 'null');
      return data?.success === true && !data.error && Array.isArray(data.data?.web) && data.data.web.some(row => /^https?:\/\//.test(row.url ?? '') && (row.title || row.description));
    } catch { return false; }
  });
}
