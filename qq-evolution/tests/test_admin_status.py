import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from admin_status import build_snapshot, format_route


class AdminStatusTests(unittest.TestCase):
    def test_snapshot_contains_both_hosts_and_no_conversation_or_credentials(self):
        data = build_snapshot(
            now=1000,
            control={"online": True, "supervisor": True, "memoryAvailableMiB": 300},
            production={"online": True, "bridge": True, "api": True, "napcat": True,
                        "router": {"active": "grok", "activeModel": "grok-4.6", "lastSuccess": 900,
                                   "routes": [{"name": "gemini", "model": "gemini-3.8-flash", "available": False, "visionAvailable": False},
                                              {"name": "grok", "model": "grok-4.6", "available": True, "visionAvailable": True}]}},
            health={"lastFetch": 950, "pollStarted": 980},
            state={"lastIteration": 800, "lastReason": "减少模板化表达", "lastRevision": "abc123"},
            latest_change={"timestamp": 850, "changed": ["qq-persona.md"]},
        )
        serialized = json.dumps(data, ensure_ascii=False)
        self.assertEqual(data["qq"]["activeModel"], "grok-4.6")
        self.assertTrue(data["qq"]["canReply"])
        self.assertTrue(data["qq"]["canSeeImages"])
        self.assertEqual(data["codex"]["lastIteration"], 800)
        self.assertNotIn("conversation text", serialized)
        self.assertNotIn("secret-key", serialized)

    def test_provider_label_and_health_are_clear(self):
        self.assertEqual(format_route({"name": "gemini-nekocloud", "model": "grok-4.6", "available": True}),
                         {"name": "新中转站 Grok", "model": "grok-4.6", "available": True, "visionAvailable": False})
        self.assertEqual(format_route({"name": "gemini-nekocloud-gemini", "model": "gemini-3.8-flash", "available": True}),
                         {"name": "新中转站 Gemini", "model": "gemini-3.8-flash", "available": True, "visionAvailable": False})
        self.assertEqual(format_route({"name": "deepseek-relay", "model": "deepseek-v4.1-flash", "available": True}),
                         {"name": "中转站 DeepSeek", "model": "deepseek-v4.1-flash", "available": True, "visionAvailable": False})
        self.assertEqual(format_route({"name": "gpt", "model": "gpt-6-luna", "available": False}),
                         {"name": "GPT 中转站", "model": "gpt-6-luna", "available": False, "visionAvailable": False})


if __name__ == "__main__":
    unittest.main()
