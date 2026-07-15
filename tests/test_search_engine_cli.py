import json
import os
import subprocess
import sys
import tempfile
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SearchEngineCliTests(unittest.TestCase):
    def test_tavily_missing_key_degrades_to_empty_json(self):
        env = os.environ.copy()
        env.pop("TAVILY_API_KEY", None)

        result = subprocess.run(
            [
                sys.executable,
                "scripts/search_engine.py",
                "OpenAI GPT release",
                "--engines",
                "tavily",
                "--budget",
                "minimal",
                "--verify",
                "--output",
                "json",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        data = json.loads(result.stdout)

        self.assertEqual(data["engines"], ["tavily"])
        self.assertEqual(data["total_raw"], 0)
        self.assertEqual(data["total_fused"], 0)
        self.assertEqual(data["verification"]["verified_count"], 0)

    def test_claims_json_output_degrades_to_insufficient_claim(self):
        env = os.environ.copy()
        env.pop("TAVILY_API_KEY", None)

        result = subprocess.run(
            [
                sys.executable,
                "scripts/search_engine.py",
                "OpenAI GPT latest release",
                "--engines",
                "tavily",
                "--budget",
                "minimal",
                "--output",
                "claims-json",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        data = json.loads(result.stdout)

        self.assertEqual(data["schema_version"], "v2-alpha.evidence-pack")
        self.assertIn("v2-alpha.claim-package", data["compatible_schema_versions"])
        self.assertEqual(data["claims"][0]["confidence"], "E")
        self.assertEqual(data["search"]["engines"], ["tavily"])
        self.assertEqual(data["search"]["total_fused"], 0)
        self.assertTrue(data["limitations"])

    def test_doctor_reports_optional_tavily_and_google(self):
        result = subprocess.run(
            [sys.executable, "scripts/search_engine.py", "--doctor"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        data = json.loads(result.stdout)

        self.assertTrue(data["python"]["meets_minimum"])
        self.assertEqual(data["search"]["tavily"]["integration"], "direct_rest_api")
        self.assertFalse(data["search"]["google"]["default_enabled"])
        self.assertEqual(data["host_search"]["status"], "input_results_only")
        self.assertEqual(data["context_budget"]["hard_red_line_tokens"], 256000)
        self.assertIn("config", data)
        self.assertTrue(data["config"]["sources"])

    def test_help_returns_zero(self):
        result = subprocess.run(
            [sys.executable, "scripts/search_engine.py", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage", result.stdout.lower())

    def test_version_flag_outputs_version(self):
        result = subprocess.run(
            [sys.executable, "scripts/search_engine.py", "--version"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("2.0.2", result.stdout)

    def test_invalid_mode_exits_nonzero(self):
        result = subprocess.run(
            [sys.executable, "scripts/search_engine.py", "query", "--mode", "invalid"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr.lower())

    def test_perspective_mode_marks_non_factual_sections(self):
        env = os.environ.copy()
        env.pop("TAVILY_API_KEY", None)

        result = subprocess.run(
            [
                sys.executable,
                "scripts/search_engine.py",
                "某政策 争议 观点",
                "--engines",
                "tavily",
                "--mode",
                "perspective",
                "--budget",
                "lite",
                "--output",
                "claims-json",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        data = json.loads(result.stdout)

        self.assertEqual(data["research_mode"], "perspective")
        self.assertIn("perspective_map", data)
        self.assertIn("common_misconceptions", data)
        self.assertIn("controversies_uncertainties", data)
        self.assertIn("temporal_evolution", data)
        self.assertEqual(data["context_budget"]["name"], "lite")

    def test_input_results_feed_host_search_without_engines(self):
        fixture = [
            {
                "url": "https://example.com/tech",
                "title": "48V vs 800V active suspension comparison",
                "content": "48V and 800V active suspension have different power and response tradeoffs.",
                "full_content": "2026-06-01 48V and 800V active suspension have different power and response tradeoffs.",
                "engine": "host_search",
                "author": "Host Agent",
                "source_type": "host_search_result",
                "fetch_source": "kimi_fetch",
            }
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as f:
            json.dump(fixture, f)
            path = f.name
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/search_engine.py",
                    "48V 800V active suspension",
                    "--input-results",
                    path,
                    "--engines",
                    "none",
                    "--budget",
                    "auto",
                    "--checkpoint",
                    "batch",
                    "--verify",
                    "--output",
                    "claims-json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            )
        finally:
            os.unlink(path)
        data = json.loads(result.stdout)

        self.assertEqual(data["search"]["budget_requested"], "auto")
        self.assertEqual(data["search"]["checkpoint"], "batch")
        self.assertEqual(data["search"]["engine_status"]["host_search"]["status"], "ok")
        self.assertEqual(data["evidence"][0]["source_attribution"]["author"], "Host Agent")
        self.assertTrue(data["evidence"][0]["source_attribution"]["has_full_content"])

    def test_auto_budget_suggests_deep_for_multidimensional_research(self):
        env = os.environ.copy()
        env.pop("TAVILY_API_KEY", None)
        result = subprocess.run(
            [
                sys.executable,
                "scripts/search_engine.py",
                "调研 48V vs 800V 主动悬架 优劣 争议 趋势",
                "--engines",
                "none",
                "--budget",
                "auto",
                "--output",
                "json",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        data = json.loads(result.stdout)

        self.assertEqual(data["budget_requested"], "auto")
        self.assertEqual(data["budget"], "deep")
        self.assertEqual(data["engine_status"], {})


if __name__ == "__main__":
    unittest.main()
