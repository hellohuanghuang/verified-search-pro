#!/usr/bin/env python3
"""
Verified Search Pro · 主搜索引擎
职责：多引擎调度、结果融合、交叉验证、输出报告
纯 Python 标准库，零外部依赖

用法：
  python3 search_engine.py "搜索查询" [--mode auto|fact|perspective|research] [--budget auto|lite|standard|deep] [--checkpoint auto|batch|interactive] [--input-results path.json] [--engines tavily,baidu,bing_cn,sogou] [--verify] [--fetch-content] [--output json|md|claims-json]
  python3 search_engine.py --doctor
"""

import argparse
import concurrent.futures
import json
import os
import platform
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# 导入子模块（同目录）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

try:
    import baidu_api_adapter
    import config as _config
    import cross_verify
    import html_parser
    import network as _network
    import result_fusion
    import tavily_adapter
    import trust_model
    import wsa_adapter
    import wechat_fetch
except ImportError as e:
    print(f"[Error] Failed to import module: {e}", file=sys.stderr)
    sys.exit(1)


__version__ = "2.1.0-beta"

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
OUTPUT_MODES = {"json", "md", "claims-json", "claim-json", "evidence-pack", "evidence-json"}
STRUCTURED_OUTPUTS = {"claims-json", "claim-json", "evidence-pack", "evidence-json"}

# 中文疑问词前缀（用于查询改写）
_CHINESE_QUESTION_PREFIXES = (
    "如何", "怎样", "怎么", "为什么", "怎么个", "为何",
    "什么是", "什么",
    "哪", "哪些", "哪个", "哪里", "哪儿", "谁", "多少", "几",
)

# 内置中英翻译小字典（不依赖外部 API）
_ENGLISH_TRANSLATION_MAP = {
    "比熊": "bichon",
    "泪痕": "tear stains",
    "消除": "remove",
    "去除": "remove",
    "清理": "clean",
    "泰迪": "poodle",
    "金毛": "golden retriever",
    "柯基": "corgi",
    "狗粮": "dog food",
    "猫粮": "cat food",
    "猫砂": "cat litter",
    "疫苗": "vaccine",
    "驱虫": "deworming",
    "绝育": "neuter",
    "怀孕": "pregnancy",
    "症状": "symptoms",
    "治疗": "treatment",
    "原因": "causes",
    "方法": "methods",
}


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
        '[--engines tavily,tencent_wsa,baidu_api,baidu,bing_cn,sogou,wechat,duckduckgo,toutiao] '
        '[--search-concepts "concept1,concept2"] '
        '[--verify] [--fetch-content] [--output json|md|claims-json]\n'
        '       python3 scripts/search_engine.py --doctor'
    )


def load_runtime_config():
    """加载运行时配置并构建 web 引擎表。"""
    cfg = _config.load_config()
    web_cfg = _config.get_web_engines(cfg)
    user_agent = _config.get_user_agent(cfg)

    web_engines = {}
    for name, ecfg in web_cfg.items():
        parser = html_parser.get_parser(name)
        if not parser:
            continue
        web_engines[name] = {
            "url": ecfg["url"],
            "parser": parser,
            "timeout": ecfg.get("timeout", 5),
            "weight": ecfg.get("weight", 0.75),
            "enabled": ecfg.get("enabled", True),
        }

    budget_limits = {
        name: prof.get("max_evidence", 10)
        for name, prof in cfg.get("budget_profiles", {}).items()
    }

    return cfg, web_engines, user_agent, budget_limits


_RUNTIME_CONFIG, WEB_ENGINES, USER_AGENT, BUDGET_RESULT_LIMITS = load_runtime_config()


# ── Tavily 提醒机制 ──────────────────────────────────────────────
_TAVILY_REMINDER_MARKER = Path.home() / ".vsp_tavily_reminded"


