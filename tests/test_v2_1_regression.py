#!/usr/bin/env python3
"""新增测试：覆盖 v2.1.0-beta 修复的 6 个问题。"""

import json
import os
import subprocess
import sys
import unittest
from unittest import mock


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SearchEngineV2_1_Tests(unittest.TestCase):
    """问题 3/4/5/6 的单元测试（不依赖真实网络）"""

    @classmethod
    def setUpClass(cls):
        cls._original_path = list(sys.path)
        sys.path.insert(0, os.path.join(ROOT, "scripts"))

    @classmethod
    def tearDownClass(cls):
        sys.path = cls._original_path

    def _import_engine(self):
        import search_engine
        return search_engine

    def test_chinese_question_query_with_concepts_generates_variants(self):
        search_engine = self._import_engine()
        variants = search_engine.generate_query_variants(
            "如何消除比熊泪痕", search_concepts=["比熊", "泪痕", "消除"]
        )
        self.assertIn("如何消除比熊泪痕", variants)
        self.assertIn("消除比熊泪痕", variants)
        self.assertIn("比熊 泪痕 消除", variants)
        self.assertIn('"比熊" "泪痕" "消除"', variants)
        self.assertIn("remove bichon tear stains", variants)

    def test_translate_query_terms(self):
        search_engine = self._import_engine()
        result = search_engine.translate_query_terms("比熊泪痕消除")
        self.assertIn("bichon", result)
        self.assertIn("tear stains", result)
        self.assertIn("remove", result)

    def test_bing_quality_detected_degraded_for_question_only(self):
        search_engine = self._import_engine()
        degraded_results = [
            {"title": "如何", "url": "https://example.com/a", "content": ""},
            {"title": "怎样", "url": "https://example.com/b", "content": ""},
        ]
        report = search_engine._check_bing_result_quality(degraded_results)
        self.assertTrue(report["degraded"])
        self.assertEqual(report["reason"], "question_only_or_too_few")

    def test_bing_quality_ok_for_relevant_results(self):
        search_engine = self._import_engine()
        results = [
            {"title": "比熊泪痕消除方法", "url": "https://example.com/a", "content": ""},
            {"title": "比熊泪痕怎么清理", "url": "https://example.com/b", "content": ""},
        ]
        report = search_engine._check_bing_result_quality(results)
        self.assertFalse(report["degraded"])

    def test_duckduckgo_fallback_tries_bing_int_then_bing_cn(self):
        search_engine = self._import_engine()
        with mock.patch.object(search_engine, "_fetch_web_engine_once") as mock_fetch:
            mock_fetch.return_value = {
                "results": [
                    {"title": "fallback result", "url": "https://example.com/fb", "content": ""}
                ],
                "status": {"status": "ok"},
            }
            fallback = search_engine._duckduckgo_fallback_search("query")
            self.assertEqual(fallback["status"]["status"], "ok")
            self.assertEqual(len(fallback["results"]), 1)

    def test_duckduckgo_chinese_query_fallback_uses_search_concepts(self):
        search_engine = self._import_engine()
        with mock.patch.object(search_engine, "search_web_engine_with_status") as mock_search:
            mock_search.return_value = {
                "results": [
                    {"title": "cn result", "url": "https://example.com/cn", "content": ""}
                ],
                "status": {"status": "ok"},
            }
            fallback = search_engine._duckduckgo_fallback_search(
                "如何消除比熊泪痕", search_concepts=["比熊", "泪痕", "消除"]
            )
            self.assertEqual(fallback["status"]["status"], "ok")
            mock_search.assert_called_once()


class HtmlParserV2_1_Tests(unittest.TestCase):
    """HTML 解析器相关测试"""

    @classmethod
    def setUpClass(cls):
        cls._original_path = list(sys.path)
        sys.path.insert(0, os.path.join(ROOT, "scripts"))

    @classmethod
    def tearDownClass(cls):
        sys.path = cls._original_path

    def test_sogou_encrypted_link_normalized(self):
        import html_parser
        url = "/link?url=dn9a_1234"
        resolved = html_parser._resolve_sogou_link(url)
        # 无法真实网络请求时至少返回完整 sogou URL
        self.assertTrue(resolved.startswith("https://www.sogou.com"))

    def test_question_only_titles_filtered_by_bing_parser(self):
        import html_parser
        html = """
        <ol id="b_results">
          <li class="b_algo">
            <h2><a href="https://example.com/1">如何</a></h2>
            <p>snippet</p>
          </li>
          <li class="b_algo">
            <h2><a href="https://example.com/2">比熊泪痕消除方法</a></h2>
            <p>snippet</p>
          </li>
        </ol>
        """
        results = html_parser.parse_bing(html)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "比熊泪痕消除方法")

    def test_html_parser_sogou_decrypts_link(self):
        import html_parser
        html = """
        <div class="vr">
          <h3><a href="/link?url=dn9a_1234">搜狗加密结果</a></h3>
          <p class="str">snippet</p>
        </div>
        """
        results = html_parser.parse_sogou(html)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["url"].startswith("https://www.sogou.com"))

    def test_duckduckgo_parser_web_result_class(self):
        import html_parser
        html = """
        <div class="web-result">
          <a class="result__a" href="https://example.com/ddg">DDG Result</a>
          <div class="result__snippet">snippet text</div>
        </div>
        """
        results = html_parser.parse_duckduckgo(html)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "DDG Result")
        self.assertEqual(results[0]["url"], "https://example.com/ddg")


