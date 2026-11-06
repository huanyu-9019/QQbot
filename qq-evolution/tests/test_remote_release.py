import shutil
import sys
import tempfile
import unittest
import subprocess
from unittest.mock import patch
from pathlib import Path
from contextlib import nullcontext

sys.path.insert(0, str(Path(__file__).parents[1]))
from remote_release import FILES, SNAPSHOT_FILES, apply_source_patch
import remote_release as release


class RemotePatchTests(unittest.TestCase):
    def test_astrbot_health_rejects_connected_runtime_without_working_reply(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp)/'runtime'
            marker.write_text('astrbot')
            with patch.object(release, 'Path', return_value=marker), patch.object(release, 'probe_runtime', return_value={'api': True, 'qqConnected': True, 'reply': False}):
                self.assertFalse(release.health())

    def test_apply_always_enters_common_production_lock(self):
        with patch.object(release, 'production_lock', return_value=nullcontext()) as lock, patch.object(release, 'apply_locked') as apply:
            release.apply('patch')
            lock.assert_called_once()
            apply.assert_called_once_with('patch')

    def test_release_health_scopes_old_failed_turns_out_of_current_health(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp)/'runtime'
            marker.write_text('astrbot')
            def probe(since=0):
                return dict(api=True, qqConnected=True, reply=since > 100)
            with patch.object(release, 'Path', return_value=marker), patch.object(release, 'probe_runtime', side_effect=probe):
                self.assertFalse(release.health())
                self.assertTrue(release.health(since=200))

    def test_astrbot_patch_snapshots_nested_source_and_never_restarts_hermes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            name = 'migration/plugin/policy.py'
            target = source / name
            target.parent.mkdir(parents=True)
            target.write_text('old\n')
            diff = f'--- a/{name}\n+++ b/{name}\n@@ -1 +1 @@\n-old\n+new\n'
            calls = []
            def execute(args, **kwargs):
                calls.append(args)
                return subprocess.CompletedProcess(args, 0, '', '')
            with patch.multiple(release, SOURCE=source, SNAPSHOTS=root/'snapshots', FILES=[name], SNAPSHOT_FILES=[name]), \
                 patch.object(release, 'selected_runtime', return_value='astrbot'), \
                 patch.object(release, 'apply_source_patch', side_effect=lambda source, diff: apply_source_patch(source, diff, git=shutil.which('git'))), \
                 patch.object(release, 'sync_astrbot') as sync, \
                 patch.object(release, 'production_lock', return_value=nullcontext()), \
                 patch.object(release, 'verify_completion', return_value=True), \
                 patch.object(release, 'health', return_value=True), \
                 patch.object(release, 'run', side_effect=execute), \
                 patch.object(release.time, 'sleep'):
                release.apply(diff)
                self.assertEqual('new\n', target.read_text())
                self.assertTrue(list((root/'snapshots').glob('*/migration/plugin/policy.py')))
                self.assertIn(['/usr/bin/systemctl','restart','jiangsheng-astrbot.service'], calls)
                self.assertFalse(any('qq-hermes-bridge.service' in args for args in calls))
                self.assertTrue(any('--test' in args for args in calls))
                self.assertTrue(any('unittest' in args for args in calls))
                sync.assert_called_once()

    def test_new_runtime_modules_and_tests_are_in_release_snapshots(self):
        self.assertIn("qq-group-style.mjs", FILES)
        self.assertIn("qq-space-disk-report.mjs", FILES)
        self.assertIn("qq-group-style.test.mjs", SNAPSHOT_FILES)
        self.assertIn("qq-space-disk-report.test.mjs", SNAPSHOT_FILES)

    def test_real_git_applies_valid_diff_and_leaves_stale_target_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            target = source / "qq-persona.md"
            target.write_text("old\n", encoding="utf-8")
            diff = "--- a/qq-persona.md\n+++ b/qq-persona.md\n@@ -1 +1 @@\n-old\n+new\n"
            apply_source_patch(source, diff, git=shutil.which("git"))
            self.assertEqual(target.read_text(), "new\n")
            with self.assertRaises(RuntimeError):
                apply_source_patch(source, diff, git=shutil.which("git"))
            self.assertEqual(target.read_text(), "new\n")


class PreservedBaselineTests(unittest.TestCase):
    def test_real_git_applies_valid_zero_context_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            target = source / "qq-persona.md"
            target.write_text("old\n", encoding="utf-8")
            diff = "--- a/qq-persona.md\n+++ b/qq-persona.md\n@@ -1 +1 @@\n-old\n+new\n"
            apply_source_patch(source, diff, git=shutil.which("git"))
            self.assertEqual(target.read_text(encoding="utf-8"), "new\n")

