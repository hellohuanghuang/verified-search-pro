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


if __name__ == "__main__":
    unittest.main()
