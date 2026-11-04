import json
import tempfile
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from collector import read_events, redact_text, sanitize_record


class CollectorTests(unittest.TestCase):
    def test_redacts_credentials_phone_qq_and_address_patterns(self):
        text = "api_key=sk-live-abcdefghijklmnop phone 13812345678 QQ:123456789 地址：北京市朝阳区幸福路12号"
        redacted = redact_text(text)
        self.assertNotIn("sk-live-abcdefghijklmnop", redacted)
        self.assertNotIn("13812345678", redacted)
        self.assertNotIn("123456789", redacted)
        self.assertNotIn("北京市朝阳区幸福路12号", redacted)

    def test_sanitize_bounds_text_and_drops_malformed_records(self):
        safe = sanitize_record({"timestamp": 1, "direction": "incoming", "kind": "private", "sessionHash": "a" * 64, "text": "x" * 5000})
        self.assertEqual(len(safe["text"]), 1200)
        self.assertIsNone(sanitize_record({"direction": "incoming", "text": "bad"}))
        self.assertIsNone(sanitize_record("not an object"))

    def test_cursor_resumes_without_replaying_or_accepting_malformed_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            cursor_path = Path(tmp) / "cursor.json"
            path.write_text("\n".join([
                json.dumps({"timestamp": 1, "direction": "incoming", "kind": "private", "sessionHash": "a" * 64, "text": "one"}),
                "not json",
                json.dumps({"timestamp": 2, "direction": "delivered", "kind": "private", "sessionHash": "a" * 64, "text": "two"}),
            ]) + "\n", encoding="utf-8")
            first, cursor = read_events([path], cursor_path)
            second, cursor = read_events([path], cursor_path)
            self.assertEqual([row["text"] for row in first], ["one", "two"])
            self.assertEqual(second, [])
            self.assertTrue(cursor_path.exists())


if __name__ == "__main__":
    unittest.main()
