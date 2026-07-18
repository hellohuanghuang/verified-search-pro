#!/usr/bin/env python3
"""示例脚本存在性、可运行性与语法检查。

权限门禁分层（2026-07-19 zip 丢权限问题修复）：
- git 工作区（开发 / CI / git clone）：脚本在 git 索引中必须为 100755 且工作区
  带有可执行位——拦截"仓库丢失 +x"的真实回归；
- 非 git 环境（如 GitHub "Source code (zip)" 解压，部分解压工具不还原 Unix
  权限位）：降级为"存在且可读"，运行方式见 examples/README.md
  （一律可用 `bash examples/xxx.sh`，或 `chmod +x` 一次性恢复）。
"""

import os
import subprocess
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _in_git_worktree() -> bool:
    return os.path.isdir(os.path.join(ROOT, ".git"))


def _git_mode(name: str) -> str:
    """返回 git 索引中的文件模式（如 "100755"）；查询失败返回空串。"""
    result = subprocess.run(
        ["git", "ls-files", "-s", os.path.join("examples", name)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return ""
    return result.stdout.split()[0]


class ExamplesTests(unittest.TestCase):
    def _script_path(self, name: str) -> str:
        return os.path.join(ROOT, "examples", name)

    def _assert_exists_and_runnable(self, name: str):
        path = self._script_path(name)
        self.assertTrue(os.path.exists(path), f"examples/{name} 不存在")
        if _in_git_worktree():
            self.assertEqual(
                _git_mode(name),
                "100755",
                f"examples/{name} 在 git 索引中丢失可执行位（应为 100755）；"
                f"修复：git update-index --chmod=+x examples/{name}",
            )
            self.assertTrue(
                os.access(path, os.X_OK),
                f"examples/{name} 工作区无可执行权限；修复：chmod +x examples/{name}",
            )
        else:
            # zip 解压等分发渠道丢失 Unix 可执行位不视为产品缺陷；
            # 用户侧修复方式见 examples/README.md。
            self.assertTrue(
                os.access(path, os.R_OK),
                f"examples/{name} 不可读；zip 解压丢失可执行位时，"
                f"请用 bash examples/{name} 运行或 chmod +x examples/*.sh 恢复",
            )

    def test_fact_check_script_exists_and_executable(self):
        self._assert_exists_and_runnable("fact_check.sh")

    def test_research_report_script_exists_and_executable(self):
        self._assert_exists_and_runnable("research_report.sh")

    def test_host_input_script_exists_and_executable(self):
        self._assert_exists_and_runnable("host_input.sh")

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

    def test_git_index_marks_scripts_executable_when_in_worktree(self):
        """git 环境中脚本必须以 100755 入库（防止 +x 回归的最终闸门）。"""
        if not _in_git_worktree():
            self.skipTest("非 git 环境（如 zip 解压），跳过索引权限检查")
        for name in ("fact_check.sh", "research_report.sh", "host_input.sh"):
            self.assertEqual(
                _git_mode(name),
                "100755",
                f"examples/{name} git 索引模式应为 100755",
            )


if __name__ == "__main__":
    unittest.main()
