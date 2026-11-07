import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('portrait_policy', Path(__file__).parents[1]/'plugin/policy.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class PortraitTests(unittest.TestCase):
    def test_portrait_exposes_saved_attitude_scores_as_historical_estimates(self):
        result = policy.person_portrait({}, {
            'stage': '熟悉的朋友', 'affection': 72, 'familiarity': 88,
            'trust': 64, 'boundary': '不喜欢被催', 'lastMood': '开心',
            'updatedAt': 1760000000,
        })
        attitude = result['relationship']['attitude']
        self.assertEqual(attitude['affection'], 72)
        self.assertEqual(attitude['familiarity'], 88)
        self.assertEqual(attitude['trust'], 64)
        self.assertEqual(attitude['stage'], '熟悉的朋友')
        self.assertEqual(attitude['basis'], 'legacy_estimate')

    def test_legacy_relationship_is_not_confirmed_or_overridden_by_old_score(self):
        result = policy.person_portrait({'preferredName': '甲', 'relationships': ['情侣']},
                                       {'stage': '保持距离', 'affection': 30, 'turns': 100})
        self.assertEqual(result['relationship']['labels'], ['情侣'])
        self.assertEqual(result['relationship']['basis'], 'legacy_unverified')
        self.assertIn('不能', result['relationship']['note'])
        self.assertNotIn('保持距离', result['relationship']['description'])
        self.assertNotIn('100', result['relationship']['description'])

    def test_fragments_duplicates_names_and_boundaries(self):
        result = policy.person_portrait({
            'preferredName': '甲', 'privateNickname': '阿甲',
            'groupNicknames': {'1': '阿甲', '2': '阿甲', '3': '甲同学'},
            'preferences': ['我吗', '足球', '足球。', '主人'],
            'chatHabits': ['关注机器人、关注机器人', '不喜欢被催促', '上班时间为9点'],
        }, {})
        self.assertEqual(result['aliases'], ['阿甲', '甲同学'])
        self.assertEqual(result['preferences'], ['足球'])
        self.assertEqual(result['habits'], ['关注机器人'])
        self.assertEqual(result['boundaries'], ['不喜欢被催促'])
        self.assertEqual(result['routine'], ['上班时间为9点'])
        self.assertEqual(result['review']['rejected'], ['我吗'])

    def test_prompt_uses_cleaned_unverified_profile_and_no_fake_certainty(self):
        result = policy.profile_context({'relationships': ['情侣'],
                                         'preferences': ['我吗', '足球', '足球'],
                                         'chatHabits': ['不喜欢被催促']})
        self.assertNotIn('我吗', result)
        self.assertNotIn('明确关系', result)
        self.assertEqual(result.count('足球'), 1)
        self.assertIn('迁入', result)
        self.assertIn('不喜欢被催促', result)


if __name__ == '__main__': unittest.main()