def _generate_tips(engine_status: dict) -> list:
    """根据引擎状态生成 tips 提示，供 Agent 读取并转告用户。"""
    tips = []
    tavily_status = (engine_status or {}).get("tavily", {})
    if tavily_status.get("status") == "skipped" and tavily_status.get("reason") == "api_key_missing":
        tips.append({
            "level": "info",
            "code": "tavily_missing",
            "msg": "Tavily AI 搜索未配置，当前仅使用 Web 搜索。配置后可显著提升结果质量和语义理解能力。",
            "setup_url": "https://app.tavily.com",
            "setup_steps": "注册账号 → 获取 API Key → 设置环境变量 TAVILY_API_KEY",
            "impact": "结果质量降低约 30-40%，缺少 AI 语义搜索能力",
        })
    wsa_status = (engine_status or {}).get("tencent_wsa", {})
    if wsa_status.get("status") == "skipped" and wsa_status.get("reason") == "api_key_missing":
        tips.append({
            "level": "info",
            "code": "tencent_wsa_missing",
            "msg": "腾讯云联网搜索（WSA）未配置，当前缺少该引擎的中文网页检索结果与发布时间元数据。",
            "setup_url": "https://cloud.tencent.com/product/wsa",
            "setup_steps": "注册腾讯云账号并完成个人实名认证 → 控制台开通「联网搜索 API」标准版（活动专区可每日领取免费调用额度）→ API 密钥管理创建 SecretId/SecretKey → 配置环境变量 TENCENTCLOUD_SECRET_ID / TENCENTCLOUD_SECRET_KEY",
            "impact": "缺少腾讯云 WSA 提供的中文检索覆盖与结果发布日期",
        })
    baidu_status = (engine_status or {}).get("baidu_api", {})
    if baidu_status.get("status") == "skipped" and baidu_status.get("reason") == "api_key_missing":
        tips.append({
            "level": "info",
            "code": "baidu_api_missing",
            "msg": "百度千帆 AI 搜索未配置，当前缺少百度搜索官方数据源的网页检索结果与发布时间元数据。",
            "setup_url": "https://console.bce.baidu.com/ai-search/qianfan/ais/console/apiKey",
            "setup_steps": "注册百度智能云账号并完成个人实名认证 → 进入千帆「应用接入」页创建 API Key（Key 以 bce-v3/ALTAK- 开头）→ 设置环境变量 BAIDU_API_KEY → 运行 python3 scripts/search_engine.py --doctor 验证（每日有免费调用额度，具体以控制台页面为准）",
            "impact": "缺少百度搜索官方数据源的中文网页覆盖与结果发布日期",
        })
    return tips


def _tavily_one_time_reminder():
    """CLI 用户一次性提醒：只在第一次检测到 Tavily 缺失时打印，之后用标记文件静默。"""
    if tavily_adapter.is_available():
        return
    if _TAVILY_REMINDER_MARKER.exists():
        return
    print(
        "[Tip] Tavily AI 搜索未配置，当前仅 Web 搜索。"
        "获取免费 API Key → https://app.tavily.com"
        "（设置环境变量 TAVILY_API_KEY 后生效）",
        file=sys.stderr,
    )
    try:
        _TAVILY_REMINDER_MARKER.touch()
    except OSError:
        pass  # 标记文件写入失败不影响主流程


# ── /Tavily 提醒机制 ─────────────────────────────────────────────


def _tavily_doctor_status() -> dict:
    """--doctor 输出中的 Tavily 状态，带配置指引。"""
    status = tavily_adapter.get_status()
    if status["available"]:
        return status
    return {
        **status,
        "status": "not_configured",
        "impact": "结果质量降低约 30-40%，缺少 AI 语义搜索能力",
        "setup": {
            "step_1": "访问 https://app.tavily.com 注册（免费额度 1000 次/月）",
            "step_2": "在 Dashboard 获取 API Key",
            "step_3": "设置环境变量：export TAVILY_API_KEY=tvly-xxxxx",
            "step_4": "运行 python3 scripts/search_engine.py --doctor 验证",
        },
    }


