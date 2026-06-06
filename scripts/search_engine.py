#!/usr/bin/env python3
"""
Verified Search Pro · 主搜索引擎
职责：多引擎调度、结果融合、交叉验证、输出报告
纯 Python 标准库，零外部依赖

用法：
  python3 search_engine.py "搜索查询" [--mode auto|fact|perspective|research] [--budget lite|standard|deep] [--engines tavily,baidu,bing_cn,sogou] [--verify] [--fetch-content] [--output json|md|claims-json]
  python3 search_engine.py --doctor
"""

import sys
import json
import urllib.request
import urllib.parse
import concurrent.futures
import time
import os
import platform
import shutil

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

BUDGET_RESULT_LIMITS = {
    "lite": 5,
    "standard": 10,
    "deep": 20,
}

BUDGET_ALIASES = {
    "minimal": "lite",
    "balanced": "standard",
    "comprehensive": "deep",
    "lite": "lite",
    "standard": "standard",
    "deep": "deep",
}

ENGINE_ALIASES = {
    "bing": "bing_cn",
    "bing_global": "bing_int",
    "bing_intl": "bing_int",
    "google": "google_cse",
}

SUPPORTED_MODES = {"auto", "fact", "perspective", "research"}
STRUCTURED_OUTPUTS = {"claims-json", "claim-json", "evidence-pack", "evidence-json"}


def normalize_budget(budget: str) -> str:
    return BUDGET_ALIASES.get((budget or "standard").lower(), "standard")


def normalize_engines(engines: list) -> list:
    normalized = []
    for engine in engines:
        name = ENGINE_ALIASES.get(engine.strip(), engine.strip())
        if name and name not in normalized:
            normalized.append(name)
    return normalized


def usage() -> str:
    return (
        'Usage: python3 scripts/search_engine.py "query" '
        '[--mode auto|fact|perspective|research] '
        '[--budget lite|standard|deep] '
        '[--engines tavily,baidu,bing_cn,sogou,wechat] '
        '[--verify] [--fetch-content] [--output json|md|claims-json]\n'
        '       python3 scripts/search_engine.py --doctor'
    )


def check_environment() -> dict:
    node_path = shutil.which("node")
    return {
        "ok": True,
        "python": {
            "version": platform.python_version(),
            "meets_minimum": sys.version_info >= (3, 8),
            "executable": sys.executable,
        },
        "search": {
            "default_engines": ["tavily", "baidu", "bing_cn"],
            "web_engines": sorted(WEB_ENGINES.keys()),
            "tavily": tavily_adapter.get_status(),
            "google": {
                "available": False,
                "default_enabled": False,
                "status": "future_optional_adapter",
                "reason": "Google is not a 2.0 default because it needs separate Custom Search setup, API credentials, and reliable network/proxy access.",
            },
        },
        "optional_runtime": {
            "node": {
                "available": bool(node_path),
                "path": node_path,
                "used_for": "wechat_fetch_only",
            }
        },
        "delivery": {
            "default": ["Markdown", "claims-json"],
            "optional_adapters": ["Feishu", "Notion", "Google Docs", "Obsidian"],
        },
        "initialization": {
            "mode": "read_only_doctor",
            "writes_files": False,
            "stores_secrets": False,
            "recommended_first_run": "python3 scripts/search_engine.py --doctor",
            "next_steps": [
                "Run without Tavily first to confirm web-only fallback works.",
                "Set TAVILY_API_KEY only if higher-quality AI search is needed.",
                "Install Node.js only if WeChat article content fetching is required.",
            ],
        },
        "context_budget": {
            "profiles": ["lite", "standard", "deep"],
            "default": "standard",
            "hard_red_line_tokens": 256000,
            "policy": "Reserve room for system prompts, user task context, and downstream reasoning.",
        },
    }

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
        "query": "",
        "budget": "standard",
        "engines": ["tavily", "baidu", "bing_cn"],
        "mode": "auto",
        "verify": False,
        "fetch_content": False,
        "output": "json",
        "doctor": False,
    }
    positionals = []
    i = 0
    while i < len(args):
        token = args[i]
        if token in ("--doctor", "--check-env"):
            result["doctor"] = True
            i += 1
        elif token == "--budget" and i + 1 < len(args):
            result["budget"] = normalize_budget(args[i + 1])
            i += 2
        elif token == "--engines" and i + 1 < len(args):
            result["engines"] = normalize_engines(args[i + 1].split(","))
            i += 2
        elif token == "--mode" and i + 1 < len(args):
            mode = args[i + 1].lower()
            result["mode"] = mode if mode in SUPPORTED_MODES else "auto"
            i += 2
        elif token == "--verify":
            result["verify"] = True
            i += 1
        elif token == "--fetch-content":
            result["fetch_content"] = True
            i += 1
        elif token == "--output" and i + 1 < len(args):
            result["output"] = args[i + 1]
            i += 2
        elif token.startswith("-"):
            i += 1
        else:
            positionals.append(token)
            i += 1
    result["query"] = " ".join(positionals).strip()
    return result


