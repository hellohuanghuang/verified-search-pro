#!/usr/bin/env python3
"""
Verified Search Pro · Benchmark 运行器

运行 benchmark/queries.json 中定义的所有查询，并将 evidence-pack 保存到 benchmark/results/。
默认使用 bing_cn 引擎，避免对 Tavily API 的依赖。

用法：
    python3 benchmark/run.py [--engines bing_cn] [--output-dir benchmark/results]
"""

import argparse
import json
import os
import subprocess
import sys
import time


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_query(query: str, mode: str, budget: str, engines: list, output_dir: str, concepts: str = None) -> dict:
    """调用 search_engine.py 运行单个查询并返回 evidence-pack。"""
    result_path = os.path.join(output_dir, f"{query_id_safe(query)}.json")
    cmd = [
        sys.executable,
        os.path.join(ROOT, "scripts", "search_engine.py"),
        query,
        "--mode", mode,
        "--budget", budget,
        "--engines", ",".join(engines),
        "--verify",
        "--output", "claims-json",
        "--no-cache",
    ]
    # v2.1.0 起中文自然语言查询必须携带核心概念（SKILL.md 合规调用契约），
    # benchmark 用例同样遵守，否则视为违规调用。
    if concepts:
        cmd.extend(["--search-concepts", concepts])
    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
        elapsed = time.time() - start
        if proc.returncode != 0:
            return {
                "query": query,
                "status": "error",
                "returncode": proc.returncode,
                "stderr": proc.stderr[:500],
                "elapsed_seconds": elapsed,
            }
        package = json.loads(proc.stdout)
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(package, f, indent=2, ensure_ascii=False)
        return {
            "query": query,
            "status": "ok",
            "result_path": result_path,
            "elapsed_seconds": elapsed,
            "summary": {
                "confidence": package["claims"][0]["confidence"] if package.get("claims") else "E",
                "evidence_returned": package.get("search", {}).get("evidence_returned", 0),
                "trusted_conclusions": len(package.get("trusted_conclusions", [])),
            },
        }
    except subprocess.TimeoutExpired:
        return {"query": query, "status": "timeout", "elapsed_seconds": 120}
    except json.JSONDecodeError as e:
        return {"query": query, "status": "json_error", "error": str(e)}


def query_id_safe(query: str) -> str:
    """将查询转换为可用作文件名的 ID。"""
    return "".join(c if c.isalnum() or c in "_-" else "_" for c in query)[:40]


def main():
    parser = argparse.ArgumentParser(description="Run VSP benchmark")
    parser.add_argument("--engines", default="duckduckgo,sogou,bing_cn",
                        help="逗号分隔的引擎列表（默认覆盖全部免费 Web 引擎，无需 Tavily key）")
    parser.add_argument("--output-dir", default=os.path.join(ROOT, "benchmark", "results"))
    args = parser.parse_args()

    engines = [e.strip() for e in args.engines.split(",") if e.strip()]
    os.makedirs(args.output_dir, exist_ok=True)

    queries_path = os.path.join(ROOT, "benchmark", "queries.json")
    with open(queries_path, "r", encoding="utf-8") as f:
        queries = json.load(f)

    results = []
    for item in queries:
        print(f"[benchmark] running: {item['query']} ...", file=sys.stderr)
        result = run_query(item["query"], item["mode"], item["budget"], engines, args.output_dir,
                           concepts=item.get("concepts"))
        result["id"] = item.get("id", query_id_safe(item["query"]))
        result["expected"] = item.get("expected", {})
        results.append(result)
        print(f"[benchmark] {result['status']} in {result.get('elapsed_seconds', 0):.1f}s", file=sys.stderr)

    summary_path = os.path.join(args.output_dir, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({"results": results, "total": len(results)}, f, indent=2, ensure_ascii=False)

    print(json.dumps({"results": results, "total": len(results)}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
