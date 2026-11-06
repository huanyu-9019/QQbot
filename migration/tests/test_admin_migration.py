import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch


class AdminMigrationTest(unittest.TestCase):
    def test_legacy_restart_buttons_target_astrbot_after_cutover(self):
        source = Path(__file__).parents[1] / 'admin/action.py'
        self.assertTrue(source.exists(), 'runtime-aware admin action helper missing')
        spec = importlib.util.spec_from_file_location('migration_admin', source)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        with patch.object(m, 'is_astrbot', return_value=True), \
             patch.object(m, 'service_state', return_value={'active': True}), \
             patch.object(m, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')) as run:
            for service in ['hermes-api', 'qq-bridge']:
                m.restart_checked(service)
                self.assertEqual('jiangsheng-astrbot.service', run.call_args.args[0][-1])
        with patch.object(m, 'is_astrbot', return_value=True):
            with self.assertRaises(m.ActionError):
                m.set_model('unused-legacy-model')
