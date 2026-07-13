#!/usr/bin/env python3
"""域名评级注册表单元测试。"""

import os
import sys
import tempfile
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import domain_registry  # noqa: E402


class DomainRegistryTests(unittest.TestCase):
    def setUp(self):
        domain_registry.reload_registry()

    def tearDown(self):
        domain_registry.reload_registry()

    def test_authoritative_domain_score(self):
        self.assertGreaterEqual(
            domain_registry.get_domain_score("https://www.gov.cn/zhengce/2026-01-01.htm"),
            0.9,
        )

    def test_media_domain_grade(self):
        self.assertEqual(
            domain_registry.get_source_grade("https://www.nytimes.com/2026/07/14/world/asia/example.html"),
            "B",
        )

    def test_subdomain_matches_parent(self):
        self.assertEqual(
            domain_registry.get_source_grade("https://world.nytimes.com/article/123"),
            "B",
        )

    def test_fake_domain_does_not_match(self):
        self.assertEqual(
            domain_registry.get_source_grade("https://fake-reuters.com/news"),
            "unknown",
        )

    def test_user_config_can_override_defaults(self):
        cfg = {
            "domain_ranking": {
                "authoritative": {"example.com": 0.99},
                "high_risk": {"reuters.com": 0.1},
            }
        }
        domain_registry.reload_registry(cfg)
        self.assertEqual(
            domain_registry.get_source_grade("https://example.com/article"),
            "A",
        )
        self.assertEqual(
            domain_registry.get_source_grade("https://www.reuters.com/article"),
            "D",
        )

    def test_load_user_domains_returns_empty_for_missing_file(self):
        self.assertEqual(domain_registry.load_user_domains("/non/existent/path.json"), {})

    def test_load_user_domains_reads_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write('{"authoritative": {"my.gov": 0.95}}')
            path = f.name
        try:
            data = domain_registry.load_user_domains(path)
            self.assertEqual(data["authoritative"]["my.gov"], 0.95)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
