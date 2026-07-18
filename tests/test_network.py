#!/usr/bin/env python3
"""网络请求工具单元测试（带缓存和重试）。"""

import io
import os
import sys
import tempfile
import unittest
from unittest import mock
import urllib.error
import urllib.request


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import cache  # noqa: E402
import network  # noqa: E402


class FetchWithRetryTests(unittest.TestCase):
    def setUp(self):
        # 每次测试使用独立缓存，避免互相影响
        self.tmpdir = tempfile.mkdtemp()
        self.cache_db = os.path.join(self.tmpdir, "cache.db")
        cache._global_cache.instance = cache.ResponseCache(db_path=self.cache_db, ttl_seconds=60)

    def tearDown(self):
        cache._global_cache.instance.clear()

    @mock.patch("urllib.request.urlopen")
    def test_successful_request_returns_200_and_caches(self, mock_urlopen):
        mock_resp = mock.MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.read.return_value = b"hello"
        mock_urlopen.return_value = mock_resp

        status, headers, body = network.fetch_with_retry(
            "https://example.com", use_cache=True, max_retries=0
        )

        self.assertEqual(status, 200)
        self.assertEqual(body, b"hello")
        cached = cache.get_cache().get("GET", "https://example.com")
        self.assertIsNotNone(cached)

    @mock.patch("urllib.request.urlopen")
    def test_500_then_success_retries(self, mock_urlopen):
        error_resp = mock.MagicMock()
        error_resp.code = 500
        error_resp.headers = {}
        error_resp.read.return_value = b"error"

        ok_resp = mock.MagicMock()
        ok_resp.getcode.return_value = 200
        ok_resp.headers = {}
        ok_resp.read.return_value = b"ok"

        mock_urlopen.side_effect = [
            urllib.error.HTTPError("https://example.com", 500, "Server Error", {}, io.BytesIO(b"error")),
            ok_resp,
        ]

        status, headers, body = network.fetch_with_retry(
            "https://example.com", use_cache=False, max_retries=2, backoff_factor=0.01
        )
        self.assertEqual(status, 200)
        self.assertEqual(body, b"ok")
        self.assertEqual(mock_urlopen.call_count, 2)

    @mock.patch("urllib.request.urlopen")
    def test_404_does_not_retry(self, mock_urlopen):
        error_resp = mock.MagicMock()
        error_resp.code = 404
        error_resp.headers = {}
        error_resp.read.return_value = b"not found"

        mock_urlopen.side_effect = [
            urllib.error.HTTPError("https://example.com", 404, "Not Found", {}, io.BytesIO(b"not found")),
        ]

        status, headers, body = network.fetch_with_retry(
            "https://example.com", use_cache=False, max_retries=2, backoff_factor=0.01
        )
        self.assertEqual(status, 404)
        self.assertEqual(mock_urlopen.call_count, 1)

    @mock.patch("urllib.request.urlopen")
    def test_respects_retry_after_header(self, mock_urlopen):
        retry_resp = mock.MagicMock()
        retry_resp.code = 429
        retry_resp.headers = {"Retry-After": "2"}
        retry_resp.read.return_value = b"retry"

        ok_resp = mock.MagicMock()
        ok_resp.getcode.return_value = 200
        ok_resp.headers = {}
        ok_resp.read.return_value = b"ok"

        mock_urlopen.side_effect = [
            urllib.error.HTTPError("https://example.com", 429, "Too Many Requests", retry_resp.headers, io.BytesIO(b"retry")),
            ok_resp,
        ]

        status, headers, body = network.fetch_with_retry(
            "https://example.com", use_cache=False, max_retries=2, backoff_factor=0.01
        )
        self.assertEqual(status, 200)

    @mock.patch("urllib.request.urlopen")
    def test_max_retries_exceeded_raises(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        with self.assertRaises(urllib.error.URLError):
            network.fetch_with_retry(
                "https://example.com", use_cache=False, max_retries=1, backoff_factor=0.01
            )


class CookieSessionTests(unittest.TestCase):
    """BUG-001 回归：Cookie 会话管理"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cache_db = os.path.join(self.tmpdir, "cache.db")
        cache._global_cache.instance = cache.ResponseCache(
            db_path=self.cache_db, ttl_seconds=60
        )

    def tearDown(self):
        cache._global_cache.instance.clear()

    @mock.patch.object(network, "_ensure_cookie_opener")
    def test_warmup_session_returns_true_on_success(self, mock_get_opener):
        import http.cookiejar
        mock_opener = mock.MagicMock()
        mock_get_opener.return_value = mock_opener
        network._cookie_jar = http.cookiejar.CookieJar()
        result = network.warmup_session(
            "https://cn.bing.com",
            headers={"User-Agent": "test"},
        )
        self.assertTrue(result)
        mock_opener.open.assert_called_once()

    @mock.patch.object(network, "_ensure_cookie_opener")
    def test_warmup_session_returns_false_on_error(self, mock_get_opener):
        import http.cookiejar
        mock_opener = mock.MagicMock()
        mock_opener.open.side_effect = urllib.error.URLError("timeout")
        mock_get_opener.return_value = mock_opener
        network._cookie_jar = http.cookiejar.CookieJar()
        result = network.warmup_session("https://cn.bing.com")
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
