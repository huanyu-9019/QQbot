import importlib.util
import tempfile
import time
import unittest
from pathlib import Path


class RuntimeSupportTest(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).parents[2] / 'qq-evolution/runtime_support.py'
        self.assertTrue(source.exists(), 'AstrBot maintenance integration missing')
        spec = importlib.util.spec_from_file_location('runtime_support', source)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)

    def test_old_runtime_not_used_when_astrbot_is_selected(self):
        self.assertEqual('jiangsheng-astrbot.service', self.m.responder_unit('astrbot'))
        self.assertEqual('qq-hermes-bridge.service', self.m.responder_unit('hermes'))

    def test_disconnected_or_test_heartbeat_cannot_report_production_healthy(self):
        now = time.time()
        state = {'timestamp': now, 'qqConnected': True, 'companionReady': True, 'acceptance': True}
        self.assertFalse(self.m.runtime_ready(state, now))
        state['acceptance'] = False
        self.assertTrue(self.m.runtime_ready(state, now))
        self.assertFalse(self.m.runtime_ready(state, now + 60))
        state['qqConnected'] = False
        self.assertFalse(self.m.runtime_ready(state, now))
