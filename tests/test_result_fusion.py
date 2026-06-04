import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import result_fusion  # noqa: E402


class ResultFusionTests(unittest.TestCase):
    def test_normalize_url_strips_tracking_and_www(self):
        url = "https://www.Example.com/path/?utm_source=news&ref=home&id=42"

        self.assertEqual(result_fusion.normalize_url(url), "example.com/path?id=42")

    def test_fuse_results_merges_same_url_sources(self):
        results = [
            {
                "url": "https://example.com/a?utm_source=x",
                "title": "Verified Search",
                "content": "A reliable search result",
                "engine": "bing_cn",
                "score": 0.4,
            },
            {
                "url": "http://www.example.com/a",
                "title": "Verified Search",
                "content": "A reliable search result",
                "engine": "baidu",
                "score": 0.3,
            },
        ]

        fused = result_fusion.fuse_results(results, "balanced")

        self.assertEqual(len(fused), 1)
        self.assertEqual(fused[0]["sources"], ["bing_cn"])

    def test_fuse_results_keeps_stronger_domain_for_fingerprint_duplicate(self):
        results = [
            {
                "url": "https://unknown.example/report",
                "title": "Market report",
                "content": "The same claim appears in this article with supporting text.",
                "engine": "sogou",
                "score": 0.1,
            },
            {
                "url": "https://www.reuters.com/world/report",
                "title": "Market report",
                "content": "The same claim appears in this article with supporting text.",
                "engine": "bing_cn",
                "score": 0.1,
            },
        ]

        fused = result_fusion.fuse_results(results, "balanced")

        self.assertEqual(len(fused), 1)
        self.assertIn("reuters.com", fused[0]["url"])
        self.assertEqual(fused[0]["domain_score"], 0.9)
        self.assertEqual(fused[0]["sources"], ["bing_cn", "sogou"])

    def test_budget_limits_results(self):
        topics = [
            "semiconductor supply chain analysis",
            "electric vehicle policy timeline",
            "open source license compliance",
            "healthcare reimbursement reform",
            "cloud security incident review",
            "renewable energy storage market",
            "AI model evaluation benchmark",
            "consumer finance regulation",
            "robotics manufacturing capacity",
            "space launch insurance pricing",
            "education technology adoption",
            "pharmaceutical patent dispute",
        ]
        results = [
            {
                "url": f"https://example.com/{i}",
                "title": topic.title(),
                "content": f"{topic} contains distinct context and evidence for record {i}.",
                "engine": "bing_cn",
                "score": 0.1,
            }
            for i, topic in enumerate(topics)
        ]

        self.assertEqual(len(result_fusion.fuse_results(results, "minimal")), 5)


if __name__ == "__main__":
    unittest.main()
