#!/usr/bin/env python3
"""HTML 解析器单元测试。使用本地 fixture，不依赖真实网络。"""

import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import html_parser  # noqa: E402


FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_html(name: str) -> str:
    with open(os.path.join(FIXTURE_DIR, name), "r", encoding="utf-8") as f:
        return f.read()


class StripAndNormalizeTests(unittest.TestCase):
    def test_strip_tags_removes_html_and_decodes_entities(self):
        raw = "<div>Hello&nbsp;World &quot;quote&quot;</div>"
        self.assertEqual(html_parser._strip_tags(raw), "Hello World \"quote\"")

    def test_normalize_url_decodes_baidu_redirect(self):
        url = "/url?url=https%3A%2F%2Fwww.gov.cn%2Fpolicy%2F2026-01-01.htm"
        self.assertEqual(
            html_parser._normalize_url(url),
            "https://www.gov.cn/policy/2026-01-01.htm",
        )

    def test_normalize_url_filters_relative_path(self):
        self.assertEqual(html_parser._normalize_url("/relative/path"), "")

    def test_normalize_url_keeps_absolute_url(self):
        url = "https://example.com/article"
        self.assertEqual(html_parser._normalize_url(url), url)


class BaiduParserTests(unittest.TestCase):
    def test_parses_results_from_fixture(self):
        html = _load_html("baidu_sample.html")
        results = html_parser.parse_baidu(html)

        self.assertGreaterEqual(len(results), 2)
        self.assertEqual(results[0]["title"], "2026 年新能源汽车政策发布")
        self.assertEqual(results[0]["url"], "https://www.gov.cn/policy/2026-01-01.htm")
        self.assertIn("国务院", results[0]["content"])

    def test_parses_both_result_and_c_container_classes(self):
        html = _load_html("baidu_sample.html")
        results = html_parser.parse_baidu(html)

        titles = [r["title"] for r in results]
        self.assertIn("新能源汽车销量创新高", titles)


class BingParserTests(unittest.TestCase):
    def test_parses_results_from_fixture(self):
        html = _load_html("bing_sample.html")
        results = html_parser.parse_bing(html)

        self.assertGreaterEqual(len(results), 3)
        self.assertEqual(results[0]["title"], "Global EV sales rise 30% in first half of 2026")
        self.assertEqual(results[0]["url"], "https://www.reuters.com/business/autos/electric-vehicles-2026")
        self.assertIn("electric vehicle", results[0]["content"].lower())


class SogouParserTests(unittest.TestCase):
    def test_parses_results_from_fixture(self):
        html = _load_html("sogou_sample.html")
        results = html_parser.parse_sogou(html)

        self.assertGreaterEqual(len(results), 2)
        titles = [r["title"] for r in results]
        self.assertIn("2026 年新能源车市场分析报告", titles)
        self.assertIn("国务院发布新能源汽车产业规划", titles)


class WeChatParserTests(unittest.TestCase):
    def test_parses_wechat_results_from_fixture(self):
        html = _load_html("wechat_sample.html")
        results = html_parser.parse_wechat_sogou(html)

        self.assertGreaterEqual(len(results), 2)
        self.assertEqual(results[0]["title"], "2026 年新能源汽车十大趋势")
        self.assertEqual(results[0]["url"], "https://mp.weixin.qq.com/s/abc123")
        self.assertIn("微信公众号", results[0]["content"])


class ParserRegistryTests(unittest.TestCase):
    def test_get_parser_returns_callable_for_known_engines(self):
        for engine in ("baidu", "bing_cn", "sogou", "wechat"):
            parser = html_parser.get_parser(engine)
            self.assertTrue(callable(parser), f"{engine} parser should be callable")

    def test_get_parser_returns_none_for_unknown_engine(self):
        self.assertIsNone(html_parser.get_parser("unknown_engine"))


if __name__ == "__main__":
    unittest.main()