def _wsa_doctor_status() -> dict:
    """--doctor 输出中的腾讯云 WSA 状态，带配置指引。"""
    status = wsa_adapter.get_status()
    if status["available"]:
        return status
    return {
        **status,
        "status": "not_configured",
        "impact": "缺少腾讯云 WSA 提供的中文检索覆盖与结果发布日期",
        "setup": {
            "step_1": "注册腾讯云账号并完成个人实名认证（https://cloud.tencent.com）",
            "step_2": "控制台开通「联网搜索 API」标准版（活动专区可每日领取免费调用额度）",
            "step_3": "在 API 密钥管理创建 SecretId / SecretKey",
            "step_4": "设置环境变量 TENCENTCLOUD_SECRET_ID / TENCENTCLOUD_SECRET_KEY，运行 --doctor 验证",
        },
    }


def _baidu_api_doctor_status() -> dict:
    """--doctor 输出中的百度千帆 AI 搜索状态，带配置指引。"""
    status = baidu_api_adapter.get_status()
    if status["available"]:
        return status
    return {
        **status,
        "status": "not_configured",
        "impact": "缺少百度搜索官方数据源的中文网页覆盖与结果发布日期",
        "setup": {
            "step_1": "注册百度智能云账号并完成个人实名认证（https://cloud.baidu.com）",
            "step_2": "进入千帆「应用接入」页创建 API Key（https://console.bce.baidu.com/ai-search/qianfan/ais/console/apiKey ，Key 以 bce-v3/ALTAK- 开头）",
            "step_3": "设置环境变量 BAIDU_API_KEY，运行 --doctor 验证",
            "step_4": "每日有免费调用额度，具体以控制台页面为准",
        },
    }


