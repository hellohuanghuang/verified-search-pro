#!/usr/bin/env python3
"""HTML 解析器单元测试。使用本地 fixture，不依赖真实网络。"""

import os
import sys
import unittest
import urllib.parse
from unittest import mock


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


class DuckDuckGoParserTests(unittest.TestCase):
    def test_parses_results_from_fixture(self):
        html = _load_html("duckduckgo_sample.html")
        results = html_parser.parse_duckduckgo(html)

        self.assertGreaterEqual(len(results), 2)
        titles = [r["title"] for r in results]
        self.assertIn("比熊泪痕怎么去除？知乎回答", titles)
        urls = [r["url"] for r in results]
        self.assertTrue(any("zhihu.com" in u or "sohu.com" in u for u in urls))

    def test_legacy_parse_duckduckgo_fallback(self):
        html = _load_html("duckduckgo_sample.html")
        results = html_parser._legacy_parse_duckduckgo(html)
        self.assertGreaterEqual(len(results), 2)

    def test_duckduckgo_registered(self):
        self.assertTrue(callable(html_parser.get_parser("duckduckgo")))


class ParserRegistryTests(unittest.TestCase):
    def test_get_parser_returns_callable_for_known_engines(self):
        for engine in ("baidu", "bing_cn", "sogou", "wechat", "duckduckgo"):
            parser = html_parser.get_parser(engine)
            self.assertTrue(callable(parser), f"{engine} parser should be callable")

    def test_get_parser_returns_none_for_unknown_engine(self):
        self.assertIsNone(html_parser.get_parser("unknown_engine"))


class BingRealPageRegressionTests(unittest.TestCase):
    """BUG-ENV-1 回归：真实必应页用 <ol id="b_results"> 包裹 li.b_algo，
    状态机不得把整页结果合并成一条，且标题与 URL 不得跨块串扰。"""

    def test_real_sample_yields_per_block_results(self):
        html = _load_html("bing_real_sample.html")
        results = html_parser.parse_bing(html)

        self.assertGreaterEqual(len(results), 5)
        for r in results:
            self.assertTrue(r["title"])
            self.assertTrue(r["url"].startswith("http"))
            self.assertTrue(r["content"])
        by_title = {r["title"]: r["url"] for r in results}
        self.assertEqual(by_title["OpenAI"], "https://openai.smapply.org/")
        self.assertEqual(by_title["OpenAI · GitHub"], "https://github.com/openai/")
        self.assertIn("mission", results[0]["content"])

    def test_ol_wrapper_with_unquoted_attrs_does_not_merge(self):
        html = (
            '<ol id="b_results" class="">'
            '<li class="b_algo" data-id iid=SERP.1><h2 class=""><a href="https://a.example/1">结果甲</a></h2>'
            '<div class="b_caption"><p class="b_lineclamp2">摘要甲</p></div></li>'
            '<li class="b_algo" data-id iid=SERP.2><h2 class=""><a href="https://a.example/2">结果乙</a></h2>'
            '<div class="b_caption"><p class="b_lineclamp2">摘要乙</p></div></li>'
            '</ol>'
        )
        results = html_parser.parse_bing(html)

        self.assertEqual([r["title"] for r in results], ["结果甲", "结果乙"])
        self.assertEqual([r["url"] for r in results], ["https://a.example/1", "https://a.example/2"])
        self.assertEqual([r["content"] for r in results], ["摘要甲", "摘要乙"])


