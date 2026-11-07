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
from contextlib import contextmanager
from patch_policy import changed_paths
from runtime_support import ASTRBOT_FILES, COMPANION_FILES, companion_destination, probe_runtime, responder_unit

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
    "qq-chat-router.py",
]
FILES += list(ASTRBOT_FILES) + list(COMPANION_FILES)
SNAPSHOT_FILES = sorted(FILES + [
    "qq-gemini-tts.test.mjs", "qq-group-routing.test.mjs", "qq-live-facts.test.mjs",
    "qq-media.test.mjs", "qq-memory-cross-session.test.mjs", "qq-memory-recent.test.mjs",
    "qq-relationship.test.mjs", "qq-reminders.test.mjs", "qq-song-clips.test.mjs",
    "qq-conversation-audit.test.mjs",
    "qq-persona-messages.test.mjs", "qq-profile-safety.test.mjs",
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
        destination.parent.mkdir(parents=True, exist_ok=True)
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


def health(since=0):
    marker = Path('/etc/jiangsheng-runtime')
    if marker.exists() and marker.read_text().strip() == 'astrbot':
        state = probe_runtime(since=since)
        return state.get('api') is True and state.get('qqConnected') is True and state.get('reply') is True and state.get('sharedMemoryReady') is not False
    bridge = run(["/usr/bin/systemctl", "is-active", "qq-hermes-bridge.service"], timeout=15)
    api = run(["/usr/bin/systemctl", "is-active", "hermes-qq-api.service"], timeout=15)
    return bridge.stdout.strip() == "active" and api.stdout.strip() == "active"


def selected_runtime():
    marker = Path('/etc/jiangsheng-runtime')
    return 'astrbot' if marker.exists() and marker.read_text().strip() == 'astrbot' else 'hermes'


def sync_astrbot():
    target = Path('/opt/jiangsheng-astrbot/runtime/data/plugins/astrbot_plugin_jiangsheng')
    for name in ASTRBOT_FILES:
        destination = target / Path(name).name
        shutil.copy2(SOURCE / name, destination)
        owner = (SOURCE / name).stat()
        os.chown(destination, owner.st_uid, owner.st_gid)
    for name in COMPANION_FILES:
        source = SOURCE / name
        if not source.exists():
            raise RuntimeError('native source baseline is incomplete')
        destination = companion_destination(name)
        if destination.is_symlink() or not destination.is_file():
            raise RuntimeError('native destination is not a regular file')
        shutil.copy2(source, destination)
        owner = source.stat()
        os.chown(destination, owner.st_uid, owner.st_gid)
    script = '''import asyncio,os,sys
from pathlib import Path
os.environ['ASTRBOT_ROOT']='/opt/jiangsheng-astrbot/runtime'
sys.path.insert(0,'/opt/jiangsheng-astrbot/app')
from astrbot.core import db_helper
async def main():
 await db_helper.initialize()
 await db_helper.update_persona('default',system_prompt=Path('/home/hermes/qq-persona.md').read_text(),tools=[])
asyncio.run(main())
'''
    result = run(['/usr/sbin/runuser', '-u', 'hermes', '--', '/opt/jiangsheng-astrbot/venv/bin/python', '-c', script])
    if result.returncode:
        raise RuntimeError('AstrBot persona synchronization failed')


def verify_companion_sources(paths):
    checks = {
        'conversation/group_questions.py': ('test_social_questions.py',),
        'conversation/group_admission.py': ('test_mixed_admission.py', 'test_active_group_admission.py'),
        'memory/person/service.py': ('test_person_identity.py',),
        'expression/style_service.py': ('test_expression_request_contract.py',),
    }
    for name in paths:
        if name not in COMPANION_FILES:
            continue
        if run(['/opt/jiangsheng-astrbot/venv/bin/python', '-m', 'py_compile', str(SOURCE / name)], timeout=30).returncode:
            raise RuntimeError('native source syntax failed')
        for short, tests in checks.items():
            if name.endswith(short):
                for test in tests:
                    result = run(['/opt/jiangsheng-astrbot/venv/bin/python', str(SOURCE/'migration/patches'/test), str(SOURCE/name)], timeout=45)
                    if result.returncode:
                        raise RuntimeError('native contract regression failed')



def apply_source_patch(source, diff, git="/usr/bin/git"):
    for options in (["--check"], ["--whitespace=nowarn"]):
        result = subprocess.run([git, "-C", str(source), "apply", *options, "-"],
                                input=diff, text=True, capture_output=True, timeout=30, check=False)
        if result.returncode:
            raise RuntimeError("patch rejected")


@contextmanager
def production_lock():
    import fcntl
    with open('/run/lock/jiangsheng-responder.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def verify_completion():
    import urllib.request
    cfg = json.loads((SOURCE / '.hermes/chat-routing.json').read_text())
    payload = dict(model='qq-chat', stream=False, max_tokens=16,
                   messages=[dict(role='user', content='Reply exactly OK')])
    request = urllib.request.Request('http://127.0.0.1:8650/v1/chat/completions',
        data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + cfg['localKey']})
    result = json.load(urllib.request.urlopen(request, timeout=60))
    return bool(result.get('choices', [{}])[0].get('message', {}).get('content', '').strip())


def apply(diff):
    with production_lock():
        return apply_locked(diff)


def apply_locked(diff):
    paths = changed_paths(diff, FILES)
    for name in paths:
        path = SOURCE / name
        if not path.is_file() or path.is_symlink():
            raise ValueError("patch target is not a regular source file")
        if b"\x00" in path.read_bytes():
            raise ValueError("binary patch target rejected")
    ident = snapshot()
    runtime = selected_runtime()
    unit = responder_unit(runtime)
    try:
        apply_source_patch(SOURCE, diff)
        node = "/home/hermes/.hermes/tools/node-26.12.1-linux-x64/bin/node"
        tests = sorted(str(path) for path in SOURCE.glob("qq-*.test.mjs"))
        suite = run([node, "--test", *tests], cwd=SOURCE, timeout=240)
        if suite.returncode != 0:
            raise RuntimeError("production test suite failed")
        for name in paths:
            if name.endswith('.mjs'):
                if run([node, '--check', str(SOURCE / name)], timeout=30).returncode:
                    raise RuntimeError('syntax check failed')
        if runtime == 'astrbot':
            suite = run(['/opt/jiangsheng-astrbot/venv/bin/python', '-m', 'unittest', 'discover', '-s', str(SOURCE / 'migration/tests')], cwd=SOURCE, timeout=90)
            if suite.returncode:
                raise RuntimeError('AstrBot regression suite failed')
            check_python = run(['/opt/jiangsheng-astrbot/venv/bin/python', '-m', 'compileall', '-q', str(SOURCE / 'migration/plugin')])
            if check_python.returncode:
                raise RuntimeError('AstrBot syntax check failed')
            verify_companion_sources(paths)
            sync_astrbot()
        if 'qq-chat-router.py' in paths:
            if run(['/usr/bin/systemctl', 'restart', 'qq-chat-router.service'], timeout=60).returncode:
                raise RuntimeError('router restart failed')
        started = time.time()
        restart = run(["/usr/bin/systemctl", "restart", unit], timeout=60)
        if restart.returncode != 0:
            raise RuntimeError("restart failed")
        for _ in range(30):
            time.sleep(3)
            if health(since=started):
                break
        if not health(since=started):
            raise RuntimeError("health check failed")
        if (runtime == 'astrbot' or 'qq-chat-router.py' in paths) and not verify_completion():
            raise RuntimeError('real completion verification failed')
        time.sleep(60)
        if not health(since=started):
            raise RuntimeError("stability observation failed")
        append_release_record({"status": "healthy", "snapshot": ident, "changed": paths})
        print(json.dumps({"status": "healthy", "snapshot": ident}), flush=True)
    except Exception:
        try:
            restore(ident)
            if runtime == 'astrbot':
                sync_astrbot()
            if 'qq-chat-router.py' in paths:
                run(['/usr/bin/systemctl', 'restart', 'qq-chat-router.service'], timeout=60)
            started = time.time()
            run(["/usr/bin/systemctl", "restart", unit], timeout=60)
            for _ in range(30):
                time.sleep(3)
                if health(since=started):
                    break
            if not health(since=started):
                raise RuntimeError("rollback health check failed")
            append_release_record({"status": "rolled_back", "snapshot": ident, "changed": paths})
        except Exception:
            run(["/usr/bin/systemctl", "stop", unit], timeout=30)
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
