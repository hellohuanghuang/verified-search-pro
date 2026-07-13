#!/usr/bin/env python3
"""
Verified Search Pro · 结果融合与去重
职责：URL去重、内容指纹去重、相似度去重、same-story 检测、域名评分、融合得分排序
纯 Python 标准库
"""

import hashlib
import re
import urllib.parse
from difflib import SequenceMatcher

import config as _config
import domain_registry  # noqa: E402


def get_domain_score(url: str) -> float:
    """通过 domain_registry 获取域名评分，保持向后兼容。"""
    return domain_registry.get_domain_score(url)


def extract_domain(url: str) -> str:
    """提取规范化域名（去掉协议、www、路径）。"""
    if not url:
        return ""
    candidate = url.strip()
    if not re.match(r"^[a-z][a-z0-9+.-]*://", candidate, re.IGNORECASE):
        candidate = "//" + candidate
    parsed = urllib.parse.urlsplit(candidate)
    domain = parsed.netloc.lower()
    return re.sub(r"^www\.", "", domain)


def normalize_url(url: str) -> str:
    """URL 归一化用于去重"""
    if not url:
        return ""
    candidate = url.strip()
    if not re.match(r"^[a-z][a-z0-9+.-]*://", candidate, re.IGNORECASE):
        candidate = "//" + candidate
    parsed = urllib.parse.urlsplit(candidate)
    domain = parsed.netloc.lower()
    domain = re.sub(r"^www\.", "", domain)
    path = parsed.path.rstrip("/")
    query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    filtered = [
        (k, v)
        for k, v in query_pairs
        if not (k.lower().startswith("utm_") or k.lower() in {"ref", "source", "from"})
    ]
    query = urllib.parse.urlencode(filtered, doseq=True)
    normalized = domain + path
    if query:
        normalized += "?" + query
    return normalized


def text_similarity(t1: str, t2: str) -> float:
    """计算文本相似度"""
    if not t1 or not t2:
        return 0.0
    return SequenceMatcher(None, t1.lower(), t2.lower()).ratio()


def result_text(result: dict) -> str:
    """Prefer full content when a host agent already provided it."""
    return result.get("full_content") or result.get("content", "")


def content_fingerprint(title: str, content: str) -> str:
    """生成内容指纹（15词，中文更精准）"""
    combined = (title + " " + content[:100]).lower()
    combined = re.sub(r'[^\w\s]', '', combined)
    words = combined.split()[:15]
    return hashlib.md5(" ".join(words).encode()).hexdigest()[:16]


def normalize_budget(budget: str) -> str:
    """Normalize legacy and 2.0 budget names to one canonical profile."""
    aliases = {
        "minimal": "lite",
        "balanced": "standard",
        "comprehensive": "deep",
        "lite": "lite",
        "standard": "standard",
        "deep": "deep",
    }
    return aliases.get((budget or "standard").lower(), "standard")


def _max_evidence_for_budget(budget: str) -> int:
    cfg = _config.load_config(apply_env=False)
    profiles = cfg.get("budget_profiles", {})
    return profiles.get(normalize_budget(budget), {}).get("max_evidence", 10)


def _detect_same_story(a: dict, b: dict) -> bool:
    """判断两篇不同域名的结果是否为同一稿件/同一条新闻的转载。"""
    url_a = a.get("url", "")
    url_b = b.get("url", "")
    if not url_a or not url_b:
        return False

    # 同一域名不标记 same_story，避免去重逻辑重复
    domain_a = extract_domain(url_a)
    domain_b = extract_domain(url_b)
    if domain_a == domain_b:
        return False

    title_sim = text_similarity(a.get("title", ""), b.get("title", ""))
    content_sim = text_similarity(result_text(a), result_text(b))
    return title_sim > 0.95 and content_sim > 0.9


