import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import trust_model  # noqa: E402


class TrustModelTests(unittest.TestCase):
    def test_classifies_authoritative_source_reliability(self):
        result = {
            "url": "https://www.reuters.com/world/example",
            "domain_score": 0.9,
        }

        reliability = trust_model.classify_source_reliability(result)

        self.assertEqual(reliability["grade"], "A")
        self.assertGreaterEqual(reliability["score"], 0.9)

    def test_source_reliability_does_not_match_domain_substrings(self):
        result = {
            "url": "https://fake-reuters.com/world/example",
            "domain_score": 0.5,
        }

        reliability = trust_model.classify_source_reliability(result)

        self.assertEqual(reliability["grade"], "unknown")

    def test_classifies_single_ugc_as_possible_not_probable(self):
        result = {
            "url": "https://www.zhihu.com/question/123",
            "domain_score": 0.65,
            "verification_score": 0.8,
            "verified": True,
            "sources": ["bing_cn"],
        }

        reliability = trust_model.classify_source_reliability(result)
        freshness = {"status": "unknown"}
        credibility = trust_model.classify_information_credibility(result, reliability, freshness)

        self.assertEqual(reliability["grade"], "C")
        self.assertEqual(credibility["grade"], "3")

    def test_extract_publication_date_from_chinese_date(self):
        result = {"content": "文章发布于 2026年06月05日，随后更新。"}

        self.assertEqual(trust_model.extract_publication_date(result), "2026-06-05")

    def test_build_claim_package_without_evidence_is_insufficient(self):
        package = trust_model.build_claim_package(
            "OpenAI GPT 最新发布",
            [],
            {"budget": "minimal", "engines": ["tavily"], "total_raw": 0},
            generated_at="2026-06-05T00:00:00+00:00",
        )

        self.assertEqual(package["schema_version"], "v2-alpha.claim-package")
        self.assertEqual(package["claims"][0]["confidence"], "E")
        self.assertTrue(package["limitations"])
        self.assertEqual(package["search"]["total_fused"], 0)

    def test_build_claim_package_links_verified_evidence(self):
        result = {
            "url": "https://www.reuters.com/world/report",
            "title": "OpenAI GPT release update",
            "content": "OpenAI GPT release update 2026-06-01",
            "sources": ["tavily", "bing_cn"],
            "domain_score": 0.9,
            "verification_score": 0.8,
            "verified": True,
            "matched": 3,
            "total_terms": 3,
            "key_terms": ["openai", "gpt", "release"],
            "confidence_level": "A",
            "fusion_score": 0.88,
        }

        package = trust_model.build_claim_package(
            "OpenAI GPT release",
            [result],
            {"budget": "minimal", "engines": ["tavily", "bing_cn"], "total_raw": 2},
            generated_at="2026-06-05T00:00:00+00:00",
        )

        evidence = package["evidence"][0]
        self.assertEqual(package["claims"][0]["supporting_evidence"], ["ev-1"])
        self.assertEqual(evidence["source_reliability"]["grade"], "A")
        self.assertEqual(evidence["information_credibility"]["grade"], "1")
        self.assertEqual(evidence["freshness"]["status"], "current")


if __name__ == "__main__":
    unittest.main()