def check_environment() -> dict:
    node_path = shutil.which("node")
    config_sources = _config.get_config_sources()
    return {
        "ok": True,
        "python": {
            "version": platform.python_version(),
            "meets_minimum": sys.version_info >= (3, 8),
            "executable": sys.executable,
        },
        "config": {
            "sources": [{"type": t, "path": p} for t, p in config_sources],
            "user_agent": USER_AGENT,
            "cache_ttl_seconds": _RUNTIME_CONFIG.get("cache_ttl_seconds", 300),
        },
        "search": {
            "default_engines": ["tavily", "tencent_wsa", "baidu_api", "duckduckgo", "bing_cn", "sogou"],
            "web_engines": sorted(WEB_ENGINES.keys()),
            "tavily": _tavily_doctor_status(),
            "tencent_wsa": _wsa_doctor_status(),
            "baidu_api": _baidu_api_doctor_status(),
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
        "duckduckgo": ("anomaly-modal", "complete the following challenge", "select all squares", "bots use duckduckgo"),
        # 头条风控页签名词（已验证均不出现在正常结果页中）；
        # 命中即标记 blocked 并停止，绝不尝试绕过
        "toutiao": (
            "安全验证", "请输入验证码", "拖动滑块", "滑块验证",
            "captcha-verify", "secsdk-captcha", "验证中心",
        ),
    }
    for token in signatures.get(engine_name, ()):
        if token.lower() in lowered:
            return {
                "blocked": True,
                "reason": "captcha_or_security_challenge",
                "signature": token,
            }
    if engine_name == "toutiao":
        # 头条结构性风控识别：无签名词但结果容器完全缺失且页面异常短。
        # 正常结果页必含 real-index=" 结果标记（只出现在真实结果 DOM，不在 CSS/JS 中），
        # 且 SSR 页面体积远大于 20KB；验证/跳转壳页通常只有几 KB。
        # 宁可保守误判为 blocked（停止），也不对异常页面反复请求。
        if 'real-index="' not in lowered and len(html_text or "") < 20000:
            return {
                "blocked": True,
                "reason": "missing_result_container",
                "signature": "short_page_without_result_container",
            }
    return {"blocked": False}


# ── 查询改写与翻译辅助 ─────────────────────────────────────────────


def _is_chinese_natural_language(query: str) -> bool:
    """简单判断是否为中文自然语言（含中文字符）。"""
    return bool(re.search(r"[\u4e00-\u9fff]", query or ""))


def _strip_question_prefix(query: str) -> str:
    """去掉中文疑问词前缀。"""
    stripped = query.strip()
    for prefix in _CHINESE_QUESTION_PREFIXES:
        if stripped.startswith(prefix):
            remaining = stripped[len(prefix):].strip()
            # 边界检查："什么" 后接 "时候" 不是疑问前缀，而是时间状语
            if prefix == "什么" and remaining.startswith("时候"):
                continue
            stripped = remaining
            break
    return stripped


def translate_query_terms(query: str) -> str:
    """
    使用内置小字典，把中文查询中的常见关键词翻译为英文。
    保留未命中词的原样，返回英文查询变体。
    """
    if not query:
        return ""
    terms = []
    # 简单按空格/中文标点分词，优先匹配字典中较长的词
    remaining = query
    while remaining:
        matched = False
        for cn, en in sorted(_ENGLISH_TRANSLATION_MAP.items(), key=lambda x: -len(x[0])):
            if remaining.startswith(cn):
                terms.append(en)
                remaining = remaining[len(cn):].lstrip(" \t，,。")
                matched = True
                break
        if not matched:
            # 未命中字典：至少跳过一个字符，避免正则匹配零个字符导致死循环
            m = re.match(r"[^\u4e00-\u9fff\w]+", remaining)
            if m:
                remaining = remaining[m.end():]
            else:
                remaining = remaining[1:]
    return " ".join(terms)


def generate_query_variants(query: str, search_concepts: list = None) -> list:
    """
    对中文疑问句生成多种查询变体，用于并行搜索和结果合并。
    返回唯一查询变体列表。
    """
    if not _is_chinese_natural_language(query):
        return [query]

    variants = [query]

    # 1. 去掉疑问词前缀
    no_question = _strip_question_prefix(query)
    if no_question and no_question != query:
        variants.append(no_question)

    # 2. 基于 concepts 的紧凑查询
    if search_concepts:
        variants.append(" ".join(search_concepts))
        variants.append(" ".join([f'"{c}"' for c in search_concepts if c]))

    # 3. 英文翻译变体
    english = translate_query_terms(query)
    if english and english != query:
        variants.append(english)
        variants.append(english + " how to")

    # 去重并保持顺序
    seen = set()
    unique = []
    for v in variants:
        if v and v not in seen:
            seen.add(v)
            unique.append(v)
    return unique


def _check_bing_result_quality(results: list) -> dict:
    """
    必应结果质量检测：如果结果标题全部只含疑问词或明显无关，标记 degraded。
    """
    if not results:
        return {"degraded": True, "reason": "no_results"}
    total = len(results)
    question_only = sum(1 for r in results if html_parser._is_question_only_title(r.get("title", "")))
    if question_only == total or total < 2:
        return {
            "degraded": True,
            "reason": "question_only_or_too_few",
            "question_only_count": question_only,
            "total": total,
        }
    return {"degraded": False, "reason": "ok", "question_only_count": question_only, "total": total}


# ── /查询改写与翻译辅助 ─────────────────────────────────────────────


def _fetch_web_engine_once(engine_name: str, query: str, use_cache: bool = True) -> dict:
    """Internal helper to perform a single fetch for a query variant."""
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
        needs_cookies = engine_name in ("bing_cn", "bing_int")
        if needs_cookies:
            _network.warmup_session(
                "https://cn.bing.com",
                headers={"User-Agent": USER_AGENT},
                timeout=config["timeout"],
            )
        # DuckDuckGo HTML 端点建议 POST 请求，带完整反爬头
        if engine_name == "duckduckgo":
            headers["DNT"] = "1"
            headers["Referer"] = "https://html.duckduckgo.com/"
            headers["Origin"] = "https://html.duckduckgo.com"
            headers["Accept-Language"] = "en-US,en;q=0.9"
            post_url = config.get("post_url", "https://html.duckduckgo.com/html")
            status, resp_headers, body = _network.fetch_post_with_retry(
                post_url,
                data={"q": query, "kl": "us-en"},
                headers=headers,
                timeout=config["timeout"],
                use_cache=use_cache,
                cache_ttl_seconds=_RUNTIME_CONFIG.get("cache_ttl_seconds"),
            )
        else:
            req = urllib.request.Request(url, headers=headers)
            status, resp_headers, body = _network.fetch_with_retry(
                url,
                request=req,
                timeout=config["timeout"],
                use_cache=use_cache,
                cache_ttl_seconds=_RUNTIME_CONFIG.get("cache_ttl_seconds"),
                use_cookies=needs_cookies,
            )
        final_url = resp_headers.get("X-Original-Url", url)
        html = body.decode("utf-8", errors="ignore")
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
        status_text = "ok" if results else "empty"
        return {"results": results, "status": {"status": status_text, "reason": "parsed_results" if results else "no_results_parsed"}}
    except Exception as e:
        print(f"[{engine_name}] Error: {e}", file=sys.stderr)
        return {"results": [], "status": {"status": "failed", "reason": type(e).__name__, "message": str(e)[:200]}}


def search_web_engine_with_status(engine_name: str, query: str, search_concepts: list = None, use_cache: bool = True) -> dict:
    """搜索单个 Web 引擎，并返回轻量健康状态。"""
    # 对必应中文疑问句执行查询改写 + 并行多变体搜索
    if engine_name in ("bing_cn", "bing_int") and _is_chinese_natural_language(query):
        variants = generate_query_variants(query, search_concepts=search_concepts)
        all_results = []
        quality_report = None
        for variant in variants:
            payload = _fetch_web_engine_once(engine_name, variant, use_cache)
            if payload.get("status", {}).get("status") == "ok":
                all_results.extend(payload["results"])
            if engine_name in ("bing_cn", "bing_int") and quality_report is None:
                quality_report = _check_bing_result_quality(payload["results"])
        # 如果质量降级或空结果，尝试中英文混合兜底：提取英文/拼音关键词再搜索
        if (quality_report and quality_report.get("degraded") or not all_results) and engine_name == "bing_cn":
            fallback_queries = []
            if search_concepts:
                english_from_concepts = translate_query_terms(" ".join(search_concepts))
                if english_from_concepts:
                    fallback_queries.append(english_from_concepts)
            english_query = translate_query_terms(query)
            if english_query and english_query not in fallback_queries:
                fallback_queries.append(english_query)
            for fbq in fallback_queries:
                payload = _fetch_web_engine_once("bing_int", fbq, use_cache)
                if payload.get("status", {}).get("status") == "ok":
                    all_results.extend(payload["results"])
                payload = _fetch_web_engine_once("bing_cn", fbq, use_cache)
                if payload.get("status", {}).get("status") == "ok":
                    all_results.extend(payload["results"])
        # 去重：基于 URL
        seen = set()
        unique = []
        for r in all_results:
            norm = result_fusion.normalize_url(r.get("url", ""))
            if norm and norm not in seen:
                seen.add(norm)
                unique.append(r)
        status_text = "ok" if unique else "empty"
        if quality_report and quality_report.get("degraded"):
            status_text = "degraded"
        return {
            "results": unique,
            "status": {
                "status": status_text,
                "reason": "query_variants_merged" if unique else "no_results_from_variants",
                "variants": variants,
                "quality": quality_report,
            },
        }

    return _fetch_web_engine_once(engine_name, query, use_cache)


def search_web_engine(engine_name: str, query: str, search_concepts: list = None) -> list:
    """Backward-compatible wrapper that returns only result rows."""
    return search_web_engine_with_status(engine_name, query, search_concepts=search_concepts)["results"]


# ── DuckDuckGo 降级 ──────────────────────────────────────────────


def _duckduckgo_fallback_search(query: str, search_concepts: list = None, use_cache: bool = True) -> dict:
    """当 DuckDuckGo 被 block/失败/空结果时，尝试必应国际版，再尝试必应中国。"""
    fallback_engines = []
    if "bing_int" in WEB_ENGINES:
        fallback_engines.append("bing_int")
    if "bing_cn" in WEB_ENGINES and "bing_cn" not in fallback_engines:
        fallback_engines.append("bing_cn")

    for fb_engine in fallback_engines:
        print(f"[duckduckgo] DuckDuckGo blocked/empty, falling back to {fb_engine}", file=sys.stderr)
        if fb_engine in ("bing_cn", "bing_int") and _is_chinese_natural_language(query):
            payload = search_web_engine_with_status(fb_engine, query, search_concepts=search_concepts, use_cache=use_cache)
        else:
            payload = _fetch_web_engine_once(fb_engine, query, use_cache)
        if payload.get("results"):
            return {**payload, "status": {"status": "ok", "reason": f"duckduckgo_fallback_to_{fb_engine}"}}
    return {"results": [], "status": {"status": "skipped", "reason": "no_fallback_engine"}}


# ── /DuckDuckGo 降级 ─────────────────────────────────────────────


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
    """使用 argparse 解析命令行参数，保持与旧版 CLI 的兼容性。"""
    parser = argparse.ArgumentParser(
        prog="search_engine.py",
        description="Verified Search Pro · 可信研究助理",
        usage=usage(),
        add_help=True,
    )
    parser.add_argument("query", nargs="?", default="", help="搜索查询")
    parser.add_argument(
        "--mode",
        choices=["auto", "fact", "perspective", "research"],
        default="auto",
        help="研究模式",
    )
    parser.add_argument(
        "--budget",
        choices=["auto", "lite", "standard", "deep", "minimal", "balanced", "comprehensive"],
        default="auto",
        help="预算/证据数量",
    )
    parser.add_argument(
        "--checkpoint",
        choices=["auto", "batch", "interactive"],
        default="auto",
        help="检查点模式",
    )
    parser.add_argument("--input-results", default="", help="宿主搜索输入 JSON 路径")
    parser.add_argument("--engines", default="tavily,tencent_wsa,baidu_api,duckduckgo,bing_cn,sogou", help="逗号分隔的引擎列表")
    parser.add_argument("--search-concepts", default="", help="逗号分隔的搜索概念（由 Agent 层 LLM 提取）")
    parser.add_argument("--verify", action="store_true", help="启用反向验证")
    parser.add_argument("--fetch-content", action="store_true", help="抓取微信文章内容")
    parser.add_argument(
        "--output",
        choices=["json", "md", "claims-json", "claim-json", "evidence-pack", "evidence-json"],
        default="json",
        help="输出格式",
    )
    parser.add_argument("--doctor", "--check-env", action="store_true", help="环境自检")
    parser.add_argument("--no-cache", action="store_true", help="禁用请求缓存")
    parser.add_argument("--version", "-v", action="version", version=f"%(prog)s {__version__}")

    parsed = parser.parse_args(args)

    engines = normalize_engines(parsed.engines.split(","))
    search_concepts = [c.strip() for c in parsed.search_concepts.split(",") if c.strip()] or None
    return {
        "query": parsed.query.strip(),
        "budget": normalize_budget(parsed.budget),
        "engines": engines,
        "search_concepts": search_concepts,
        "mode": parsed.mode,
        "checkpoint": parsed.checkpoint,
        "input_results": parsed.input_results,
        "verify": parsed.verify,
        "fetch_content": parsed.fetch_content,
        "output": parsed.output,
        "doctor": parsed.doctor,
        "no_cache": parsed.no_cache,
    }


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
    parsed = parse_args(args)
    if parsed["doctor"]:
        print(json.dumps(check_environment(), indent=2, ensure_ascii=False))
        return
    if not parsed["query"]:
        print(usage())
        sys.exit(1)

    query = parsed["query"]
    budget_requested = parsed["budget"]
    engines = parsed["engines"]
    search_concepts = parsed.get("search_concepts")
    mode = parsed["mode"]
    checkpoint = parsed["checkpoint"]
    verify = parsed["verify"]
    fetch_content = parsed["fetch_content"]
    output_format = parsed["output"]
    use_cache = not parsed["no_cache"]
    budget = recommend_budget(query, mode) if budget_requested == "auto" else budget_requested

    # 中文自然语言缺少 concepts 时发出警告
    if _is_chinese_natural_language(query) and not search_concepts:
        print(
            "[Warning] 未使用 --search-concepts，建议由 Agent 提取核心关键词后再调用 VSP。",
            file=sys.stderr,
        )

    print(f"[Search] Query: {query}", file=sys.stderr)
    print(f"[Search] Concepts: {search_concepts}", file=sys.stderr)
    print(f"[Search] Engines: {engines}", file=sys.stderr)
    print(f"[Search] Budget: {budget} (requested: {budget_requested})", file=sys.stderr)
    print(f"[Search] Mode: {mode}", file=sys.stderr)
    print(f"[Search] Checkpoint: {checkpoint}", file=sys.stderr)

    # 读取宿主 agent 已经搜索到的结果；不调用 Kimi/OpenClaw 等宿主运行时。
    all_results = []
    engine_status = {}
    if parsed["input_results"]:
        try:
            host_results = load_input_results(parsed["input_results"])
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
            elif e == "tencent_wsa":
                wsa_cfg = _RUNTIME_CONFIG.get("tencent_wsa", {})
                if not wsa_cfg.get("enabled", True):
                    engine_status["tencent_wsa"] = {"status": "skipped", "reason": "config_disabled"}
                    continue
                if not wsa_adapter.is_available():
                    engine_status["tencent_wsa"] = {
                        "status": "skipped",
                        "reason": "api_key_missing",
                        "requires": ["TENCENTCLOUD_SECRET_ID", "TENCENTCLOUD_SECRET_KEY"],
                    }
                    continue
                max_results = BUDGET_RESULT_LIMITS.get(budget, 10)
                futures[executor.submit(
                    wsa_adapter.search_with_status,
                    query,
                    max_results=max_results,
                    timeout=wsa_cfg.get("timeout", 15),
                )] = ("tencent_wsa", "api_status")
            elif e == "baidu_api":
                baidu_cfg = _RUNTIME_CONFIG.get("baidu_api", {})
                if not baidu_cfg.get("enabled", True):
                    engine_status["baidu_api"] = {"status": "skipped", "reason": "config_disabled"}
                    continue
                if not baidu_api_adapter.is_available():
                    engine_status["baidu_api"] = {
                        "status": "skipped",
                        "reason": "api_key_missing",
                        "requires": ["BAIDU_API_KEY"],
                    }
                    continue
                max_results = BUDGET_RESULT_LIMITS.get(budget, 10)
                futures[executor.submit(
                    baidu_api_adapter.search_with_status,
                    query,
                    max_results=max_results,
                    timeout=baidu_cfg.get("timeout", 15),
                )] = ("baidu_api", "api_status")
            elif e in WEB_ENGINES:
                futures[executor.submit(search_web_engine_with_status, e, query, search_concepts, use_cache)] = (e, "web")
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
                if engine_type in ("web", "api_status"):
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

    # DuckDuckGo 被 block/失败/空结果时自动降级
    ddgo_status = engine_status.get("duckduckgo", {}).get("status")
    if ddgo_status in ("blocked", "failed", "empty"):
        fallback = _duckduckgo_fallback_search(query, search_concepts=search_concepts, use_cache=use_cache)
        if fallback.get("results"):
            all_results.extend(fallback["results"])
            engine_status["duckduckgo"]["fallback"] = {
                "engine": fallback["status"].get("reason", "bing").replace("duckduckgo_fallback_to_", ""),
                "count": len(fallback["results"]),
                "status": fallback["status"]["status"],
            }

    # 生成 tips 并执行一次性 Tavily 提醒
    tips = _generate_tips(engine_status)
    if tips:
        _tavily_one_time_reminder()

    # 融合
    fused = result_fusion.fuse_results(all_results, budget, query=query, search_concepts=search_concepts)
    print(f"[Fuse] {len(fused)} unique results", file=sys.stderr)

    # 交叉验证
    needs_verification = verify or output_format in STRUCTURED_OUTPUTS or output_format == "md"
    if needs_verification:
        fused = cross_verify.cross_verify_all(query, fused, search_concepts)
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
    if tips:
        output["tips"] = tips

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
            "tips": tips,
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
            "tips": tips,
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
            "tips": tips,
        }, mode=mode, budget=budget)
        print(render_markdown_report(package))
    else:
        print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
