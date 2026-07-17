#!/usr/bin/env python3
"""research 模式检测测试"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import trust_model


class ResearchModeDetectionTests(unittest.TestCase):
    """验证 research 模式正确检测"""

    def test_research_keyword_triggers_research_mode(self):
        self.assertEqual(trust_model.detect_research_mode("人工智能发展趋势调研报告"), "research")

    def test_analysis_keyword_triggers_research_mode(self):
        self.assertEqual(trust_model.detect_research_mode("新能源汽车市场分析"), "research")

    def test_survey_keyword_triggers_research_mode(self):
        self.assertEqual(trust_model.detect_research_mode("大学生就业现状调查"), "research")

    def test_report_keyword_triggers_research_mode(self):
        self.assertEqual(trust_model.detect_research_mode("2026年经济报告"), "research")

    def test_review_keyword_triggers_research_mode(self):
        self.assertEqual(trust_model.detect_research_mode("机器学习文献综述"), "research")

    def test_evaluation_keyword_triggers_research_mode(self):
        self.assertEqual(trust_model.detect_research_mode("项目风险评估"), "research")

    def test_comparison_keyword_triggers_research_mode(self):
        self.assertEqual(trust_model.detect_research_mode("中美贸易政策比较"), "research")

    def test_fact_query_stays_fact(self):
        self.assertEqual(trust_model.detect_research_mode("今天星期几"), "fact")

    def test_perspective_query_stays_perspective(self):
        self.assertEqual(trust_model.detect_research_mode("如何评价这个政策"), "perspective")

    def test_explicit_mode_overrides(self):
        self.assertEqual(trust_model.detect_research_mode("调研报告", "fact"), "fact")
        self.assertEqual(trust_model.detect_research_mode("简单事实", "research"), "research")


class LimitationsLocalizationTests(unittest.TestCase):
    """限制标注（limitations）必须为中文文案（v2.1.0-beta.2 中文化固化）。"""

    def _evidence_item(self, verified=False, freshness_status="unknown", source_grade="unknown"):
        return {
            "verification": {"verified": verified},
            "freshness": {"status": freshness_status},
            "source_reliability": {"grade": source_grade},
        }

    def test_empty_results_limit_is_chinese(self):
        limits = trust_model.summarize_limits([], [])
        self.assertEqual(limits, ["未收集到任何证据结果；置信度只能保持 E/证据不足。"])

    def test_single_and_unverified_limits_are_chinese(self):
        evidence = [self._evidence_item()]
        limits = trust_model.summarize_limits([{"url": "https://example.com"}], evidence)
        self.assertIn("没有任何证据通过反向验证。", limits)
        self.assertIn("仅 1 条去重证据可用，缺少独立信源交叉印证。", limits)
        self.assertIn("至少 1 条证据未检测到发布日期。", limits)
        self.assertIn("至少 1 个来源域名未被信源可靠性图谱分类。", limits)
        for limit in limits:
            self.assertNotRegex(limit, r"[A-Za-z]{4,}")  # 不得残留成段英文

    def test_engine_limits_are_chinese(self):
        engine_status = {
            "baidu": {"status": "blocked", "reason": "captcha_or_security_challenge"},
            "sogou": {"status": "failed", "reason": "TimeoutError"},
            "tavily": {"status": "skipped", "reason": "api_key_missing"},
            "bing_cn": {"status": "empty", "reason": "no_results_parsed"},
        }
        limits = trust_model.summarize_engine_limits(engine_status)
        self.assertEqual(
            limits,
            [
                "搜索引擎 baidu 被拦截（captcha_or_security_challenge）；这不等于证据不存在。",
                "搜索引擎 bing_cn 未解析到结果。",
                "搜索引擎 sogou 调用失败（TimeoutError）；覆盖可能不完整。",
                "搜索引擎 tavily 已跳过（api_key_missing）。",
            ],
        )


if __name__ == "__main__":
    unittest.main()
