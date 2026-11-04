import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from status_report import report_slot, format_report

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
        self.assertIn('回复异常',text)
        self.assertIn('主链故障',text)
