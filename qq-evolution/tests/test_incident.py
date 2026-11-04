import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from incident import needs_repair, validate_decision, repair_incident

class IncidentTests(unittest.TestCase):
 def test_primary_down_triggers_repair_even_when_backup_works(self):
  self.assertTrue(needs_repair({'primary':False,'deepseek':True,'napcat':True,'reply':True}))
  self.assertFalse(needs_repair({'primary':True,'deepseek':True,'napcat':True,'reply':True}))
 def test_unknown_action_rejected(self):
  with self.assertRaises(ValueError):validate_decision({'action':'shell','reason':'x','diff':''})
 def test_recovery_requires_fresh_probe_after_action(self):
  calls=[]
  result=repair_incident({'primary':False,'deepseek':True,'napcat':True},
   decide=lambda h:{'action':'use_deepseek','reason':'upstream unavailable','diff':''},
   execute=lambda d:calls.append(d['action']),probe=lambda:{'primary':False,'deepseek':True,'napcat':True,'reply':True})
  self.assertEqual(calls,['use_deepseek']);self.assertEqual(result['status'],'degraded')
 def test_model_unavailable_still_runs_fixed_continuity_recovery(self):
  def broken(h):raise RuntimeError('model down')
  calls=[]
  result=repair_incident({'primary':False,'deepseek':True,'napcat':True},broken,
   lambda d:calls.append(d['action']),lambda:{'primary':True,'deepseek':True,'napcat':True,'reply':True})
  self.assertEqual(calls,['use_deepseek']);self.assertEqual(result['status'],'recovered')
