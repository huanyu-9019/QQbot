"""Regression over the exact deployed pure social-question scorer."""
import ast,re,sys,unittest
from datetime import datetime,timezone
from pathlib import Path
p=Path(sys.argv[1]);sys.argv=sys.argv[:1]
tree=ast.parse(p.read_text(encoding='utf-8'))
tree.body=[n for n in tree.body if not isinstance(n,(ast.Import,ast.ImportFrom))]
ns={'re':re,'clean_group_text':lambda s:re.sub(r'\[(?:图片|语音)(?: \d+)?\]',' ',s).strip(),'parse_moment':lambda x:datetime.fromisoformat(x) if x else None}
exec(compile(tree,str(p),'exec'),ns)
class SocialQuestions(unittest.TestCase):
 def test_social_questions_enter_contextual_judgment(self):
  for text in ['我叫什么','你记得我吗','我和你是什么关系','你觉得我是谁','那你呢','你在干嘛']:
   with self.subTest(text=text):self.assertGreaterEqual(ns['question_signal'](text)['score'],55)
 def test_not_every_message_is_a_question(self):
  for text in ['哈哈','[图片]','今天吃了饭','你俩什么关系？','他叫什么？','```你记得我吗```']:
   with self.subTest(text=text):self.assertLess(ns['question_signal'](text)['score'],55)
 def test_other_people_reduce_ambiguous_social_cues(self):
  at=datetime.now(timezone.utc)
  score=ns['question_signal']('你记得我吗',recent=[{'speaker_id':'other','received_at':at.isoformat(),'text':'正在聊天'}],at=at,speaker_id='user')['score']
  self.assertLess(score,ns['question_signal']('你记得我吗')['score'])
if __name__=='__main__':unittest.main()
