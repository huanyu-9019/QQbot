import hashlib
import json
import datetime
import os
import stat
import shutil
import subprocess
import sys
import time
from pathlib import Path
from patch_policy import changed_paths

SOURCE = Path("/home/hermes")
SNAPSHOTS = SOURCE / "qq-evolution-snapshots"
FILES = [
    "qq-hermes-bridge.mjs", "qq-persona.md", "qq-conversation-audit.mjs",
    "qq-memory.mjs", "qq-relationship.mjs", "qq-send-receipts.mjs",
    "qq-task-queue.mjs", "qq-persona-messages.mjs", "qq-media.mjs",
    "qq-reminders.mjs", "qq-proactive.mjs", "qq-online-stickers.mjs",
    "qq-learned-stickers.mjs", "qq-recent-images.mjs", "qq-typing.mjs",
    "qq-interaction-config.mjs", "qq-search-policy.mjs", "qq-live-facts.mjs",
    "qq-gemini-tts.mjs", "qq-song-clips.mjs", "qq-public-fetch.mjs",
    "qq-qzone-post.mjs", "qq-stickers.mjs", "qq-group-style.mjs",
    "qq-space-disk-report.mjs",
    "qq-qzone-lock.mjs",
    "qq-model-fallback.mjs", "qq-model-health.mjs",
]
SNAPSHOT_FILES = sorted(FILES + [
    "qq-gemini-tts.test.mjs", "qq-group-routing.test.mjs", "qq-live-facts.test.mjs",
    "qq-media.test.mjs", "qq-memory-cross-session.test.mjs", "qq-memory-recent.test.mjs",
    "qq-relationship.test.mjs", "qq-reminders.test.mjs", "qq-song-clips.test.mjs",
    "qq-conversation-audit.test.mjs",
    "qq-group-style.test.mjs", "qq-space-disk-report.test.mjs",
    "qq-qzone-lock.test.mjs",
    "qq-model-fallback.test.mjs",
])


def run(args, **kwargs):
    return subprocess.run(args, text=True, capture_output=True, timeout=kwargs.pop("timeout", 120), check=False, **kwargs)


def snapshot():
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(SOURCE).free < 100 * 1024 * 1024:
        raise RuntimeError("insufficient free disk space")
    ident = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + hashlib.sha256(str(time.time_ns()).encode()).hexdigest()[:8]
    target = SNAPSHOTS / ident
    target.mkdir(parents=True, exist_ok=False)
    entries = []
    for name in SNAPSHOT_FILES:
        source = SOURCE / name
        if not source.exists():
            continue
        if source.is_symlink() or not source.is_file():
            raise RuntimeError("snapshot source is not a regular file")
        destination = target / name
        shutil.copy2(source, destination)
        metadata = source.stat(follow_symlinks=False)
        entries.append({"path": name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "mode": stat.S_IMODE(metadata.st_mode), "uid": metadata.st_uid, "gid": metadata.st_gid})
    (target / "manifest.json").write_text(json.dumps({"id": ident, "files": entries}, sort_keys=True), encoding="utf-8")
    return ident


def restore(ident):
    manifest = json.loads((SNAPSHOTS / ident / "manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        source = SNAPSHOTS / ident / entry["path"]
        if hashlib.sha256(source.read_bytes()).hexdigest() != entry["sha256"]:
            raise RuntimeError("snapshot hash mismatch")
        destination = SOURCE / entry["path"]
        shutil.copy2(source, destination)
        os.chown(destination, entry["uid"], entry["gid"])
        os.chmod(destination, entry["mode"])


def health():
    bridge = run(["/usr/bin/systemctl", "is-active", "qq-hermes-bridge.service"], timeout=15)
    api = run(["/usr/bin/systemctl", "is-active", "hermes-qq-api.service"], timeout=15)
    return bridge.stdout.strip() == "active" and api.stdout.strip() == "active"


def apply_source_patch(source, diff, git="/usr/bin/git"):
    for options in (["--check"], ["--whitespace=nowarn"]):
        result = subprocess.run([git, "-C", str(source), "apply", *options, "-"],
                                input=diff, text=True, capture_output=True, timeout=30, check=False)
        if result.returncode:
            raise RuntimeError("patch rejected")


def apply(diff):
    paths = changed_paths(diff, FILES)
    for name in paths:
        path = SOURCE / name
        if not path.is_file() or path.is_symlink():
            raise ValueError("patch target is not a regular source file")
        if b"\x00" in path.read_bytes():
            raise ValueError("binary patch target rejected")
    ident = snapshot()
    try:
        apply_source_patch(SOURCE, diff)
        node = "/home/hermes/.hermes/tools/node-26.12.1-linux-x64/bin/node"
        tests = sorted(str(path) for path in SOURCE.glob("qq-*.test.mjs"))
        suite = run([node, "--test", *tests], timeout=240)
        if suite.returncode != 0:
            raise RuntimeError("production test suite failed")
        check = run([node, "--check", str(SOURCE / "qq-hermes-bridge.mjs")], timeout=30)
        if check.returncode != 0:
            raise RuntimeError("syntax check failed")
        restart = run(["/usr/bin/systemctl", "restart", "qq-hermes-bridge.service"], timeout=60)
        if restart.returncode != 0:
            raise RuntimeError("restart failed")
        time.sleep(3)
        if not health():
            raise RuntimeError("health check failed")
        time.sleep(60)
        if not health():
            raise RuntimeError("stability observation failed")
        append_release_record({"status": "healthy", "snapshot": ident, "changed": paths})
        print(json.dumps({"status": "healthy", "snapshot": ident}), flush=True)
    except Exception:
        try:
            restore(ident)
            run(["/usr/bin/systemctl", "restart", "qq-hermes-bridge.service"], timeout=60)
            if not health():
                raise RuntimeError("rollback health check failed")
            append_release_record({"status": "rolled_back", "snapshot": ident, "changed": paths})
        except Exception:
            run(["/usr/bin/systemctl", "stop", "qq-hermes-bridge.service"], timeout=30)
            raise
        print(json.dumps({"status": "rolled_back", "snapshot": ident}), flush=True)
        raise


def append_release_record(record):
    record["timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    path = SOURCE / "qq-evolution-release.jsonl"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")
    os.chmod(path, 0o600)


if __name__ == "__main__":
    apply(sys.stdin.read())
