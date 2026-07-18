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

    def test_strategy_docs_track_current_engine_chassis(self):
        """场景文档必须与当前搜索底盘一致（2026-07-18 甲方审计发现的同步滞后固化为门禁）。

        - 默认引擎 baidu_api 必须出现在策略与降级文档中；
        - 已放弃/移除的通道（搜狗微信作为推荐路径、旧百度 HTML 引擎）不得复活。
        """
        strategy = read_text("references/01-search-strategy.md")
        fallback = read_text("references/06-fallback-guide.md")
        self.assertIn("baidu_api", strategy)
        self.assertIn("baidu_api", fallback)
        self.assertNotIn("搜狗微信 |", strategy)          # 不得作为表格首选/推荐路径
        self.assertNotIn("可用百度", strategy)             # 旧百度 HTML 残留
        self.assertNotIn("可用百度", fallback)
        self.assertNotIn("engines baidu", fallback)        # 失效引擎 id

    def test_skill_md_consistency_with_engine_chassis(self):
        """SKILL.md 表述必须与搜索底盘一致（2026-07-18 甲方审计第二批意见固化为门禁）。

        frontmatter 与正文涉及引擎/密钥的表述，必须与代码真实环境变量、references 唯一事实源对齐；
        SKILL.md 含字面反斜杠转义，断言前先去反斜杠归一化。
        """
        skill = read_text("SKILL.md").replace("\\", "")
        for token in [
            "TAVILY_API_KEY",
            "TENCENTCLOUD_SECRET_ID",
            "TENCENTCLOUD_SECRET_KEY",
            "BAIDU_API_KEY",
            "Node.js",
            "baidu_api",
        ]:
            self.assertIn(token, skill)
        self.assertIn("何时读取本文件", read_text("references/07-cross-platform.md"))

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

    def test_readme_has_quickstart_and_troubleshooting_and_contributing(self):
        readme = read_text("README.md")

        self.assertIn("5 分钟上手", readme)
        self.assertIn("常见失败排查", readme)
        self.assertIn("如何贡献", readme)
        self.assertIn("CONTRIBUTING.md", readme)


if __name__ == "__main__":
    unittest.main()
