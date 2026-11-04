import json
import os
from pathlib import Path


class StateStore:
    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save(self, value):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
        temporary.replace(self.path)


class SingleJobLock:
    def __init__(self, path):
        self.path = Path(path)
        self.handle = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.handle = self.path.open("x", encoding="utf-8")
            self.handle.write(str(os.getpid()))
            self.handle.flush()
            return True
        except FileExistsError:
            return False

    def release(self):
        if self.handle:
            self.handle.close()
            self.handle = None
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass


class EvolutionSupervisor:
    def __init__(self, state, lock, cooldown=900, max_rollback_failures=2):
        self.state = state
        self.lock = lock
        self.cooldown = cooldown
        self.max_rollback_failures = max_rollback_failures

    def record_rollback_failure(self):
        current = self.state.load()
        current["rollbackFailures"] = int(current.get("rollbackFailures", 0)) + 1
        self.state.save(current)

    def run_once(self, evaluate, publish, now):
        current = self.state.load()
        if int(current.get("rollbackFailures", 0)) >= self.max_rollback_failures:
            return "locked_out"
        if now - int(current.get("lastRun", -10**18)) < self.cooldown:
            return "cooldown"
        if not self.lock.acquire():
            return "busy"
        try:
            current["lastRun"] = now
            current["status"] = "evaluating"
            self.state.save(current)
            artifact = evaluate()
            if not artifact:
                current["status"] = "no_change"
                self.state.save(current)
                return "no_change"
            publish_result = publish(artifact)
            if publish_result is False or publish_result == "rejected":
                current["status"] = "rejected"
                self.state.save(current)
                return "rejected"
            if publish_result in {"rolled_back", "release_error"}:
                current["rollbackFailures"] = int(current.get("rollbackFailures", 0)) + 1
                current["status"] = publish_result
                self.state.save(current)
                return publish_result
            current["status"] = "published"
            current["rollbackFailures"] = 0
            self.state.save(current)
            return "published"
        finally:
            self.lock.release()
