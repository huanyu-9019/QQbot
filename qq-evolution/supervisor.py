import os
import time
import subprocess
from pathlib import Path

from agent import evaluate, propose_patch
from collector import fetch_remote_events
from daemon import EvolutionSupervisor, SingleJobLock, StateStore
from metrics import aggregate


STATE = Path(os.environ.get("QQ_EVOLUTION_STATE", "/home/admin/qq-evolution-state/state.json"))
LOCK = Path(os.environ.get("QQ_EVOLUTION_LOCK", "/home/admin/qq-evolution-state/job.lock"))
PRODUCTION_HOST = os.environ.get("QQ_PRODUCTION_HOST", "root@39.105.219.112")


def run_cycle():
    state = StateStore(STATE)
    lock = SingleJobLock(LOCK)
    supervisor = EvolutionSupervisor(state, lock, cooldown=int(os.environ.get("QQ_EVOLUTION_COOLDOWN", "1800")))

    def evaluate_window():
        events = fetch_remote_events(PRODUCTION_HOST, "/home/hermes/qq-audit")
        metrics = aggregate(events, minimum_pairs=3)
        if not metrics["eligible"] or metrics["successRate"] >= 0.8 and metrics["repeatedReplies"] == 0:
            return ""
        finding = evaluate(events[-80:], cwd="/home/admin/qq-evolution/github-publish")
        return propose_patch(finding, "/home/admin/qq-evolution/github-publish") if finding else ""

    def publish(diff):
        args = ["/usr/bin/ssh", "-i", "/home/admin/.ssh/qq-evolution-prod", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", PRODUCTION_HOST, "sudo -u hermes /usr/bin/python3 /home/hermes/qq-evolution-release.py"]
        result = subprocess.run(args, input=diff, text=True, capture_output=True, timeout=180, check=False)
        return result.returncode == 0

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
