import ast,re,sys,unittest
from pathlib import Path
from types import SimpleNamespace as S
p=Path(sys.argv[1]);sys.argv=sys.argv[:1]
tree=ast.parse(p.read_text(encoding='utf-8'))
helper=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='direct_before_mention')
cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='GroupReplyAdmission')
cls.body=[next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='candidate')]
ns={'re':re,'clean_group_text':lambda s:s,'group_wakeup_settings':lambda s:s}
exec(compile(ast.Module(body=[helper,cls],type_ignores=[]),str(p),'exec'),ns)
class Admission(unittest.TestCase):
 def test_mixed_mention_and_foreign_address(self):
  obj=ns['GroupReplyAdmission']();obj.messages=S(group_context=S(authorize=lambda *x:None),tasks=S(now=lambda:0));obj._quoted_reply=lambda *x:False;obj._behavior_candidate=lambda *x:False
  context=S(actor=S(principal=S(native_account_id='sender')))
  settings={'group_wakeup_direct_words':['江生'],'group_wakeup_bot_name_enabled':False,'group_wakeup_primary_member_ids':[],'group_wakeup_enabled':True}
  for text,expected in [('江生， [提及账号 other] 是谁','direct_word'),('[提及账号 other] 江生你怎么看',''),('[提及账号 other] 你认识江生吗','')]:
   with self.subTest(text=text):self.assertEqual(obj.candidate(context,text=text,instruction='',at=0,settings=settings,participation={},mentions_others=True,continuation={'limit_reached':False,'candidate_reason':''}),expected)
if __name__=='__main__':unittest.main()
