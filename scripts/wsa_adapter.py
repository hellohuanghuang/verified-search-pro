#!/usr/bin/env python3
"""
Verified Search Pro · 腾讯云 WSA（联网搜索 API）适配器
职责：调用腾讯云 SearchPro API 进行联网搜索（TC3-HMAC-SHA256 签名）
可选依赖：需要 TENCENTCLOUD_SECRET_ID / TENCENTCLOUD_SECRET_KEY 环境变量，
缺失时返回结构化"未配置"状态而非抛异常。
纯 Python 标准库，零外部依赖。

注：标准版（standard）仅支持 Query / Mode / Site / FromTime / ToTime；
Cnt、Industry、Freshness、Deeplinks 为尊享/旗舰版专属，本适配器不发送。
"""

import datetime
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request

WSA_HOST = "wsa.tencentcloudapi.com"
WSA_SERVICE = "wsa"
WSA_ACTION = "SearchPro"
WSA_VERSION = "2025-05-08"
WSA_ENDPOINT = os.environ.get("TENCENTCLOUD_WSA_ENDPOINT", f"https://{WSA_HOST}/")

REQUIRED_ENV = ["TENCENTCLOUD_SECRET_ID", "TENCENTCLOUD_SECRET_KEY"]

# 业务错误码 → 引擎健康状态（语义参照现有引擎：skipped/blocked/failed）
_ERROR_STATUS_MAP = {
    # 未开通服务：与"未启用"同类，降级为 skipped
    "ResourceNotFound": ("skipped", "service_not_activated"),
    # 未授权/密钥错误：配置问题，视为 failed
    "UnauthorizedOperation": ("failed", "unauthorized"),
    # 超限：临时性拦截，与反爬 blocked 语义一致
    "RequestLimitExceeded": ("blocked", "rate_limit_exceeded"),
}


def is_available() -> bool:
    """检查腾讯云 CAM 密钥对是否已配置。"""
    return all(os.environ.get(name) for name in REQUIRED_ENV)


