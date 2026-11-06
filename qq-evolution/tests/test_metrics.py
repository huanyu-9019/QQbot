import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from metrics import aggregate, overdue_turns


class MetricsTests(unittest.TestCase):
    def test_requires_minimum_pair_count_before_scoring(self):
        result = aggregate([], minimum_pairs=3)
        self.assertFalse(result["eligible"])
        self.assertEqual(result["pairs"], 0)

    def test_aggregates_latency_failures_repetition_and_silence(self):
        events = [
            {"direction": "incoming", "turnId": "1", "sessionHash": "a", "timestamp": 1, "text": "hi"},
            {"direction": "delivered", "turnId": "1", "sessionHash": "a", "timestamp": 11, "text": "hello"},
            {"direction": "incoming", "turnId": "2", "sessionHash": "b", "timestamp": 20, "text": "again"},
            {"direction": "delivered", "turnId": "2", "sessionHash": "b", "timestamp": 50, "text": "hello"},
            {"direction": "incoming", "turnId": "3", "sessionHash": "c", "timestamp": 60, "text": "silent"},
        ]
        result = aggregate(events, minimum_pairs=2)
        self.assertTrue(result["eligible"])
        self.assertEqual(result["pairs"], 2)
        self.assertEqual(result["silences"], 1)
        self.assertEqual(result["repeatedReplies"], 1)
        self.assertEqual(result["meanLatencyMs"], 20)
        self.assertEqual(result["successRate"], 2 / 3)


if __name__ == "__main__":
    unittest.main()


class PreservedBaselineTests(unittest.TestCase):
    def test_audited_voice_with_matching_text_is_one_intentional_reply(self):
        events = [
            dict(direction='incoming', turnId='a', timestamp=1, text='你好', media='text'),
            dict(direction='voice_source', turnId='a', timestamp=2, text='你好呀', media='voice'),
            dict(direction='delivered', turnId='a', timestamp=3, text='你好呀', media='voice'),
            dict(direction='delivered', turnId='a', timestamp=4, text='你好呀', media='text'),
        ]
        result = aggregate(events, minimum_pairs=1)
        self.assertEqual(result['multiMessageTurns'], 0)
        self.assertEqual(result['unsolicitedVoice'], 0)

    def test_voice_duration_placeholders_are_not_scored_as_conversation_pairs(self):
        events = [
            {"direction": "incoming", "turnId": "voice", "timestamp": 1, "text": "[语音 7s]"},
            {"direction": "delivered", "turnId": "voice", "timestamp": 50, "text": "你刚说什么？"},
            {"direction": "incoming", "turnId": "text", "timestamp": 60, "text": "今天天气不错"},
            {"direction": "delivered", "turnId": "text", "timestamp": 100, "text": "是啊"},
        ]
        result = aggregate(events, minimum_pairs=1)
        self.assertEqual(result["pairs"], 1)
        self.assertEqual(result["unobservableTurns"], 1)
        self.assertEqual(result["meanLatencyMs"], 40)

    def test_overdue_turns_exclude_intentional_silence_and_legacy_audits(self):
        events = [
            {"version": 2, "direction": "incoming", "turnId": "pending", "timestamp": 1000},
            {"version": 2, "direction": "incoming", "turnId": "silent", "timestamp": 1000},
            {"version": 2, "direction": "silent", "turnId": "silent", "timestamp": 1100},
            {"version": 1, "direction": "incoming", "turnId": "legacy", "timestamp": 1000},
            {"version": 2, "direction": "incoming", "turnId": "failed", "timestamp": 1000},
            {"version": 2, "direction": "failed", "turnId": "failed", "timestamp": 1200},
        ]
        self.assertEqual(overdue_turns(events, now_ms=4000, grace_ms=2000), 2)

    def test_flags_routing_media_and_multi_message_quality_failures(self):
        events = [
            {"direction": "incoming", "turnId": "1", "timestamp": 1, "kind": "group", "mentioned": False, "mentionedOther": True, "text": "@someone"},
            {"direction": "delivered", "turnId": "1", "timestamp": 11, "kind": "group", "media": "text", "text": "wrong"},
            {"direction": "delivered", "turnId": "1", "timestamp": 12, "kind": "group", "media": "voice", "text": "wrong"},
            {"direction": "incoming", "turnId": "2", "timestamp": 20, "kind": "group", "mentioned": True, "mentionedOther": False, "media": "image", "text": "看图"},
            {"direction": "delivered", "turnId": "2", "timestamp": 30, "kind": "group", "media": "text", "text": '<img src="https://bad.example/x.png">'},
            {"direction": "incoming", "turnId": "3", "timestamp": 40, "kind": "group", "mentioned": True, "mentionedOther": False, "media": "text", "text": "你好"},
            {"direction": "delivered", "turnId": "3", "timestamp": 50, "kind": "group", "media": "voice", "text": "语音"},
        ]
        result = aggregate(events, minimum_pairs=1)
        self.assertEqual(result["foreignMentionReplies"], 1)
        self.assertEqual(result["multiMessageTurns"], 1)
        self.assertEqual(result["htmlLeaks"], 1)
        self.assertEqual(result["unsolicitedVoice"], 2)
