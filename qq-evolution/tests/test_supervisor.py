import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
from supervisor import development_repo


class SupervisorTests(unittest.TestCase):
    def test_uses_current_development_tree_and_allows_explicit_path_override(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("QQ_EVOLUTION_REPO", None)
            self.assertEqual(development_repo(), Path("/home/admin/qq-evolution/development"))
        with patch.dict(os.environ, {"QQ_EVOLUTION_REPO": "/tmp/repo"}):
            self.assertEqual(development_repo(), Path("/tmp/repo"))


if __name__ == "__main__":
    unittest.main()
