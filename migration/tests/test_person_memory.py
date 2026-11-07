import importlib.util,sys,types,unittest,tempfile,sqlite3,json
from contextlib import closing
from pathlib import Path
PLUGIN=Path(__file__).parents[1]/'plugin'
pkg=types.ModuleType('_js_memory_test');pkg.__path__=[str(PLUGIN)];sys.modules[pkg.__name__]=pkg
spec=importlib.util.spec_from_file_location('_js_memory_test.person_memory',PLUGIN/'person_memory.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class SharedMemoryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'memory.sqlite3';self.m=mod.PersonMemory(self.path)
 def record(self,uid,turn,channel,text,direction='human',at=1):return self.m.record(uid,turn,channel,direction,text,at=at)
 def test_group_private_bidirectional_for_every_account(self):
  for uid in ['100','200']:
   self.record(uid,'private-'+uid,'private','我们是在图书馆认识的',at=1)
   self.record(uid,'group-'+uid,'group:99','约好下次去看日落',at=2)
   ctx=self.m.recall(uid,'我们怎么认识的')
   text=json.dumps(ctx,ensure_ascii=False)
   self.assertIn('图书馆',text);self.assertIn('日落',text)
   self.assertEqual({x['channel'] for x in ctx['exchanges']},{'private','group:99'})
 def test_no_identity_merging_and_no_secret_context(self):
  self.record('100','a','private','只有甲的回忆 sk-'+'x'*35)
  self.record('200','b','group:9','只有乙的回忆')
  text=json.dumps(self.m.recall('200','回忆'),ensure_ascii=False)
  self.assertNotIn('甲',text);self.assertIn('乙',text)
  text=json.dumps(self.m.recall('100','回忆'),ensure_ascii=False)
  self.assertNotIn('sk-',text);self.assertIn('REDACTED',text)
 def test_persistence_idempotency_and_confirmed_bot_evidence(self):
  self.record('100','a','private','我叫甲')
  self.record('100','a','private','我叫甲')
  self.record('100','a','private','认识你很高兴','bot',at=2)
  ctx=mod.PersonMemory(self.path).recall('100','我是谁')
  self.assertEqual(len(ctx['exchanges']),2)
  self.assertEqual({x['speaker'] for x in ctx['exchanges']},{'human','bot'})
 def test_query_retrieves_old_episode_with_bounded_context(self):
  self.record('100','old','private','约定了梧桐树下见面',at=1)
  for i in range(240):self.record('100',str(i),'group:9','今天聊天'+str(i),at=i+2)
  ctx=self.m.recall('100','梧桐树下的约定',max_chars=5000)
  text=json.dumps(ctx,ensure_ascii=False)
  self.assertIn('梧桐树',text);self.assertLessEqual(len(json.dumps(ctx,ensure_ascii=False)),5000)
 def test_does_not_mix_new_turns_with_other_subjects(self):
  self.record('100','same-turn','private','甲的内容')
  self.record('200','same-turn','private','乙的内容')
  self.assertNotIn('乙的内容',json.dumps(self.m.recall('100','内容'),ensure_ascii=False))
 def test_incremental_recorder_import_is_account_bound(self):
  p=Path(self.tmp.name)/'recorder.db'
  with closing(sqlite3.connect(p)) as db, db:
   db.execute('CREATE TABLE messages(id INTEGER PRIMARY KEY,platform TEXT,message_id TEXT,sender_id TEXT,message_str TEXT,group_id TEXT,timestamp INTEGER)')
   db.executemany('INSERT INTO messages VALUES (?,?,?,?,?,?,?)',[(1,'qq','1','100','私下认识的','','1000'),(2,'qq','2','200','乙的群消息','9','2000'),(3,'qq','3','3899701587','未核实的机器人话','9','3000')])
  self.assertEqual(self.m.import_recorder(p),3);self.assertEqual(self.m.import_recorder(p),0)
  text=json.dumps(self.m.recall('100','认识'),ensure_ascii=False)
  self.assertIn('私下认识的',text);self.assertNotIn('乙的群消息',text);self.assertNotIn('未核实',text)
 def test_full_message_search_beyond_opening_and_no_current_turn_echo(self):
  for j in range(5):self.record('100','first'+str(j),'private','最初的话题',at=j-10)
  self.record('100','old','private','普通话题'*50+'紫藤花下相遇',at=1)
  for i in range(50):self.record('100',str(i),'private','别的话题',at=i+2)
  ctx=self.m.recall('100','紫藤花',exclude_turn='49')
  self.assertTrue(any('紫藤花' in x['text'] for x in ctx['exchanges']))
  self.assertFalse(any(x['turn']=='49' for x in ctx['exchanges']))
 def test_native_memory_uses_authenticated_subject_and_active_state(self):
  p=Path(self.tmp.name)/'native.db'
  def enc(x):return json.dumps(x,sort_keys=True,ensure_ascii=True,separators=(',',':'))
  import hashlib
  owner=hashlib.sha256(enc(['inst','bot','role','subject-a','private']).encode()).hexdigest()
  with closing(sqlite3.connect(p)) as db,db:
   db.execute('CREATE TABLE identity_bindings(installation_id TEXT,bot_id TEXT,native_account_id TEXT,payload_json TEXT)')
   db.execute('CREATE TABLE memory_atoms(atom_id TEXT,owner_key TEXT,state TEXT,record_json TEXT,updated_at TEXT)')
   db.execute('CREATE TABLE relationship_memories(state TEXT,owner_json TEXT,subject_json TEXT,record_json TEXT,updated_at TEXT)')
   db.execute('INSERT INTO identity_bindings VALUES (?,?,?,?)',('inst','bot','100',enc({'subject':{'kind':'human','subject_id':'subject-a'}})))
   for key,state,word in [(owner,'active','同一人的经历'),(owner,'invalidated','已撤回内容'),('wrong','active','别人的经历')]:
    db.execute('INSERT INTO memory_atoms VALUES (?,?,?,?,?)',(word,key,state,enc({'proposal':{'representation':word}}),'2026-11-08'))
   db.execute('INSERT INTO relationship_memories VALUES (?,?,?,?,?)',('adopted',enc({'installation_id':'inst','bot_id':'bot','persona_id':'role'}),enc({'subject_id':'subject-a'}),enc({'interpretation':'我们的关系理解'}),'2026-11-08'))
  text=json.dumps(mod.native_memories(p,'100',installation='inst',bot='bot',role='role'),ensure_ascii=False)
  self.assertIn('同一人的经历',text);self.assertIn('我们的关系理解',text)
  self.assertNotIn('撤回',text);self.assertNotIn('别人',text)
  self.assertEqual(mod.native_memories(p,'200',installation='inst',bot='bot',role='role'),[])
if __name__=='__main__':unittest.main()
