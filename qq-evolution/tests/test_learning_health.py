import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from runtime_support import learning_status
class LearningHealth(unittest.TestCase):
 def test_restart_does_not_clear_failed_learning(self):
  self.assertFalse(learning_status('code=expression_output_invalid\nAstrBot started\nreason=retry_exhausted')[1])
 def test_later_commit_clears_expression_failure(self):
  self.assertTrue(learning_status('code=expression_output_invalid\ncommitted=yes')[1])
 def test_failure_after_commit_is_degraded(self):
  self.assertFalse(learning_status('committed=yes\ncode=model_usage_unknown')[1])
 def test_other_material_success_does_not_hide_failure(self):
  self.assertFalse(learning_status('material=aaa committed=no code=expression_output_invalid\nmaterial=bbb committed=yes')[1])
if __name__=='__main__':unittest.main()
