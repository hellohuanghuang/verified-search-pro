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

    def test_domain_score_does_not_match_domain_substrings(self):
        self.assertEqual(result_fusion.get_domain_score("https://fake-reuters.com/report"), 0.0)

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
        self.assertEqual(set(fused[0]["sources"]), {"bing_cn", "baidu"})

    def test_same_story_detected_for_near_identical_cross_domain(self):
        results = [
            {
                "url": "https://site-a.com/news/123",
                "title": "China to phase out NEV subsidies by 2028",
                "content": "China announced it will phase out new energy vehicle subsidies by 2028.",
                "engine": "bing_cn",
                "score": 0.8,
            },
            {
                "url": "https://site-b.com/articles/456",
                "title": "China to phase out NEV subsidies by 2028",
                "content": "China announced it will phase out new energy vehicle subsidies by 2028.",
                "engine": "sogou",
                "score": 0.7,
            },
        ]

        fused = result_fusion.fuse_results(results, "standard")

        self.assertEqual(len(fused), 1)
        self.assertTrue(fused[0].get("same_story_group"))
        self.assertIn("primary_source", fused[0])

    def test_independent_reports_not_marked_same_story(self):
        results = [
            {
                "url": "https://site-a.com/news/123",
                "title": "NEV subsidies to be phased out by 2028",
                "content": "China announced it will phase out new energy vehicle subsidies by 2028.",
                "engine": "bing_cn",
                "score": 0.8,
            },
            {
                "url": "https://site-b.com/articles/456",
                "title": "Analysis of battery costs in 2026",
                "content": "Battery costs continue to fall, which affects NEV pricing and market share.",
                "engine": "sogou",
                "score": 0.6,
            },
        ]

        fused = result_fusion.fuse_results(results, "standard")

        self.assertEqual(len(fused), 2)
        for r in fused:
            self.assertFalse(r.get("same_story_group", False))

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

    def test_full_content_participates_in_similarity_dedup(self):
        shared = "Full article text about 48V and 800V suspension architecture with identical technical discussion."
        results = [
            {
                "url": "https://example.com/a",
                "title": "Active suspension analysis A",
                "content": "short summary a",
                "full_content": shared,
                "engine": "host_search",
                "score": 0.5,
            },
            {
                "url": "https://example.org/b",
                "title": "Active suspension analysis B",
                "content": "short summary b",
                "full_content": shared,
                "engine": "tavily",
                "score": 0.5,
            },
        ]

        fused = result_fusion.fuse_results(results, "standard")

        self.assertEqual(len(fused), 1)
        self.assertEqual(fused[0]["sources"], ["host_search", "tavily"])


if __name__ == "__main__":
    unittest.main()
