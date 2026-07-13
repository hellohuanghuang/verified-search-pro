#!/usr/bin/env python3
"""HTTP 响应缓存单元测试。"""

import os
import sys
import tempfile
import time
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import cache  # noqa: E402


class ResponseCacheTests(unittest.TestCase):
    def test_cache_hit_on_same_request(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "cache.db")
            c = cache.ResponseCache(db_path=db, ttl_seconds=60)
            c.set("GET", "https://example.com", 200, {"Content-Type": "text/html"}, b"hello")

            cached = c.get("GET", "https://example.com")
            self.assertIsNotNone(cached)
            self.assertEqual(cached["body"], b"hello")
            self.assertTrue(cached["from_cache"])

    def test_cache_miss_after_ttl(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "cache.db")
            c = cache.ResponseCache(db_path=db, ttl_seconds=0)
            c.set("GET", "https://example.com", 200, {}, b"hello")
            cached = c.get("GET", "https://example.com")
            self.assertIsNone(cached)

    def test_no_cache_for_error_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "cache.db")
            c = cache.ResponseCache(db_path=db, ttl_seconds=60)
            c.set("GET", "https://example.com", 500, {}, b"error")
            self.assertIsNone(c.get("GET", "https://example.com"))

    def test_disabled_cache_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "cache.db")
            c = cache.ResponseCache(db_path=db, ttl_seconds=60)
            c.set("GET", "https://example.com", 200, {}, b"hello")
            c.disable()
            self.assertIsNone(c.get("GET", "https://example.com"))

    def test_post_body_in_cache_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "cache.db")
            c = cache.ResponseCache(db_path=db, ttl_seconds=60)
            body_a = b'{"q": "a"}'
            body_b = b'{"q": "b"}'
            c.set("POST", "https://api.example.com", 200, {}, b"result_a", body_input=body_a)
            self.assertEqual(c.get("POST", "https://api.example.com", body_a)["body"], b"result_a")
            self.assertIsNone(c.get("POST", "https://api.example.com", body_b))


if __name__ == "__main__":
    unittest.main()
