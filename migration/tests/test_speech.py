import importlib.util
import unittest
from pathlib import Path


class SpeechTest(unittest.TestCase):
    def test_transcript_excludes_internal_thought_and_rejects_empty(self):
        source = Path(__file__).parents[1] / 'plugin/speech.py'
        self.assertTrue(source.exists(), 'cloud transcription adapter missing')
        spec = importlib.util.spec_from_file_location('speech', source)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        payload = {'candidates': [{'content': {'parts': [
            {'thought': True, 'text': 'private analysis'}, {'text': '你好，今天阳光很好。'}]}}]}
        self.assertEqual('你好，今天阳光很好。', m.transcript_text(payload))
        with self.assertRaises(ValueError):
            m.transcript_text({'candidates': []})

