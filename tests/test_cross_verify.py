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

    def test_extract_entities_with_search_concepts(self):
        concepts = ["比熊", "泪痕", "消除方法"]
        entities = cross_verify.extract_entities("如何消除比熊的泪痕", search_concepts=concepts)
        # search_concepts 作为补充：n-gram 结果 + concepts 都应存在
        self.assertIn("比熊", entities)
        self.assertIn("泪痕", entities)
        self.assertIn("消除方法", entities)
        # n-gram 结果仍应保留（未被替换）
        self.assertIn("如何消除比熊的泪痕", entities)

    def test_extract_entities_chinese_fallback(self):
        entities = cross_verify.extract_entities("如何消除比熊的泪痕")
        # 原句被保留
        self.assertIn("如何消除比熊的泪痕", entities)
        # 2-gram 辅助应包含关键实体
        self.assertIn("比熊", entities)
        self.assertIn("泪痕", entities)
        self.assertIn("消除", entities)

    def test_extract_entities_preserves_proper_nouns(self):
        entities = cross_verify.extract_entities("The Beatles 我的祖国")
        self.assertIn("the beatles", entities)
        self.assertIn("我的祖国", entities)

    def test_verify_result_marks_relevant_result(self):
        result = {
            "title": "OpenAI GPT 2026 发布计划更新",
            "content": "OpenAI GPT roadmap mentions 2026 planning details.",
        }

        verified = cross_verify.verify_result("OpenAI GPT 2026 发布计划", result)

        self.assertTrue(verified["verified"])
        self.assertGreaterEqual(verified["verification_score"], 0.75)

    def test_verify_result_with_search_concepts(self):
        result = {
            "title": "比熊泪痕清理方法大全",
            "content": "比熊犬容易出现泪痕，定期清洁眼部可以有效缓解。",
        }
        verified = cross_verify.verify_result(
            "如何消除比熊的泪痕",
            result,
            search_concepts=["比熊", "泪痕", "消除方法"],
        )
        self.assertTrue(verified["verified"])
        self.assertIn("比熊", verified["matched_terms"])
        self.assertIn("泪痕", verified["matched_terms"])

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
