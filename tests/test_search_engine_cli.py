import json
import os
import subprocess
import sys
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
        self.assertEqual(data["context_budget"]["hard_red_line_tokens"], 256000)

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


if __name__ == "__main__":
    unittest.main()
