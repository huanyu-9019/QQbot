import ast,re,sys,unittest
from pathlib import Path
from types import SimpleNamespace as S
p=Path(sys.argv[1]);sys.argv=sys.argv[:1];tree=ast.parse(p.read_text(encoding='utf-8-sig'))
helper=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='direct_before_mention')
cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='GroupReplyAdmission');cls.body=[next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='candidate')]
ns={'re':re,'clean_group_text':lambda s:s.strip(),'group_wakeup_settings':lambda s:s,'image_wakeup_candidate':lambda *a,**k:False,'stamp':lambda x:'now'}
exec(compile(ast.Module(body=[helper,cls],type_ignores=[]),str(p),'exec'),ns)
class ActiveGroup(unittest.TestCase):
 def candidate(self,text,*,limited=False,other=False,enabled=True):
  obj=ns['GroupReplyAdmission']();obj.messages=S(group_context=S(authorize=lambda *x:None),tasks=S(now=lambda:0));obj._quoted_reply=lambda *x:False;obj._behavior_candidate=lambda *x:False;obj.observations={};obj._key=lambda c:'g';obj.question_reference=lambda *a,**k:{'score':0}
  context=S(actor=S(principal=S(native_account_id='user')))
  settings={'group_wakeup_direct_words':['江生'],'group_wakeup_bot_name_enabled':False,'group_wakeup_primary_member_ids':[],'group_wakeup_enabled':enabled,'group_wakeup_question_enabled':False,'group_wakeup_context_words':[],'group_wakeup_interest_keywords':[],'group_wakeup_cold_group_enabled':False}
  return obj.candidate(context,text=text,instruction='',at=0,settings=settings,participation={'enable_group_repeat_follow':False,'enable_group_interjection':False},mentions_others=other,continuation={'limit_reached':limited,'candidate_reason':''})
 def test_ordinary_unmentioned_group_messages_reach_model(self):
  for text in ['我有两个服务器','第一次见','这种贴图bug','哈哈','今天好累']:
   self.assertEqual(self.candidate(text),'role_choice')
 def test_followup_limit_is_not_a_global_mute(self):self.assertEqual(self.candidate('我们换个话题，晚上吃什么',limited=True),'role_choice')
 def test_explicit_address_still_first(self):self.assertEqual(self.candidate('江生，记得我吗',limited=True),'direct_word')
 def test_other_address_and_disabled_wakeup_stay_silent(self):
  self.assertEqual(self.candidate('你怎么看',other=True),'');self.assertEqual(self.candidate('普通群话题',enabled=False),'')
 def test_empty_and_punctuation_do_not_generate_empty_replies(self):
  for text in ['', '???','。。。']:self.assertEqual(self.candidate(text),'')
if __name__=='__main__':unittest.main()
