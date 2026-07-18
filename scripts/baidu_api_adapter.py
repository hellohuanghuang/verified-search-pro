#!/usr/bin/env python3
"""
Verified Search Pro · 百度千帆 AI 搜索适配器
职责：调用百度千帆 AI 搜索 API（/v2/ai_search/web_search）进行联网搜索（Bearer 鉴权）
可选依赖：需要 BAIDU_API_KEY 环境变量，缺失时返回结构化"未配置"状态而非抛异常。
纯 Python 标准库，零外部依赖。

请求/响应契约以百度官方 baidu-search Skill 源码（scripts/search.py）为准：
- 请求头：Authorization Bearer + X-Appbuilder-From 渠道标记（VSP 填自己的产品名）
- resource_type_filter 为数组；search_filter 始终存在（无时效过滤时为 {}）
- 时效过滤通过 search_filter.range.page_time 的 gte/lt 实现
  （pd/pw/pm/py 快捷档，或 YYYY-MM-DDtoYYYY-MM-DD 自定义区间）
- 响应顶层出现 code 字段即业务错误（message 为错误信息）；结果在 references 数组
- references 条目可能同时带 content 与 snippet 摘要字段，VSP 兼容读取、content 优先

官方源码的沙盒代理逻辑（DUMATE_* 环境变量分支）为 OpenClaw 平台特有，本适配器只实现直连。
"""

import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.request

BAIDU_ENDPOINT = os.environ.get(
    "BAIDU_API_ENDPOINT", "https://qianfan.baidubce.com/v2/ai_search/web_search"
)
# X-Appbuilder-From 渠道标记头：官方 Skill 填 "openclaw"，VSP 填自己的产品名
APPBUILDER_FROM = "verified-search-pro"

REQUIRED_ENV = ["BAIDU_API_KEY"]

DEFAULT_TOP_K = 10
MAX_TOP_K = 50  # 官方 Skill：count 上限 50，超出截断

# 时效快捷档 → 回溯天数（与官方 Skill 一致：pd=-1, pw=-6, pm=-30, py=-364；end=明天）
_FRESHNESS_DAYS = {"pd": 1, "pw": 6, "pm": 30, "py": 364}
_FRESHNESS_RANGE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}to\d{4}-\d{2}-\d{2}$")

# HTTP 状态码 → 引擎健康状态（语义与现有引擎对齐：skipped/blocked/failed）
_HTTP_STATUS_MAP = {
    401: ("failed", "unauthorized"),
    403: ("failed", "unauthorized"),
    429: ("blocked", "rate_limit_exceeded"),
}

# 业务错误码（响应顶层 code 字段）→ 引擎健康状态
_ERROR_STATUS_MAP = {
    "AuthenticationError": ("failed", "unauthorized"),
    "Unauthorized": ("failed", "unauthorized"),
    "AccessDenied": ("failed", "unauthorized"),
    "RateLimitExceeded": ("blocked", "rate_limit_exceeded"),
    "QPSLimitExceeded": ("blocked", "rate_limit_exceeded"),
    "QuotaExceeded": ("blocked", "rate_limit_exceeded"),
}


def is_available() -> bool:
    """检查百度千帆 API Key 是否已配置。"""
    return all(os.environ.get(name) for name in REQUIRED_ENV)


def get_status() -> dict:
    """Return a small environment status object for first-run diagnostics."""
    return {
        "available": is_available(),
        "requires": REQUIRED_ENV,
        "endpoint": BAIDU_ENDPOINT,
        "integration": "baidu_qianfan_ai_search_api",
        "fallback": "web_only_search_when_key_missing_or_request_fails",
    }


def _clamp_top_k(max_results) -> int:
    """top_k 边界与官方 Skill 一致：非正数回退默认 10，超过 50 截断为 50。"""
    try:
        count = int(max_results)
    except (TypeError, ValueError):
        return DEFAULT_TOP_K
    if count <= 0:
        return DEFAULT_TOP_K
    return min(count, MAX_TOP_K)


def build_search_filter(freshness: str = "", now: datetime.datetime = None) -> dict:
    """
    构造 search_filter：无时效过滤返回 {}；
    pd/pw/pm/py 快捷档或 YYYY-MM-DDtoYYYY-MM-DD 自定义区间 → range.page_time.gte/lt。
    非法值降级为无时效过滤（返回 {}），不中断搜索；now 可注入以便测试。
    """
    text = (freshness or "").strip()
    if not text:
        return {}
    now = now or datetime.datetime.now()
    end_date = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    if text in _FRESHNESS_DAYS:
        start_date = (now - datetime.timedelta(days=_FRESHNESS_DAYS[text])).strftime("%Y-%m-%d")
        return {"range": {"page_time": {"gte": start_date, "lt": end_date}}}
    if _FRESHNESS_RANGE_RE.match(text):
        start_date, end_date = text.split("to", 1)
        return {"range": {"page_time": {"gte": start_date, "lt": end_date}}}
    return {}


def _build_payload(query: str, max_results: int = 10, freshness: str = "", site: str = "") -> bytes:
    """构造千帆 AI 搜索请求体（结构以官方 Skill 为准）。

    site：域名限定（产品手册 search_filter.match.site，数组形式），
    与 freshness 的 range.page_time 可共存于同一 search_filter。
    """
    search_filter = build_search_filter(freshness)
    if site and site.strip():
        search_filter["match"] = {"site": [site.strip()]}
    body = {
        "messages": [{"content": query, "role": "user"}],
        "search_source": "baidu_search_v2",
        "resource_type_filter": [{"type": "web", "top_k": _clamp_top_k(max_results)}],
        "search_filter": search_filter,
    }
    return json.dumps(body, ensure_ascii=False).encode("utf-8")


