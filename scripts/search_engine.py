#!/usr/bin/env python3
"""
Verified Search Pro · 主搜索引擎
职责：多引擎调度、结果融合、交叉验证、输出报告
纯 Python 标准库，零外部依赖

用法：
  python3 search_engine.py "搜索查询" [--mode auto|fact|perspective|research] [--budget auto|lite|standard|deep] [--checkpoint auto|batch|interactive] [--input-results path.json] [--engines tavily,baidu,bing_cn,sogou] [--verify] [--fetch-content] [--output json|md|claims-json]
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
    "auto": "auto",
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
    "host": "host_search",
    "host_input": "host_search",
    "kimi": "host_search",
}

SUPPORTED_MODES = {"auto", "fact", "perspective", "research"}
CHECKPOINT_MODES = {"auto", "batch", "interactive"}
STRUCTURED_OUTPUTS = {"claims-json", "claim-json", "evidence-pack", "evidence-json"}


def normalize_budget(budget: str) -> str:
    return BUDGET_ALIASES.get((budget or "standard").lower(), "standard")


def normalize_engines(engines: list) -> list:
    normalized = []
    for engine in engines:
        if engine.strip().lower() in {"none", "input_only", "host_only"}:
            continue
        name = ENGINE_ALIASES.get(engine.strip(), engine.strip())
        if name and name not in normalized:
            normalized.append(name)
    return normalized


def recommend_budget(query: str, mode: str) -> str:
    """Small rule-based budget suggestion; no model call and no extra network probe."""
    lowered = query.lower()
    deep_tokens = (
        "调研", "研究", "对比", "优劣", "趋势", "争议", "观点", "时间演进",
        "技术路线", "供应链", "竞品", "政策", "pros and cons", "controversy",
        "market research", "compare", "roadmap",
    )
    lite_tokens = ("是否", "真假", "确认", "date", "when", "who", "what is")
    term_count = len([part for part in query.replace("/", " ").replace(",", " ").split() if part])
    if mode in {"research", "perspective"}:
        return "deep"
    if any(token in query or token in lowered for token in deep_tokens):
        return "deep"
    if term_count <= 4 and any(token in query or token in lowered for token in lite_tokens):
        return "lite"
    return "standard"


def usage() -> str:
    return (
        'Usage: python3 scripts/search_engine.py "query" '
        '[--mode auto|fact|perspective|research] '
        '[--budget auto|lite|standard|deep] '
        '[--checkpoint auto|batch|interactive] '
        '[--input-results path.json] '
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
            "default_engines": ["tavily", "bing_cn"],
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
            "default": "auto_to_standard_or_task_specific",
            "hard_red_line_tokens": 256000,
            "policy": "Reserve room for system prompts, user task context, and downstream reasoning.",
        },
        "host_search": {
            "available": False,
            "default_enabled": False,
            "status": "input_results_only",
            "reason": "Host search tools such as Kimi Search are accepted through --input-results; VSP does not control or require them.",
        },
    }


def detect_blocked_page(engine_name: str, html_text: str) -> dict:
    """Detect common search-engine anti-bot pages without trying to bypass them."""
    lowered = (html_text or "").lower()
    signatures = {
        "baidu": (
            "百度安全验证", "安全验证", "请输入验证码", "verify.baidu.com",
            "wappass.baidu.com", "异常流量", "网络不给力",
        ),
        "wechat": ("请输入验证码", "antispider", "用户您好", "搜狗搜索"),
        "sogou": ("请输入验证码", "antispider", "您的访问出错了"),
    }
    for token in signatures.get(engine_name, ()):
        if token.lower() in lowered:
            return {
                "blocked": True,
                "reason": "captcha_or_security_challenge",
                "signature": token,
            }
    return {"blocked": False}


def search_web_engine_with_status(engine_name: str, query: str) -> dict:
    """搜索单个 Web 引擎，并返回轻量健康状态。"""
    config = WEB_ENGINES.get(engine_name)
    if not config:
        return {"results": [], "status": {"status": "skipped", "reason": "unknown_engine"}}
    url = config["url"].format(urllib.parse.quote(query))
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        resp = urllib.request.urlopen(req, timeout=config["timeout"])
        final_url = getattr(resp, "url", url)
        html = resp.read().decode("utf-8", errors="ignore")
        blocked = detect_blocked_page(engine_name, html)
        if blocked["blocked"]:
            return {
                "results": [],
                "status": {
                    "status": "blocked",
                    "reason": blocked["reason"],
                    "signature": blocked["signature"],
                    "url": final_url,
                },
            }
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
        status = "ok" if results else "empty"
        return {"results": results, "status": {"status": status, "reason": "parsed_results" if results else "no_results_parsed"}}
    except Exception as e:
        print(f"[{engine_name}] Error: {e}", file=sys.stderr)
        return {"results": [], "status": {"status": "failed", "reason": type(e).__name__, "message": str(e)[:200]}}


def search_web_engine(engine_name: str, query: str) -> list:
    """Backward-compatible wrapper that returns only result rows."""
    return search_web_engine_with_status(engine_name, query)["results"]


def normalize_input_result(record: dict, index: int) -> dict:
    """Normalize host-provided search records into VSP's lightweight schema."""
    content = record.get("content") or record.get("snippet") or record.get("summary") or ""
    full_content = record.get("full_content") or record.get("raw_content") or ""
    return {
        "url": record.get("url", ""),
        "title": record.get("title", "") or record.get("name", ""),
        "content": content,
        "full_content": full_content,
        "engine": record.get("engine") or record.get("source_engine") or "host_search",
        "score": record.get("score", 0),
        "timestamp": record.get("timestamp", time.time()),
        "published_at": record.get("published_at") or record.get("published_date") or record.get("date", ""),
        "fetch_source": record.get("fetch_source", ""),
        "author": record.get("author", ""),
        "source_type": record.get("source_type", ""),
        "original_source_url": record.get("original_source_url", ""),
        "host_record_index": index,
    }


