import json
import re

ALLOWED_CATEGORIES = {"repetition", "silence", "latency", "error", "unnatural", "privacy"}
ALLOWED_CHANGE_TYPES = {"prompt", "rule", "code"}
ALLOWED_FILES = re.compile(r"^(?:qq-[A-Za-z0-9._-]+\.mjs|qq-persona\.md|qq-[A-Za-z0-9._-]+\.test\.mjs)$")


def parse_finding(raw):
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    if value.get("category") not in ALLOWED_CATEGORIES or value.get("changeType") not in ALLOWED_CHANGE_TYPES:
        return None
    if value.get("severity") not in {"low", "medium", "high"}:
        return None
    if not isinstance(value.get("evidence"), list) or not value["evidence"]:
        return None
    confidence = value.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        return None
    return {"category": value["category"], "severity": value["severity"], "evidence": [str(x)[:240] for x in value["evidence"][:5]], "confidence": confidence, "changeType": value["changeType"]}


def validate_diff(diff):
    if not isinstance(diff, str) or not diff.strip() or "\x00" in diff:
        return False
    if re.search(r"^(?:RUN|CMD|FROM|#!)\s", diff, re.MULTILINE):
        return False
    headers = re.findall(r"^\+\+\+ b/(.+)$", diff, re.MULTILINE)
    old_headers = re.findall(r"^--- a/(.+)$", diff, re.MULTILINE)
    if not headers or headers != old_headers:
        return False
    return all(ALLOWED_FILES.fullmatch(path) and ".." not in path and "\\" not in path for path in headers)
