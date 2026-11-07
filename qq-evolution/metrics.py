from collections import defaultdict
import re

_VOICE_PLACEHOLDER = re.compile(r"^\s*\[语音\s*\d+\s*s?\]\s*$", re.IGNORECASE)



_ANALYSIS_LEAK = re.compile(r"\b(?:initial assessment|now assessing|debugging artifacts|chain[ -]of[ -]thought|the interaction (?:involves|indicates)|the user (?:expresses|is asking|wants|appears|seems)|the response should|the [\"'][^\"']+[\"'] messages? (?:exhibit|show|contain))\b|<(?:think|analysis)>", re.I)

def reply_quality_issue(text, incoming=''):
    value = str(text or '').strip()
    if not value or value == '<QQ_SILENT>': return None
    if _ANALYSIS_LEAK.search(value): return 'analysis_leak'
    source = str(incoming or '')
    requested = re.search(r'英文|英语|English|翻译|translate|代码|code|```', source, re.I) or len(re.findall(r'[a-z]', source, re.I)) >= 60
    letters = len(re.findall(r'[a-z]', value, re.I))
    if not requested and letters >= 100 and letters / len(value) >= 0.55: return 'unexpected_english'
    return None


def aggregate(events, minimum_pairs=3):
    private_openings = defaultdict(dict)
    for row in events:
        if (row.get('direction') == 'delivered' and row.get('kind') == 'private'
                and row.get('sessionHash') and row.get('turnId')):
            private_openings[row['sessionHash']].setdefault(row['turnId'], str(row.get('text', '')).strip())
    habitual_acknowledgements = sum(
        len(turns) >= 5 and sum(bool(re.match(r'^嗯+(?:[，,。.!！?？、\s]|$)', text))
                               for text in list(turns.values())[-20:]) / min(20, len(turns)) >= .6
        for turns in private_openings.values())
    pending = {}
    pairs = []
    silences = 0
    unobservable = 0
    replies = []
    foreign_mention_replies = 0
    html_leaks = 0
    unsolicited_voice = 0
    multi_message_turns = 0
    delivered_by_turn = defaultdict(list)
    for event in events:
        turn_id = event.get("turnId")
        if not turn_id:
            continue
        if event.get("direction") == "delivered":
            delivered_by_turn[turn_id].append(event)
        if event.get("direction") == "incoming":
            pending[turn_id] = event
        elif event.get("direction") in {"delivered", "silent", "failed"} and turn_id in pending:
            incoming = pending.pop(turn_id)
            if event.get("direction") == "delivered":
                if _VOICE_PLACEHOLDER.fullmatch(str(incoming.get("text", ""))):
                    unobservable += 1
                    continue
                latency = max(0, int(event["timestamp"]) - int(incoming["timestamp"]))
                pairs.append(latency)
                replies.append(event.get("text", ""))
            elif event.get("direction") == "silent" and _VOICE_PLACEHOLDER.fullmatch(str(incoming.get("text", ""))):
                unobservable += 1
            elif event.get("direction") == "failed":
                pending[turn_id] = incoming
    silences = len(pending)
    repeated = sum(1 for index in range(1, len(replies)) if replies[index] and replies[index] == replies[index - 1])
    for turn_id, delivered in delivered_by_turn.items():
        incoming = next((row for row in events if row.get("turnId") == turn_id and row.get("direction") == "incoming"), {})
        voice_audited = any(row.get('turnId') == turn_id and row.get('direction') == 'voice_source' for row in events)
        paired_voice = (voice_audited and len(delivered) == 2
                        and {row.get('media') for row in delivered} == {'text', 'voice'}
                        and delivered[0].get('text') == delivered[1].get('text'))
        if len(delivered) > 1 and not paired_voice:
            multi_message_turns += 1
        if incoming.get("mentionedOther") is True and not incoming.get('directedToBot') and delivered:
            foreign_mention_replies += 1
        if any(re.search(r"<img\b|<a\b|<script\b", str(row.get("text", "")), re.I) for row in delivered):
            html_leaks += 1
        if not voice_audited and incoming.get("media") not in {"voice", "audio"} and any(row.get("media") == "voice" for row in delivered):
            unsolicited_voice += 1
    incoming_by_turn = {row.get('turnId'): row.get('text', '') for row in events if row.get('direction') == 'incoming'}
    issues = [reply_quality_issue(row.get('text'), incoming_by_turn.get(row.get('turnId'), ''))
              for row in events if row.get('direction') == 'delivered']
    blocked_identity = sum(row.get('direction') == 'quality' and row.get('outcome') == 'sender_identity_mismatch' for row in events)
    blocked = sum(row.get('direction') == 'quality' and row.get('outcome') in {'analysis_leak','unexpected_english'} for row in events) + blocked_identity
    total_turns = len(pairs) + silences
    return {
        "eligible": len(pairs) >= minimum_pairs,
        "analysisLeaks": issues.count('analysis_leak'),
        "unexpectedEnglishReplies": issues.count('unexpected_english'),
        "blockedQualityReplies": blocked,
        "blockedIdentityReplies": blocked_identity,
        "mentionResolutionFailures": sum(row.get('direction')=='quality' and row.get('outcome')=='mention_target_unresolved' for row in events),
        "mediaFailures": sum(row.get('direction') == 'quality' and row.get('outcome') in {'stt_failed', 'tts_failed', 'vision_failed'} for row in events),
        "pairs": len(pairs),
        "silences": silences,
        "unobservableTurns": unobservable,
        "repeatedReplies": repeated,
        "habitualAcknowledgementSessions": habitual_acknowledgements,
        "meanLatencyMs": sum(pairs) / len(pairs) if pairs else None,
        "successRate": len(pairs) / total_turns if total_turns else 0.0,
        "foreignMentionReplies": foreign_mention_replies,
        "htmlLeaks": html_leaks,
        "unsolicitedVoice": unsolicited_voice,
        "multiMessageTurns": multi_message_turns,
    }


def overdue_turns(events, *, now_ms, grace_ms=180000):
    pending = {}
    for event in sorted(events, key=lambda row: int(row.get("timestamp", 0))):
        if int(event.get("version", 1)) < 2:
            continue
        turn_id = event.get("turnId")
        if not turn_id:
            continue
        if event.get("direction") == "incoming":
            pending[turn_id] = int(event["timestamp"])
        elif event.get("direction") in {"delivered", "silent"}:
            pending.pop(turn_id, None)
        elif event.get("direction") == "failed":
            pending[turn_id] = min(pending.get(turn_id, int(event["timestamp"])), int(event["timestamp"]) - grace_ms)
    return sum(1 for timestamp in pending.values() if int(now_ms) - timestamp >= grace_ms)
