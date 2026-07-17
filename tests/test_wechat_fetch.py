import json
import os
import subprocess
import sys
import unittest
from unittest import mock


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import wechat_fetch  # noqa: E402


WECHAT_URL = "https://mp.weixin.qq.com/s/abc123def456"
NON_WECHAT_URL = "https://example.com/article/123"

SUCCESS_PAYLOAD = {
    "success": True,
    "title": "新能源汽车产业链深度观察",
    "content": "正文内容……",
    "url": WECHAT_URL,
}


def make_completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=["node"], returncode=returncode, stdout=stdout, stderr=stderr)


class UrlGuardTests(unittest.TestCase):
    """is_wechat_url 与输入防御。"""

    def test_wechat_url_recognized(self):
        self.assertTrue(wechat_fetch.is_wechat_url(WECHAT_URL))

    def test_wechat_url_requires_s_path(self):
        self.assertFalse(wechat_fetch.is_wechat_url("https://mp.weixin.qq.com/"))

    def test_non_wechat_and_empty_urls(self):
        for bad in (NON_WECHAT_URL, "", None, "not-a-url", "   "):
            with self.subTest(url=bad):
                self.assertFalse(wechat_fetch.is_wechat_url(bad))

    def test_spoofed_wechat_domains_rejected(self):
        """域名精确匹配：各类仿冒/伪装形式一律拒绝。"""
        spoofed = (
            "https://mp.weixin.qq.com.evil.com/s/x",      # 后缀域名仿冒
            "https://mp.weixin.qq.com@evil.com/s/x",      # userinfo 伪装
            "https://evil.com/mp.weixin.qq.com/s/x",      # 域名出现在路径中
            "https://evil.com/s/mp.weixin.qq.com",        # 域名出现在路径尾部
            "https://mp.weixin.qq.com:443.evil.com/s/x",  # 端口样式混淆
            "https://mmp.weixin.qq.com/s/x",              # 近似域名
            "https://weixin.qq.com/s/x",                  # 父域名不含 mp 前缀
        )
        for bad in spoofed:
            with self.subTest(url=bad):
                self.assertFalse(wechat_fetch.is_wechat_url(bad))

    def test_genuine_wechat_url_variants_accepted(self):
        """真实微信文章 URL 的常见变体仍可识别。"""
        genuine = (
            "https://mp.weixin.qq.com/s/abc123def456",
            "http://mp.weixin.qq.com/s/abc123",            # http scheme
            "HTTPS://MP.WEIXIN.QQ.COM/s/abc123",           # 大小写
            "mp.weixin.qq.com/s/abc123",                   # 无 scheme 裸 URL
            "https://mp.weixin.qq.com./s/abc123",          # FQDN 尾点
            "  https://mp.weixin.qq.com/s/abc123  ",       # 首尾空白
        )
        for good in genuine:
            with self.subTest(url=good):
                self.assertTrue(wechat_fetch.is_wechat_url(good))

    def test_fetch_article_rejects_non_wechat_url(self):
        result = wechat_fetch.fetch_article(NON_WECHAT_URL)
        self.assertIn("error", result)
        self.assertEqual(result["url"], NON_WECHAT_URL)

    def test_fetch_article_rejects_empty_and_malformed_url(self):
        for bad in ("", "not-a-url"):
            with self.subTest(url=bad):
                result = wechat_fetch.fetch_article(bad)
                self.assertIn("error", result)


class ScriptAvailabilityTests(unittest.TestCase):
    def test_missing_fetch_script_returns_structured_error(self):
        with mock.patch.object(wechat_fetch, "WECHAT_FETCH_SCRIPT", "/nonexistent/wx-article-fetch.js"):
            self.assertFalse(wechat_fetch.is_available())
            result = wechat_fetch.fetch_article(WECHAT_URL)
            self.assertEqual(result["error"], "微信抓取脚本不存在")
            self.assertEqual(result["url"], WECHAT_URL)


