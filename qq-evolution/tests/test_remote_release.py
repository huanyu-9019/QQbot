import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from remote_release import apply_source_patch


class RemotePatchTests(unittest.TestCase):
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
