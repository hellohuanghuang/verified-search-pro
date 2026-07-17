import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import search_engine  # noqa: E402


class SearchEnginePolicyTests(unittest.TestCase):
    def test_detects_baidu_security_challenge(self):
        html = """
        <html>
          <title>百度安全验证</title>
          <body>请输入验证码后继续访问 verify.baidu.com</body>
        </html>
        """

        blocked = search_engine.detect_blocked_page("baidu", html)

        self.assertTrue(blocked["blocked"])
        self.assertEqual(blocked["reason"], "captcha_or_security_challenge")

    def test_auto_budget_keeps_simple_fact_check_light(self):
        self.assertEqual(search_engine.recommend_budget("确认 OpenAI CEO 是谁", "fact"), "lite")

    def test_auto_budget_uses_deep_for_perspective_mode(self):
        self.assertEqual(search_engine.recommend_budget("某政策 争议 观点", "perspective"), "deep")

    def test_default_engines_include_duckduckgo(self):
        env = search_engine.check_environment()
        default_engines = env["search"]["default_engines"]
        self.assertIn("duckduckgo", default_engines)
        self.assertIn("bing_cn", default_engines)
        self.assertIn("sogou", default_engines)

    def test_parse_args_accepts_search_concepts(self):
        parsed = search_engine.parse_args(["如何消除比熊的泪痕", "--search-concepts", "比熊,泪痕,消除方法", "--verify"])
        self.assertEqual(parsed["search_concepts"], ["比熊", "泪痕", "消除方法"])
        self.assertIn("duckduckgo", parsed["engines"])
        self.assertTrue(parsed["verify"])

    def test_parse_args_empty_search_concepts(self):
        parsed = search_engine.parse_args(["比熊泪痕"])
        self.assertIsNone(parsed["search_concepts"])

    def test_duckduckgo_registered_as_web_engine(self):
        env = search_engine.check_environment()
        self.assertIn("duckduckgo", env["search"]["web_engines"])

    def test_toutiao_registered_as_web_engine_but_not_default(self):
        """头条搜索已注册进 WEB_ENGINES（doctor 可见），但不进入默认引擎列表。"""
        env = search_engine.check_environment()
        self.assertIn("toutiao", env["search"]["web_engines"])
        self.assertNotIn("toutiao", env["search"]["default_engines"])

    def test_parse_args_keeps_default_engines_without_toutiao(self):
        parsed = search_engine.parse_args(["科技"])
        self.assertNotIn("toutiao", parsed["engines"])

    def test_parse_args_accepts_explicit_toutiao(self):
        parsed = search_engine.parse_args(["科技", "--engines", "toutiao,bing_cn"])
        self.assertIn("toutiao", parsed["engines"])

    def test_detects_toutiao_security_challenge(self):
        html = """
        <html>
          <title>安全验证</title>
          <body>安全验证：请拖动滑块完成验证后继续访问</body>
        </html>
        """

        blocked = search_engine.detect_blocked_page("toutiao", html)

        self.assertTrue(blocked["blocked"])
        self.assertEqual(blocked["reason"], "captcha_or_security_challenge")

    def test_detects_toutiao_short_page_without_result_container(self):
        """无签名词但结果容器完全缺失且页面异常短 → 结构性风控识别为 blocked。"""
        html = "<html><head><title>跳转中</title></head><body>loading...</body></html>"

        blocked = search_engine.detect_blocked_page("toutiao", html)

        self.assertTrue(blocked["blocked"])
        self.assertEqual(blocked["reason"], "missing_result_container")

    def test_toutiao_normal_page_not_marked_blocked(self):
        """含结果容器标记的正常结果页不得误判为 blocked。"""
        with open(
            os.path.join(ROOT, "tests", "fixtures", "toutiao_sample.html"),
            "r", encoding="utf-8",
        ) as f:
            html = f.read()

        blocked = search_engine.detect_blocked_page("toutiao", html)

        self.assertFalse(blocked["blocked"])

    def test_toutiao_blocked_fixture_marked_blocked(self):
        """合成风控页 fixture → 签名词命中 + 结构特征双重判定为 blocked。"""
        with open(
            os.path.join(ROOT, "tests", "fixtures", "toutiao_blocked_sample.html"),
            "r", encoding="utf-8",
        ) as f:
            html = f.read()

        blocked = search_engine.detect_blocked_page("toutiao", html)

        self.assertTrue(blocked["blocked"])

    def test_toutiao_template_variant_page_not_marked_blocked(self):
        """undefined-default 模板变体的正常 SERP（"新能源汽车" 实测页）不得误判为 blocked。

        该页含 result-content/real-index 结果容器与真实有机结果，
        仅因有机结果使用另一种卡片模板；verify/slider 等子串在两份实测
        正常页中等量出现（JS 事件名/CSS 类），不得作为风控依据。
        """
        with open(
            os.path.join(ROOT, "tests", "fixtures", "toutiao_nev_sample.html"),
            "r", encoding="utf-8",
        ) as f:
            html = f.read()

        blocked = search_engine.detect_blocked_page("toutiao", html)

        self.assertFalse(blocked["blocked"])


if __name__ == "__main__":
    unittest.main()
