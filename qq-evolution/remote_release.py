import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

SOURCE = Path("/home/hermes")
SNAPSHOTS = SOURCE / "qq-evolution-snapshots"
FILES = ["qq-hermes-bridge.mjs", "qq-persona.md"]


def run(args, **kwargs):
    return subprocess.run(args, text=True, capture_output=True, timeout=kwargs.pop("timeout", 120), check=False, **kwargs)


def snapshot():
    ident = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + hashlib.sha256(str(time.time_ns()).encode()).hexdigest()[:8]
    target = SNAPSHOTS / ident
    target.mkdir(parents=True, exist_ok=False)
    entries = []
    for name in FILES:
        source = SOURCE / name
        destination = target / name
        shutil.copy2(source, destination)
        entries.append({"path": name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
    (target / "manifest.json").write_text(json.dumps({"id": ident, "files": entries}, sort_keys=True), encoding="utf-8")
    return ident


def restore(ident):
    manifest = json.loads((SNAPSHOTS / ident / "manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        source = SNAPSHOTS / ident / entry["path"]
        if hashlib.sha256(source.read_bytes()).hexdigest() != entry["sha256"]:
            raise RuntimeError("snapshot hash mismatch")
        shutil.copy2(source, SOURCE / entry["path"])


def health():
    bridge = run(["/usr/bin/systemctl", "is-active", "qq-hermes-bridge.service"], timeout=15)
    api = run(["/usr/bin/systemctl", "is-active", "hermes-qq-api.service"], timeout=15)
    return bridge.stdout.strip() == "active" and api.stdout.strip() == "active"


def apply(diff):
    ident = snapshot()
    try:
        result = subprocess.run(["/usr/bin/patch", "--batch", "--forward", "--fuzz=0", "-p1", "-d", str(SOURCE)], input=diff, text=True, capture_output=True, timeout=30, check=False)
        if result.returncode != 0:
            raise RuntimeError("patch rejected")
        node = "/home/hermes/.hermes/tools/node-26.12.1-linux-x64/bin/node"
        check = run([node, "--check", str(SOURCE / "qq-hermes-bridge.mjs")], timeout=30)
        if check.returncode != 0:
            raise RuntimeError("syntax check failed")
        restart = run(["/usr/bin/systemctl", "restart", "qq-hermes-bridge.service"], timeout=60)
        if restart.returncode != 0:
            raise RuntimeError("restart failed")
        time.sleep(3)
        if not health():
            raise RuntimeError("health check failed")
        print(json.dumps({"status": "healthy", "snapshot": ident}), flush=True)
    except Exception:
        restore(ident)
        run(["/usr/bin/systemctl", "restart", "qq-hermes-bridge.service"], timeout=60)
        print(json.dumps({"status": "rolled_back", "snapshot": ident}), flush=True)
        raise


if __name__ == "__main__":
    apply(sys.stdin.read())
