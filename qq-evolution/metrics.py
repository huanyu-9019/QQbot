from collections import defaultdict


def aggregate(events, minimum_pairs=3):
    pending = {}
    pairs = []
    silences = 0
    replies = []
    for event in events:
        turn_id = event.get("turnId")
        if not turn_id:
            continue
        if event.get("direction") == "incoming":
            pending[turn_id] = event
        elif event.get("direction") == "delivered" and turn_id in pending:
            incoming = pending.pop(turn_id)
            latency = max(0, int(event["timestamp"]) - int(incoming["timestamp"]))
            pairs.append(latency)
            replies.append(event.get("text", ""))
    silences = len(pending)
    repeated = sum(1 for index in range(1, len(replies)) if replies[index] and replies[index] == replies[index - 1])
    total_turns = len(pairs) + silences
    return {
        "eligible": len(pairs) >= minimum_pairs,
        "pairs": len(pairs),
        "silences": silences,
        "repeatedReplies": repeated,
        "meanLatencyMs": sum(pairs) / len(pairs) if pairs else None,
        "successRate": len(pairs) / total_turns if total_turns else 0.0,
    }
