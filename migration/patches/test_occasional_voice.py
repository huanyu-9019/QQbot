"""Exercise deployed voice authorization methods without any network calls."""
import ast
import asyncio
from contextvars import ContextVar
from pathlib import Path
import re
import sys
import time
from types import SimpleNamespace as NS
import unittest


class VoiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_random_voice_is_attributed_rate_limited_and_respects_refusal(self):
        tree = ast.parse(Path(sys.argv[1]).read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'JiangshengMigration')
        cls.decorator_list = []; cls.bases = []
        cls.body = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in ('voice_requested', 'patch_tts')]
        module = ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[]))
        current = ContextVar('event', default=None)
        env = dict(re=re, time=time, current_message_event=current, quality_issue=lambda *args: None)
        exec(compile(module, '<voice-methods>', 'exec'), env)
        obj = env['JiangshengMigration'](); obj.patched_tts = []; obj.write = lambda *a, **k: None
        async def audio(text): return 'synthetic-audio.wav'
        provider = NS(get_audio=audio); obj.patch_tts(provider)
        def event(text):
            extra = {'jiangsheng_turn': 'synthetic', 'jiangsheng_llm_started': True}
            return NS(message_str=text, get_extra=lambda k: extra.get(k), set_extra=lambda k,v: extra.__setitem__(k,v))
        current.set(event('今天挺开心'))
        self.assertEqual(await provider.get_audio('我也是'), 'synthetic-audio.wav')
        self.assertTrue(current.get().get_extra('jiangsheng_occasional_voice'))
        self.assertEqual(current.get().get_extra('jiangsheng_voice_source'), '我也是')
        current.set(event('接着说'))
        with self.assertRaises(ValueError): await provider.get_audio('下一句')
        obj.last_occasional_voice = 0; current.set(event('不要发语音，只用文字'))
        with self.assertRaises(ValueError): await provider.get_audio('好的')
        current.set(None)
        with self.assertRaises(ValueError): await provider.get_audio('无归因')
        current.set(event('用语音回复我'))
        self.assertEqual(await provider.get_audio('好的'), 'synthetic-audio.wav')


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]], verbosity=2)
