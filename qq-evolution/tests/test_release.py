import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parents[1]))
from release import create_snapshot, validate_patch


class ReleaseTests(unittest.TestCase):
    def test_validate_patch_requires_allowlisted_files(self):
        self.assertTrue(validate_patch("--- a/qq-persona.md\n+++ b/qq-persona.md\n@@ -1 +1 @@\n-a\n+b\n"))
        self.assertFalse(validate_patch("--- a/.env\n+++ b/.env\n@@ -1 +1 @@\n-a\n+b\n"))

    def test_snapshot_writes_manifest_with_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            snapshots = Path(tmp) / "snapshots"
            source.mkdir()
            (source / "qq-persona.md").write_text("hello", encoding="utf-8")
            manifest = create_snapshot(source, snapshots, ["qq-persona.md"])
            self.assertEqual(manifest["files"][0]["path"], "qq-persona.md")
            self.assertTrue((snapshots / manifest["id"] / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