def _build_request(payload: bytes, api_key: str) -> urllib.request.Request:
    req = urllib.request.Request(BAIDU_ENDPOINT, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("X-Appbuilder-From", APPBUILDER_FROM)
    return req


def _normalize_date(raw: str) -> str:
    """规范化为 ISO 日期 'YYYY-MM-DD'；解析失败返回空串。（与 wsa_adapter 同一思路，各自实现以保持适配器自包含）"""
    text = (raw or "").strip()
    if not text:
        return ""
    date_part = text.split(" ", 1)[0].split("T", 1)[0]
    try:
        return datetime.date.fromisoformat(date_part).isoformat()
    except ValueError:
        return ""


def _map_reference(ref: dict) -> dict:
    """将 references 单条记录映射为 VSP 标准结果格式。摘要 content 优先、snippet 兜底。"""
    return {
        "url": ref.get("url", ""),
        "title": ref.get("title", ""),
        "content": ref.get("content") or ref.get("snippet", ""),
        "score": ref.get("score", 0),
        "engine": "baidu_api",
        "published_at": _normalize_date(ref.get("date", "")),
        "source": ref.get("website", ""),
    }


def _error_status(code: str, message: str) -> dict:
    status, reason = _ERROR_STATUS_MAP.get(code, ("failed", "api_error"))
    result = {"status": status, "reason": reason, "error_code": code}
    if message:
        result["message"] = message[:200]
    return result


def _http_error_status(http_code: int, code: str, message: str) -> dict:
    """HTTP 错误优先按状态码映射；不在映射表时回退到响应体中的业务码。"""
    if http_code in _HTTP_STATUS_MAP:
        status, reason = _HTTP_STATUS_MAP[http_code]
    elif code in _ERROR_STATUS_MAP:
        status, reason = _ERROR_STATUS_MAP[code]
    else:
        status, reason = "failed", "api_error"
    result = {"status": status, "reason": reason, "error_code": code or f"HTTP {http_code}"}
    if message:
        result["message"] = message[:200]
    return result


def _parse_error_body(raw: bytes) -> tuple:
    """从错误响应体中提取 (code, message)；解析失败返回 ("", "")。"""
    try:
        data = json.loads(raw.decode("utf-8", errors="ignore"))
        return str(data.get("code", "") or ""), str(data.get("message", "") or "")
    except (ValueError, AttributeError):
        return "", ""


def search_with_status(
    query: str,
    max_results: int = 10,
    freshness: str = "",
    timeout: int = 15,
    site: str = "",
) -> dict:
    """
    调用百度千帆 AI 搜索，返回 {"results": [...], "status": {...}}。
    任何失败都映射为引擎健康状态，不抛异常，让主流程自动降级。
    site：可选域名限定（对应官方 search_filter.match.site）。
    """
    if not is_available():
        return {
            "results": [],
            "status": {
                "status": "skipped",
                "reason": "api_key_missing",
                "requires": REQUIRED_ENV,
            },
        }

    api_key = os.environ["BAIDU_API_KEY"]
    payload = _build_payload(query, max_results=max_results, freshness=freshness, site=site)

    try:
        req = _build_request(payload, api_key)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except urllib.error.HTTPError as e:
        body = e.read() if hasattr(e, "read") else b""
        code, message = _parse_error_body(body)
        status = _http_error_status(e.code, code, message)
        print(f"[baidu_api] HTTP {e.code}: {code} {message}"[:200], file=sys.stderr)
        return {"results": [], "status": status}
    except urllib.error.URLError as e:
        print(f"[baidu_api] Network error: {e.reason}", file=sys.stderr)
        return {"results": [], "status": {"status": "failed", "reason": "network_error", "message": str(e.reason)[:200]}}
    except TimeoutError:
        print("[baidu_api] Timeout", file=sys.stderr)
        return {"results": [], "status": {"status": "failed", "reason": "timeout"}}
    except Exception as e:
        print(f"[baidu_api] Error: {e}", file=sys.stderr)
        return {"results": [], "status": {"status": "failed", "reason": type(e).__name__, "message": str(e)[:200]}}

    # 官方契约：响应顶层出现 code 字段即业务错误
    if "code" in data:
        code = str(data.get("code", "") or "")
        message = str(data.get("message", "") or "")
        print(f"[baidu_api] API error: {code} {message}"[:200], file=sys.stderr)
        return {"results": [], "status": _error_status(code, message)}

    results = []
    for ref in data.get("references", []):
        if isinstance(ref, dict) and ref.get("url") and ref.get("title"):
            results.append(_map_reference(ref))
    results = results[:max_results]

    status = {"status": "ok" if results else "empty", "reason": "api_results" if results else "no_results_returned"}
    if data.get("request_id"):
        status["request_id"] = data["request_id"]
    return {"results": results, "status": status}


def search(query: str, max_results: int = 10, timeout: int = 15, **kwargs) -> list:
    """Tavily 风格契约：只返回结果列表；失败时返回空列表，让主流程自动降级。"""
    return search_with_status(query, max_results=max_results, timeout=timeout, **kwargs)["results"]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python3 baidu_api_adapter.py "query" [max_results] [freshness]')
        sys.exit(1)
    query = sys.argv[1]
    max_results = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    freshness = sys.argv[3] if len(sys.argv) > 3 else ""
    print(json.dumps(search(query, max_results, freshness=freshness), indent=2, ensure_ascii=False))