def get_status() -> dict:
    """Return a small environment status object for first-run diagnostics."""
    return {
        "available": is_available(),
        "requires": REQUIRED_ENV,
        "endpoint": WSA_ENDPOINT,
        "integration": "tencent_cloud_tc3_signed_api",
        "fallback": "web_only_search_when_key_missing_or_request_fails",
    }


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def build_authorization(secret_id: str, secret_key: str, payload: bytes, timestamp: int) -> str:
    """
    构造 TC3-HMAC-SHA256 Authorization 头。
    给定相同输入（含 timestamp）输出完全确定，便于测试断言与排障。
    """
    date = time.strftime("%Y-%m-%d", time.gmtime(timestamp))
    content_type = "application/json; charset=utf-8"

    canonical_headers = f"content-type:{content_type}\nhost:{WSA_HOST}\n"
    signed_headers = "content-type;host"
    hashed_payload = hashlib.sha256(payload).hexdigest()
    canonical_request = (
        "POST\n/\n\n" + canonical_headers + "\n" + signed_headers + "\n" + hashed_payload
    )

    credential_scope = f"{date}/{WSA_SERVICE}/tc3_request"
    string_to_sign = (
        "TC3-HMAC-SHA256\n"
        + str(timestamp)
        + "\n"
        + credential_scope
        + "\n"
        + hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    )

    secret_date = _hmac_sha256(("TC3" + secret_key).encode("utf-8"), date)
    secret_service = _hmac_sha256(secret_date, WSA_SERVICE)
    secret_signing = _hmac_sha256(secret_service, "tc3_request")
    signature = hmac.new(
        secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    return (
        f"TC3-HMAC-SHA256 Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )


def _build_payload(
    query: str,
    site: str = "",
    from_time: int = None,
    to_time: int = None,
    mode: int = 0,
) -> bytes:
    """构造 SearchPro 请求体（仅标准版可用参数）。"""
    params = {"Query": query}
    if mode:
        params["Mode"] = mode
    if site:
        params["Site"] = site
    if from_time is not None:
        params["FromTime"] = int(from_time)
    if to_time is not None:
        params["ToTime"] = int(to_time)
    return json.dumps(params, ensure_ascii=False).encode("utf-8")


def _build_request(payload: bytes, secret_id: str, secret_key: str) -> urllib.request.Request:
    timestamp = int(time.time())
    req = urllib.request.Request(WSA_ENDPOINT, data=payload, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    req.add_header("Host", WSA_HOST)
    req.add_header("X-TC-Action", WSA_ACTION)
    req.add_header("X-TC-Version", WSA_VERSION)
    req.add_header("X-TC-Timestamp", str(timestamp))
    req.add_header("Authorization", build_authorization(secret_id, secret_key, payload, timestamp))
    return req


def _normalize_date(raw: str) -> str:
    """把 WSA 的 'YYYY-MM-DD HH:MM:SS' 规范化为 ISO 日期 'YYYY-MM-DD'；解析失败返回空串。"""
    text = (raw or "").strip()
    if not text:
        return ""
    date_part = text.split(" ", 1)[0].split("T", 1)[0]
    try:
        return datetime.date.fromisoformat(date_part).isoformat()
    except ValueError:
        return ""


def _map_page(page: dict) -> dict:
    """将 WSA Pages 单条记录映射为 VSP 标准结果格式。"""
    return {
        "url": page.get("url", ""),
        "title": page.get("title", ""),
        "content": page.get("passage", ""),
        "score": page.get("score", 0),
        "engine": "tencent_wsa",
        "published_at": _normalize_date(page.get("date", "")),
        "source": page.get("site", ""),
    }


def _error_status(code: str, message: str) -> dict:
    status, reason = _ERROR_STATUS_MAP.get(code, ("failed", "api_error"))
    result = {"status": status, "reason": reason, "error_code": code}
    if message:
        result["message"] = message[:200]
    return result


def _parse_error_body(raw: bytes) -> tuple:
    """从错误响应体中提取 (code, message)；解析失败返回 ("", "")。"""
    try:
        error = json.loads(raw.decode("utf-8", errors="ignore")).get("Response", {}).get("Error", {})
        return error.get("Code", ""), error.get("Message", "")
    except (ValueError, AttributeError):
        return "", ""


def search_with_status(
    query: str,
    max_results: int = 10,
    site: str = "",
    from_time: int = None,
    to_time: int = None,
    mode: int = 0,
    timeout: int = 30,
) -> dict:
    """
    调用腾讯云 WSA SearchPro，返回 {"results": [...], "status": {...}}。
    任何失败都映射为引擎健康状态，不抛异常，让主流程自动降级。
    注：标准版不支持 Cnt 参数，max_results 仅用于本地截断。
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

    secret_id = os.environ["TENCENTCLOUD_SECRET_ID"]
    secret_key = os.environ["TENCENTCLOUD_SECRET_KEY"]
    payload = _build_payload(query, site=site, from_time=from_time, to_time=to_time, mode=mode)

    try:
        req = _build_request(payload, secret_id, secret_key)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except urllib.error.HTTPError as e:
        body = e.read() if hasattr(e, "read") else b""
        code, message = _parse_error_body(body)
        status = _error_status(code or f"HTTP {e.code}", message)
        print(f"[tencent_wsa] HTTP {e.code}: {code} {message}"[:200], file=sys.stderr)
        return {"results": [], "status": status}
    except urllib.error.URLError as e:
        print(f"[tencent_wsa] Network error: {e.reason}", file=sys.stderr)
        return {"results": [], "status": {"status": "failed", "reason": "network_error", "message": str(e.reason)[:200]}}
    except TimeoutError:
        print("[tencent_wsa] Timeout", file=sys.stderr)
        return {"results": [], "status": {"status": "failed", "reason": "timeout"}}
    except Exception as e:
        print(f"[tencent_wsa] Error: {e}", file=sys.stderr)
        return {"results": [], "status": {"status": "failed", "reason": type(e).__name__, "message": str(e)[:200]}}

    response = data.get("Response", {})
    if "Error" in response:
        error = response["Error"]
        print(f"[tencent_wsa] API error: {error.get('Code')} {error.get('Message')}", file=sys.stderr)
        return {"results": [], "status": _error_status(error.get("Code", ""), error.get("Message", ""))}

    results = []
    for raw_page in response.get("Pages", []):
        try:
            page = json.loads(raw_page) if isinstance(raw_page, str) else raw_page
        except ValueError:
            continue  # 跳过无法解析的 Pages 条目
        if isinstance(page, dict) and page.get("url") and page.get("title"):
            results.append(_map_page(page))
    results = results[:max_results]

    status = {"status": "ok" if results else "empty", "reason": "api_results" if results else "no_results_returned"}
    if response.get("Version"):
        status["account_version"] = response["Version"]
    if response.get("Msg"):
        status["api_msg"] = response["Msg"]
    return {"results": results, "status": status}


def search(query: str, max_results: int = 10, timeout: int = 30, **kwargs) -> list:
    """Tavily 风格契约：只返回结果列表；失败时返回空列表，让主流程自动降级。"""
    return search_with_status(query, max_results=max_results, timeout=timeout, **kwargs)["results"]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 wsa_adapter.py \"query\" [max_results]")
        sys.exit(1)
    query = sys.argv[1]
    max_results = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    print(json.dumps(search(query, max_results), indent=2, ensure_ascii=False))
