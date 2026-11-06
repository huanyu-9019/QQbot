"""Build a small, credential-free status snapshot for the QQ admin panel."""

PROVIDER_LABELS = {
    "gemini-nekocloud": "新中转站 Grok",
    "gemini-nekocloud-gemini": "新中转站 Gemini",
    "grok": "原中转站 Grok",
    "deepseek-relay": "中转站 DeepSeek",
    "gpt": "GPT 中转站",
    "deepseek": "官方 DeepSeek",
}


def format_route(route):
    return {
        "name": PROVIDER_LABELS.get(route.get("name"), "未知线路"),
        "model": str(route.get("model", ""))[:100],
        "available": route.get("available") is True,
        "visionAvailable": route.get("visionAvailable") is True,
    }


def build_snapshot(*, now, control, production, health, state, latest_change, learning_history=None, changes=None):
    router = production.get("router") if isinstance(production.get("router"), dict) else {}
    routes = [format_route(row) for row in router.get("routes", []) if isinstance(row, dict)]
    chain_ok = any(row["available"] for row in routes)
    vision_ok = any(row["visionAvailable"] for row in routes)
    qq_ok = all(production.get(key) is True for key in ("bridge", "api", "napcat"))
    codex_fresh = (
        control.get("supervisor") is True
        and 0 <= now - int(health.get("lastFetch", 0)) <= 2400
        and 0 <= now - int(health.get("pollStarted", 0)) <= 600
    )
    changed = latest_change.get("changed", []) if isinstance(latest_change, dict) else []
    return {
        "generatedAt": int(now),
        "codex": {
            "online": control.get("online") is True,
            "listening": codex_fresh,
            "lastFetch": health.get("lastFetch"),
            "lastPoll": health.get("pollFinished"),
            "lastIteration": state.get("lastIteration"),
            "iterationStatus": state.get("status"),
            "lastReason": str(state.get("lastReason", ""))[:240],
            "lastRevision": str(state.get("lastRevision", ""))[:80],
            "iterationCount": int(state.get('iterationCount', 0)),
            "learningStatus": health.get('learningStatus', 'unknown'),
            "learningStarted": health.get('learningStarted'),
            "learningFinished": health.get('learningFinished'),
            "learningEvents": health.get('learningEvents'),
            "learningIntervalSeconds": 900,
            "nextIteration": int(state.get('lastIteration', 0)) + 900,
            "pollIntervalSeconds": 300,
            "learningHistory": [
                {'at': row.get('timestamp'), 'iteration': row.get('iteration'),
                 'kind': 'failed' if str(row.get('reason', '')).startswith('Iteration assessment unavailable:') else row.get('updated'),
                 'reason': str(row.get('reason', ''))[:240], 'revision': str(row.get('revision', ''))[:80]}
                for row in (learning_history or [])[-12:][::-1] if isinstance(row, dict)
            ],
            "changes": changes or [],
            "memoryAvailableMiB": control.get("memoryAvailableMiB"),
            "diskFreeGiB": control.get("diskFreeGiB"),
        },
        "qq": {
            "runtime": production.get('runtime', 'hermes'),
            "astrbot": production.get('astrbot') is True,
            "qqConnected": production.get('qqConnected'),
            "companionReady": production.get('companionReady'),
            "lastIncoming": production.get('lastIncoming'),
            "lastDelivered": production.get('lastSent'),
            "unanswered": production.get('unanswered', 0),
            "online": production.get("online") is True,
            "canReply": qq_ok and chain_ok and not production.get('unanswered', 0),
            "canSeeImages": qq_ok and vision_ok,
            "bridge": production.get("bridge") is True,
            "api": production.get("api") is True,
            "napcat": production.get("napcat") is True,
            "activeProvider": PROVIDER_LABELS.get(router.get("active"), router.get("active")),
            "activeModel": router.get("activeModel"),
            "lastReply": router.get("lastSuccess"),
            "lastRouteProbe": router.get("lastProbe"),
            "routes": routes,
            "memoryAvailableMiB": production.get("memoryAvailableMiB"),
            "diskFreeGiB": production.get("diskFreeGiB"),
        },
        "latestChange": {
            "at": latest_change.get("timestamp") if isinstance(latest_change, dict) else None,
            "files": [str(name)[:100] for name in changed[:12]],
            "revision": str(latest_change.get("revision", ""))[:80] if isinstance(latest_change, dict) else "",
            "status": str(latest_change.get("status", ""))[:40] if isinstance(latest_change, dict) else "",
        },
    }
