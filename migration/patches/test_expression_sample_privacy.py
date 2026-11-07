import json
import unittest
from types import SimpleNamespace

from companion_v2.expression.style_service import ExpressionStyleService
from tests.test_expression_style import NOW, SampleCatalogTests


class ExpressionSamplePrivacyTests(unittest.TestCase):
    def test_model_request_redacts_identifiers_and_credentials_without_mutating_audit_samples(self):
        original = [{"handle": "sample:opaque", "text":
                     "联系 13800138000，邮箱 a@example.com，token=sk-1234567890abcdef；平时就说好呀。"}]
        job = {
            "context": SampleCatalogTests.group_context(),
            "request_key": "expression-privacy-test",
            "at": NOW,
            "instruction": "role instructions",
            "policy": SimpleNamespace(learning_mode="balanced"),
            "sample_document": {"characters": len(original[0]["text"]), "source_kind": "conversation_input"},
            "catalogue": original,
        }

        request = ExpressionStyleService._request(None, job, [], 1)
        payload = json.loads(request.context.materials[0].payload)
        model_sample = payload["samples"][0]["text"]

        self.assertNotIn("13800138000", model_sample)
        self.assertNotIn("a@example.com", model_sample)
        self.assertNotIn("sk-1234567890abcdef", model_sample)
        self.assertIn("平时就说好呀", model_sample)
        self.assertEqual(original[0]["text"],
                         "联系 13800138000，邮箱 a@example.com，token=sk-1234567890abcdef；平时就说好呀。")