class SogouRealPageRegressionTests(unittest.TestCase):
    """BUG-ENV-2 回归：真实搜狗页主链接是 /link?url=... 加密相对链接，
    提取阶段必须保留（否则整条结果被丢弃），并由解密钩子统一解析。"""

    def test_real_sample_preserves_and_resolves_encrypted_links(self):
        html = _load_html("sogou_real_sample.html")
        with mock.patch.object(
            html_parser,
            "_resolve_sogou_link",
            side_effect=lambda url, **kw: "https://resolved.test/" + urllib.parse.quote(url, safe=""),
        ) as resolver:
            results = html_parser.parse_sogou(html)

        # 8 个经典块（7 条加密链接 + 1 条绝对链接）；无 h3 的卡片块与推荐框应被跳过
        self.assertEqual(len(results), 8)
        self.assertEqual(resolver.call_count, 7)
        titles = [r["title"] for r in results]
        self.assertTrue(any("奥特曼为Reddit第三大股东" in t for t in titles))
        self.assertTrue(any("马斯克骂我们都是蠢货" in t for t in titles))
        self.assertTrue(any("OpenAICEO" in t for t in titles))
        self.assertFalse(any("大家还在搜" in t for t in titles))
        self.assertFalse(any("Palantir" in t for t in titles))
        for r in results:
            self.assertTrue(r["title"])
            self.assertTrue(r["url"].startswith("http"))
            self.assertTrue(r["content"])
        # 绝对链接结果不经过解密钩子，原样保留
        self.assertIn(
            "http://mp.weixin.qq.com/s?src=11&timestamp=1784281980&ver=6848&signature=AKyOK",
            [r["url"] for r in results],
        )
        # 摘要来自真实页的 space-txt 容器
        self.assertTrue(any("Reddit" in r["content"] for r in results))

    def test_extractor_preserves_sogou_link_before_resolution(self):
        """底层提取器对 /link?url=... 应保留原始路径，而不是置空丢弃。"""
        html = (
            '<div class="vrwrap"><h3 class="vr-title">'
            '<a target="_blank" href="/link?url=hedJjaC291NbWrwHYHKCyPvjU9Tbu8QRaJrgRIXUqR5_.">加密标题</a></h3>'
            '<div class="fz-mid space-txt">摘要文本</div></div>'
        )
        raw = html_parser._extract_with_parser(
            html,
            [{"tag": "div", "class": "vrwrap"}],
            [{"tag": "h3"}],
            [{"tag": "div", "class": "space-txt"}],
            url_normalizer=html_parser._preserve_sogou_link,
        )
        self.assertEqual(len(raw), 1)
        self.assertEqual(raw[0]["url"], "/link?url=hedJjaC291NbWrwHYHKCyPvjU9Tbu8QRaJrgRIXUqR5_.")
        self.assertEqual(raw[0]["title"], "加密标题")
        self.assertEqual(raw[0]["content"], "摘要文本")


