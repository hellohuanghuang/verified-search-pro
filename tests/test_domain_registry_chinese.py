#!/usr/bin/env python3
"""域名库中文权威域测试"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import domain_registry


class ChineseDomainRegistryTests(unittest.TestCase):
    """验证中文垂直领域权威域名正确分级"""

    def test_lamcvet_is_authoritative(self):
        result = domain_registry._registry().lookup("https://www.lamcvet.com/page")
        self.assertEqual(result["grade"], "A")
        self.assertGreaterEqual(result["score"], 0.85)

    def test_moguvet_is_authoritative(self):
        result = domain_registry._registry().lookup("https://www.moguvet.com/article")
        self.assertEqual(result["grade"], "A")
        self.assertGreaterEqual(result["score"], 0.8)

    def test_xiaohe_is_authoritative(self):
        result = domain_registry._registry().lookup("https://www.xiaohe.cn/medical")
        self.assertEqual(result["grade"], "A")
        self.assertGreaterEqual(result["score"], 0.75)

    def test_dxy_is_authoritative(self):
        result = domain_registry._registry().lookup("https://www.dxy.cn/article")
        self.assertEqual(result["grade"], "A")
        self.assertGreaterEqual(result["score"], 0.85)

    def test_cwbaike_is_high_risk(self):
        result = domain_registry._registry().lookup("https://www.cwbaike.com/page")
        self.assertEqual(result["grade"], "D")
        self.assertLessEqual(result["score"], 0.4)

    def test_unknown_domain_returns_unknown(self):
        result = domain_registry._registry().lookup("https://www.unknown-domain-xyz.com/")
        self.assertEqual(result["grade"], "unknown")

    def test_subdomain_matching(self):
        result = domain_registry._registry().lookup("https://sub.lamcvet.com/page")
        self.assertEqual(result["grade"], "A")

    def test_gov_cn_still_authoritative(self):
        result = domain_registry._registry().lookup("https://www.gov.cn/zhengce/")
        self.assertEqual(result["grade"], "A")
        self.assertGreaterEqual(result["score"], 0.9)


if __name__ == "__main__":
    unittest.main()
