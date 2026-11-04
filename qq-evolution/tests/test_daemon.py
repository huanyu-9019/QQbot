import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[1]))
from daemon import StateStore, SingleJobLock


class DaemonTests(unittest.TestCase):
    def test_state_store_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            StateStore(path).save({"status": "healthy", "version": "v1"})
            self.assertEqual(StateStore(path).load()["version"], "v1")

    def test_single_job_lock_blocks_second_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "job.lock"
            first = SingleJobLock(lock_path)
            second = SingleJobLock(lock_path)
            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire())
            first.release()
            self.assertTrue(second.acquire())
            second.release()


if __name__ == "__main__":
    unittest.main()
