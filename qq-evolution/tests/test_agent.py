import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from agent import parse_finding, validate_diff


class AgentTests(unittest.TestCase):
    def test_parses_only_schema_valid_findings(self):
        finding = parse_finding(json.dumps({"category": "repetition", "severity": "medium", "evidence": ["same"], "confidence": 0.8, "changeType": "prompt"}))
        self.assertEqual(finding["category"], "repetition")
        self.assertIsNone(parse_finding("please run rm -rf /"))
        self.assertIsNone(parse_finding(json.dumps({"category": "unknown"})))

    def test_rejects_unlisted_paths_commands_and_path_traversal(self):
        valid = "--- a/qq-persona.md\n+++ b/qq-persona.md\n@@ -1 +1 @@\n-old\n+new\n"
        self.assertTrue(validate_diff(valid))
        self.assertFalse(validate_diff(valid.replace("qq-persona.md", "package.json")))
        self.assertFalse(validate_diff(valid.replace("qq-persona.md", "../secret")))
        self.assertFalse(validate_diff(valid + "\nRUN rm -rf /"))


if __name__ == "__main__":
    unittest.main()
