import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[1]))
from daemon import EvolutionSupervisor, StateStore, SingleJobLock


class DaemonTests(unittest.TestCase):
    def test_repeated_failed_releases_back_off_then_resume_without_human_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = StateStore(Path(tmp) / "state.json")
            supervisor = EvolutionSupervisor(state, SingleJobLock(Path(tmp) / "job.lock"), cooldown=0, failure_backoff=100)
            self.assertEqual(supervisor.run_once(lambda: "patch", lambda _: "rolled_back", now=10), "rolled_back")
            self.assertEqual(supervisor.run_once(lambda: "patch", lambda _: "rolled_back", now=20), "rolled_back")
            self.assertEqual(supervisor.run_once(lambda: "patch", lambda _: "published", now=30), "locked_out")
            self.assertEqual(supervisor.run_once(lambda: "patch", lambda _: "published", now=119), "locked_out")
            self.assertEqual(supervisor.run_once(lambda: "patch", lambda _: "published", now=120), "published")
            self.assertEqual(state.load()["rollbackFailures"], 0)

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

    def test_cooldown_and_rollback_lockout_stop_repeated_publishing(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = StateStore(Path(tmp) / "state.json")
            supervisor = EvolutionSupervisor(state, SingleJobLock(Path(tmp) / "job.lock"), cooldown=60)
            calls = []
            self.assertEqual(supervisor.run_once(lambda: "patch", lambda patch: calls.append(patch) or True, now=100), "published")
            self.assertEqual(supervisor.run_once(lambda: "patch", lambda patch: calls.append(patch) or True, now=110), "cooldown")
            supervisor.record_rollback_failure()
            supervisor.record_rollback_failure()
            self.assertEqual(supervisor.run_once(lambda: "patch", lambda patch: True, now=200), "locked_out")

    def test_rolled_back_release_increments_failure_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = StateStore(Path(tmp) / "state.json")
            supervisor = EvolutionSupervisor(state, SingleJobLock(Path(tmp) / "job.lock"), cooldown=0)
            self.assertEqual(supervisor.run_once(lambda: "patch", lambda patch: "rolled_back", now=1), "rolled_back")
            self.assertEqual(state.load()["rollbackFailures"], 1)

    def test_single_job_lock_recovers_stale_dead_process_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "job.lock"
            lock_path.write_text("99999999", encoding="utf-8")
            lock = SingleJobLock(lock_path)
            self.assertTrue(lock.acquire())
            lock.release()


if __name__ == "__main__":
    unittest.main()
