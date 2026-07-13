#!/usr/bin/env python3
"""
Verified Search Pro · HTTP 响应缓存
职责：缓存 urllib 请求的响应体，减少重复搜索请求，支持 TTL。
纯 Python 标准库（sqlite3 + hashlib），零外部依赖。
"""

import hashlib
import os
import sqlite3
import time


_APP_NAME = "verified-search-pro"


def _xdg_cache_home() -> str:
    return os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")


def _default_db_path() -> str:
    return os.path.join(_xdg_cache_home(), _APP_NAME, "cache.db")


def _make_cache_key(method: str, url: str, body: bytes = None) -> str:
    parts = [method.upper(), url]
    if body:
        parts.append(hashlib.sha256(body).hexdigest())
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


class ResponseCache:
    def __init__(self, db_path: str = None, ttl_seconds: int = 300):
        self.db_path = db_path or _default_db_path()
        self.ttl_seconds = ttl_seconds
        self._enabled = True
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS responses (
                    key TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    status INTEGER,
                    headers TEXT,
                    body BLOB,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_expires ON responses(expires_at)"
            )

    def get(self, method: str, url: str, body: bytes = None) -> dict:
        if not self._enabled:
            return None
        key = _make_cache_key(method, url, body)
        now = int(time.time())
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT status, headers, body, expires_at FROM responses WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        status, headers_json, body_blob, expires_at = row
        if now >= expires_at:
            return None
        import json
        return {
            "status": status,
            "headers": json.loads(headers_json) if headers_json else {},
            "body": body_blob,
            "from_cache": True,
        }

    def set(
        self,
        method: str,
        url: str,
        status: int,
        headers: dict,
        body: bytes,
        body_input: bytes = None,
    ):
        if not self._enabled:
            return
        if status >= 400:
            # 不缓存错误响应
            return
        import json
        key = _make_cache_key(method, url, body_input)
        now = int(time.time())
        expires = now + self.ttl_seconds
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO responses (key, url, status, headers, body, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    url,
                    status,
                    json.dumps(headers, ensure_ascii=False),
                    body,
                    now,
                    expires,
                ),
            )

    def clear(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM responses")

    def purge_expired(self):
        now = int(time.time())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM responses WHERE expires_at <= ?", (now,))

    def disable(self):
        self._enabled = False

    def enable(self):
        self._enabled = True


def _global_cache() -> ResponseCache:
    # 延迟初始化，避免导入时创建文件
    if not hasattr(_global_cache, "instance"):
        _global_cache.instance = ResponseCache()
    return _global_cache.instance


def get_cache() -> ResponseCache:
    return _global_cache()


def reset_cache():
    if hasattr(_global_cache, "instance"):
        _global_cache.instance.clear()
