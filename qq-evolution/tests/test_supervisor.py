import os
import sys
import unittest
import tempfile
import subprocess
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
from supervisor import development_repo, assess_events, check_candidate, advance_baseline
import supervisor as service


class SupervisorTests(unittest.TestCase):
    def test_same_audit_window_is_not_reevaluated_until_new_conversation_arrives(self):
        events = []
        for i in range(3):
            events.extend([{"direction": "incoming", "turnId": str(i), "timestamp": i * 1000},
                           {"direction": "delivered", "turnId": str(i), "timestamp": i * 1000 + 100, "text": str(i)}])
        with tempfile.TemporaryDirectory() as tmp, \
                patch.multiple(service, STATE=Path(tmp) / "state.json", LOCK=Path(tmp) / "lock"), \
                patch.dict(os.environ, {"QQ_EVOLUTION_COOLDOWN": "0", "QQ_EVOLUTION_GIT_REMOTE": ""}), \
                patch.object(service, "fetch_remote_events", return_value=events), \
                patch.object(service, "run_learning_iteration"), \
                patch.object(service, "flush_learning_notices"), \
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
            message = subprocess.check_output(['git', 'log', '-1', '--format=%B'], cwd=repo, text=True, encoding='utf-8')
            self.assertIn('qq-persona.md', message)
            self.assertIn('Patch-SHA256:', message)
            self.assertIn('Validation:', message)
            self.assertNotIn('old\n+new', message)

    def test_commit_message_records_safe_receipt_without_chat_or_credentials(self):
        diff = '--- a/qq-persona.md\n+++ b/qq-persona.md\n@@ -1 +1 @@\n-secret old conversation\n+secret new conversation\n'
        receipt = 'diagnostic token=do-not-copy\n{"status":"healthy","snapshot":"20261108T000000Z-abc123"}'
        message = service.deployment_commit_message(diff, ['qq-persona.md'], receipt)
        self.assertIn('20261108T000000Z-abc123', message)
        self.assertNotIn('do-not-copy', message)
        self.assertNotIn('secret old conversation', message)
        self.assertIn('+1 / -1', message)

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


class PreservedBaselineTests(unittest.TestCase):
    def test_release_failure_classifier_returns_stage_not_raw_stderr(self):
        self.assertEqual(service.release_failure_code(1, 'RuntimeError: production test suite failed'), 'production_tests')
        self.assertEqual(service.release_failure_code(255, 'ssh connection timed out'), 'ssh_transport')

    def test_release_lock_conflict_is_returned_and_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock = root / 'release.lock'
            lock.write_text(str(os.getpid()))
            with patch.object(service, 'STATE', root / 'state.json'), patch.object(service, 'record_monitor_health') as heartbeat:
                result = service.publish_iteration_patch_result('unused', root)
            self.assertEqual(result, (False, 'release_lock_busy'))
            self.assertEqual(heartbeat.call_args.kwargs['lastReleaseFailure'], 'release_lock_busy')

    def test_production_test_failure_is_returned_without_storing_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(service, 'STATE', root / 'state.json'), \
                 patch.object(service, 'check_candidate'), \
                 patch.object(service, 'record_monitor_health') as heartbeat, \
                 patch.object(service.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stderr='production test suite failed; token=private')):
                result = service.publish_iteration_patch_result('patch', root)
            self.assertEqual(result, (False, 'production_tests'))
            self.assertEqual(heartbeat.call_args.kwargs['lastReleaseFailure'], 'production_tests')
            self.assertNotIn('private', str(heartbeat.call_args.kwargs))

    def test_learning_record_keeps_safe_release_failure_code(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / 'state.json'
            diff = '--- a/qq-persona.md\n+++ b/qq-persona.md\n@@ -1 +1 @@\n-old\n+new\n'
            response = json.dumps({'finding': {'category': 'quality', 'changeType': 'code'},
                                   'diff': diff, 'reflection': '减少重复表达并保留语境'})
            with patch.multiple(service, STATE=state, LOCK=root / 'job.lock'), \
                 patch.object(service, 'fetch_learning_events', return_value=[]), \
                 patch.object(service, 'check_candidate'), \
                 patch.object(service, 'record_monitor_health'), \
                 patch.object(service, 'publish_iteration_patch', return_value=False), \
                 patch.object(service, 'publish_iteration_patch_result', return_value=(False, 'release_lock_busy'), create=True), \
                 patch('agent._invoke_fixed', return_value=response):
                service.run_learning_iteration(root, service.StateStore(state))
            row = json.loads((root / 'learning-records.jsonl').read_text(encoding='utf-8').splitlines()[-1])
            self.assertIn('release_lock_busy', row['reason'])
            self.assertNotIn('stderr', row['reason'].lower())

    def test_learning_fetch_refreshes_monitor_freshness(self):
        from unittest.mock import patch
        with patch.object(service, "fetch_remote_events", return_value=[{"text": "safe"}]), \
             patch.object(service, "record_monitor_health") as heartbeat:
            rows = service.fetch_learning_events()
        self.assertEqual(rows, [{"text": "safe"}])
        self.assertEqual(heartbeat.call_args.kwargs.keys(), {"lastFetch"})
