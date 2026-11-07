import sys,importlib.util,unittest
from pathlib import Path
p=Path(sys.argv[1]);sys.argv=sys.argv[:1];spec=importlib.util.spec_from_file_location('policy',p);policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)
class MixedMention(unittest.TestCase):
 def test_address_bot_to_identify_other_member(self):
  s=[{'type':'text','data':{'text':'江生， '}},{'type':'at','data':{'qq':'other'}},{'type':'text','data':{'text':' 是谁'}}]
  self.assertTrue(policy.may_reply(s,'bot',group=True))
 def test_address_other_member_stays_silent(self):
  for text in ['江生你怎么看','你认识江生吗']:
   self.assertFalse(policy.may_reply([{'type':'at','data':{'qq':'other'}},{'type':'text','data':{'text':text}}],'bot',group=True))
 def test_identity_is_scoped_to_sender(self):
  self.assertEqual(policy.identity_answer('我是谁',{'preferredName':'甲'},'昵称乙'),'你是甲。')
  self.assertEqual(policy.identity_answer('我是谁',{},'昵称乙'),'你现在的群名片是昵称乙；还没确认你想让我怎么称呼你。')
  self.assertIsNone(policy.identity_answer('他是谁',{'preferredName':'甲'},'昵称乙'))
if __name__=='__main__':unittest.main()
