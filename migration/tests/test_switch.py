import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).parents[1] / 'switch.py'


class CutoverTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.exists(), 'verified cutover/rollback implementation is missing')
        spec = importlib.util.spec_from_file_location('migration_switch', SOURCE)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.live = {'qq-hermes-bridge.service'}
        self.calls = []

    def execute(self, action, unit):
        self.calls.append((action, unit))
        if action == 'stop':
            self.live.discard(unit)
        if action == 'start':
            self.live.add(unit)
        self.assertFalse({'qq-hermes-bridge.service', 'jiangsheng-astrbot.service'} <= self.live,
                         'two QQ responders were active at the same time')

    def test_no_cutover_without_acceptance(self):
        with self.assertRaises(ValueError):
            self.m.cutover(self.execute, lambda: True, acceptance={})
        self.assertEqual([], self.calls)

    def test_failed_new_runtime_restores_old_responder(self):
        with self.assertRaises(RuntimeError):
            self.m.cutover(self.execute, lambda: False, acceptance=dict.fromkeys(self.m.REQUIRED, True))
        self.assertEqual({'qq-hermes-bridge.service'}, self.live)

    def test_healthy_new_runtime_changes_boot_policy(self):
        self.m.cutover(self.execute, lambda: True, acceptance=dict.fromkeys(self.m.REQUIRED, True))
        self.assertEqual({'jiangsheng-astrbot.service'}, self.live)
        self.assertIn(('enable', 'jiangsheng-astrbot.service'), self.calls)
        self.assertIn(('disable', 'qq-hermes-bridge.service'), self.calls)

    def test_rollback_stops_new_before_starting_old(self):
        self.live = {'jiangsheng-astrbot.service'}
        self.m.rollback(self.execute)
        self.assertEqual({'qq-hermes-bridge.service'}, self.live)

    def test_connection_failure_restores_original_napcat_and_only_old_responder(self):
        connected = []
        def connect(enabled):
            connected.append(enabled)
            if enabled:
                raise RuntimeError('NapCat reload failed')
        with self.assertRaises(RuntimeError):
            self.m.cutover(self.execute, lambda: True, acceptance=dict.fromkeys(self.m.REQUIRED, True), connect=connect)
        self.assertEqual([True, False], connected)
        self.assertEqual({'qq-hermes-bridge.service'}, self.live)


if __name__ == '__main__':
    unittest.main()
