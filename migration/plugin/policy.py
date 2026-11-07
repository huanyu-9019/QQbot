"""Small migration policies, independent of AstrBot imports for replay testing."""

import re
import json
import hashlib
import sqlite3
import time
from contextlib import closing
from pathlib import Path

_ANALYSIS = re.compile(r'\b(?:initial assessment|now assessing|debugging artifacts|chain[ -]of[ -]thought|the interaction (?:involves|indicates)|the user (?:expresses|is asking|wants|appears|seems)|the response should)\b|<(?:think|analysis)>', re.I)
_RESPONSE_REASONING = re.compile(r'\b(?:the repeated use of .{1,100}? appears to be|further investigation is needed to ascertain|considering both options are unclear|the guidelines suggest active participation)\b', re.I | re.S)
_REASONING_BOUNDARY = re.compile(r'</?(?:think|analysis|reasoning)(?:\s[^>]*)?>|<\|(?:analysis|start_header_id|end_header_id)\|>|(?m:^\s*(?:思考过程|内部分析|回复策略|analysis|reasoning)\s*[:：])', re.I)
_UNEQUAL = re.compile(r'主人|奴隶|奴仆|所有者|支配者|服从|归.*所有|master|slave|owner', re.I)


def may_reply(segments, self_id, *, group):
    """Only veto foreign addressing; companion still decides whether to speak."""
    if not group:
        return True
    mentions = {str(p.get('data', {}).get('qq', '')) for p in segments
                if isinstance(p, dict) and p.get('type') == 'at'}
    if not (mentions - {str(self_id)}) or str(self_id) in mentions:
        return True
    prefix = ''
    for part in segments:
        if not isinstance(part, dict):
            continue
        if part.get('type') == 'at':
            break
        if part.get('type') == 'text':
            prefix += str(part.get('data', {}).get('text', ''))
    return bool(re.match(r'^\s*江生(?:[，,：:！!？?\s]|$)', prefix))


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
    if _ANALYSIS.search(text) or _RESPONSE_REASONING.search(text) or _REASONING_BOUNDARY.search(text):
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


def identity_answer(text, profile, display_name):
    """Answer exact self-identification from this sender's record only."""
    question = re.sub(r'^\s*(?:@?江生[，,：:！!？?\s]*)?', '', str(text or ''))
    question = question.strip(' \t\r\n?？。！!')
    if question not in ('我是谁', '我叫什么', '我叫什么名字', '你记得我叫什么吗'):
        return None
    name = profile.get('preferredName')
    if isinstance(name, str) and name.strip() and len(name.strip()) <= 40 and not _UNEQUAL.search(name):
        return '你是' + redact(name.strip()) + '。'
    name = redact(str(display_name or '未设置').strip())[:40]
    return '你现在的群名片是' + name + '；还没确认你想让我怎么称呼你。'


def sender_binding(root, account, display_name):
    """Bind names to authenticated profile filenames, never to shared chat text."""
    key = hashlib.sha256(('user:' + str(account)).encode()).hexdigest()
    folder = Path(root) / 'legacy/qq-user-memory'
    own, others, relationships = set(), set(), []
    preferred = ''
    for path in folder.glob('*.json'):
        try:
            profile = json.loads(path.read_text(encoding='utf-8')).get('profile', {})
            names = [profile.get('preferredName'), profile.get('privateNickname')]
            group_names = profile.get('groupNicknames', {})
            if isinstance(group_names, dict):
                names.extend(group_names.values())
            names = {v.strip() for v in names if isinstance(v, str) and 2 <= len(v.strip()) <= 40 and not _UNEQUAL.search(v)}
            if path.stem == key:
                own.update(names)
                value = profile.get('preferredName')
                preferred = value.strip() if isinstance(value, str) and value.strip() in names else ''
                values = profile.get('relationships', [])
                relationships = [redact(v)[:160] for v in values[:8] if isinstance(v, str) and not _UNEQUAL.search(v)] if isinstance(values, list) else []
            else:
                others.update(names)
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    display = redact(display_name).strip()[:40]
    if display:
        own.add(display)
    return {'account': str(account), 'name': preferred or display,
            'aliases': sorted(own), 'foreign_aliases': sorted(others - own),
            'relationships': relationships}


def sender_identity_conflict(text, binding):
    """Detect direct misidentification, allowing ordinary third-person mentions."""
    own = set(binding.get('aliases', []))
    for name in binding.get('foreign_aliases', []):
        if name in own:
            continue
        alias = re.escape(name)
        ending = r'(?:[啊呀啦呢哦吧～~\s]*[。！!？?，,；;]|[啊呀啦呢哦吧～~\s]*$)'
        if re.search(r'(?:^|[。！!？?\n])\s*你(?:就)?是(?:我的|我家|咱家)?\s*' + alias + ending, str(text)):
            return True
        if re.match(r'^\s*' + alias + r'[，,：:]\s*', str(text)):
            return True
    return False
