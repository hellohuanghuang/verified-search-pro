import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import cross_verify  # noqa: E402


class CrossVerifyTests(unittest.TestCase):
    def test_extract_entities_handles_mixed_query(self):
        entities = cross_verify.extract_entities("OpenAI GPT 2026 发布计划")

        self.assertIn("openai gpt", entities)
        self.assertIn("2026", entities)
        self.assertIn("发布计划", entities)

    def test_verify_result_marks_relevant_result(self):
        result = {
            "title": "OpenAI GPT 2026 发布计划更新",
            "content": "OpenAI GPT roadmap mentions 2026 planning details.",
        }

        verified = cross_verify.verify_result("OpenAI GPT 2026 发布计划", result)

        self.assertTrue(verified["verified"])
        self.assertGreaterEqual(verified["verification_score"], 0.75)

    def test_grade_confidence_a_requires_authority_and_multiple_sources(self):
        result = {
            "verification_score": 0.8,
            "sources": ["tavily", "bing_cn"],
            "domain_score": 0.9,
        }

        self.assertEqual(cross_verify.grade_confidence(result, {"consistent": True}), "A")

    def test_grade_confidence_d_for_low_verification(self):
        result = {
            "verification_score": 0.1,
            "sources": ["bing_cn"],
            "domain_score": 0.5,
        }

        self.assertEqual(cross_verify.grade_confidence(result, {"consistent": True}), "D")


if __name__ == "__main__":
    unittest.main()
