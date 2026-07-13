#!/usr/bin/env python3
"""
Verified Search Pro · 网络请求工具
职责：带缓存、指数退避重试的 urllib 请求封装。
纯 Python 标准库，零外部依赖。
"""

import sys
import time
import urllib.error
import urllib.request

import cache as _cache


def _parse_retry_after(headers: dict) -> int:
    value = headers.get("Retry-After") or headers.get("retry-after")
    if not value:
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


def fetch_with_retry(
    url: str,
    request: urllib.request.Request = None,
    timeout: float = 30,
    max_retries: int = 2,
    backoff_factor: float = 1.5,
    respect_retry_after: bool = True,
    use_cache: bool = True,
    cache_ttl_seconds: int = None,
) -> tuple:
    """
    执行 HTTP 请求，支持缓存和指数退避重试。
    返回 (status: int, headers: dict, body: bytes)
    """
    req = request or urllib.request.Request(url, method="GET")
    method = req.get_method() or "GET"
    body_input = req.data if isinstance(req.data, bytes) else None

    cache = _cache.get_cache()
    if cache_ttl_seconds is not None:
        cache.ttl_seconds = cache_ttl_seconds

    if use_cache:
        cached = cache.get(method, url, body_input)
        if cached:
            return cached["status"], cached["headers"], cached["body"]

    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
            status = resp.getcode()
            headers = dict(resp.headers)
            body = resp.read()
            if use_cache and status == 200:
                cache.set(method, url, status, headers, body, body_input)
            return status, headers, body
        except urllib.error.HTTPError as e:
            status = e.code
            headers = dict(e.headers)
            body = e.read()
            last_exception = e

            if 400 <= status < 500 and status != 429:
                # 客户端错误不重试（429 Too Many Requests 除外）
                return status, headers, body

            if attempt == max_retries:
                if use_cache:
                    cache.set(method, url, status, headers, body, body_input)
                return status, headers, body

            wait = backoff_factor * (2 ** attempt)
            if status == 429 and respect_retry_after:
                retry_after = _parse_retry_after(headers)
                if retry_after > 0:
                    wait = retry_after

            print(
                f"[network] retrying {url} in {wait:.1f}s (HTTP {status}, attempt {attempt + 1}/{max_retries + 1})",
                file=sys.stderr,
            )
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError) as e:
            last_exception = e
            if attempt == max_retries:
                raise
            wait = backoff_factor * (2 ** attempt)
            reason = getattr(e, "reason", str(e))
            print(
                f"[network] retrying {url} in {wait:.1f}s ({type(e).__name__}: {reason}, attempt {attempt + 1}/{max_retries + 1})",
                file=sys.stderr,
            )
            time.sleep(wait)

    # 理论上不会到达这里，防御性抛出最后一次异常
    if last_exception:
        raise last_exception
    return 0, {}, b""
