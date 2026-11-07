import sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
import runtime_support as r
import remote_release as release
from patch_policy import changed_paths
class NativeMaintenance(unittest.TestCase):
 def test_native_modules_are_snapshotted_and_mapped(self):
  names=['conversation/group_questions.py','conversation/participation.py','conversation/group_admission.py','conversation/awareness_context.py','memory/person/service.py','expression/style_service.py']
  for short in names:
   name='migration/companion/companion_v2/'+short
   self.assertIn(name,release.FILES)
   self.assertIn(name,release.SNAPSHOT_FILES)
   self.assertEqual(r.companion_destination(name).as_posix(), '/opt/jiangsheng-astrbot/runtime/data/plugins/astrbot_plugin_private_companion/companion_v2/'+short)
   diff=f'--- a/{name}\n+++ b/{name}\n@@ -1 +1 @@\n-old\n+new\n'
   self.assertEqual(changed_paths(diff,{name}),[name])
 def test_shared_memory_module_is_maintainable_and_snapshotted(self):
  name='migration/plugin/person_memory.py'
  self.assertIn(name,r.ASTRBOT_FILES);self.assertIn(name,release.SNAPSHOT_FILES)
  diff=f'--- a/{name}\n+++ b/{name}\n@@ -1 +1 @@\n-old\n+new\n'
  self.assertEqual(changed_paths(diff,{name}),[name])
 def test_unknown_native_file_rejected(self):
  with self.assertRaises(ValueError):r.companion_destination('migration/companion/companion_v2/secrets.py')
 def test_semantic_checks_run_before_native_sync(self):
  import inspect
  source=inspect.getsource(release.apply_locked)
  self.assertLess(source.index('verify_companion_sources'),source.index('sync_astrbot()'))
if __name__=='__main__':unittest.main()

