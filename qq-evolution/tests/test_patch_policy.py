import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from patch_policy import changed_paths


class PatchPolicyTests(unittest.TestCase):
    def test_accepts_complete_text_hunk_for_existing_allowlisted_path(self):
        patch = '--- a/qq-persona.md\n+++ b/qq-persona.md\n@@ -1 +1 @@\n-old\n+new\n'
        self.assertEqual(changed_paths(patch, {'qq-persona.md'}), ['qq-persona.md'])

    def test_rejects_hidden_second_target_metadata_and_malformed_hunks(self):
        patch = '--- a/qq-persona.md\n+++ b/qq-persona.md\n@@ -1 +1 @@\n-old\n+new\n'
        attacks = [
            patch + '--- /etc/passwd\n+++ /etc/passwd\n@@ -1 +1 @@\n-root\n+bad\n',
            patch + 'diff --git a/x b/x\nnew file mode 120000\n',
            patch.replace('@@ -1 +1 @@', '@@ -1,9 +1 @@'),
            patch.replace('qq-persona.md', '../qq-persona.md'),
            patch.replace('qq-persona.md', 'qq-unlisted.mjs'),
            patch.replace('+++ b/qq-persona.md', '+++ b/qq-memory.mjs'),
            patch + 'arbitrary trailing commands\n',
        ]
        for attack in attacks:
            with self.subTest(attack=attack):
                with self.assertRaises(ValueError):
                    changed_paths(attack, {'qq-persona.md'})

    def test_accepts_two_independent_allowlisted_files(self):
        patch = ('--- a/qq-persona.md\n+++ b/qq-persona.md\n@@ -1 +1 @@\n-a\n+b\n'
                 '--- a/qq-live-facts.mjs\n+++ b/qq-live-facts.mjs\n@@ -2 +2 @@\n-a\n+b\n')
        self.assertEqual(changed_paths(patch, {'qq-persona.md', 'qq-live-facts.mjs'}), ['qq-persona.md', 'qq-live-facts.mjs'])
