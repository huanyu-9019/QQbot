import { appendFileSync, chmodSync, mkdirSync, readFileSync, readdirSync, statSync, unlinkSync, writeFileSync } from 'node:fs';
import { createHmac, randomBytes, randomUUID } from 'node:crypto';
import { dirname, join } from 'node:path';

const DAY_MS = 24 * 60 * 60 * 1000;
const RETENTION_DAYS = 7;
const MAX_TEXT = 1200;
const SILENCE_OUTCOMES = new Set([
  'group_cooldown', 'collection_only', 'model_silent', 'sticker_unavailable',
  'media_unavailable', 'private_throttle', 'text_too_long', 'queue_rejected',
  'unaddressed_error', 'reply_failed',
]);


const ANALYSIS_LEAK = /\b(?:initial assessment|now assessing|debugging artifacts|chain[ -]of[ -]thought|the interaction (?:involves|indicates)|the user (?:expresses|is asking|wants|appears|seems)|the response should|the ["'][^"']+["'] messages? (?:exhibit|show|contain))\b|<(?:think|analysis)>/i;
export function replyQualityIssue(text, incoming = '') {
  const value = String(text || '').trim();
  if (!value || value === '<QQ_SILENT>') return null;
  if (value.includes('<QQ_SILENT>') || /\bthe ["'][^"']+["'] messages? (?:are |is )?exhibiting\b/i.test(value)
    || ANALYSIS_LEAK.test(value)) return 'analysis_leak';
  const letters = (value.match(/[a-z]/ig) || []).length;
  const input = String(incoming || '');
  const englishRequested = /英文|英语|English|翻译|translate|代码|code|```/i.test(input)
    || (input.match(/[a-z]/ig) || []).length >= 60;
  if (!englishRequested && letters >= 100 && letters / value.length >= 0.55) return 'unexpected_english';
  return null;
}

export async function guardReplyQuality(generate, { incoming = '', onIssue = () => {}, fallback = '刚才回复出了点问题，你那句再跟我说说？' } = {}) {
  for (let attempt = 0; attempt < 2; attempt++) {
    let answer;
    try { answer = await generate(attempt > 0); }
    catch (error) { if (attempt === 0) throw error; return fallback; }
    const issue = replyQualityIssue(answer, incoming);
    if (!issue) return answer;
    await onIssue(issue);
  }
  return fallback;
}

function dayFile(directory, timestamp) {
  return join(directory, new Date(timestamp).toISOString().slice(0, 10) + '.jsonl');
}

export function createConversationAudit({ directory, sessionSalt, saltFile, now = Date.now } = {}) {
  if (!directory) throw new TypeError('audit directory is required');
  mkdirSync(directory, { recursive: true, mode: 0o700 });
  if (!sessionSalt && !saltFile) throw new TypeError('audit session salt is required');
  if (saltFile) {
    mkdirSync(dirname(saltFile), { recursive: true, mode: 0o700 });
    try {
      sessionSalt = readFileSync(saltFile, 'utf8').trim();
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
      sessionSalt = randomBytes(32).toString('hex');
      writeFileSync(saltFile, `${sessionSalt}\n`, { encoding: 'utf8', mode: 0o600, flag: 'wx' });
    }
    if (!sessionSalt) throw new TypeError('audit session salt is empty');
    chmodSync(saltFile, 0o600);
  }

  function append(event) {
    const timestamp = now();
    const file = dayFile(directory, timestamp);
    const row = JSON.stringify({
      version: 2,
      timestamp,
      turnId: event.turnId || randomUUID(),
      direction: event.direction,
      kind: event.kind === 'group' ? 'group' : 'private',
      sessionHash: createHmac('sha256', sessionSalt).update(String(event.sessionKey)).digest('hex'),
      text: String(event.text || '').slice(0, MAX_TEXT),
      ...(typeof event.mentioned === 'boolean' ? { mentioned: event.mentioned } : {}),
      ...(typeof event.mentionedOther === 'boolean' ? { mentionedOther: event.mentionedOther } : {}),
      ...(['text', 'image', 'sticker', 'voice'].includes(event.media) ? { media: event.media } : {}),
      ...(event.direction === 'silent' || event.direction === 'failed' || event.direction === 'quality' ? { outcome: event.outcome } : {}),
    }) + '\n';
    appendFileSync(file, row, { encoding: 'utf8', mode: 0o600 });
    chmodSync(file, 0o600);
    return JSON.parse(row).turnId;
  }

  function recordIncoming(event) {
    return append({ ...event, direction: 'incoming' });
  }

  function recordDelivered(event) {
    return append({ ...event, direction: 'delivered' });
  }

  function recordSilent(event) {
    if (!SILENCE_OUTCOMES.has(event.outcome)) throw new TypeError('invalid silence outcome');
    return append({ ...event, direction: 'silent', text: '' });
  }

  function recordFailure(event) {
    if (event.outcome !== 'reply_failed') throw new TypeError('invalid failure outcome');
    return append({ ...event, direction: 'failed', text: '' });
  }

  function recordQuality(event) {
    if (!['analysis_leak', 'unexpected_english'].includes(event.outcome)) throw new TypeError('invalid quality outcome');
    return append({ ...event, direction: 'quality', text: '' });
  }

  function prune(referenceTime = now()) {
    for (const name of readdirSync(directory)) {
      if (!/^\d{4}-\d{2}-\d{2}\.jsonl$/.test(name)) continue;
      const file = join(directory, name);
      if (referenceTime - statSync(file).mtimeMs > RETENTION_DAYS * DAY_MS) unlinkSync(file);
    }
  }

  return { recordIncoming, recordDelivered, recordSilent, recordFailure, recordQuality, prune };
}
