import importlib.util
from pathlib import Path
from types import SimpleNamespace as S
import unittest

spec = importlib.util.spec_from_file_location('mention_policy', Path(__file__).parents[1]/'plugin/policy.py')
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)


class Mentions(unittest.TestCase):
    def test_identifying_a_mentioned_person_is_not_addressing_them(self):
        at = {'type': 'at', 'data': {'qq': '200'}}
        for text in ['是谁', '他叫什么名字', '你认识他吗']:
            chain = [at, {'type': 'text', 'data': {'text': text}}]
            self.assertTrue(p.may_reply(chain, '100', group=True), text)
        for text in ['想我了吗', '你是谁', '你认识江生吗', '江生你怎么看']:
            chain = [at, {'type': 'text', 'data': {'text': text}}]
            self.assertFalse(p.may_reply(chain, '100', group=True), text)

    def test_transport_components_resolve_when_raw_is_missing_without_parsing_plaintext_mentions(self):
        event = S(message_obj=S(raw_message=None, message=[S(type='At', qq=200, name='梦l'), S(type='Plain', text='是谁')]))
        segments = p.message_segments(event)
        self.assertEqual(segments[0]['data']['qq'], '200')
        self.assertEqual(segments[0]['data']['name'], '梦l')
        self.assertTrue(p.mention_identity_question(segments, '100'))
        event.message_obj.message = [S(type='Plain', text='@梦l(200) 是谁')]
        self.assertFalse(p.mention_identity_question(p.message_segments(event), '100'))

    def test_identity_answer_names_the_target_not_the_sender_or_a_real_identity_guess(self):
        chain = [{'type':'at','data':{'qq':'200'}}, {'type':'text','data':{'text':'是谁'}}]
        self.assertEqual(p.mentioned_identity_answer(chain, '100', [{'account':'200','displayName':'HandsomeTa.','preferredName':'KAKÀ'}]),
                         '你@的是HandsomeTa.，我这里记的称呼是KAKÀ。')
        self.assertEqual(p.mentioned_identity_answer(chain, '100', [{'account':'200','displayName':'梦l','preferredName':''}]),
                         '你@的是梦l。更具体的身份，我还没有可靠记录。')
        self.assertIsNone(p.mentioned_identity_answer(chain,'100',[]))
        self.assertIsNone(p.mentioned_identity_answer([chain[0],{'type':'text','data':{'text':'想我了吗'}}],'100',[{'account':'200','displayName':'梦l'}]))
