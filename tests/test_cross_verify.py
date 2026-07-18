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

    def test_concepts_precede_ngrams_in_order(self):
        """顺序契约：原句 > LLM 概念 > 机械分词。

        保证任何"取前 N"的消费场景 concepts 优先可见（主力而非候补）。
        """
        concepts = ["泪痕", "比熊"]
        entities = cross_verify.extract_entities("如何消除比熊的泪痕", search_concepts=concepts)
        self.assertEqual(entities[0], "如何消除比熊的泪痕")  # 原句第一
        self.assertEqual(entities[1], "泪痕")               # concepts 紧随
        self.assertEqual(entities[2], "比熊")
        # 存活下来的 n-gram 切片（如"消除"）必须排在 concepts 之后
        # （"如何"属疑问停用词本就被过滤，不作为样例）
        self.assertGreater(entities.index("消除"), entities.index("比熊"))

    def test_concepts_not_deduped_against_later_ngrams(self):
        """concepts 与 n-gram 重复时只保留一次（最终去重兜底）。"""
        entities = cross_verify.extract_entities("如何消除比熊的泪痕", search_concepts=["比熊"])
        self.assertEqual(entities.count("比熊"), 1)

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


class NGramScoringTests(unittest.TestCase):
    """BUG-002 回归：n-gram 噪声过滤"""

    def test_scoring_includes_leihen_without_concepts(self):
        """无 search_concepts 时，'泪痕'应进入 scoring_terms 并被命中"""
        result = {
            "title": "比熊泪痕消除方法大全",
            "content": "比熊犬容易出现泪痕，消除泪痕的方法包括定期清洁眼部。",
        }
        verified = cross_verify.verify_result("如何消除比熊的泪痕", result)
        self.assertIn("泪痕", verified["key_terms"])
        self.assertTrue(verified["verified"])

    def test_stop_char_ngrams_filtered_from_scoring(self):
        """含虚词字符的 n-gram 不应导致关键术语被截断"""
        result = {"title": "泪痕", "content": "泪痕"}
        verified = cross_verify.verify_result("如何消除比熊的泪痕", result)
        # 关键点：泪痕 应在 matched_terms 中（未被噪声挤出 scoring_terms）
        self.assertIn("泪痕", verified["matched_terms"])


class NoneValueDefenseTests(unittest.TestCase):
    """BUG-003 回归：None 值防御"""

    def test_verify_result_handles_none_title(self):
        result = {"title": None, "content": "比熊泪痕相关内容"}
        verified = cross_verify.verify_result("比熊泪痕", result)
        self.assertIsNotNone(verified)

    def test_verify_result_handles_none_content(self):
        result = {"title": "比熊泪痕", "content": None}
        verified = cross_verify.verify_result("比熊泪痕", result)
        self.assertIsNotNone(verified)

    def test_verify_result_handles_all_none(self):
        result = {"title": None, "content": None}
        verified = cross_verify.verify_result("任意查询", result)
        self.assertFalse(verified["verified"])


class EnglishProperNounTests(unittest.TestCase):
    """BUG-004 回归：职位词断开"""

    def test_job_title_splits_proper_nouns(self):
        entities = cross_verify.extract_entities("OpenAI CEO Sam Altman")
        self.assertIn("openai", entities)
        self.assertIn("sam altman", entities)
        # 原句被保留用于整句匹配是设计意图，拆分后应同时存在独立 term

    def test_cto_also_splits(self):
        entities = cross_verify.extract_entities("Microsoft CTO Kevin Scott")
        self.assertIn("microsoft", entities)
        self.assertIn("kevin scott", entities)


class TraditionalChineseNormalizationTests(unittest.TestCase):
    """繁简归一：避免繁体源因字符不匹配导致验证失败"""

    def test_traditional_query_matches_simplified_content(self):
        """繁体查询能匹配简体内容"""
        result = {
            "title": "比熊泪痕消除方法",
            "content": "比熊犬容易出现泪痕，消除泪痕的方法包括定期清洁眼部。",
        }
        verified = cross_verify.verify_result("如何消除比熊淚痕", result)
        self.assertTrue(verified["verified"])

    def test_traditional_content_matches_simplified_query(self):
        """简体查询能匹配繁体内容"""
        result = {
            "title": "比熊淚痕消除方法",
            "content": "比熊犬容易出現淚痕，消除淚痕的方法包括定期清潔眼部。",
        }
        verified = cross_verify.verify_result("如何消除比熊泪痕", result)
        self.assertTrue(verified["verified"])

    def test_traditional_query_matches_traditional_content(self):
        """繁体查询能匹配繁体内容"""
        result = {
            "title": "比熊淚痕消除方法",
            "content": "比熊犬容易出現淚痕，消除淚痕的方法包括定期清潔眼部。",
        }
        verified = cross_verify.verify_result("如何消除比熊淚痕", result)
        self.assertTrue(verified["verified"])

    def test_normalize_traditional_chinese_function(self):
        """归一化函数正确转换繁体字"""
        self.assertEqual(cross_verify._normalize_traditional_chinese("國學術醫"), "国学术医")
        self.assertEqual(cross_verify._normalize_traditional_chinese("寵物淚痕"), "宠物泪痕")
        self.assertEqual(cross_verify._normalize_traditional_chinese("简体中文"), "简体中文")
        self.assertEqual(cross_verify._normalize_traditional_chinese(""), "")

    def test_traditional_mixed_content(self):
        """繁简混合内容正确处理"""
        result = {
            "title": "比熊泪痕消除方法大全",
            "content": "比熊犬容易出現淚痕，消除泪痕的方法包括定期清洁眼部。",
        }
        verified = cross_verify.verify_result("如何消除比熊淚痕", result)
        self.assertTrue(verified["verified"])


if __name__ == "__main__":
    unittest.main()
