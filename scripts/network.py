#!/usr/bin/env python3
"""
Verified Search Pro · 网络请求工具
职责：带缓存、指数退避重试的 urllib 请求封装。
纯 Python 标准库，零外部依赖。
"""

import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar

import cache as _cache


# ── Cookie 会话管理 ──────────────────────────────────────────────
# 部分搜索引擎（如必应）在无 Cookie 时对特定长尾查询返回降级结果。
# 通过 warmup_session 先访问首页建立会话，再发起搜索请求。
_cookie_jar = None
_cookie_opener = None


def _ensure_cookie_opener():
    """惰性创建带 Cookie 处理的 opener（纯标准库）。"""
    global _cookie_jar, _cookie_opener
    if _cookie_opener is None:
        _cookie_jar = http.cookiejar.CookieJar()
        _cookie_opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(_cookie_jar)
        )
    return _cookie_opener


def warmup_session(url: str, headers: dict = None, timeout: float = 10) -> bool:
    """
    访问指定 URL 建立会话 Cookie（如必应首页），提升后续搜索质量。
    已有同域 Cookie 时跳过。失败时静默返回 False，不阻断主流程。
    """
    opener = _ensure_cookie_opener()
    domain = urllib.parse.urlparse(url).hostname or ""
    if _cookie_jar and any(
        domain and domain in (c.domain or "") for c in _cookie_jar
    ):
        return True
    try:
        req = urllib.request.Request(url, headers=headers or {})
        opener.open(req, timeout=timeout)
        return True
    except Exception:
        return False


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
    use_cookies: bool = False,
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
            if use_cookies:
                resp = _ensure_cookie_opener().open(req, timeout=timeout)
            else:
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


def fetch_post_with_retry(
    url: str,
    data: dict,
    headers: dict = None,
    timeout: float = 30,
    max_retries: int = 2,
    backoff_factor: float = 1.5,
    respect_retry_after: bool = True,
    use_cache: bool = True,
    cache_ttl_seconds: int = None,
) -> tuple:
    """
    执行 POST 请求，支持缓存和指数退避重试。
    DuckDuckGo HTML 端点建议使用 POST 请求。
    返回 (status: int, headers: dict, body: bytes)
    """
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=encoded,
        method="POST",
        headers=headers or {},
    )
    return fetch_with_retry(
        url,
        request=req,
        timeout=timeout,
        max_retries=max_retries,
        backoff_factor=backoff_factor,
        respect_retry_after=respect_retry_after,
        use_cache=use_cache,
        cache_ttl_seconds=cache_ttl_seconds,
    )
