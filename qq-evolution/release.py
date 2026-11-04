import hashlib
import json
import re
import shutil
import time
from pathlib import Path

ALLOWED_FILE = re.compile(r"^(?:qq-[A-Za-z0-9._-]+\.mjs|qq-persona\.md|qq-[A-Za-z0-9._-]+\.test\.mjs)$")


def validate_patch(diff):
    if not isinstance(diff, str) or "\x00" in diff or re.search(r"^(?:RUN|CMD|FROM|#!)\s", diff, re.MULTILINE):
        return False
    old = re.findall(r"^--- a/(.+)$", diff, re.MULTILINE)
    new = re.findall(r"^\+\+\+ b/(.+)$", diff, re.MULTILINE)
    return bool(old) and old == new and all(ALLOWED_FILE.fullmatch(path) and ".." not in path and "\\" not in path for path in new)


def create_snapshot(source, snapshots, files):
    source = Path(source)
    snapshots = Path(snapshots)
    snapshot_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + hashlib.sha256(str(time.time_ns()).encode()).hexdigest()[:8]
    target = snapshots / snapshot_id
    target.mkdir(parents=True, exist_ok=False)
    entries = []
    for relative in files:
        path = Path(relative)
        if not ALLOWED_FILE.fullmatch(path.as_posix()) or path.is_absolute() or ".." in path.parts:
            raise ValueError("snapshot path is not allowlisted")
        source_file = source / path
        if not source_file.is_file():
            raise FileNotFoundError(source_file)
        destination = target / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, destination)
        digest = hashlib.sha256(source_file.read_bytes()).hexdigest()
        entries.append({"path": path.as_posix(), "sha256": digest})
    manifest = {"version": 1, "id": snapshot_id, "files": entries}
    (target / "manifest.json").write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    return manifest
