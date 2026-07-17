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


if __name__ == "__main__":
    unittest.main()
