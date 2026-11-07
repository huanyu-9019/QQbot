import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('reply_routing', Path(__file__).parents[1] / 'reply_routing.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReplyRoutingTests(unittest.TestCase):
    def test_companion_owns_bare_name_and_mention_without_changing_other_settings(self):
        config = {'wake_prefix': ['江生', '@江生'], 'platform_settings': {'empty_mention_waiting': True, 'ignore_bot_self_message': True}, 'provider': ['existing-route']}
        module.companion_owns_wakeup(config)
        self.assertEqual(config['wake_prefix'], [])
        self.assertFalse(config['platform_settings']['empty_mention_waiting'])
        self.assertFalse(config['platform_settings']['empty_mention_waiting_need_reply'])
        self.assertTrue(config['platform_settings']['ignore_bot_self_message'])
        self.assertEqual(config['provider'], ['existing-route'])