def render_markdown_report(package: dict) -> str:
    """Render the evidence pack into a compact human-readable Markdown report."""
    lines = [
        f"# 搜索研究报告: {package['query']}",
        "",
        f"- **模式**: {package['research_mode']}",
        f"- **预算**: {package['search']['budget']}",
        f"- **证据数**: {package['search']['evidence_returned']} / {package['search']['total_fused']}",
        "",
        "## 可信结论",
    ]
    if package["trusted_conclusions"]:
        for claim in package["trusted_conclusions"]:
            lines.append(f"- **{claim['claim']}** (confidence: {claim['confidence']})")
            lines.append(f"  - 证据: {', '.join(claim['supporting_evidence']) or '无'}")
            lines.append(f"  - 限制: {'; '.join(claim['limits']) or '无'}")
    else:
        lines.append("- 当前证据不足以形成可直接引用的可信结论。")

    lines.extend(["", "## 观点地图"])
    if package["perspective_map"]["items"]:
        for item in package["perspective_map"]["items"]:
            lines.append(f"- **{item['summary']}**")
            lines.append(f"  - 用途: {item['use_as']}; 不可直接当事实: {item['must_not_be_used_as_fact']}")
    else:
        lines.append("- 未检测到需要单独标注的观点材料。")

    lines.extend(["", "## 常见误区"])
    if package["common_misconceptions"]:
        for item in package["common_misconceptions"]:
            lines.append(f"- **{item['summary']}**")
            lines.append(f"  - 标注: {item['label']}; 原因: {item['reason']}")
    else:
        lines.append("- 未检测到明显误区或噪声样本。")

    lines.extend(["", "## 争议与不确定性"])
    if package["controversies_uncertainties"]["items"]:
        for item in package["controversies_uncertainties"]["items"]:
            lines.append(f"- {item['summary']}")
    else:
        lines.append("- 未检测到需要单独标注的争议或不确定性。")

    lines.extend(["", "## 时间演进"])
    if package["temporal_evolution"]:
        for item in package["temporal_evolution"]:
            lines.append(
                f"- **{item['title']}**: {item['temporal_status']} "
                f"(date: {item['publication_date'] or 'unknown'})"
            )
    else:
        lines.append("- 暂无可用时间线。")

    lines.extend(["", "## 来源证据"])
    for ev in package["evidence"]:
        lines.append(f"- [{ev['evidence_id']}] {ev['title']} - {ev['url']}")
    return "\n".join(lines)

def main():
    args = sys.argv[1:]
    config = parse_args(args)
    if config["doctor"]:
        print(json.dumps(check_environment(), indent=2, ensure_ascii=False))
        return
    if not config["query"]:
        print(usage())
        sys.exit(1)

    query = config["query"]
    budget = config["budget"]
    engines = config["engines"]
    mode = config["mode"]
    verify = config["verify"]
    fetch_content = config["fetch_content"]
    output_format = config["output"]
    
    print(f"[Search] Query: {query}", file=sys.stderr)
    print(f"[Search] Engines: {engines}", file=sys.stderr)
    print(f"[Search] Budget: {budget}", file=sys.stderr)
    print(f"[Search] Mode: {mode}", file=sys.stderr)
    
    # 并行搜索
    all_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for e in engines:
            if e == "tavily":
                max_results = BUDGET_RESULT_LIMITS.get(budget, 10)
                search_depth = "advanced" if budget in {"standard", "deep"} else "basic"
                futures[executor.submit(tavily_adapter.search, query, max_results, search_depth)] = "tavily"
            elif e in WEB_ENGINES:
                futures[executor.submit(search_web_engine, e, query)] = e
            elif e == "google_cse":
                print("[google_cse] Not enabled by default in 2.0; skipped", file=sys.stderr)
        
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
    needs_verification = verify or output_format in STRUCTURED_OUTPUTS or output_format == "md"
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
        "mode": mode,
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
            "mode": mode,
        }, mode=mode, budget=budget)
        print(json.dumps(package, indent=2, ensure_ascii=False))
    elif output_format in ("evidence-pack", "evidence-json"):
        package = trust_model.build_claim_package(query, fused, {
            "budget": budget,
            "engines": engines,
            "total_raw": len(all_results),
            "mode": mode,
        }, mode=mode, budget=budget)
        print(json.dumps(package, indent=2, ensure_ascii=False))
    elif output_format == "md":
        package = trust_model.build_claim_package(query, fused, {
            "budget": budget,
            "engines": engines,
            "total_raw": len(all_results),
            "mode": mode,
        }, mode=mode, budget=budget)
        print(render_markdown_report(package))
    else:
        print(json.dumps(output, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
