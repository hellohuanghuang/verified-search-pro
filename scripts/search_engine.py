#!/usr/bin/env python3
"""
Verified Search Pro · 主搜索引擎
职责：多引擎调度、结果融合、交叉验证、输出报告
纯 Python 标准库，零外部依赖

用法：
  python3 search_engine.py "搜索查询" [--budget balanced] [--engines tavily,baidu,bing,sogou] [--verify] [--fetch-content] [--output json|md|claims-json]
"""

import sys
import json
import urllib.request
import urllib.parse
import concurrent.futures
import time
import os

# 导入子模块（同目录）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

try:
    import html_parser
    import result_fusion
    import cross_verify
    import trust_model
    import tavily_adapter
    import wechat_fetch
except ImportError as e:
    print(f"[Error] Failed to import module: {e}", file=sys.stderr)
    sys.exit(1)

# Web 引擎配置
WEB_ENGINES = {
    "baidu": {"url": "https://www.baidu.com/s?wd={}", "parser": html_parser.parse_baidu, "timeout": 5, "weight": 0.8},
    "bing_cn": {"url": "https://cn.bing.com/search?q={}", "parser": html_parser.parse_bing, "timeout": 5, "weight": 0.85},
    "bing_int": {"url": "https://cn.bing.com/search?q={}&ensearch=1", "parser": html_parser.parse_bing, "timeout": 8, "weight": 0.85},
    "sogou": {"url": "https://www.sogou.com/web?query={}", "parser": html_parser.parse_sogou, "timeout": 5, "weight": 0.75},
    "wechat": {"url": "https://wx.sogou.com/weixin?type=2&query={}", "parser": html_parser.parse_wechat_sogou, "timeout": 5, "weight": 0.75},
}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def search_web_engine(engine_name: str, query: str) -> list:
    """搜索单个 Web 引擎"""
    config = WEB_ENGINES.get(engine_name)
    if not config:
        return []
    url = config["url"].format(urllib.parse.quote(query))
    headers = {"User-Agent": USER_AGENT}
    try:
        req = urllib.request.Request(url, headers=headers)
        resp = urllib.request.urlopen(req, timeout=config["timeout"])
        html = resp.read().decode("utf-8", errors="ignore")
        raw = config["parser"](html)
        results = []
        for r in raw:
            if r.get("url") and r.get("title"):
                results.append({
                    "url": r["url"],
                    "title": r["title"],
                    "content": r.get("content", ""),
                    "engine": engine_name,
                    "score": 0,
                    "timestamp": time.time(),
                })
        return results
    except Exception as e:
        print(f"[{engine_name}] Error: {e}", file=sys.stderr)
        return []

def parse_args(args: list) -> dict:
    """解析命令行参数"""
    result = {
        "query": args[0] if args else "",
        "budget": "balanced",
        "engines": ["tavily", "baidu", "bing_cn"],
        "verify": False,
        "fetch_content": False,
        "output": "json",
    }
    i = 1
    while i < len(args):
        if args[i] == "--budget" and i + 1 < len(args):
            result["budget"] = args[i + 1]
            i += 2
        elif args[i] == "--engines" and i + 1 < len(args):
            result["engines"] = args[i + 1].split(",")
            i += 2
        elif args[i] == "--verify":
            result["verify"] = True
            i += 1
        elif args[i] == "--fetch-content":
            result["fetch_content"] = True
            i += 1
        elif args[i] == "--output" and i + 1 < len(args):
            result["output"] = args[i + 1]
            i += 2
        else:
            i += 1
    return result

def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: python3 search_engine.py \"query\" [--budget minimal|balanced|comprehensive] [--engines tavily,baidu,bing_cn,sogou,wechat] [--verify] [--fetch-content] [--output json|md|claims-json]")
        sys.exit(1)
    
    config = parse_args(args)
    query = config["query"]
    budget = config["budget"]
    engines = config["engines"]
    verify = config["verify"]
    fetch_content = config["fetch_content"]
    output_format = config["output"]
    
    print(f"[Search] Query: {query}", file=sys.stderr)
    print(f"[Search] Engines: {engines}", file=sys.stderr)
    print(f"[Search] Budget: {budget}", file=sys.stderr)
    
    # 并行搜索
    all_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for e in engines:
            if e == "tavily":
                budget_map = {"minimal": 5, "balanced": 10, "comprehensive": 20}
                max_results = budget_map.get(budget, 10)
                futures[executor.submit(tavily_adapter.search, query, max_results)] = "tavily"
            elif e in WEB_ENGINES:
                futures[executor.submit(search_web_engine, e, query)] = e
        
        for future in concurrent.futures.as_completed(futures):
            engine = futures[future]
            try:
                res = future.result()
                all_results.extend(res)
                print(f"[{engine}] {len(res)} results", file=sys.stderr)
            except Exception as e:
                print(f"[{engine}] Failed: {e}", file=sys.stderr)
    
    # 融合
    fused = result_fusion.fuse_results(all_results, budget)
    print(f"[Fuse] {len(fused)} unique results", file=sys.stderr)
    
    # 交叉验证
    needs_verification = verify or output_format in ("claims-json", "claim-json")
    if needs_verification:
        fused = cross_verify.cross_verify_all(query, fused)
        verified_count = sum(1 for r in fused if r.get("verified"))
        print(f"[Verify] {verified_count}/{len(fused)} verified", file=sys.stderr)
    
    # 抓取微信内容
    if fetch_content:
        fused = wechat_fetch.enrich_results(fused)
    
    # 构建输出
    output = {
        "query": query,
        "budget": budget,
        "engines": engines,
        "total_raw": len(all_results),
        "total_fused": len(fused),
        "results": fused,
    }
    if needs_verification:
        output["verification"] = {
            "verified_count": sum(1 for r in fused if r.get("verified")),
            "total_count": len(fused),
        }
    
    # 输出
    if output_format == "json":
        print(json.dumps(output, indent=2, ensure_ascii=False))
    elif output_format in ("claims-json", "claim-json"):
        package = trust_model.build_claim_package(query, fused, {
            "budget": budget,
            "engines": engines,
            "total_raw": len(all_results),
        })
        print(json.dumps(package, indent=2, ensure_ascii=False))
    elif output_format == "md":
        print("# 搜索结果报告\n")
        print(f"**查询**: {query}\n")
        print(f"**引擎**: {', '.join(engines)}\n")
        print(f"**结果数**: {len(fused)} 条（去重后）\n")
        print("---\n")
        for i, r in enumerate(fused, 1):
            print(f"### {i}. {r.get('title', 'N/A')}\n")
            print(f"- **URL**: {r.get('url', 'N/A')}")
            print(f"- **来源**: {', '.join(r.get('sources', [r.get('engine', 'N/A')]))}")
            print(f"- **融合得分**: {r.get('fusion_score', 0):.3f}")
            if "confidence_level" in r:
                print(f"- **置信度**: {r['confidence_level']}")
            if "verified" in r:
                print(f"- **验证状态**: {'✅ 通过' if r['verified'] else '❌ 未通过'}")
            print(f"- **摘要**: {r.get('content', 'N/A')[:200]}...\n")
    else:
        print(json.dumps(output, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
