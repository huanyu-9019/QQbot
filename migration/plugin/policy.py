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
_MENTION_IDENTITY = r'(?:(?:他|她|这个人|这位)?是谁|(?:他|她)?叫(?:什么(?:名字)?|啥)|你(?:还)?(?:认识|记得)(?:他|她)(?:吗|不))'


def message_segments(event):
    """Read transport components; never infer an account from a typed @ string."""
    obj = getattr(event, 'message_obj', None)
    raw = getattr(obj, 'raw_message', None)
    parts = raw.get('message') if isinstance(raw, dict) else None
    typed = getattr(obj, 'message', None) or []
    result = []
    if isinstance(parts, list):
        result = [dict(type=p.get('type'), data=dict(p.get('data', {}))) for p in parts[:128]
                  if isinstance(p, dict) and isinstance(p.get('data', {}), dict)]
    else:
        for part in typed[:128]:
            kind = getattr(part, 'type', type(part).__name__)
            kind = getattr(kind, 'value', kind)
            if kind == 'At':
                result.append({'type':'at','data':{'qq':str(getattr(part,'qq','')),'name':str(getattr(part,'name','') or '')}})
            elif kind == 'Plain':
                result.append({'type':'text','data':{'text':str(getattr(part,'text',''))}})
    names = {str(getattr(p,'qq','')):str(getattr(p,'name','') or '') for p in typed if getattr(p,'qq',None) is not None}
    for part in result:
        if part['type'] == 'at':
            part['data']['qq'] = str(part['data'].get('qq',''))
            if names.get(part['data']['qq']):
                part['data']['name'] = names[part['data']['qq']][:80]
    return result


def mention_identity_question(segments, self_id):
    targets = {str(p.get('data',{}).get('qq','')) for p in segments if p.get('type')=='at'} - {str(self_id), 'all', ''}
    if not targets:
        return False
    text = ''.join(str(p.get('data',{}).get('text','')) for p in segments if p.get('type')=='text').strip()
    text = re.sub(r'^江生[\s，,：:]*', '', text)
    return bool(re.fullmatch(_MENTION_IDENTITY+r'[\s?？。!！]*', text))


def mentioned_identity_answer(segments, self_id, people):
    if not mention_identity_question(segments, self_id):
        return None
    targets = list(dict.fromkeys(str(p.get('data',{}).get('qq','')) for p in segments
                                if p.get('type')=='at' and str(p.get('data',{}).get('qq','')) not in (str(self_id),'all','')))
    if len(targets) != 1:
        return None
    person = next((p for p in people if p.get('account') == targets[0]), {})
    display = redact(person.get('displayName') or person.get('preferredName')).strip()[:80]
    preferred = redact(person.get('preferredName')).strip()[:80]
    if not display:
        return None
    if preferred and preferred != display:
        return '你@的是'+display+'，我这里记的称呼是'+preferred+'。'
    return '你@的是'+display+'。更具体的身份，我还没有可靠记录。'


def may_reply(segments, self_id, *, group):
    """Only veto foreign addressing; companion still decides whether to speak."""
    if not group:
        return True
    mentions = {str(p.get('data', {}).get('qq', '')) for p in segments
                if isinstance(p, dict) and p.get('type') == 'at'}
    if not (mentions - {str(self_id)}) or str(self_id) in mentions:
        return True
    if mention_identity_question(segments, self_id):
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


def person_portrait(profile, relationship=None):
    """A conservative shared read model, never a new source of invented facts.

    Legacy extraction has no per-item evidence. Keep its usable clues, but do
    not promote them to confirmed relationships or treat heuristic scores as
    memories. Originals remain untouched for audit and later corrections.
    """
    profile = profile if isinstance(profile, dict) else {}
    rejected = []
    def clean(values, *, split=False):
        seen, result = set(), []
        for value in values if isinstance(values, list) else []:
            if not isinstance(value, str) or _UNEQUAL.search(value):
                continue
            for text in re.split('[、；;\n]', value) if split else [value]:
                text = redact(text).strip().strip('。，,；; ').strip()[:180]
                key = re.sub(r'\s+', '', text).casefold()
                if not key or key in seen:
                    continue
                seen.add(key)
                if re.fullmatch(r'(?:我|你|他|她|这|那)(?:吗|呢|啊|呀|么)?[?？]?|[?？…]+', text):
                    rejected.append(text)
                    continue
                result.append(text)
        return result[:24]
    preferred = clean([profile.get('preferredName')])
    group_names = profile.get('groupNicknames', {})
    aliases = clean([profile.get('privateNickname')] + (list(group_names.values()) if isinstance(group_names, dict) else []))
    aliases = [x for x in aliases if x not in preferred]
    labels = clean(profile.get('relationships', []))
    habits, boundaries, routine = [], [], []
    for item in clean(profile.get('chatHabits', []), split=True):
        if re.search('不喜欢|不希望|不要|别再|不接受|讨厌', item):
            boundaries.append(item)
        elif re.search('上班|下班|上课|作息|起床|睡觉时间', item):
            routine.append(item)
        else:
            habits.append(item)
    return {'name': preferred[0] if preferred else '', 'aliases': aliases,
            'relationship': {'labels': labels, 'basis': 'legacy_unverified',
                'description': ('迁入资料记有“' + '、'.join(labels) + '”的关系。') if labels else '暂没有可核实的明确关系记录。',
                'note': '旧资料缺少逐条原话依据，不能当作新确认；也不能用旧分数推翻已有来往。当前明确更正及有来源的新记忆优先。'},
            'habits': habits, 'boundaries': boundaries, 'routine': routine,
            'preferences': clean(profile.get('preferences', []), split=True),
            'basis': 'legacy_unverified', 'review': {'rejected': rejected},
            'legacyDiagnostics': relationship if isinstance(relationship, dict) else {}}


def profile_context(profile, *, group_id=None):
    """Use the same conservative profile as the admin portrait."""
    result = []
    def add(label, value):
        if isinstance(value, str) and value.strip() and not _UNEQUAL.search(value):
            result.append(label + ': ' + redact(value.strip())[:160])
    portrait = person_portrait(profile)
    add('迁入称呼', portrait['name'])
    if group_id:
        nicknames = profile.get('groupNicknames', {})
        if isinstance(nicknames, dict):
            add('本群昵称', nicknames.get(str(group_id)))
    else:
        add('私聊昵称', profile.get('privateNickname'))
        for field, label in [('habits', '迁入交流习惯'), ('boundaries', '迁入边界'), ('routine', '迁入作息'), ('preferences', '迁入偏好线索')]:
            for value in portrait[field][:8]:
                add(label, value)
        if portrait['relationship']['labels']:
            add('迁入关系记录（非新确认）', '、'.join(portrait['relationship']['labels']))
        add('资料依据', '迁入提取可能有误；不能用消息数推断亲密关系，当前更正和有来源的新记忆优先')
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
            'relationships': relationships, 'relationships_basis': 'legacy_unverified'}


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
