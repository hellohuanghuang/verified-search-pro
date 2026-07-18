import datetime
import os
import sys
import unittest
from unittest import mock


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import date_extract  # noqa: E402
import search_engine  # noqa: E402


NOW = datetime.datetime(2026, 2, 10, 12, 0, 0)


class ExplicitDateTests(unittest.TestCase):
    """显式日期文本：中文 / ISO / 斜杠 / 英文序。"""

    def test_chinese_date(self):
        self.assertEqual(date_extract.extract_from_text("2026年1月12日，财政部发布……", now=NOW), "2026-01-12")

    def test_chinese_date_without_day_suffix(self):
        self.assertEqual(date_extract.extract_from_text("截至2026年1月12，政策已生效", now=NOW), "2026-01-12")

    def test_iso_date(self):
        self.assertEqual(date_extract.extract_from_text("发布于 2026-01-12 的新闻", now=NOW), "2026-01-12")

    def test_slash_date(self):
        self.assertEqual(date_extract.extract_from_text("更新：2026/01/12", now=NOW), "2026-01-12")

    def test_dot_date(self):
        self.assertEqual(date_extract.extract_from_text("版本 2026.01.12 发布", now=NOW), "2026-01-12")

    def test_english_order_date(self):
        self.assertEqual(date_extract.extract_from_text("Posted 01/12/2026 by admin", now=NOW), "2026-01-12")

    def test_year_first_not_confused_with_english_order(self):
        # 2026/01/12 应按年-月-日解析，而非 20/26/01
        self.assertEqual(date_extract.extract_from_text("2026/01/12", now=NOW), "2026-01-12")


class RelativeDateTests(unittest.TestCase):
    """相对日期：以注入基准时间换算。"""

    def test_days_ago(self):
        self.assertEqual(date_extract.extract_from_text("3天前", now=NOW), "2026-02-07")

    def test_hours_ago_same_day(self):
        self.assertEqual(date_extract.extract_from_text("5小时前", now=NOW), "2026-02-10")

    def test_hours_ago_crosses_midnight(self):
        self.assertEqual(date_extract.extract_from_text("20小时前", now=NOW), "2026-02-09")

    def test_weeks_ago(self):
        self.assertEqual(date_extract.extract_from_text("2周前", now=NOW), "2026-01-27")

    def test_weeks_ago_xingqi(self):
        self.assertEqual(date_extract.extract_from_text("1星期前", now=NOW), "2026-02-03")

    def test_months_ago(self):
        self.assertEqual(date_extract.extract_from_text("3个月前", now=NOW), "2025-11-10")

    def test_months_ago_without_ge(self):
        self.assertEqual(date_extract.extract_from_text("2月前", now=NOW), "2025-12-10")

    def test_months_ago_clamps_day(self):
        # 1月31日回退1个月 → 去年12月31日（12月有31日，无需 clamp）；
        # 3月31日回退1个月 → 2月28日（需 clamp）
        now = datetime.datetime(2026, 3, 31, 12, 0, 0)
        self.assertEqual(date_extract.extract_from_text("1个月前", now=now), "2026-02-28")

    def test_yesterday(self):
        self.assertEqual(date_extract.extract_from_text("昨天", now=NOW), "2026-02-09")

    def test_yesterday_with_time(self):
        self.assertEqual(date_extract.extract_from_text("昨天 16:30", now=NOW), "2026-02-09")


class UrlDateTests(unittest.TestCase):
    """URL 日期路径三种形态。"""

    def test_slash_separated_path(self):
        self.assertEqual(date_extract.extract_from_url("https://example.com/2026/01/12/policy", now=NOW), "2026-01-12")

    def test_dash_separated_path(self):
        self.assertEqual(date_extract.extract_from_url("https://example.com/news/2026-01-12/", now=NOW), "2026-01-12")

    def test_compact_path(self):
        self.assertEqual(date_extract.extract_from_url("https://example.com/p/20260112.html", now=NOW), "2026-01-12")

    def test_url_without_date(self):
        self.assertEqual(date_extract.extract_from_url("https://example.com/about", now=NOW), "")


