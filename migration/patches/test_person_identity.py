import ast,sys,unittest,json
from pathlib import Path
from types import SimpleNamespace as S
p=Path(sys.argv[1]);sys.argv=sys.argv[:1];tree=ast.parse(p.read_text(encoding='utf-8'));cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and any(isinstance(x,ast.FunctionDef) and x.name=='projection' for x in n.body));func=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='projection');ns={'display_name':lambda d,s:('群名片','group'),'aggregate':lambda d:dict(msg_count=3,active_days=1,first_seen='x',last_seen='y'),'legacy_nickname':lambda d:None,'known_names':lambda d,s:[],'encode':json.dumps};exec(compile(ast.Module(body=[func],type_ignores=[]),str(p),'exec'),ns)
class PersonCard(unittest.TestCase):
 def test_only_boolean_crosses_private_boundary(self):
  for contexts,expected in [({'private':{'secret':'PRIVATE_CONTENT'}},True),({},False)]:
   payload=ns['projection'](None,S(scope=None),{'native_account_id':'current','contexts':contexts},budget=4096)
   self.assertEqual(payload['private_contact_known'],expected);self.assertNotIn('PRIVATE_CONTENT',json.dumps(payload));self.assertEqual(payload['native_account_id'],'current')
 def test_familiarity_survives_group_projection_without_private_details(self):
  cases=[({'private':{'msg_count':12,'secret':'DO_NOT_EXPORT'}},False,'repeated_contact'),({'private':{'msg_count':1}},False,'contact'),({},True,'contact'),({},False,'unknown')]
  for contexts,legacy,expected in cases:
   with self.subTest(expected=expected):
    payload=ns['projection'](None,S(scope=None),{'native_account_id':'current','contexts':contexts,'legacy_private_contact':legacy},budget=4096)
    self.assertEqual(payload['private_familiarity'],expected)
    self.assertNotIn('DO_NOT_EXPORT',json.dumps(payload))
if __name__=='__main__':unittest.main()
