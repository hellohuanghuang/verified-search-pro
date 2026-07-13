#!/usr/bin/env python3
"""示例脚本存在性与语法检查。"""

import os
import subprocess
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ExamplesTests(unittest.TestCase):
    def _script_path(self, name: str) -> str:
        return os.path.join(ROOT, "examples", name)

    def test_fact_check_script_exists_and_executable(self):
        path = self._script_path("fact_check.sh")
        self.assertTrue(os.path.exists(path))
        self.assertTrue(os.access(path, os.X_OK))

    def test_research_report_script_exists_and_executable(self):
        path = self._script_path("research_report.sh")
        self.assertTrue(os.path.exists(path))
        self.assertTrue(os.access(path, os.X_OK))

    def test_host_input_script_exists_and_executable(self):
        path = self._script_path("host_input.sh")
        self.assertTrue(os.path.exists(path))
        self.assertTrue(os.access(path, os.X_OK))

    def test_example_scripts_have_valid_bash_syntax(self):
        for name in ("fact_check.sh", "research_report.sh", "host_input.sh"):
            path = self._script_path(name)
            result = subprocess.run(
                ["bash", "-n", path],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, f"{name} has invalid bash syntax: {result.stderr}")


if __name__ == "__main__":
    unittest.main()
