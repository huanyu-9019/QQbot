import json
import tempfile
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from collector import fetch_remote_events, read_events, redact_text, sanitize_record


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
        self.assertIsNone(sanitize_record({"timestamp": "bad", "direction": "incoming", "kind": "private", "sessionHash": "a" * 64, "text": "x"}))

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

    def test_remote_fetch_uses_validated_daily_filenames_and_sanitizes_before_return(self):
        calls = []
        raw = json.dumps({"timestamp": 1, "direction": "incoming", "kind": "private", "sessionHash": "a" * 64, "text": "my phone 13812345678", "turnId": "1"})
        def runner(args):
            calls.append(args)
            return "2026-11-04.jsonl\n../secret\n" if len(calls) == 1 else raw + "\n"
        events = fetch_remote_events("root@host", "/home/hermes/qq-audit", runner=runner)
        self.assertEqual(events[0]["text"], "my phone [REDACTED_PHONE]")
        self.assertEqual(calls[0][0], "/usr/bin/ssh")
        self.assertIn("tail -n 2000", calls[1][-1])


if __name__ == "__main__":
    unittest.main()
