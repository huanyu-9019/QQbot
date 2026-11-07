import ast,json,sys,unittest
from pathlib import Path
from types import SimpleNamespace as N
p=Path(sys.argv[1]);sys.argv=sys.argv[:1]
tree=ast.parse(p.read_text(encoding='utf-8'));method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_request')
def request(*a,**kw):return N(**kw)
ns={'PromptRequest':request,'PromptMaterial':lambda *a:a,'BackgroundPromptTrigger':lambda *a:a,'SealedForegroundContext':lambda *a:a,'encode':json.dumps,'redact_material':lambda x:x,'learning_instruction':lambda *a:'contract','learning':N(schema=lambda n:{'type':'object','limit':n}),'OWNER':'test'}
exec(compile(ast.Module(body=[method],type_ignores=[]),str(p),'exec'),ns)
class LearningWire(unittest.TestCase):
 def test_learning_uses_its_structured_schema(self):
  job={'context':N(scope=N(kind=N(value='group')),actor=N(principal='p'),role_binding='r'),'sample_document':{},'catalogue':[],'request_key':'k','at':0,'instruction':'persona','policy':N(learning_mode='light')}
  r=ns['_request'](None,job,[],2)
  self.assertEqual(getattr(r,'response_format','text'),'json_schema')
  self.assertEqual(json.loads(r.response_schema_json),{'type':'object','limit':2})
if __name__=='__main__':unittest.main()
