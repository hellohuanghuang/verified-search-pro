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


if __name__ == "__main__":
    unittest.main()
