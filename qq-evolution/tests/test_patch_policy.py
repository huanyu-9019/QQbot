import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from patch_policy import changed_paths, recount_hunks


class PatchPolicyTests(unittest.TestCase):
    def test_recounts_only_hunk_metadata_and_still_rejects_hidden_targets(self):
        patch = '--- a/qq-persona.md\n+++ b/qq-persona.md\n@@ -1,9 +1,8 @@\n-old\n+new\n'
        fixed = recount_hunks(patch)
        self.assertEqual(fixed, patch.replace('@@ -1,9 +1,8 @@', '@@ -1,1 +1,1 @@'))
        self.assertEqual(changed_paths(fixed, {'qq-persona.md'}), ['qq-persona.md'])
        with self.assertRaises(ValueError):
            changed_paths(recount_hunks(patch + 'RUN arbitrary\n'), {'qq-persona.md'})
        with self.assertRaises(ValueError):
            changed_paths(recount_hunks(patch.replace('qq-persona.md', '../secret')), {'qq-persona.md'})

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

    def test_accepts_git_style_diff_with_metadata_but_rejects_modes_and_renames(self):
        patch = ('diff --git a/qq-persona.md b/qq-persona.md\nindex 1234567..abcdef0 100644\n'
                 '--- a/qq-persona.md\n+++ b/qq-persona.md\n@@ -1 +1 @@\n-old\n+new\n')
        self.assertEqual(changed_paths(patch, {'qq-persona.md'}), ['qq-persona.md'])
        for extra in ('new file mode 100644\n', 'old mode 100644\nnew mode 100755\n', 'rename from a\nrename to b\n'):
            with self.assertRaises(ValueError):
                changed_paths(patch.replace('@@ -1', extra + '@@ -1'), {'qq-persona.md'})
