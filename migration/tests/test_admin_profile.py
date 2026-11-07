import importlib.util
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest


class NativeProfileTests(unittest.TestCase):
    def test_reads_only_requested_person_active_facts_with_evidence_and_keeps_db_readonly(self):
        spec = importlib.util.spec_from_file_location('admin_action', Path(__file__).parents[1] / 'admin/action.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'memory.sqlite3'
            with closing(sqlite3.connect(path)) as db, db:
                db.execute('CREATE TABLE identity_bindings(installation_id TEXT,bot_id TEXT,native_account_id TEXT,payload_json TEXT)')
                db.execute('CREATE TABLE memory_atoms(atom_id TEXT,owner_key TEXT,state TEXT,subject TEXT,record_json TEXT,updated_at TEXT,revision INTEGER)')
                import hashlib
                inst = 'astrbot-private-companion-v2:multi:jiangsheng'
                bot = 'bot-3899701587'
                owner_a = hashlib.sha256(json.dumps([inst,bot,'jiangsheng','person-a','private'],sort_keys=True,ensure_ascii=True,separators=(',',':')).encode()).hexdigest()
                db.execute('INSERT INTO identity_bindings VALUES (?,?,?,?)', (inst,bot,'123456',json.dumps({'subject':{'kind':'human','subject_id':'person-a'}})))
                for owner, state in [(owner_a, 'active'), ('b', 'active'), (owner_a, 'invalidated')]:
                    document = {'proposal': {'predicate': '兴趣', 'object': '足球', 'representation': '喜欢足球',
                        'confidence': .9, 'attribution': 'user', 'qualifiers': {'场景': '课余'},
                        'evidence': [{'source': {'created_at': '2026-11-07'}}]}}
                    db.execute('INSERT INTO memory_atoms VALUES (?,?,?,?,?,?,?)',
                               (owner+state,owner,state,'self',json.dumps(document),'2026-11-07',2))
            before = path.read_bytes()
            result = module.native_profile('123456', path)
            self.assertEqual(result['status'], 'available')
            self.assertEqual(len(result['facts']), 1)
            self.assertEqual(result['facts'][0]['value'], '足球')
            self.assertEqual(result['facts'][0]['sourceCount'], 1)
            self.assertEqual(result['facts'][0]['confidence'], .9)
            self.assertEqual(path.read_bytes(), before)



class AdminPortraitTests(unittest.TestCase):
    def test_helper_and_server_preserve_shared_portrait(self):
        spec = importlib.util.spec_from_file_location('admin_action', Path(__file__).parents[1]/'admin/action.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            import hashlib
            module.USER_MEMORY = Path(tmp)/'users';module.USER_MEMORY.mkdir()
            module.RELATIONSHIP_MEMORY = Path(tmp)/'relations';module.RELATIONSHIP_MEMORY.mkdir()
            name=hashlib.sha256(b'user:123456').hexdigest()+'.json'
            (module.USER_MEMORY/name).write_text(json.dumps({'profile':{'preferredName':'甲','preferences':['我吗','足球','足球'],'relationships':['情侣']}}))
            (module.RELATIONSHIP_MEMORY/name).write_text(json.dumps({'stage':'熟悉的朋友','affection':72,'familiarity':88,'trust':64}))
            result = module.profile_read('123456')
            self.assertEqual(result['portrait']['preferences'], ['足球'])
            self.assertEqual(result['portrait']['relationship']['basis'], 'legacy_unverified')
            self.assertEqual(result['portrait']['relationship']['attitude']['affection'], 72)
            server_spec=importlib.util.spec_from_file_location('admin_server',Path(__file__).parents[1]/'admin/server.py')
            server=importlib.util.module_from_spec(server_spec);server_spec.loader.exec_module(server)
            view=server.profile_view(result)
            self.assertEqual(view['portrait'],result['portrait'])
            self.assertEqual(view['native'],result['native'])

if __name__ == '__main__': unittest.main()
