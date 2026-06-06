#!/usr/bin/env python3
"""
Verified Search Pro · Tavily 适配器
职责：调用 Tavily API 进行 AI 搜索
可选依赖：需要 TAVILY_API_KEY 环境变量，缺失时返回空列表
"""

import os
import json
import sys
import urllib.error
import urllib.request

TAVILY_ENDPOINT = os.environ.get("TAVILY_API_URL", "https://api.tavily.com/search")


def is_available() -> bool:
    """检查 Tavily API Key 是否已配置。"""
    return bool(os.environ.get("TAVILY_API_KEY"))


def get_status() -> dict:
    """Return a small environment status object for first-run diagnostics."""
    return {
        "available": is_available(),
        "requires": ["TAVILY_API_KEY"],
        "endpoint": TAVILY_ENDPOINT,
        "integration": "direct_rest_api",
        "fallback": "web_only_search_when_key_missing_or_request_fails",
    }


def _build_request(query: str, max_results: int, search_depth: str) -> urllib.request.Request:
    api_key = os.environ.get("TAVILY_API_KEY", "")
    payload = {
        "query": query,
        "max_results": max_results,
        "search_depth": search_depth,
        "include_answer": False,
        "include_raw_content": False,
    }
    return urllib.request.Request(
        TAVILY_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )


def _map_result(record: dict) -> dict:
    return {
        "url": record.get("url", ""),
        "title": record.get("title", ""),
        "content": record.get("content", "") or record.get("snippet", ""),
        "score": record.get("score", 0),
        "engine": "tavily",
        "published_at": record.get("published_date") or record.get("published_at", ""),
    }


def search(query: str, max_results: int = 10, search_depth: str = "advanced") -> list:
    """调用 Tavily Search API；失败时返回空列表，让主流程自动降级。"""
    if not is_available():
        return []

    try:
        req = _build_request(query, max_results, search_depth)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        return [_map_result(r) for r in data.get("results", []) if r.get("url") and r.get("title")]
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")[:200]
        print(f"[tavily] HTTP {e.code}: {detail}", file=sys.stderr)
        return []
    except urllib.error.URLError as e:
        print(f"[tavily] Network error: {e.reason}", file=sys.stderr)
        return []
    except TimeoutError:
        print("[tavily] Timeout", file=sys.stderr)
        return []
    except Exception as e:
        print(f"[tavily] Error: {e}", file=sys.stderr)
        return []

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 tavily_adapter.py \"query\" [max_results]")
        sys.exit(1)
    query = sys.argv[1]
    max_results = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    results = search(query, max_results)
    print(json.dumps(results, indent=2, ensure_ascii=False))
