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

        self.assertEqual(package["schema_version"], "v2-alpha.evidence-pack")
        self.assertEqual(package["claims"][0]["confidence"], "E")
        self.assertEqual(package["trusted_conclusions"], [])
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
        self.assertEqual(package["trusted_conclusions"][0]["confidence"], "B")
        self.assertEqual(evidence["source_reliability"]["grade"], "A")
        self.assertEqual(evidence["information_credibility"]["grade"], "1")
        self.assertEqual(evidence["freshness"]["status"], "current")

    def test_budget_caps_evidence_and_snippets(self):
        results = [
            {
                "url": f"https://example.com/report-{i}",
                "title": f"Example report {i}",
                "content": "x" * 1000,
                "sources": ["bing_cn"],
                "domain_score": 0.5,
                "verification_score": 0.7,
                "verified": True,
            }
            for i in range(8)
        ]

        package = trust_model.build_claim_package(
            "Example policy research",
            results,
            {"budget": "lite", "engines": ["bing_cn"], "total_raw": 8},
            generated_at="2026-06-05T00:00:00+00:00",
            budget="lite",
        )

        self.assertEqual(package["context_budget"]["name"], "lite")
        self.assertEqual(package["search"]["evidence_returned"], 5)
        self.assertLessEqual(len(package["evidence"][0]["snippet"]), 240)
        self.assertIn("capped by the lite context budget", package["limitations"][-1])

    def test_perspective_mode_keeps_uncertain_material_out_of_trusted_conclusions(self):
        result = {
            "url": "https://www.zhihu.com/question/456",
            "title": "某政策争议观点汇总",
            "content": "网友对某政策存在支持和反对观点。",
            "sources": ["bing_cn"],
            "domain_score": 0.65,
            "verification_score": 0.2,
            "verified": False,
            "matched": 1,
            "total_terms": 4,
            "key_terms": ["政策", "争议"],
            "fusion_score": 0.5,
        }

        package = trust_model.build_claim_package(
            "某政策 争议 观点",
            [result],
            {"budget": "standard", "engines": ["bing_cn"], "total_raw": 1},
            generated_at="2026-06-05T00:00:00+00:00",
            mode="perspective",
        )

        self.assertEqual(package["research_mode"], "perspective")
        self.assertEqual(package["trusted_conclusions"], [])
        self.assertEqual(package["perspective_map"]["items"][0]["use_as"], "background_or_hypothesis_only")
        self.assertTrue(package["common_misconceptions"][0]["must_not_be_used_as_fact"])
        self.assertEqual(package["controversies_uncertainties"]["status"], "present")


if __name__ == "__main__":
    unittest.main()
