"""Small migration policies, independent of AstrBot imports for replay testing."""

import re
import sqlite3
import time
from contextlib import closing
from pathlib import Path

_ANALYSIS = re.compile(r'\b(?:initial assessment|now assessing|debugging artifacts|chain[ -]of[ -]thought|the interaction (?:involves|indicates)|the user (?:expresses|is asking|wants|appears|seems)|the response should)\b|<(?:think|analysis)>', re.I)
_RESPONSE_REASONING = re.compile(r'\b(?:the repeated use of .{1,100}? appears to be|further investigation is needed to ascertain|considering both options are unclear|the guidelines suggest active participation)\b', re.I | re.S)
_UNEQUAL = re.compile(r'主人|奴隶|奴仆|所有者|支配者|服从|归.*所有|master|slave|owner', re.I)


def may_reply(segments, self_id, *, group):
    """Only veto foreign addressing; companion still decides whether to speak."""
    if not group:
        return True
    mentions = {str(p.get('data', {}).get('qq', '')) for p in segments
                if isinstance(p, dict) and p.get('type') == 'at'}
    return not (mentions - {str(self_id)}) or str(self_id) in mentions


def claim_message(database, platform, message_id, *, now=None):
    """A persistent idempotency claim; caller must not use it for non-message events."""
    if not message_id:
        return True
    now = time.time() if now is None else now
    Path(database).parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database, timeout=10)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS seen (platform TEXT, message_id TEXT, at REAL, PRIMARY KEY(platform,message_id))')
        db.execute('DELETE FROM seen WHERE at < ?', (now - 7 * 86400,))
        result = db.execute('INSERT OR IGNORE INTO seen VALUES (?,?,?)', (str(platform), str(message_id), now))
        return result.rowcount == 1


def redact(value):
    text = re.sub(r'\bsk-[A-Za-z0-9_-]{12,}', '[REDACTED_SECRET]', str(value or ''))
    text = re.sub(r'(?i)\b(?:authorization)\s*[:=]\s*(?:bearer\s+)?[^\s,;]+', '[REDACTED_SECRET]', text)
    text = re.sub(r'(?i)\b(?:api[_-]?key|token|secret|password)\s*[:=]\s*[^\s,;]+', '[REDACTED_SECRET]', text)
    text = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[REDACTED_PHONE]', text)
    return text


def profile_context(profile, *, group_id=None):
    """Import only factual profile fields, with private material kept private."""
    result = []
    def add(label, value):
        if isinstance(value, str) and value.strip() and not _UNEQUAL.search(value):
            result.append(label + ': ' + redact(value.strip())[:160])
    add('明确自称', profile.get('preferredName'))
    if group_id:
        nicknames = profile.get('groupNicknames', {})
        if isinstance(nicknames, dict):
            add('本群昵称', nicknames.get(str(group_id)))
    else:
        add('私聊昵称', profile.get('privateNickname'))
        for field, label in [('relationships', '明确关系'), ('chatHabits', '交流偏好'), ('preferences', '兴趣')]:
            values = profile.get(field, [])
            for value in values[:8] if isinstance(values, list) else []:
                add(label, value)
    return '\n'.join(result)[:1800]


def legacy_summary(record):
    summary = record.get('summary', '') if isinstance(record, dict) else ''
    if not isinstance(summary, str):
        return ''
    return '\n'.join(redact(line) for line in summary.splitlines() if not _UNEQUAL.search(line))[:1200]


def quality_issue(text, incoming=''):
    text = str(text or '')
    if '<QQ_SILENT>' in text and text.strip() != '<QQ_SILENT>':
        return 'mixed_silence_marker'
    if _ANALYSIS.search(text) or _RESPONSE_REASONING.search(text):
        return 'analysis_leak'
    letters = len(re.findall(r'[a-z]', text, re.I))
    allowed = re.search(r'英文|英语|English|翻译|translate|代码|code|```', incoming, re.I)
    allowed = allowed or len(re.findall(r'[a-z]', incoming, re.I)) >= 60
    if not allowed and letters >= 100 and letters / max(1, len(text)) >= .55:
        return 'unexpected_english'
    return None


def confirmed_send(result):
    if not isinstance(result, dict) or result.get('retcode', 0) != 0 or result.get('status', 'ok') not in ('ok', 'async'):
        return False
    data = result.get('data', result)
    return isinstance(data, dict) and data.get('message_id') is not None
