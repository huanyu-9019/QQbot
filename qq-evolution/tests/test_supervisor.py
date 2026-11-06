import os
import sys
import unittest
import tempfile
import subprocess
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
from supervisor import development_repo, assess_events, check_candidate, advance_baseline
import supervisor as service


class SupervisorTests(unittest.TestCase):
    def test_learning_fetch_refreshes_monitor_freshness(self):
        from unittest.mock import patch
        with patch.object(service, "fetch_remote_events", return_value=[{"text": "safe"}]), \
             patch.object(service, "record_monitor_health") as heartbeat:
            rows = service.fetch_learning_events()
        self.assertEqual(rows, [{"text": "safe"}])
        self.assertEqual(heartbeat.call_args.kwargs.keys(), {"lastFetch"})

    def test_same_audit_window_is_not_reevaluated_until_new_conversation_arrives(self):
        events = []
        for i in range(3):
            events.extend([{"direction": "incoming", "turnId": str(i), "timestamp": i * 1000},
                           {"direction": "delivered", "turnId": str(i), "timestamp": i * 1000 + 100, "text": str(i)}])
        with tempfile.TemporaryDirectory() as tmp, \
                patch.multiple(service, STATE=Path(tmp) / "state.json", LOCK=Path(tmp) / "lock"), \
                patch.dict(os.environ, {"QQ_EVOLUTION_COOLDOWN": "0", "QQ_EVOLUTION_GIT_REMOTE": ""}), \
                patch.object(service, "fetch_remote_events", return_value=events), \
                patch.object(service, "evaluate_and_propose", return_value=(None, "")) as model:
            service.run_cycle()
            service.run_cycle()
            self.assertEqual(model.call_count, 1)
            events.append({"direction": "incoming", "turnId": "new", "timestamp": 4000})
            service.run_cycle()
            self.assertEqual(model.call_count, 2)

    def test_successful_deployment_advances_only_its_files_in_development_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            (repo / "qq-persona.md").write_text("old\n")
            (repo / "other.txt").write_text("original\n")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@localhost", "commit", "-qm", "initial"], cwd=repo, check=True)
            (repo / "other.txt").write_text("unrelated\n")
            diff = "--- a/qq-persona.md\n+++ b/qq-persona.md\n@@ -1 +1 @@\n-old\n+new\n"
            remote = repo / "archive.git"
            subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
            with patch.dict(os.environ, {"QQ_EVOLUTION_GIT_REMOTE": str(remote)}):
                advance_baseline(diff, repo)
            self.assertEqual(subprocess.check_output(["git", "show", "HEAD:qq-persona.md"], cwd=repo, text=True), "new\n")
            self.assertEqual(subprocess.check_output(["git", "show", "HEAD:other.txt"], cwd=repo, text=True), "original\n")
            self.assertEqual((repo / "other.txt").read_text(), "unrelated\n")
            self.assertEqual(subprocess.check_output(["git", "--git-dir", str(remote), "show", "refs/heads/codex/qq-autonomous-evolution:qq-persona.md"], text=True), "new\n")

    def test_successful_nonrepeated_replies_still_receive_quality_assessment(self):
        events = []
        for i in range(3):
            events.extend([{"direction": "incoming", "turnId": str(i), "timestamp": i * 1000, "text": "hello"},
                           {"direction": "delivered", "turnId": str(i), "timestamp": i * 1000 + 100, "text": "different " + str(i)}])
        def evaluator(window, cwd):
            return {"category": "unnatural"}, "quality patch"
        self.assertEqual(assess_events(events, Path("/repo"), evaluator), "quality patch")

    def test_stale_patch_is_rejected_before_remote_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "qq-persona.md").write_text("current\n", encoding="utf-8")
            good = "--- a/qq-persona.md\n+++ b/qq-persona.md\n@@ -1 +1 @@\n-current\n+improved\n"
            self.assertEqual(check_candidate(good, repo), ["qq-persona.md"])
            with self.assertRaises(ValueError):
                check_candidate(good.replace("-current", "-obsolete"), repo)
            self.assertEqual((repo / "qq-persona.md").read_text(), "current\n")

    def test_uses_current_development_tree_and_allows_explicit_path_override(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("QQ_EVOLUTION_REPO", None)
            self.assertEqual(development_repo(), Path("/home/admin/qq-evolution/development"))
        with patch.dict(os.environ, {"QQ_EVOLUTION_REPO": "/tmp/repo"}):
            self.assertEqual(development_repo(), Path("/tmp/repo"))


if __name__ == "__main__":
    unittest.main()
