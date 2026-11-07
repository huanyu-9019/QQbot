import importlib.util
import json
import hashlib
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('sender_policy', Path(__file__).parents[1] / 'plugin/policy.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class SenderBindingTests(unittest.TestCase):
    def test_distinct_accounts_do_not_inherit_name_or_relationship(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            folder = root / 'legacy/qq-user-memory'
            folder.mkdir(parents=True)
            for uid, profile in [('100', {'preferredName': '环宇', 'privateNickname': '龟仙人', 'relationships': ['情侣']}),
                                 ('200', {'preferredName': 'KAKÀ', 'relationships': []})]:
                (folder / (hashlib.sha256(('user:' + uid).encode()).hexdigest() + '.json')).write_text(json.dumps({'profile': profile}), encoding='utf-8')
            binding = p.sender_binding(root, '200', 'HandsomeTa.')
            self.assertEqual(binding['name'], 'KAKÀ')
            self.assertNotIn('情侣', binding['relationships'])
            for response in ['你是我的环宇啊。', '你是我的龟仙人啊。', '环宇，今天怎么了？']:
                self.assertTrue(p.sender_identity_conflict(response, binding), response)
            for response in ['你认识环宇吗？', '环宇是你的朋友。', '你是环宇的朋友。', '你是KAKÀ啊。']:
                self.assertFalse(p.sender_identity_conflict(response, binding), response)
            own = p.sender_binding(root, '100', '龟仙人')
            self.assertFalse(p.sender_identity_conflict('你是我的环宇啊。', own))
            self.assertIn('情侣', own['relationships'])

    def test_alias_collision_and_no_name_do_not_guess(self):
        binding = {'name': '同名', 'aliases': ['同名'], 'foreign_aliases': ['同名', '别人']}
        self.assertFalse(p.sender_identity_conflict('同名，你来了。', binding))
        self.assertTrue(p.sender_identity_conflict('你是别人。', binding))
        self.assertFalse(p.sender_identity_conflict('你是个好人。', {}))


if __name__ == '__main__':
    unittest.main()
