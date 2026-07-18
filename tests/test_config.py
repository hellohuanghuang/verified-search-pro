#!/usr/bin/env python3
"""配置系统单元测试。"""

import os
import sys
import tempfile
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import config  # noqa: E402


class ConfigLoadingTests(unittest.TestCase):
    def test_default_config_loads_with_required_keys(self):
        cfg = config.load_config(apply_env=False)
        self.assertIn("user_agent", cfg)
        self.assertIn("web_engines", cfg)
        self.assertIn("domain_ranking", cfg)
        self.assertIn("budget_profiles", cfg)
        self.assertIn("cache_ttl_seconds", cfg)
        self.assertIn("network", cfg)

    def test_user_config_overrides_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            user_path = os.path.join(tmpdir, "config.json")
            with open(user_path, "w", encoding="utf-8") as f:
                f.write('{"user_agent": "CustomAgent/1.0", "cache_ttl_seconds": 60}')

            cfg = config.load_config(user_path=user_path, apply_env=False)
            self.assertEqual(cfg["user_agent"], "CustomAgent/1.0")
            self.assertEqual(cfg["cache_ttl_seconds"], 60)
            # 默认值仍保留
            self.assertIn("web_engines", cfg)

    def test_environment_variable_overrides_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            user_path = os.path.join(tmpdir, "config.json")
            with open(user_path, "w", encoding="utf-8") as f:
                f.write('{"user_agent": "UserAgent/1.0"}')

            env = os.environ.copy()
            env["VSP_USER_AGENT"] = "EnvAgent/1.0"
            old = os.environ.get("VSP_USER_AGENT")
            os.environ["VSP_USER_AGENT"] = "EnvAgent/1.0"
            try:
                cfg = config.load_config(user_path=user_path, apply_env=True)
                self.assertEqual(cfg["user_agent"], "EnvAgent/1.0")
            finally:
                if old is None:
                    os.environ.pop("VSP_USER_AGENT", None)
                else:
                    os.environ["VSP_USER_AGENT"] = old

    def test_nested_environment_variable_overrides(self):
        old = os.environ.get("VSP_NETWORK__MAX_RETRIES")
        os.environ["VSP_NETWORK__MAX_RETRIES"] = "5"
        try:
            cfg = config.load_config(apply_env=True)
            self.assertEqual(cfg["network"]["max_retries"], 5)
        finally:
            if old is None:
                os.environ.pop("VSP_NETWORK__MAX_RETRIES", None)
            else:
                os.environ["VSP_NETWORK__MAX_RETRIES"] = old

    def test_missing_config_file_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_default = os.path.join(tmpdir, "default.json")
            with open(fake_default, "w", encoding="utf-8") as f:
                f.write('{"user_agent": "Default"}')
            fake_user = os.path.join(tmpdir, "not_exists.json")
            cfg = config.load_config(default_path=fake_default, user_path=fake_user, apply_env=False)
            self.assertEqual(cfg["user_agent"], "Default")


class ConfigSourceTests(unittest.TestCase):
    def test_config_sources_reports_default_and_existing_user(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            user_path = os.path.join(tmpdir, "config.json")
            with open(user_path, "w", encoding="utf-8") as f:
                f.write('{}')
            default_path = os.path.join(tmpdir, "default.json")
            with open(default_path, "w", encoding="utf-8") as f:
                f.write('{}')

            sources = config.get_config_sources(
                default_path=default_path,
                project_path=os.path.join(tmpdir, "no_project.json"),
                user_path=user_path,
                apply_env=False,
            )
            types = [s[0] for s in sources]
            self.assertIn("default", types)
            self.assertIn("user", types)
            self.assertNotIn("project", types)


if __name__ == "__main__":
    unittest.main()
