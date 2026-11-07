"""Exercise the actual production hook bodies with isolated transport and storage."""
import ast,asyncio,contextvars,hashlib,json,re,tempfile,time,types,unittest,sys
from pathlib import Path
PLUGIN=Path(__file__).parents[1]/'plugin'
pkg=types.ModuleType('_js_hook_test');pkg.__path__=[str(PLUGIN)];sys.modules[pkg.__name__]=pkg
from importlib import import_module
mem=import_module('_js_hook_test.person_memory');policy=import_module('_js_hook_test.policy')
tree=ast.parse((PLUGIN/'main.py').read_text(encoding='utf-8'))
cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='JiangshengMigration')
cls.bases=[];cls.decorator_list=[];cls.body=[n for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in ('patch_client','remember','shared_person_context','imported_facts','generated')]
for n in cls.body:n.decorator_list=[]
current=contextvars.ContextVar('current',default=None)
ns={'asyncio':asyncio,'json':json,'hashlib':hashlib,'time':time,'re':re,'current_message_event':current,'native_memories':mem.native_memories,'SHARED_MEMORY_INSTRUCTION':mem.INSTRUCTION,**{k:getattr(policy,k) for k in ('quality_issue','confirmed_send','profile_context','legacy_summary','identity_answer','sender_binding','sender_identity_conflict')}}
exec(compile(ast.Module(body=[cls],type_ignores=[]),'live-hooks','exec'),ns)
class Event:
 def __init__(self,uid='100',group='9'):
  self.uid=uid;self.group=group;self.message_str='我们怎么认识的';self.extras={'jiangsheng_turn':'jiangsheng:123','jiangsheng_llm_started':True};self.message_obj=types.SimpleNamespace(raw_message={'message':[]})
 def get_sender_id(self):return self.uid
 def get_group_id(self):return self.group
 def get_self_id(self):return '3899701587'
 def get_sender_name(self):return '当前名片'
 def get_extra(self,k):return self.extras.get(k)
 def set_extra(self,k,v):self.extras[k]=v
class Hooks(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.obj=ns['JiangshengMigration']();self.obj.root=Path(self.tmp.name);self.obj.person_memory=mem.PersonMemory(self.obj.root/'m.db');self.obj.shared_memory_error=None;self.obj.patched=[];self.obj.write=lambda *a,**k:None;self.obj.voice_requested=lambda e:False
 async def test_group_request_receives_same_account_private_experience(self):
  self.obj.person_memory.record('100','old','private','human','我们在海边认识，还说好一起看星星',at=1)
  self.obj.person_memory.record('200','wrong','private','human','只有别人的经历',at=1)
  event=Event();req=types.SimpleNamespace(system_prompt='')
  await self.obj.imported_facts(event,req)
  self.assertIn('海边认识',req.system_prompt);self.assertIn('看星星',req.system_prompt);self.assertNotIn('只有别人的经历',req.system_prompt)
  self.assertTrue(event.get_extra('jiangsheng_shared_memory'))
 async def test_only_confirmed_qq_delivery_is_archived_as_bot_speech(self):
  for ok in (False,True):
   async def call(action,**params):return {'retcode':0,'status':'ok','data':{'message_id':7}} if ok else {'retcode':1,'status':'failed'}
   bot=types.SimpleNamespace(call_action=call);self.obj.patch_client(bot);event=Event();token=current.set(event)
   try:
    if ok:await bot.call_action('send_group_msg',group_id='9',message=[{'type':'text','data':{'text':'我当然记得海边的那次'}}])
    else:
     with self.assertRaises(RuntimeError):await bot.call_action('send_group_msg',group_id='9',message=[{'type':'text','data':{'text':'不该被记住的未送达内容'}}])
   finally:current.reset(token)
  result=json.dumps(self.obj.person_memory.recall('100','海边'),ensure_ascii=False)
  self.assertIn('海边的那次',result);self.assertNotIn('未送达内容',result)
 async def test_wrong_bot_name_is_not_recalled_as_personal_evidence(self):
  self.obj.person_memory.record('100','wrong','group:9','bot','你是我的环宇啊。',at=1)
  event=Event();event.set_extra('jiangsheng_sender_binding',{'name':'KAKÀ','aliases':['KAKÀ'],'foreign_aliases':['环宇']})
  context=await self.obj.shared_person_context(event)
  self.assertNotIn('你是我的环宇啊',context)
 async def test_response_guard_and_transport_do_not_send_foreign_identity(self):
  event=Event();event.set_extra('jiangsheng_sender_binding',{'name':'KAKÀ','aliases':['KAKÀ'],'foreign_aliases':['环宇']})
  response=types.SimpleNamespace(completion_text='你是我的环宇啊。')
  await self.obj.generated(event,response)
  self.assertIn('KAKÀ',response.completion_text)
  self.assertNotIn('你是我的',response.completion_text)
  calls=[]
  async def call(action,**params):calls.append(params);return {'message_id':7}
  bot=types.SimpleNamespace(call_action=call);self.obj.patch_client(bot);token=current.set(event)
  try:
   with self.assertRaises(ValueError):
    await bot.call_action('send_group_msg',group_id='9',message='你是我的环宇啊。')
  finally:current.reset(token)
  self.assertEqual(calls,[])
if __name__=='__main__':unittest.main()

