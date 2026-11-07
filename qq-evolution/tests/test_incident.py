import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
import incident
from incident import needs_repair, validate_decision, repair_incident

class IncidentTests(unittest.TestCase):
 def test_native_learning_failure_is_not_reported_healthy(self):
  self.assertTrue(needs_repair({'api':True,'napcat':True,'reply':True,'learningHealthy':False}))
 def test_astrbot_vision_health_uses_fresh_route_probes(self):
  runtime={'runtime':'astrbot','vision':False,'router':{'routes':[{'visionAvailable':True,'visionCheckedAt':incident.time.time()}]}}
  with patch.object(incident,'remote_script',return_value=runtime),patch.object(incident,'_legacy_probe_health',return_value={'visionProbeRaw':False}):
   result=incident.probe_health()
  self.assertTrue(result['vision'])

 def test_vision_probe_status_rejects_stale_or_failed_routes(self):
  self.assertEqual(incident.vision_probe_status({'routes':[{'visionAvailable':True,'visionCheckedAt':50}]},now=1000), (False,50))
  self.assertEqual(incident.vision_probe_status({'routes':[{'visionAvailable':False,'visionCheckedAt':995}]},now=1000), (False,995))

 def test_primary_down_does_not_interrupt_healthy_fallback(self):
  self.assertFalse(needs_repair({'primary':False,'deepseek':True,'api':True,'napcat':True,'reply':True}))
  self.assertFalse(needs_repair({'primary':True,'deepseek':True,'api':True,'napcat':True,'reply':True}))
  self.assertTrue(needs_repair({'primary':True,'deepseek':True,'api':False,'napcat':True,'reply':True}))
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
   lambda d:calls.append(d['action']),lambda:{'primary':True,'deepseek':True,'api':True,'napcat':True,'reply':True})
  self.assertEqual(calls,['use_deepseek']);self.assertEqual(result['status'],'recovered')


class SharedMemoryIncidentTests(unittest.TestCase):
 def test_shared_memory_failure_is_not_healthy_just_because_reply_works(self):
  self.assertTrue(needs_repair({'api':True,'napcat':True,'reply':True,'sharedMemoryReady':False}))


class PreservedBaselineTests(unittest.TestCase):
 def test_primary_down_does_not_trigger_repair_when_fallback_replies(self):
  self.assertFalse(needs_repair({'primary':False,'deepseek':True,'api':True,'napcat':True,'reply':True,'unanswered':0}))
  self.assertFalse(needs_repair({'primary':True,'deepseek':True,'api':True,'napcat':True,'reply':True,'unanswered':0}))

 def test_unavailable_chat_routes_trigger_repair(self):
  self.assertTrue(needs_repair({'primary':False,'deepseek':False,'api':True,'napcat':True,'reply':False}))

 def test_overdue_unanswered_turns_trigger_repair(self):
  self.assertTrue(needs_repair({'api':True,'napcat':True,'reply':False,'unanswered':1}))
