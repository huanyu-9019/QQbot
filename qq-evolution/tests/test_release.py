import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parents[1]))
from release import ReleaseManager, create_snapshot, validate_patch


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

    def test_failed_health_check_restores_previous_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            snapshots = Path(tmp) / "snapshots"
            source.mkdir()
            file = source / "qq-persona.md"
            file.write_text("old", encoding="utf-8")
            manager = ReleaseManager(source, snapshots, ["qq-persona.md"], restart=lambda: None, health=lambda: False)
            artifact = "--- a/qq-persona.md\n+++ b/qq-persona.md\n@@ -1 +1 @@\n-old\n+new\n"
            with self.assertRaises(RuntimeError):
                manager.apply(artifact)
            self.assertEqual(file.read_text(encoding="utf-8"), "old")


if __name__ == "__main__":
    unittest.main()