def fuse_results(results: list, budget: str = "standard", detect_syndication: bool = True) -> list:
    """
    融合结果：URL去重 → 内容指纹去重 → 相似度去重 → same-story 检测 → 域名评分 → 融合得分排序 → 预算截断
    """
    # 1. URL 去重（合并来源）
    seen_urls = {}
    unique = []
    for r in results:
        url = r.get("url", "")
        norm = normalize_url(url)
        if not norm:
            continue
        if norm in seen_urls:
            existing = seen_urls[norm]
            sources = set(existing.get("sources", [existing.get("engine", "")]))
            sources.add(r.get("engine", ""))
            existing["sources"] = sorted(s for s in sources if s)
            continue
        r["sources"] = [r.get("engine", "")]
        seen_urls[norm] = r
        unique.append(r)

    # 2. 内容指纹去重（合并来源，检测 same-story）
    fingerprints = {}
    deduped = []
    for r in unique:
        fp = content_fingerprint(r.get("title", ""), result_text(r))
        if fp in fingerprints:
            existing = fingerprints[fp]
            existing_sources = set(existing.get("sources", []))
            existing_sources.update(r.get("sources", []))
            existing["sources"] = sorted(s for s in existing_sources if s)
            # 保留域名评分更高的
            candidate_score = get_domain_score(r.get("url", ""))
            existing_score = existing.get("domain_score", get_domain_score(existing.get("url", "")))
            if candidate_score > existing_score:
                existing["domain_score"] = candidate_score
                existing["url"] = r["url"]
            # 跨域名高度相似的转载检测
            if detect_syndication and _detect_same_story(r, existing):
                existing.setdefault("same_story_group", True)
                existing.setdefault("same_story_sources", [])
                existing["same_story_sources"].append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "domain": extract_domain(r.get("url", "")),
                })
                primary = existing if existing["domain_score"] >= candidate_score else r
                existing["primary_source"] = extract_domain(primary.get("url", ""))
        else:
            r["domain_score"] = get_domain_score(r.get("url", ""))
            fingerprints[fp] = r
            deduped.append(r)

    # 3. 文本相似度去重 + same-story 检测
    final = []
    for r in deduped:
        is_duplicate = False
        for existing in final:
            sim_title = text_similarity(r.get("title", ""), existing.get("title", ""))
            sim_content = text_similarity(result_text(r), result_text(existing))
            if sim_title > 0.9 or sim_content > 0.85:
                # 合并来源
                existing_sources = set(existing.get("sources", []))
                existing_sources.update(r.get("sources", []))
                existing["sources"] = sorted(s for s in existing_sources if s)

                # 标记 same_story
                if detect_syndication and _detect_same_story(r, existing):
                    existing.setdefault("same_story_group", True)
                    existing.setdefault("same_story_sources", [])
                    existing["same_story_sources"].append({
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "domain": urllib.parse.urlparse(r.get("url", "")).netloc.lower().lstrip("www."),
                    })
                    # primary_source 指向域名评分更高的
                    primary = existing if existing["domain_score"] >= get_domain_score(r.get("url", "")) else r
                    existing["primary_source"] = urllib.parse.urlparse(primary.get("url", "")).netloc.lower().lstrip("www.")

                is_duplicate = True
                break
        if not is_duplicate:
            final.append(r)

    # 4. 计算融合得分
    for r in final:
        base_score = r.get("score", 0)
        domain_score = r.get("domain_score", 0.5)
        raw_sources = r.get("sources", [])
        # same_story 组中的重复来源不应重复计分
        unique_sources = set(raw_sources)
        source_bonus = min(len(unique_sources), 3) * 0.1
        r["fusion_score"] = base_score * 0.4 + domain_score * 0.4 + source_bonus + 0.1

    # 5. 按融合得分排序
    final.sort(key=lambda x: x["fusion_score"], reverse=True)

    # 6. 按预算截断
    limit = _max_evidence_for_budget(budget)
    return final[:limit]


if __name__ == "__main__":
    import sys
    import json
    if len(sys.argv) < 2:
        print("Usage: python3 result_fusion.py <results_json> [--budget standard]")
        sys.exit(1)
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        data = json.load(f)
    budget = "standard"
    if "--budget" in sys.argv:
        idx = sys.argv.index("--budget")
        if idx + 1 < len(sys.argv):
            budget = sys.argv[idx + 1]
    fused = fuse_results(data, budget)
    print(json.dumps(fused, indent=2, ensure_ascii=False))
