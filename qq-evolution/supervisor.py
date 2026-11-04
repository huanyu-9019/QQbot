import os
import hashlib
import json
import time
import subprocess
from pathlib import Path

from agent import evaluate_and_propose
from collector import fetch_remote_events
from daemon import EvolutionSupervisor, SingleJobLock, StateStore
from metrics import aggregate
from patch_policy import changed_paths, recount_hunks


STATE = Path(os.environ.get("QQ_EVOLUTION_STATE", "/home/admin/qq-evolution-state/state.json"))
LOCK = Path(os.environ.get("QQ_EVOLUTION_LOCK", "/home/admin/qq-evolution-state/job.lock"))
PRODUCTION_HOST = os.environ.get("QQ_PRODUCTION_HOST", "root@39.105.219.112")


def record_monitor_health(**fields):
    path = Path(os.environ.get('QQ_MONITOR_HEALTH', '/home/admin/qq-evolution-state/monitor-health.json'))
    try:
        store = StateStore(path)
        health = store.load()
        health.update(fields)
        store.save(health)
        path.chmod(0o600)
    except OSError:
        print('monitor heartbeat write failed', flush=True)


def development_repo():
    return Path(os.environ.get("QQ_EVOLUTION_REPO", "/home/admin/qq-evolution/development"))


def assess_events(events, repo, evaluator=None):
    window = events[-80:]
    if not aggregate(window, minimum_pairs=3)["eligible"]:
        return ""
    finding, diff = (evaluator or evaluate_and_propose)(window, cwd=str(repo))
    return diff if finding else ""


def check_candidate(diff, repo):
    allowed_files = {path.name for path in repo.glob("qq-*.mjs")}
    if (repo / "qq-persona.md").is_file():
        allowed_files.add("qq-persona.md")
    paths = changed_paths(diff, allowed_files)
    result = subprocess.run(["git", "apply", "--check", "-"], input=diff, text=True,
                            capture_output=True, cwd=repo, timeout=30, check=False)
    if result.returncode:
        raise ValueError("candidate does not apply to current source")
    return paths


def advance_baseline(diff, repo):
    paths = check_candidate(diff, repo)
    commands = [
        ["git", "apply", "--whitespace=nowarn", "-"],
        ["git", "add", "--", *paths],
        ["git", "-c", "user.name=QQ Evolution", "-c", "user.email=qq-evolution@localhost",
         "commit", "--only", "-m", "Record deployed QQ improvement", "--", *paths],
    ]
    for index, command in enumerate(commands):
        subprocess.run(command, input=diff if index == 0 else None, text=True,
                       capture_output=True, cwd=repo, timeout=30, check=True)
    push_archive(repo)


def push_archive(repo):
    remote = os.environ.get("QQ_EVOLUTION_GIT_REMOTE")
    if not remote:
        return
    try:
        subprocess.run(["git", "push", remote, "HEAD:refs/heads/codex/qq-autonomous-evolution"],
                       text=True, capture_output=True, cwd=repo, timeout=30, check=True)
    except (subprocess.SubprocessError, OSError):
        print("qq-evolution archive pending", flush=True)


def run_cycle():
    state = StateStore(STATE)
    lock = SingleJobLock(LOCK)
    supervisor = EvolutionSupervisor(state, lock, cooldown=int(os.environ.get("QQ_EVOLUTION_COOLDOWN", "1800")))
    repo = development_repo()
    push_archive(repo)
    window_hash = None

    def evaluate_window():
        nonlocal window_hash
        events = fetch_remote_events(PRODUCTION_HOST, "/home/hermes/qq-audit")
        record_monitor_health(lastFetch=int(time.time()))
        window_hash = hashlib.sha256(json.dumps(events[-80:], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if state.load().get("lastWindowHash") == window_hash:
            return ""
        return assess_events(events, repo)

    def publish(diff):
        try:
            diff = recount_hunks(diff)
            check_candidate(diff, repo)
        except ValueError:
            return False
        args = ["/usr/bin/ssh", "-i", "/home/admin/.ssh/qq-evolution-prod", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", PRODUCTION_HOST, "sudo /usr/bin/python3 /home/hermes/qq-evolution-release.py"]
        result = subprocess.run(args, input=diff, text=True, capture_output=True, timeout=480, check=False)
        if result.returncode == 0:
            advance_baseline(diff, repo)
            return "published"
        if '"status": "rolled_back"' in result.stdout:
            return "rolled_back"
        return "release_error"

    outcome = supervisor.run_once(evaluate_window, publish, int(time.time()))
    if window_hash and outcome in {"published", "no_change"}:
        current = state.load()
        current["lastWindowHash"] = window_hash
        state.save(current)
    return outcome


def main():
    interval = int(os.environ.get("QQ_EVOLUTION_POLL_SECONDS", "300"))
    while True:
        record_monitor_health(pollStarted=int(time.time()))
        try:
            outcome = run_cycle()
            record_monitor_health(pollFinished=int(time.time()), outcome=outcome)
        except Exception as error:
            record_monitor_health(pollFinished=int(time.time()), outcome='cycle_error')
            print("qq-evolution cycle failed:", type(error).__name__, flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