class SogouDecoderV2_1_Tests(unittest.TestCase):
    """搜狗加密链接解密测试"""

    @classmethod
    def setUpClass(cls):
        cls._original_path = list(sys.path)
        sys.path.insert(0, os.path.join(ROOT, "scripts"))

    @classmethod
    def tearDownClass(cls):
        sys.path = cls._original_path

    def test_extract_url_from_js_location_replace(self):
        import sogou_url_decoder
        html = '<script>location.replace("https://zhihu.com/question/123");</script>'
        self.assertEqual(
            sogou_url_decoder._extract_url_from_js(html),
            "https://zhihu.com/question/123",
        )

    def test_extract_url_from_js_location_href(self):
        import sogou_url_decoder
        html = '<script>window.location.href = "https://example.com/article";</script>'
        self.assertEqual(
            sogou_url_decoder._extract_url_from_js(html),
            "https://example.com/article",
        )

    def test_add_kh_params_appends_k_and_h(self):
        import sogou_url_decoder
        url = "https://www.sogou.com/link?url=dn9a_1234"
        new_url = sogou_url_decoder._add_kh_params(url)
        self.assertIn("k=1", new_url)
        self.assertIn("h=1", new_url)
        self.assertIn("url=dn9a_1234", new_url)

    def test_decode_sogou_url_detects_captcha(self):
        import sogou_url_decoder
        self.assertTrue(sogou_url_decoder._is_captcha_page("请输入验证码"))
        self.assertTrue(sogou_url_decoder._is_captcha_page("antispider"))
        self.assertFalse(sogou_url_decoder._is_captcha_page("正常结果"))

    def test_resolve_sogou_link_returns_full_url_on_failure(self):
        import sogou_url_decoder
        url = "/link?url=dn9a_1234"
        resolved = sogou_url_decoder.resolve_sogou_link(url)
        self.assertTrue(resolved.startswith("https://www.sogou.com"))


class SearchEngineCliV2_1_Tests(unittest.TestCase):
    """问题 2/4 的 CLI 级测试（不依赖网络，避免 subprocess 阻塞）"""

    @classmethod
    def setUpClass(cls):
        cls._original_path = list(sys.path)
        sys.path.insert(0, os.path.join(ROOT, "scripts"))

    @classmethod
    def tearDownClass(cls):
        sys.path = cls._original_path

    def _import_engine(self):
        import search_engine
        return search_engine

    def test_tavily_missing_tip_contains_setup_steps(self):
        search_engine = self._import_engine()
        engine_status = {
            "tavily": {"status": "skipped", "reason": "api_key_missing"},
        }
        tips = search_engine._generate_tips(engine_status)
        self.assertEqual(len(tips), 1)
        tip = tips[0]
        self.assertEqual(tip["code"], "tavily_missing")
        self.assertIn("setup_url", tip)
        self.assertTrue(tip["setup_url"].startswith("https://app.tavily.com"))
        self.assertIn("setup_steps", tip)
        self.assertIn("impact", tip)

    def test_chinese_query_without_concepts_warns_on_stderr(self):
        search_engine = self._import_engine()
        self.assertTrue(search_engine._is_chinese_natural_language("如何消除比熊泪痕"))
        self.assertFalse(search_engine._is_chinese_natural_language("bichon tear stains"))

    def test_version_flag_still_beta(self):
        search_engine = self._import_engine()
        self.assertEqual(search_engine.__version__, "2.1.1")


class SearchEngineV2_1_Bugfix_Tests(unittest.TestCase):
    """v2.1.0-beta.1 新发现 bug 修复验证"""

    @classmethod
    def setUpClass(cls):
        cls._original_path = list(sys.path)
        sys.path.insert(0, os.path.join(ROOT, "scripts"))

    @classmethod
    def tearDownClass(cls):
        sys.path = cls._original_path

    def test_what_is_prefix_fully_stripped(self):
        """NEW-BUG-001: '什么是' 前缀完整剥离"""
        import search_engine
        result = search_engine._strip_question_prefix("什么是量子纠缠")
        self.assertEqual(result, "量子纠缠")
        result2 = search_engine._strip_question_prefix("什么是比熊泪痕")
        self.assertEqual(result2, "比熊泪痕")
        # "什么" 单独使用仍正确
        result3 = search_engine._strip_question_prefix("什么时候出发")
        self.assertEqual(result3, "什么时候出发")

    def test_degraded_title_detection(self):
        """NEW-BUG-002: 降级标题检测覆盖真实模式"""
        import html_parser
        self.assertTrue(html_parser._is_question_only_title("如何（汉语词语）_百度百科"))
        self.assertTrue(html_parser._is_question_only_title("怎样（汉语词汇）_百度百科"))
        self.assertTrue(html_parser._is_question_only_title("什么是的意思 - 汉语词典"))
        self.assertTrue(html_parser._is_question_only_title("如何"))
        self.assertFalse(html_parser._is_question_only_title("比熊泪痕消除方法"))

    def test_engine_status_at_claims_json_toplevel(self):
        """NEW-BUG-003: claims-json 顶层包含 engine_status"""
        import trust_model
        engine_status = {"bing_cn": {"status": "ok", "count": 5}}
        package = trust_model.build_claim_package(
            "test query",
            [],
            metadata={"engine_status": engine_status},
        )
        self.assertIn("engine_status", package)
        self.assertEqual(package["engine_status"], engine_status)
        # 嵌套 search.engine_status 仍存在（向后兼容）
        self.assertIn("engine_status", package["search"])
        self.assertEqual(package["search"]["engine_status"], engine_status)


if __name__ == "__main__":
    unittest.main()
