#!/usr/bin/env python3
"""
Verified Search Pro · Tavily 适配器
职责：调用 Tavily API 进行 AI 搜索
可选依赖：需要 TAVILY_API_KEY 环境变量，缺失时返回空列表
"""

import os
import json
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TAVILY_SCRIPT = os.path.join(SCRIPT_DIR, "../../tavily-websearch/scripts/search.sh")

def is_available() -> bool:
    """检查 Tavily 是否可用"""
    return bool(os.environ.get("TAVILY_API_KEY")) and os.path.exists(TAVILY_SCRIPT)

def search(query: str, max_results: int = 10, search_depth: str = "advanced") -> list:
    """调用 Tavily API 搜索"""
    if not is_available():
        return []
    
    cmd = [
        "bash", TAVILY_SCRIPT,
        "--json",
        json.dumps({
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth
        })
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            results = []
            for r in data.get("results", []):
                results.append({
                    "url": r.get("url", ""),
                    "title": r.get("title", ""),
                    "content": r.get("content", ""),
                    "score": r.get("score", 0),
                    "engine": "tavily",
                })
            return results
        else:
            print(f"[tavily] Script error: {result.stderr[:200]}", file=sys.stderr)
            return []
    except subprocess.TimeoutExpired:
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