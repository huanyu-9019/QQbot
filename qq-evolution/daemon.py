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
