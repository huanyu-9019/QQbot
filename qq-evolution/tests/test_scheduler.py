import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from scheduler import append_learning_record, iteration_due, record_iteration, learning_notice


class SchedulerTests(unittest.TestCase):
    def test_long_learning_notice_fits_publisher_limit(self):
        text=learning_notice({'iteration':123,'updated':'learning_record','reason':'减少重复表达'*60})
        self.assertTrue(25 <= len(text) <= 140)
        self.assertIn('未发布代码',text)

    def test_failed_assessment_notice_is_not_claimed_as_learning(self):
        text=learning_notice({'iteration':1,'reason':'Iteration assessment unavailable: ValueError'})
        self.assertIn('评估失败',text)

    def test_iteration_records_append_and_preserve_prior_lessons(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "learning-records.jsonl"
            state = {}
            record_iteration(state, now=1800, updated=False, reason="少重复套话")
            append_learning_record(path, state)
            record_iteration(state, now=3600, updated=True, reason="改善接话节奏")
            append_learning_record(path, state)

            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([row["reason"] for row in rows], ["少重复套话", "改善接话节奏"])
            self.assertEqual(rows[1]["iteration"], 2)
            self.assertEqual(rows[1]["updated"], "code")

    def test_iteration_due_is_measured_from_last_completed_learning_round(self):
        self.assertFalse(iteration_due({"lastIteration": 100}, 999))
        self.assertTrue(iteration_due({"lastIteration": 100}, 1000))


if __name__ == "__main__":
    unittest.main()