class FetchArticleTests(unittest.TestCase):
    """mock Node 子进程：不依赖真实 Node.js 与网络。"""

    def setUp(self):
        patcher = mock.patch.object(wechat_fetch, "is_available", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_success_payload_mapped(self):
        stdout = "some node log line\n" + json.dumps(SUCCESS_PAYLOAD, ensure_ascii=False) + "\n"
        with mock.patch("subprocess.run", return_value=make_completed(stdout=stdout)) as run:
            result = wechat_fetch.fetch_article(WECHAT_URL)

        self.assertNotIn("error", result)
        self.assertEqual(result["title"], SUCCESS_PAYLOAD["title"])
        self.assertEqual(result["content"], SUCCESS_PAYLOAD["content"])
        self.assertEqual(result["source"], "wechat_fetch")
        # 子进程调用契约：node + 脚本 + --url + --format json
        cmd = run.call_args[0][0]
        self.assertEqual(cmd[0], "node")
        self.assertIn("--url", cmd)
        self.assertIn(WECHAT_URL, cmd)

    def test_success_json_found_from_last_lines(self):
        """stdout 尾部多行时，倒序扫描定位含 success 的 JSON 行。"""
        stdout = (
            json.dumps({"success": True, "title": "旧行不应采用", "content": "x"})
            + "\ntrailing noise\n"
            + json.dumps(SUCCESS_PAYLOAD, ensure_ascii=False)
            + "\n"
        )
        with mock.patch("subprocess.run", return_value=make_completed(stdout=stdout)):
            result = wechat_fetch.fetch_article(WECHAT_URL)
        self.assertEqual(result["title"], SUCCESS_PAYLOAD["title"])

    def test_business_failure_payload(self):
        stdout = json.dumps({"success": False, "error": "文章已被删除"})
        with mock.patch("subprocess.run", return_value=make_completed(stdout=stdout)):
            result = wechat_fetch.fetch_article(WECHAT_URL)
        self.assertEqual(result["error"], "文章已被删除")
        self.assertEqual(result["url"], WECHAT_URL)

    def test_nonzero_exit_returns_error_with_stderr(self):
        with mock.patch("subprocess.run", return_value=make_completed(returncode=1, stderr="boom")):
            result = wechat_fetch.fetch_article(WECHAT_URL)
        self.assertIn("code=1", result["error"])
        self.assertIn("boom", result.get("stderr", ""))

    def test_unparseable_stdout(self):
        with mock.patch("subprocess.run", return_value=make_completed(stdout="not json at all")):
            result = wechat_fetch.fetch_article(WECHAT_URL)
        self.assertEqual(result["error"], "无法解析响应")

    def test_node_missing_file_not_found(self):
        with mock.patch("subprocess.run", side_effect=FileNotFoundError("node not found")):
            result = wechat_fetch.fetch_article(WECHAT_URL)
        self.assertIn("error", result)
        self.assertTrue(result["error"].startswith("异常:"))

    def test_timeout_returns_error(self):
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="node", timeout=60)):
            result = wechat_fetch.fetch_article(WECHAT_URL)
        self.assertEqual(result["error"], "抓取超时")


class EnrichResultsTests(unittest.TestCase):
    def test_enriches_wechat_items_and_marks_failures(self):
        results = [
            {"url": WECHAT_URL, "title": "微信文"},
            {"url": "https://mp.weixin.qq.com/s/deleted", "title": "已删除"},
            {"url": NON_WECHAT_URL, "title": "普通网页"},
        ]

        def fake_fetch(url, timeout=30000):
            if url.endswith("deleted"):
                return {"error": "文章已被删除", "url": url}
            return {"title": "微信文", "content": "全文内容", "url": url, "source": "wechat_fetch"}

        with mock.patch.object(wechat_fetch, "fetch_article", side_effect=fake_fetch):
            enriched = wechat_fetch.enrich_results(results)

        self.assertEqual(enriched[0]["full_content"], "全文内容")
        self.assertEqual(enriched[0]["fetch_source"], "wechat_fetch")
        self.assertEqual(enriched[1]["fetch_error"], "文章已被删除")
        self.assertNotIn("full_content", enriched[1])
        # 非微信 URL 不触发抓取、无新增字段
        self.assertNotIn("full_content", enriched[2])
        self.assertNotIn("fetch_error", enriched[2])


if __name__ == "__main__":
    unittest.main()
