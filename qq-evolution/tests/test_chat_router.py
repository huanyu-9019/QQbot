import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from chat_router import RoutePool

class RoutingTests(unittest.TestCase):
 def test_failed_route_is_not_retried_for_every_message(self):
  calls=[]
  def request(route,payload):
   calls.append(route['name'])
   if route['name']=='gemini':raise RuntimeError('down')
   return b'{"choices":[{"finish_reason":"stop","message":{"content":"OK"}}]}','application/json'
  pool=RoutePool([{'name':n} for n in ['gemini','grok','deepseek-relay','deepseek']],request)
  pool.chat({});pool.chat({})
  self.assertEqual(calls,['gemini','grok','grok'])

 def test_switch_notifies_only_when_successful_active_route_changes(self):
  switches=[]
  def request(route,payload):
   return b'{"choices":[{"finish_reason":"stop","message":{"content":"OK"}}]}','application/json'
  pool=RoutePool([{'name':n} for n in ['gemini','grok']],request,on_switch=lambda old,new:switches.append((old,new)))
  pool.chat({});pool.chat({})
  pool.available[0]=False
  pool.chat({})
  self.assertEqual(switches,[('gemini','grok')])

 def test_switch_notification_failure_does_not_fail_chat(self):
  def request(route,payload):
   return b'{"choices":[{"finish_reason":"stop","message":{"content":"OK"}}]}','application/json'
  def broken(old,new):raise RuntimeError('space unavailable')
  pool=RoutePool([{'name':'first'},{'name':'second'}],lambda route,payload: (_ for _ in ()).throw(RuntimeError()) if route['name']=='first' else request(route,payload),on_switch=broken)
  body,_=pool.chat({})
  self.assertIn(b'OK',body)

 def test_health_exposes_active_model_and_last_success_time_without_keys(self):
  now=[123]
  def request(route,payload):
   return b'{"choices":[{"finish_reason":"stop","message":{"content":"OK"}}]}','application/json'
  pool=RoutePool([{'name':'gemini','model':'gemini-3.8-flash','key':'secret'}],request,clock=lambda:now[0])
  pool.chat({})
  status=pool.health()
  self.assertEqual(status['activeModel'],'gemini-3.8-flash')
  self.assertEqual(status['lastSuccess'],123)
  self.assertNotIn('secret',str(status))

 def test_last_active_route_survives_router_recreation(self):
  now=[321]
  def request(route,payload):
   return b'{"choices":[{"finish_reason":"stop","message":{"content":"OK"}}]}','application/json'
  pool=RoutePool([{'name':'grok','model':'grok-4.6'}],request,clock=lambda:now[0])
  pool.chat({})
  restored=RoutePool([{'name':'grok','model':'grok-4.6'}],request,clock=lambda:now[0],initial_state=pool.health())
  self.assertEqual(restored.health()['active'],'grok')
  self.assertEqual(restored.health()['lastSuccess'],321)
 def test_five_minute_probe_restores_priority_order(self):
  now=[0];down=[True];calls=[]
  def request(route,payload):
   calls.append(route['name'])
   if route['name']=='gemini' and down[0]:raise RuntimeError('down')
   return b'{"choices":[{"finish_reason":"stop","message":{"content":"OK"}}]}','application/json'
  pool=RoutePool([{'name':'gemini'},{'name':'deepseek'}],request,clock=lambda:now[0])
  pool.chat({});down[0]=False
  pool.probe_due();self.assertFalse(pool.health()['routes'][0]['available'])
  now[0]=300;pool.probe_due();pool.chat({})
  self.assertEqual(calls[-1],'gemini')
 def test_error_completion_falls_through_instead_of_looking_healthy(self):
  def request(route,payload):
   content='{"choices":[{"finish_reason":"error","message":{"content":"bad"}}]}' if route['name']=='gemini' else '{"choices":[{"finish_reason":"stop","message":{"content":"OK"}}]}'
   return content.encode(),'application/json'
  pool=RoutePool([{'name':'gemini'},{'name':'deepseek'}],request)
  body,_=pool.chat({});self.assertIn(b'OK',body)
  self.assertEqual(pool.health()['active'],'deepseek')
