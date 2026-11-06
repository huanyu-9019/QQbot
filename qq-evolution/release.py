import hashlib
import json
import re
import shutil
import subprocess
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


class ReleaseManager:
    def __init__(self, source, snapshots, files, restart, health, apply_diff=None):
        self.source = Path(source)
        self.snapshots = Path(snapshots)
        self.files = list(files)
        self.restart = restart
        self.health = health
        self.apply_diff = apply_diff or self._apply_unified_diff

    def apply(self, diff):
        if not validate_patch(diff):
            raise ValueError("patch rejected")
        manifest = create_snapshot(self.source, self.snapshots, self.files)
        try:
            self.apply_diff(self.source, diff)
            self.restart()
            if not self.health():
                raise RuntimeError("health check failed")
            return manifest
        except Exception:
            self.restore(manifest)
            self.restart()
            raise

    def restore(self, manifest):
        snapshot = self.snapshots / manifest["id"]
        for entry in manifest["files"]:
            path = Path(entry["path"])
            source_file = snapshot / path
            destination = self.source / path
            if hashlib.sha256(source_file.read_bytes()).hexdigest() != entry["sha256"]:
                raise RuntimeError("snapshot hash mismatch")
            shutil.copy2(source_file, destination)

    @staticmethod
    def _apply_unified_diff(source, diff):
        result = subprocess.run(
            ["/usr/bin/patch", "--batch", "--forward", "--fuzz=0", "-p1", "-d", str(source)],
            input=diff,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError("fixed patch application failed")
