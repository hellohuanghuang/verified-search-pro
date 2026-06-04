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


if __name__ == "__main__":
    unittest.main()
