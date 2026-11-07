import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]))
from collector import sanitize_record
from metrics import aggregate


class MentionQuality(unittest.TestCase):
    def test_explicit_question_about_someone_else_is_not_foreign_address_reply(self):
        rows=[]
        for turn, directed in [('asked',True),('foreign',False)]:
            row=sanitize_record(dict(direction='incoming',kind='group',sessionHash='a'*64,
                                     timestamp=1,text='@某人',turnId=turn,mentionedOther=True,directedToBot=directed))
            rows.extend([row,dict(direction='delivered',timestamp=2,text='回复',turnId=turn)])
        self.assertEqual(aggregate(rows)['foreignMentionReplies'],1)

    def test_unresolved_mention_survives_collection_and_is_visible_to_evaluator(self):
        row=sanitize_record(dict(direction='quality',kind='group',sessionHash='a'*64,
                                 timestamp=1,text='not needed',turnId='t',outcome='mention_target_unresolved'))
        self.assertIsNotNone(row)
        self.assertEqual(row['text'],'')
        self.assertEqual(aggregate([row])['mentionResolutionFailures'],1)
