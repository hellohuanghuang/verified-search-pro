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


if __name__ == "__main__":
    unittest.main()
