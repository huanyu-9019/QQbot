import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


class RetentionTest(unittest.TestCase):
    def test_media_quota_keeps_new_files_and_does_not_follow_symlinks(self):
        source = Path(__file__).parents[1] / 'plugin/retention.py'
        self.assertTrue(source.exists(), 'bounded media retention missing')
        spec = importlib.util.spec_from_file_location('retention', source)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'media'
            root.mkdir()
            for name, at in [('old', 10), ('new', 20)]:
                (root / name).write_bytes(b'a' * 8)
                os.utime(root / name, (at, at))
            outside = Path(tmp) / 'database.sqlite'
            outside.write_bytes(b'valuable')
            result = m.prune_media(root, max_bytes=10, max_age=100, now=30)
            self.assertFalse((root / 'old').exists())
            self.assertTrue((root / 'new').exists())
            self.assertEqual(b'valuable', outside.read_bytes())
            self.assertEqual(8, result['bytes'])
