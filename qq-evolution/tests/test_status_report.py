import sys
import unittest
from unittest.mock import patch
import subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from status_report import report_slot, format_report, remote_script, publish_event, production_probe_script

class StatusReportTests(unittest.TestCase):
    def test_five_minutes_for_two_hours_then_four_hours(self):
        start=1000000000
        self.assertEqual(report_slot(start,start+299),'fast-0')
        self.assertEqual(report_slot(start,start+300),'fast-1')
        self.assertEqual(report_slot(start,start+7199),'fast-23')
        self.assertEqual(report_slot(start,start+7200),'slow-0')
        self.assertEqual(report_slot(start,start+7200+14399),'slow-0')
        self.assertEqual(report_slot(start,start+7200+14400),'slow-1')

    def test_report_is_short_and_distinguishes_monitor_from_bot(self):
        sample={'memoryFree':500,'memoryTotal':890,'diskFree':22,'diskTotal':29,'swapFree':2048,'swapTotal':2048,'online':True}
        text=format_report(sample|{'monitor':'正常','evaluation':'正常'},sample|{'bridge':True,'api':False},0)
        self.assertIn('监听正常',text)
        self.assertIn('API异常',text)
        self.assertLessEqual(len(text),140)
        self.assertNotIn('root@',text)

    def test_active_services_with_failed_models_are_reported_unhealthy(self):
        sample={'memoryFree':500,'memoryTotal':890,'diskFree':22,'diskTotal':29,'swapFree':2048,'swapTotal':2048,'online':True}
        text=format_report(sample|{'monitor':'正常','evaluation':'正常'},sample|{'bridge':True,'api':True,'model':{'reply':False,'primary':False,'deepseek':False}},0)
        self.assertIn('回复链异常',text)
        self.assertIn('主链故障',text)

    def test_transient_ssh_failure_retries_and_returns_real_result(self):
        failed=subprocess.CompletedProcess([],255,'','connection failed')
        success=subprocess.CompletedProcess([],0,'{"sent": true}','')
        with patch('status_report.subprocess.run',side_effect=[failed,success]) as run:
            self.assertEqual(remote_script('script'),{'sent':True})
            self.assertEqual(run.call_count,2)

    def test_failed_ssh_never_becomes_a_successful_report(self):
        failed=subprocess.CompletedProcess([],255,'','connection failed')
        with patch('status_report.subprocess.run',return_value=failed):
            with self.assertRaises(RuntimeError):
                remote_script('script')


class PreservedBaselineTests(unittest.TestCase):
    def test_iteration_update_requires_valid_space_event_and_reports_confirmation(self):
        with patch('status_report.remote_script', return_value={'sent': True}) as remote:
            self.assertTrue(publish_event('qq-learn-2', '江生学习#2：减少重复表达。本轮没有代码改动，未重跑测试；沿用最近验证版本。'))
            self.assertIn('qq-learn-2', remote.call_args.args[0])
        with self.assertRaises(ValueError):
            publish_event('../bad', 'invalid')

    def test_generated_production_probe_is_valid_python_and_checks_pending_turns(self):
        script = production_probe_script()
        compile(script, "production-probe", "exec")
        self.assertIn("direction=='failed'", script)
        self.assertIn("unanswered", script)
        self.assertIn("import urllib.request", script)

    def test_half_hour_iterations_include_reasoned_no_change_events(self):
        from scheduler import iteration_due,record_iteration
        self.assertFalse(iteration_due({'lastIteration':100},100+899))
        self.assertTrue(iteration_due({'lastIteration':100},100+900))
        state={};record_iteration(state,now=1900,updated=False,reason='No measurable improvement passed the quality gate')
        self.assertEqual(state['iterationCount'],1)
        self.assertEqual(state['updateKind'],'learning_record')


