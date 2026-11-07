import importlib.util
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).parents[1] / 'plugin' / 'policy.py'


class MigrationPolicyTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.exists(), 'migration attribution and audit policy is missing')
        spec = importlib.util.spec_from_file_location('migration_policy', SOURCE)
        self.p = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.p)

    def test_other_person_mention_is_not_for_bot(self):
        msg = [{'type': 'at', 'data': {'qq': '2512930532'}},
               {'type': 'text', 'data': {'text': '你叫什么名字'}}]
        self.assertFalse(self.p.may_reply(msg, '3899701587', group=True))
        msg.insert(0, {'type': 'at', 'data': {'qq': '3899701587'}})
        self.assertTrue(self.p.may_reply(msg, '3899701587', group=True))

    def test_plain_conversation_left_to_companion_and_private_allowed(self):
        msg = [{'type': 'text', 'data': {'text': '（缓慢走到你身边）'}}]
        self.assertTrue(self.p.may_reply(msg, '3899701587', group=True))
        self.assertTrue(self.p.may_reply([{'type': 'at', 'data': {'qq': 'other'}}], '3899701587', group=False))

    def test_private_replies_drop_redundant_opening_ack_but_preserve_standalone_ack(self):
        self.assertEqual(self.p.remove_redundant_private_ack('嗯……那就休息吧。'), '那就休息吧。')
        self.assertEqual(self.p.remove_redundant_private_ack('嗯，在呢。'), '在呢。')
        self.assertEqual(self.p.remove_redundant_private_ack('嗯？老公～'), '嗯？老公～')
        self.assertEqual(self.p.remove_redundant_private_ack('嗯。'), '嗯。')
        self.assertEqual(self.p.remove_redundant_private_ack('我知道。'), '我知道。')

    def test_dedup_survives_restart_and_does_not_collide_across_platforms(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'seen.sqlite3'
            self.assertTrue(self.p.claim_message(path, 'qq', '123'))
            self.assertFalse(self.p.claim_message(path, 'qq', '123'))
            self.assertTrue(self.p.claim_message(path, 'second', '123'))

    def test_names_public_context_and_equality(self):
        profile = {'preferredName': '钟丰鸾', 'groupNicknames': {'737563998': '黄金圣斗豪'},
                   'relationships': ['我的主人', '同学'], 'preferences': ['私聊秘密'],
                   'privateNickname': '私聊专用昵称'}
        group = self.p.profile_context(profile, group_id='737563998')
        self.assertIn('钟丰鸾', group)
        self.assertIn('黄金圣斗豪', group)
        for secret in ['主人', '私聊秘密', '私聊专用昵称']:
            self.assertNotIn(secret, group)
        self.assertIn('同学', self.p.profile_context(profile))
        self.assertNotIn('主人', self.p.profile_context(profile))

    def test_secrets_never_enter_analysis(self):
        text = 'token=some-private-value sk-' + 'a' * 40 + ' Authorization: Bearer abcdef1234'
        safe = self.p.redact(text)
        for secret in ['some-private-value', 'a' * 40, 'abcdef1234']:
            self.assertNotIn(secret, safe)

    def test_quality_guard_allows_english_requests(self):
        self.assertEqual('analysis_leak', self.p.quality_issue('Initial assessment: The user expresses confusion', '你在吗'))
        self.assertIsNone(self.p.quality_issue('Hello there. ' * 20, '帮我翻译成英文'))
        self.assertEqual('unexpected_english', self.p.quality_issue('Hello there. ' * 20, '你在吗'))

    def test_sent_requires_real_receipt(self):
        self.assertFalse(self.p.confirmed_send({'status': 'ok', 'data': {}}))
        self.assertFalse(self.p.confirmed_send({'message_id': 123, 'retcode': 100}))
        self.assertTrue(self.p.confirmed_send({'message_id': 123}))
        self.assertTrue(self.p.confirmed_send({'status': 'ok', 'retcode': 0, 'data': {'message_id': 123}}))

    def test_legacy_summary_removes_unequal_claims_and_credentials(self):
        value = self.p.legacy_summary({'summary': '大家聊到下周考试\n某人是江生的主人\ntoken=private-value'})
        self.assertIn('下周考试', value)
        self.assertNotIn('主人', value)
        self.assertNotIn('private-value', value)


if __name__ == '__main__':
    unittest.main()
