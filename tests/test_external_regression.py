#!/usr/bin/env python3
"""
外部测试回归套件 — 源自 v2.0.1 外部 agent 测试报告中的失败项。
覆盖 BUG-001 ~ BUG-004 的端到端场景。
"""
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import cross_verify
import network


class ExternalRegressionTests(unittest.TestCase):
    """对应外部测试 test_023: 中文长尾搜索"""

    def test_chinese_long_tail_relevant_result_passes_verification(self):
        """'如何消除比熊的泪痕'的相关结果应通过验证（无 search_concepts）"""
        result = {
            "title": "比熊泪痕消除方法大全",
            "content": "比熊犬容易出现泪痕，消除泪痕的方法包括定期清洁眼部。",
        }
        verified = cross_verify.verify_result("如何消除比熊的泪痕", result)
        self.assertTrue(
            verified["verified"],
            f"Expected verified=True, got score={verified['verification_score']}",
        )

    """对应外部测试 test_041/test_045: n-gram 噪声"""

    def test_ngram_scoring_without_concepts_includes_key_term(self):
        """无 concepts 时关键术语'泪痕'不应被 n-gram 噪声挤出"""
        result = {
            "title": "比熊泪痕清理",
            "content": "比熊泪痕消除方法比熊犬泪痕",
        }
        verified = cross_verify.verify_result("如何消除比熊的泪痕", result)
        self.assertIn("泪痕", verified["matched_terms"])

    """对应外部测试 test_015: None 值崩溃"""

    def test_verify_result_with_all_none_fields(self):
        """title和content均为None不应崩溃"""
        result = {"title": None, "content": None, "url": "https://example.com"}
        verified = cross_verify.verify_result("任意查询", result)
        self.assertFalse(verified["verified"])
        self.assertEqual(verified["verification_score"], 0)

    """对应外部测试 test_004: 英文专有名词"""

    def test_english_proper_noun_with_job_title_extraction(self):
        """'OpenAI CEO Sam Altman' 应正确拆分"""
        entities = cross_verify.extract_entities("OpenAI CEO Sam Altman")
        self.assertIn("openai", entities)
        self.assertIn("sam altman", entities)

    """对应外部测试 test_023: Bing warmup"""

    @mock.patch.object(network, "_ensure_cookie_opener")
    def test_bing_warmup_establishes_session(self, mock_get_opener):
        """warmup_session 应成功建立会话"""
        import http.cookiejar

        mock_opener = mock.MagicMock()
        mock_get_opener.return_value = mock_opener
        network._cookie_jar = http.cookiejar.CookieJar()
        result = network.warmup_session("https://cn.bing.com")
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
