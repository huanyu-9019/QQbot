import { appendFileSync, chmodSync, mkdirSync, readFileSync, readdirSync, statSync, unlinkSync, writeFileSync } from 'node:fs';
import { createHmac, randomBytes, randomUUID } from 'node:crypto';
import { dirname, join } from 'node:path';

const DAY_MS = 24 * 60 * 60 * 1000;
const RETENTION_DAYS = 7;
const MAX_TEXT = 1200;

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
      version: 1,
      timestamp,
      turnId: event.turnId || randomUUID(),
      direction: event.direction,
      kind: event.kind === 'group' ? 'group' : 'private',
      sessionHash: createHmac('sha256', sessionSalt).update(String(event.sessionKey)).digest('hex'),
      text: String(event.text || '').slice(0, MAX_TEXT),
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

  function prune(referenceTime = now()) {
    for (const name of readdirSync(directory)) {
      if (!/^\d{4}-\d{2}-\d{2}\.jsonl$/.test(name)) continue;
      const file = join(directory, name);
      if (referenceTime - statSync(file).mtimeMs > RETENTION_DAYS * DAY_MS) unlinkSync(file);
    }
  }

  return { recordIncoming, recordDelivered, prune };
}
