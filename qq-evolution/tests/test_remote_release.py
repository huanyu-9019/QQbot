import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from remote_release import FILES, SNAPSHOT_FILES, apply_source_patch


class RemotePatchTests(unittest.TestCase):
    def test_new_runtime_modules_and_tests_are_in_release_snapshots(self):
        self.assertIn("qq-group-style.mjs", FILES)
        self.assertIn("qq-space-disk-report.mjs", FILES)
        self.assertIn("qq-chat-router.py", FILES)
        self.assertIn("qq-group-style.test.mjs", SNAPSHOT_FILES)
        self.assertIn("qq-space-disk-report.test.mjs", SNAPSHOT_FILES)
        self.assertIn("qq-conversation-audit.test.mjs", SNAPSHOT_FILES)
        self.assertIn("qq-profile-safety.test.mjs", SNAPSHOT_FILES)
        self.assertIn("qq-persona-messages.test.mjs", SNAPSHOT_FILES)

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

    def test_real_git_applies_valid_zero_context_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            target = source / "qq-persona.md"
            target.write_text("old\n", encoding="utf-8")
            diff = "--- a/qq-persona.md\n+++ b/qq-persona.md\n@@ -1 +1 @@\n-old\n+new\n"
            apply_source_patch(source, diff, git=shutil.which("git"))
            self.assertEqual(target.read_text(encoding="utf-8"), "new\n")
