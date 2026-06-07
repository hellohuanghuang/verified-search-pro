#!/usr/bin/env python3
"""
Verified Search Pro · 结果融合与去重
职责：URL去重、内容指纹去重、相似度去重、域名评分、融合得分排序
纯 Python 标准库
"""

import re
import hashlib
import urllib.parse
from difflib import SequenceMatcher

# 域名权威性评分
DOMAIN_AUTHORITY = {
    "gov.cn": 0.95, "gov.com": 0.95,
    "reuters.com": 0.9, "bloomberg.com": 0.9, "ft.com": 0.9,
    "nytimes.com": 0.9, "wsj.com": 0.9, "economist.com": 0.9,
    "nature.com": 0.95, "science.org": 0.95, "ieee.org": 0.9, "arxiv.org": 0.85,
    "github.com": 0.8, "stackoverflow.com": 0.85,
    "36kr.com": 0.75, "pingwest.com": 0.75, "techcrunch.com": 0.8,
    "zhihu.com": 0.65, "weixin.qq.com": 0.65,
    "baike.baidu.com": 0.5, "wikipedia.org": 0.8,
}

def get_domain_score(url: str) -> float:
    """提取域名并评分"""
    if not url:
        return 0.5
    domain = re.sub(r'^https?://', '', url).lower()
    domain = re.sub(r'^www\.', '', domain)
    domain = domain.split('/')[0]
    for d, score in sorted(DOMAIN_AUTHORITY.items(), key=lambda x: -len(x[0])):
        if domain == d or domain.endswith("." + d):
            return score
    return 0.5

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


def fuse_results(results: list, budget: str = "standard") -> list:
    """
    融合结果：URL去重 → 相似度去重 → 域名评分 → 融合得分排序 → 预算截断
    """
    # 1. URL 去重
    seen_urls = set()
    unique = []
    for r in results:
        url = r.get("url", "")
        norm = normalize_url(url)
        if norm and norm not in seen_urls:
            seen_urls.add(norm)
            unique.append(r)
    
    # 2. 内容指纹去重（合并来源）
    fingerprints = {}
    deduped = []
    for r in unique:
        fp = content_fingerprint(r.get("title", ""), result_text(r))
        if fp in fingerprints:
            existing = fingerprints[fp]
            existing_sources = set(existing.get("sources", [existing.get("engine", "")]))
            existing_sources.add(r.get("engine", ""))
            existing["sources"] = sorted(s for s in existing_sources if s)
            # 保留域名评分更高的
            candidate_score = get_domain_score(r.get("url", ""))
            existing_score = existing.get("domain_score", get_domain_score(existing.get("url", "")))
            if candidate_score > existing_score:
                existing["domain_score"] = candidate_score
                existing["url"] = r["url"]
        else:
            r["sources"] = [r.get("engine", "")]
            r["domain_score"] = get_domain_score(r.get("url", ""))
            fingerprints[fp] = r
            deduped.append(r)
    
    # 3. 文本相似度去重（补充）
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
                is_duplicate = True
                break
        if not is_duplicate:
            final.append(r)
    
    # 4. 计算融合得分
    for r in final:
        base_score = r.get("score", 0)
        domain_score = r.get("domain_score", 0.5)
        source_bonus = min(len(r.get("sources", [])), 3) * 0.1
        r["fusion_score"] = base_score * 0.4 + domain_score * 0.4 + source_bonus + 0.1
    
    # 5. 按融合得分排序
    final.sort(key=lambda x: x["fusion_score"], reverse=True)
    
    # 6. 按预算截断
    budget_map = {"lite": 5, "standard": 10, "deep": 20}
    limit = budget_map.get(normalize_budget(budget), 10)
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
