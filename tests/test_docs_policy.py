import json
import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_text(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()


class DocumentationPolicyTests(unittest.TestCase):
    def test_no_forced_chinese_or_default_feishu_delivery(self):
        files = [
            "SKILL.md",
            "README.md",
            "references/05-output-template.md",
            "references/07-cross-platform.md",
            ".claude/CLAUDE.md",
            ".codex/instructions.md",
        ]
        banned_phrases = [
            "中文" + "为主",
            "飞书" + "文档",
            "feishu" + "_create_doc",
            "feishu" + "_update_doc",
            "交付" + "飞书",
            "上传" + "飞书",
        ]

        for path in files:
            text = read_text(path)
            for phrase in banned_phrases:
                self.assertNotIn(phrase, text, f"{phrase!r} should not appear in {path}")

    def test_default_delivery_is_markdown_plus_claims_json(self):
        for path in ("SKILL.md", "README.md", "references/05-output-template.md"):
            text = read_text(path)
            self.assertIn("Markdown", text, path)
            self.assertIn("claims-json", text, path)

    def test_language_policy_follows_user_context(self):
        skill = read_text("SKILL.md")
        output_template = read_text("references/05-output-template.md")

        self.assertIn("跟随用户上下文", skill)
        self.assertIn("跟随用户上下文", output_template)

    def test_openclaw_is_optional_and_paths_are_relative(self):
        readme = read_text("README.md")
        cross_platform = read_text("references/07-cross-platform.md")
        with open(os.path.join(ROOT, "_meta.json"), encoding="utf-8") as f:
            meta = json.load(f)

        self.assertIn("OpenClaw（可选示例）", readme)
        self.assertIn("OpenClaw / Hermes 可选适配", cross_platform)
        self.assertEqual(meta["config"]["scriptPath"], "scripts/search_engine.py")
        self.assertNotIn("~/." + "openclaw", json.dumps(meta, ensure_ascii=False))

    def test_context_budget_and_evidence_pack_are_documented(self):
        skill = read_text("SKILL.md")
        output_template = read_text("references/05-output-template.md")

        self.assertIn("256k", skill)
        self.assertIn("lite / standard / deep", skill)
        self.assertIn("evidence-pack", output_template)
        self.assertIn("观点地图", output_template)
        self.assertIn("常见误区", output_template)
        self.assertIn("时间演进", output_template)

    def test_google_and_tavily_are_not_default_plugin_dependencies(self):
        files = [
            "SKILL.md",
            "README.md",
            "references/01-search-strategy.md",
            "references/06-fallback-guide.md",
            "references/07-cross-platform.md",
        ]
        for path in files:
            text = read_text(path)
            self.assertNotIn("Tavily " + "插件", text, path)
            self.assertNotIn("Google " + "默认", text, path)

        strategy = read_text("references/01-search-strategy.md")
        fallback = read_text("references/06-fallback-guide.md")
        self.assertIn("Google 暂不进入默认能力", strategy)
        self.assertIn("TAVILY_API_KEY", fallback)
        self.assertIn("direct REST API", fallback)

    def test_host_search_is_optional_input_not_default_dependency(self):
        files = [
            "SKILL.md",
            "README.md",
            "references/01-search-strategy.md",
            "references/07-cross-platform.md",
            ".claude/CLAUDE.md",
            ".codex/instructions.md",
        ]
        for path in files:
            text = read_text(path)
            self.assertIn("--input-results", text, path)
            self.assertNotIn("内置 " + "Kimi Search", text, path)
            self.assertNotIn("默认依赖 " + "Kimi", text, path)

    def test_checkpoint_is_adaptive_not_mandatory(self):
        skill = read_text("SKILL.md")
        readme = read_text("README.md")
        cross_platform = read_text("references/07-cross-platform.md")

        self.assertIn("--checkpoint auto|batch|interactive", skill)
        self.assertIn("自适应检查点", readme)
        self.assertIn("checkpoint=interactive", cross_platform)
        self.assertNotIn("强制" + "铁律", skill)
        self.assertNotIn("不可自动" + "连续执行", skill)

    def test_baidu_and_wechat_antibot_are_documented_as_blocked_not_bypassed(self):
        fallback = read_text("references/06-fallback-guide.md")

        self.assertIn("engine_status: blocked", fallback)
        self.assertIn("不绕过验证码", fallback)
        self.assertIn("不伪造 Cookie", fallback)
        self.assertIn("不使用代理池", fallback)


if __name__ == "__main__":
    unittest.main()