class SanityCheckTests(unittest.TestCase):
    """合理性强校验：未来日期、古早日期、非法日期、无日期文本。"""

    def test_future_date_rejected(self):
        self.assertEqual(date_extract.extract_from_text("发布于 2027-01-01", now=NOW), "")

    def test_future_within_tolerance_accepted(self):
        # +2 天时钟误差容忍
        self.assertEqual(date_extract.extract_from_text("2026-02-12", now=NOW), "2026-02-12")

    def test_pre_2005_rejected(self):
        self.assertEqual(date_extract.extract_from_text("本文写于1999年12月31日", now=NOW), "")

    def test_invalid_date_rejected(self):
        self.assertEqual(date_extract.extract_from_text("2026-13-45", now=NOW), "")

    def test_no_date_text(self):
        self.assertEqual(date_extract.extract_from_text("新能源汽车补贴政策解读", now=NOW), "")

    def test_empty_inputs(self):
        self.assertEqual(date_extract.extract_from_text("", now=NOW), "")
        self.assertEqual(date_extract.extract_from_url(None, now=NOW), "")
        self.assertEqual(date_extract.extract_date("", "", "", now=NOW), "")

    def test_future_url_date_rejected(self):
        self.assertEqual(date_extract.extract_from_url("https://example.com/2030/01/01/x", now=NOW), "")


class CombinedEntryTests(unittest.TestCase):
    """extract_date 综合入口优先级。"""

    def test_text_takes_priority_over_url(self):
        result = date_extract.extract_date(
            title="2026年2月1日发布的新规",
            snippet="",
            url="https://example.com/2025/12/01/old",
            now=NOW,
        )
        self.assertEqual(result, "2026-02-01")

    def test_url_fallback_when_text_has_no_date(self):
        result = date_extract.extract_date(
            title="补贴政策解读",
            snippet="详细内容",
            url="https://example.com/2026/01/12/policy",
            now=NOW,
        )
        self.assertEqual(result, "2026-01-12")


SOGOU_HTML_WITH_DATE = """
<html><body>
<div class="vr">
  <h3><a href="https://example.com/news/policy">2026年新能源汽车补贴政策解读</a></h3>
  <p class="str">3天前，财政部发布新能源汽车补贴政策延续购置税减免……</p>
</div>
</body></html>
"""


class EngineIntegrationTests(unittest.TestCase):
    """端到端：HTML 引擎结果经 search_engine 归一化后 published_at 被补齐。"""

    def _fetch_with_html(self, html):
        def fake_fetch(url, **kwargs):
            return 200, {}, html.encode("utf-8")
        return fake_fetch

    def test_web_engine_result_gets_published_at(self):
        with mock.patch.object(
            search_engine._network, "fetch_with_retry",
            side_effect=self._fetch_with_html(SOGOU_HTML_WITH_DATE),
        ):
            payload = search_engine._fetch_web_engine_once("sogou", "补贴政策", use_cache=False)

        self.assertEqual(payload["status"]["status"], "ok")
        self.assertEqual(len(payload["results"]), 1)
        published = payload["results"][0]["published_at"]
        expected = (datetime.datetime.now().date() - datetime.timedelta(days=3)).isoformat()
        self.assertEqual(published, expected)

    def test_parser_provided_date_not_overwritten(self):
        """解析器/API 已提供 published_at 时，启发式不得覆盖。"""
        def fake_parser(html):
            return [{
                "url": "https://example.com/a",
                "title": "已有日期的结果",
                "content": "3天前更新",
                "published_at": "2025-05-05",
            }]

        with mock.patch.dict(search_engine.WEB_ENGINES["sogou"], {"parser": fake_parser}):
            with mock.patch.object(
                search_engine._network, "fetch_with_retry",
                side_effect=self._fetch_with_html("<html><body></body></html>"),
            ):
                payload = search_engine._fetch_web_engine_once("sogou", "测试", use_cache=False)

        self.assertEqual(payload["results"][0]["published_at"], "2025-05-05")

    def test_no_date_anywhere_yields_empty(self):
        with mock.patch.object(
            search_engine._network, "fetch_with_retry",
            side_effect=self._fetch_with_html(
                '<html><body><div class="vr"><h3><a href="https://example.com/x">无日期标题</a></h3>'
                '<p class="str">无日期摘要内容</p></div></body></html>'
            ),
        ):
            payload = search_engine._fetch_web_engine_once("sogou", "测试", use_cache=False)

        self.assertEqual(payload["results"][0]["published_at"], "")


if __name__ == "__main__":
    unittest.main()