class ToutiaoParserTests(unittest.TestCase):
    """头条搜索（so.toutiao.com）解析测试。

    fixture 精简自 2026-07 真实页面：3 个普通结果（67-default/homepage_official）
    + 1 个阿拉丁卡（26-chengyu_detail）+ 1 个相关搜索框（21-undefined）。
    """

    def test_toutiao_registered(self):
        self.assertTrue(callable(html_parser.get_parser("toutiao")))

    def test_parses_results_from_fixture(self):
        html = _load_html("toutiao_sample.html")
        results = html_parser.parse_toutiao(html)

        # 3 个普通结果；阿拉丁卡与相关搜索框应被排除
        self.assertEqual(len(results), 3)
        titles = [r["title"] for r in results]
        self.assertIn("中国科技网首页", titles)
        self.assertIn("科技-新华网", titles)
        self.assertIn("科技-搜狐网", titles)
        for r in results:
            self.assertTrue(r["title"])
            self.assertTrue(r["content"])

    def test_excludes_aladdin_cards_and_related_search_boxes(self):
        html = _load_html("toutiao_sample.html")
        results = html_parser.parse_toutiao(html)

        titles = [r["title"] for r in results]
        # 相关搜索框标题不得出现
        self.assertNotIn("大家都在搜", titles)
        self.assertNotIn("相关搜索", titles)
        # 站内搜索链接（非跳转、非外链）不得作为结果 URL
        for r in results:
            self.assertFalse(r["url"].startswith("/search?"))

    def test_preserves_signed_jump_links_as_is(self):
        """头条结果 URL 是 /search/jump?aid=...&jtoken=... 签名中间跳转链接：
        合规要求原样保留，不解析、不逆向、不发起二次请求。"""
        html = _load_html("toutiao_sample.html")
        results = html_parser.parse_toutiao(html)

        self.assertTrue(results)
        for r in results:
            self.assertTrue(r["url"].startswith("/search/jump?"))
            self.assertIn("jtoken=", r["url"])

    def test_legacy_parse_toutiao_fallback(self):
        html = _load_html("toutiao_sample.html")
        results = html_parser._legacy_parse_toutiao(html)

        self.assertGreaterEqual(len(results), 3)
        titles = [r["title"] for r in results]
        self.assertIn("中国科技网首页", titles)

    def test_blocked_page_returns_empty(self):
        """验证页/风控页特征（无结果容器）时解析器返回空列表，由上层标记 blocked。"""
        captcha_html = (
            "<!DOCTYPE html><html><head><title>安全验证</title></head>"
            "<body><div class=\"captcha-wrap\">安全验证：请拖动滑块完成验证</div></body></html>"
        )
        self.assertEqual(html_parser.parse_toutiao(captcha_html), [])

    def test_blocked_fixture_returns_empty(self):
        """合成风控页 fixture（极短、无 real-index 结果标记、含安全验证文案）返回空。"""
        html = _load_html("toutiao_blocked_sample.html")
        self.assertEqual(html_parser.parse_toutiao(html), [])

    def test_empty_input_returns_empty(self):
        self.assertEqual(html_parser.parse_toutiao(""), [])


class ToutiaoTemplateVariantTests(unittest.TestCase):
    """头条 undefined-default 模板变体（头条号内容结果）解析测试。

    fixture 精简自 2026-07 真实页面（"新能源汽车" 查询）：有机结果使用
    card_undefined-default 容器，标题链接无 l-article-header（l-card-title h3），
    摘要容器为 l-paragraph；同页阿拉丁卡（26-zol_subcate）与相关搜索框应被排除。
    """

    def test_parses_template_variant_results(self):
        html = _load_html("toutiao_nev_sample.html")
        results = html_parser.parse_toutiao(html)

        self.assertEqual(len(results), 2)
        titles = [r["title"] for r in results]
        self.assertIn("新能源汽车，不能再“负重”前行", titles)
        self.assertIn("新能源汽车前景展望:为什么终局属于纯电驱动?", titles)
        for r in results:
            self.assertTrue(r["title"])
            self.assertTrue(r["content"])
            self.assertTrue(r["url"].startswith("/search/jump?"))

    def test_variant_excludes_aladdin_and_related_search(self):
        html = _load_html("toutiao_nev_sample.html")
        results = html_parser.parse_toutiao(html)

        titles = [r["title"] for r in results]
        self.assertNotIn("相关搜索", titles)
        # 阿拉丁卡标题（商品排行榜）不得混入
        self.assertFalse(any("商品排行榜" in t for t in titles))

    def test_variant_snippet_from_l_paragraph(self):
        html = _load_html("toutiao_nev_sample.html")
        results = html_parser.parse_toutiao(html)

        snippets = [r["content"] for r in results]
        self.assertTrue(any("整备质量" in s for s in snippets))
        self.assertTrue(any("纯电驱动" in s for s in snippets))

    def test_legacy_fallback_covers_template_variant(self):
        html = _load_html("toutiao_nev_sample.html")
        results = html_parser._legacy_parse_toutiao(html)

        self.assertEqual(len(results), 2)
        titles = [r["title"] for r in results]
        self.assertIn("新能源汽车，不能再“负重”前行", titles)


if __name__ == "__main__":
    unittest.main()
