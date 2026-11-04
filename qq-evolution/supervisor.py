import os
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


def development_repo():
    return Path(os.environ.get("QQ_EVOLUTION_REPO", "/home/admin/qq-evolution/development"))


def assess_events(events, repo, evaluator=evaluate_and_propose):
    window = events[-80:]
    if not aggregate(window, minimum_pairs=3)["eligible"]:
        return ""
    finding, diff = evaluator(window, cwd=str(repo))
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


def run_cycle():
    state = StateStore(STATE)
    lock = SingleJobLock(LOCK)
    supervisor = EvolutionSupervisor(state, lock, cooldown=int(os.environ.get("QQ_EVOLUTION_COOLDOWN", "1800")))
    repo = development_repo()

    def evaluate_window():
        events = fetch_remote_events(PRODUCTION_HOST, "/home/hermes/qq-audit")
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
            return "published"
        if '"status": "rolled_back"' in result.stdout:
            return "rolled_back"
        return "release_error"

    return supervisor.run_once(evaluate_window, publish, int(time.time()))


def main():
    interval = int(os.environ.get("QQ_EVOLUTION_POLL_SECONDS", "300"))
    while True:
        try:
            run_cycle()
        except Exception as error:
            print("qq-evolution cycle failed:", type(error).__name__, flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
