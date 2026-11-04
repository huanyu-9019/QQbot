import json
import re
import subprocess
from pathlib import Path

MAX_TEXT = 1200
_SECRET = re.compile(r"(?i)(?:api[_-]?key|token|secret|authorization|bearer)\s*[:=]\s*[^\s,;]+")
_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_QQ = re.compile(r"(?i)(?:(?:qq|群号|用户(?:号|id)|user[_-]?id|group[_-]?id)\s*[:=：]?\s*)\d{5,12}")
_ADDRESS = re.compile(r"(?:[\u4e00-\u9fff]{2,12}(?:省|市|区|县|路|街|号)[\u4e00-\u9fff0-9-]{0,24})")


def redact_text(text):
    value = str(text or "")
    value = _SECRET.sub("[REDACTED_SECRET]", value)
    value = _PHONE.sub("[REDACTED_PHONE]", value)
    value = _QQ.sub("[REDACTED_ID]", value)
    value = _ADDRESS.sub("[REDACTED_ADDRESS]", value)
    return value[:MAX_TEXT]


def sanitize_record(record):
    if not isinstance(record, dict):
        return None
    required = ("timestamp", "direction", "kind", "sessionHash", "text")
    if any(key not in record for key in required):
        return None
    if record["direction"] not in ("incoming", "delivered") or record["kind"] not in ("private", "group"):
        return None
    if not isinstance(record["sessionHash"], str) or not re.fullmatch(r"[a-f0-9]{64}", record["sessionHash"]):
        return None
    row = {key: record[key] for key in required}
    try:
        row["timestamp"] = int(record["timestamp"])
    except (TypeError, ValueError, OverflowError):
        return None
    row["text"] = redact_text(record["text"])
    if "turnId" in record and isinstance(record["turnId"], str):
        row["turnId"] = record["turnId"]
    return row


def read_events(paths, cursor_path):
    cursor_file = Path(cursor_path)
    try:
        cursor = json.loads(cursor_file.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        cursor = {}
    events = []
    next_cursor = {}
    for raw_path in sorted(paths, key=lambda item: str(item)):
        path = Path(raw_path)
        key = str(path)
        offset = int(cursor.get(key, 0))
        with path.open("rb") as stream:
            stream.seek(offset)
            while True:
                line = stream.readline()
                if not line:
                    break
                try:
                    row = sanitize_record(json.loads(line.decode("utf-8")))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    row = None
                if row:
                    events.append(row)
            next_cursor[key] = stream.tell()
    cursor_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = cursor_file.with_suffix(cursor_file.suffix + ".tmp")
    temporary.write_text(json.dumps(next_cursor, sort_keys=True), encoding="utf-8")
    temporary.replace(cursor_file)
    return events, next_cursor


def fetch_remote_events(host, remote_directory, runner=None, read_file=None):
    if not re.fullmatch(r"[A-Za-z0-9_.@-]+", host) or remote_directory != "/home/hermes/qq-audit":
        raise ValueError("remote source is fixed")
    list_args = ["/usr/bin/ssh", "-i", "/home/admin/.ssh/qq-evolution-prod", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", host, "find /home/hermes/qq-audit -maxdepth 1 -type f -name '*.jsonl' -printf '%f\\n'"]
    execute = runner or (lambda args: subprocess.run(args, text=True, capture_output=True, timeout=20, check=True).stdout)
    names = execute(list_args).splitlines()
    events = []
    for name in sorted(names):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}\.jsonl", name):
            continue
        path = remote_directory.rstrip("/") + "/" + name
        if read_file:
            content = read_file(name)
        else:
            args = ["/usr/bin/ssh", "-i", "/home/admin/.ssh/qq-evolution-prod", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", host, "cat -- '" + path + "'"]
            content = subprocess.run(args, text=True, capture_output=True, timeout=20, check=True).stdout
        for line in content.splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            safe = sanitize_record(record)
            if safe:
                events.append(safe)
    return events
