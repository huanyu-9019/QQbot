import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from metrics import aggregate


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