def load_input_results(path: str) -> list:
    """Load externally searched host results without invoking any host search runtime."""
    if not path:
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    rows = data.get("results", data.get("items", [])) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("--input-results must be a JSON list or an object with results/items")
    normalized = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        item = normalize_input_result(row, index)
        if item["url"] and item["title"]:
            normalized.append(item)
    return normalized

def parse_args(args: list) -> dict:
    """解析命令行参数"""
    result = {
        "query": "",
        "budget": "auto",
        "engines": ["tavily", "bing_cn"],
        "mode": "auto",
        "checkpoint": "auto",
        "input_results": "",
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
        elif token == "--checkpoint" and i + 1 < len(args):
            checkpoint = args[i + 1].lower()
            result["checkpoint"] = checkpoint if checkpoint in CHECKPOINT_MODES else "auto"
            i += 2
        elif token == "--input-results" and i + 1 < len(args):
            result["input_results"] = args[i + 1]
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
    budget_requested = config["budget"]
    engines = config["engines"]
    mode = config["mode"]
    checkpoint = config["checkpoint"]
    verify = config["verify"]
    fetch_content = config["fetch_content"]
    output_format = config["output"]
    budget = recommend_budget(query, mode) if budget_requested == "auto" else budget_requested
    
    print(f"[Search] Query: {query}", file=sys.stderr)
    print(f"[Search] Engines: {engines}", file=sys.stderr)
    print(f"[Search] Budget: {budget} (requested: {budget_requested})", file=sys.stderr)
    print(f"[Search] Mode: {mode}", file=sys.stderr)
    print(f"[Search] Checkpoint: {checkpoint}", file=sys.stderr)
    
    # 读取宿主 agent 已经搜索到的结果；不调用 Kimi/OpenClaw 等宿主运行时。
    all_results = []
    engine_status = {}
    if config["input_results"]:
        try:
            host_results = load_input_results(config["input_results"])
            all_results.extend(host_results)
            host_engines = sorted({r.get("engine", "host_search") for r in host_results})
            for host_engine in host_engines or ["host_search"]:
                engine_status[host_engine] = {
                    "status": "ok" if host_results else "empty",
                    "reason": "input_results_loaded",
                    "count": sum(1 for r in host_results if r.get("engine") == host_engine),
                    "source": "input_results",
                }
            print(f"[Input] {len(host_results)} host results", file=sys.stderr)
        except Exception as e:
            engine_status["host_search"] = {
                "status": "failed",
                "reason": "input_results_error",
                "message": str(e)[:200],
                "source": "input_results",
            }
            print(f"[Input] Failed: {e}", file=sys.stderr)

    # 并行搜索：只调用用户选择的引擎，不为健康检测额外轮询所有引擎。
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for e in engines:
            if e == "tavily":
                if not tavily_adapter.is_available():
                    engine_status["tavily"] = {
                        "status": "skipped",
                        "reason": "api_key_missing",
                        "requires": ["TAVILY_API_KEY"],
                    }
                    continue
                max_results = BUDGET_RESULT_LIMITS.get(budget, 10)
                search_depth = "advanced" if budget in {"standard", "deep"} else "basic"
                futures[executor.submit(tavily_adapter.search, query, max_results, search_depth)] = ("tavily", "api")
            elif e in WEB_ENGINES:
                futures[executor.submit(search_web_engine_with_status, e, query)] = (e, "web")
            elif e == "google_cse":
                engine_status["google_cse"] = {
                    "status": "skipped",
                    "reason": "not_default_enabled",
                }
                print("[google_cse] Not enabled by default in 2.0; skipped", file=sys.stderr)
            elif e == "host_search":
                engine_status["host_search"] = {
                    "status": "skipped",
                    "reason": "host_search_requires_input_results",
                }
        
        for future in concurrent.futures.as_completed(futures):
            engine, engine_type = futures[future]
            try:
                payload = future.result()
                if engine_type == "web":
                    res = payload["results"]
                    engine_status[engine] = payload["status"]
                    engine_status[engine]["count"] = len(res)
                else:
                    res = payload
                    engine_status[engine] = {
                        "status": "ok" if res else "empty",
                        "reason": "api_results" if res else "no_results_returned",
                        "count": len(res),
                    }
                all_results.extend(res)
                print(f"[{engine}] {len(res)} results", file=sys.stderr)
            except Exception as e:
                engine_status[engine] = {
                    "status": "failed",
                    "reason": type(e).__name__,
                    "message": str(e)[:200],
                }
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
        "budget_requested": budget_requested,
        "engines": engines,
        "mode": mode,
        "checkpoint": checkpoint,
        "engine_status": engine_status,
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
            "budget_requested": budget_requested,
            "engines": engines,
            "total_raw": len(all_results),
            "mode": mode,
            "checkpoint": checkpoint,
            "engine_status": engine_status,
        }, mode=mode, budget=budget)
        print(json.dumps(package, indent=2, ensure_ascii=False))
    elif output_format in ("evidence-pack", "evidence-json"):
        package = trust_model.build_claim_package(query, fused, {
            "budget": budget,
            "budget_requested": budget_requested,
            "engines": engines,
            "total_raw": len(all_results),
            "mode": mode,
            "checkpoint": checkpoint,
            "engine_status": engine_status,
        }, mode=mode, budget=budget)
        print(json.dumps(package, indent=2, ensure_ascii=False))
    elif output_format == "md":
        package = trust_model.build_claim_package(query, fused, {
            "budget": budget,
            "budget_requested": budget_requested,
            "engines": engines,
            "total_raw": len(all_results),
            "mode": mode,
            "checkpoint": checkpoint,
            "engine_status": engine_status,
        }, mode=mode, budget=budget)
        print(render_markdown_report(package))
    else:
        print(json.dumps(output, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
