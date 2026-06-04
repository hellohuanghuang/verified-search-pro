#!/usr/bin/env python3
"""
Verified Search Pro · claim-centric trust model
职责：将搜索结果转换为可审计的 claim / evidence 结构。
纯 Python 标准库，零外部依赖。
"""

import datetime
import re
import urllib.parse


SCHEMA_VERSION = "v2-alpha.claim-package"

AUTHORITATIVE_DOMAINS = {
    "gov.cn",
    "reuters.com",
    "bloomberg.com",
    "ft.com",
    "nature.com",
    "science.org",
    "ieee.org",
}

KNOWN_MEDIA_DOMAINS = {
    "nytimes.com",
    "wsj.com",
    "economist.com",
    "techcrunch.com",
    "36kr.com",
    "pingwest.com",
}

UGC_DOMAINS = {
    "zhihu.com",
    "weixin.qq.com",
    "baike.baidu.com",
    "wikipedia.org",
    "stackoverflow.com",
}

HIGH_RISK_DOMAINS = {
    "tieba.baidu.com",
    "douban.com",
}


def utc_now_iso() -> str:
    """Return a stable UTC timestamp for package generation."""
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def extract_domain(url: str) -> str:
    """Extract a lowercase registrable-ish host from a URL."""
    if not url:
        return ""
    candidate = url.strip()
    if not re.match(r"^[a-z][a-z0-9+.-]*://", candidate, re.IGNORECASE):
        candidate = "//" + candidate
    parsed = urllib.parse.urlsplit(candidate)
    domain = parsed.netloc.lower()
    return re.sub(r"^www\.", "", domain)


def _domain_matches(domain: str, patterns: set) -> bool:
    return any(domain == pattern or domain.endswith("." + pattern) for pattern in patterns)


def classify_source_reliability(result: dict) -> dict:
    """Classify source reliability separately from information credibility."""
    url = result.get("url", "")
    domain = extract_domain(url)
    domain_score = result.get("domain_score", 0.5)

    if not domain:
        return {
            "grade": "unknown",
            "label": "missing source",
            "score": 0.0,
            "reason": "No URL was available for source assessment.",
        }
    if _domain_matches(domain, AUTHORITATIVE_DOMAINS) or domain.endswith(".gov") or domain.endswith(".gov.cn"):
        return {
            "grade": "A",
            "label": "authoritative source",
            "score": max(domain_score, 0.9),
            "reason": "Domain matches official, academic, or high-authority publisher patterns.",
        }
    if _domain_matches(domain, KNOWN_MEDIA_DOMAINS):
        return {
            "grade": "B",
            "label": "recognized publisher",
            "score": max(domain_score, 0.75),
            "reason": "Domain is a known media or specialist publisher.",
        }
    if _domain_matches(domain, UGC_DOMAINS):
        return {
            "grade": "C",
            "label": "community or secondary source",
            "score": min(max(domain_score, 0.45), 0.7),
            "reason": "Domain is useful for leads or context but requires corroboration.",
        }
    if _domain_matches(domain, HIGH_RISK_DOMAINS):
        return {
            "grade": "D",
            "label": "high-risk source",
            "score": min(domain_score, 0.4),
            "reason": "Domain is prone to anonymous, promotional, or weakly attributed material.",
        }
    return {
        "grade": "unknown",
        "label": "unclassified source",
        "score": domain_score,
        "reason": "Domain is not in the current reliability map.",
    }


def extract_publication_date(result: dict) -> str:
    """Extract a simple publication date if it appears in known fields."""
    candidates = [
        str(result.get("published_at", "")),
        str(result.get("date", "")),
        result.get("title", ""),
        result.get("content", ""),
    ]
    text = " ".join(candidates)
    patterns = [
        r"\b(20\d{2})[-/.](0?[1-9]|1[0-2])[-/.](0?[1-9]|[12]\d|3[01])\b",
        r"\b(20\d{2})年(0?[1-9]|1[0-2])月(0?[1-9]|[12]\d|3[01])日\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            year, month, day = (int(part) for part in match.groups())
            try:
                return datetime.date(year, month, day).isoformat()
            except ValueError:
                continue
    return ""


def classify_freshness(query: str, publication_date: str, generated_at: str) -> dict:
    """Classify freshness with a small query-sensitive window."""
    lowered = query.lower()
    freshness_sensitive = any(
        token in lowered
        for token in ("最新", "today", "yesterday", "release", "政策", "融资", "动态", "更新", "latest")
    )
    if not publication_date:
        return {
            "status": "unknown",
            "window_days": 90 if freshness_sensitive else 365,
            "reason": "No publication date was detected.",
        }

    generated_date = datetime.datetime.fromisoformat(generated_at).date()
    published = datetime.date.fromisoformat(publication_date)
    age_days = (generated_date - published).days
    window_days = 90 if freshness_sensitive else 365
    status = "current" if age_days <= window_days else "stale"
    return {
        "status": status,
        "age_days": age_days,
        "window_days": window_days,
        "reason": f"Publication date is {age_days} days from package generation.",
    }


def classify_information_credibility(result: dict, source_reliability: dict, freshness: dict) -> dict:
    """Admiralty-style information credibility, separate from source reliability."""
    verification_score = result.get("verification_score")
    source_count = len(result.get("sources", []))
    verified = bool(result.get("verified"))
    reliability_grade = source_reliability.get("grade", "unknown")
    freshness_status = freshness.get("status")

    if verification_score is None:
        return {
            "grade": "6",
            "label": "cannot judge",
            "score": 0.0,
            "reason": "No verification score is available.",
        }
    if verified and source_count >= 2 and reliability_grade in {"A", "B"} and freshness_status != "stale":
        return {
            "grade": "1",
            "label": "confirmed by other sources",
            "score": min(1.0, verification_score),
            "reason": "Relevant result with multiple sources and reliable publisher signals.",
        }
    if verified and verification_score >= 0.6 and reliability_grade in {"A", "B"}:
        return {
            "grade": "2",
            "label": "probably true",
            "score": verification_score,
            "reason": "Relevant result from a source with usable reliability signals.",
        }
    if verified and verification_score >= 0.6 and reliability_grade == "C" and source_count >= 2:
        return {
            "grade": "2",
            "label": "probably true",
            "score": verification_score,
            "reason": "Community or secondary source is supported by multiple source paths.",
        }
    if verified and verification_score >= 0.4:
        return {
            "grade": "3",
            "label": "possibly true",
            "score": verification_score,
            "reason": "Result is relevant but needs stronger corroboration.",
        }
    if verification_score < 0.4:
        return {
            "grade": "4",
            "label": "doubtful",
            "score": verification_score,
            "reason": "Key query terms are weakly represented in the result.",
        }
    return {
        "grade": "6",
        "label": "cannot judge",
        "score": verification_score,
        "reason": "Insufficient evidence to classify credibility.",
    }


def detect_claim_type(query: str) -> str:
    """Infer a coarse claim type from the query."""
    lowered = query.lower()
    if any(token in query for token in ("政策", "法规", "监管")):
        return "policy"
    if any(token in query for token in ("融资", "市场", "赛道", "行业", "收入")):
        return "market"
    if any(token in lowered for token in ("api", "model", "github", "paper", "benchmark", "vla", "gpt")):
        return "technical"
    if any(token in query for token in ("创始人", "履历", "背景", "机构", "公司")):
        return "profile"
    return "fact"


def build_evidence_record(result: dict, index: int, query: str, generated_at: str) -> dict:
    """Build one evidence record from a fused result."""
    source_reliability = classify_source_reliability(result)
    publication_date = extract_publication_date(result)
    freshness = classify_freshness(query, publication_date, generated_at)
    credibility = classify_information_credibility(result, source_reliability, freshness)
    return {
        "evidence_id": f"ev-{index}",
        "url": result.get("url", ""),
        "title": result.get("title", ""),
        "snippet": result.get("content", ""),
        "source_engines": result.get("sources", [result.get("engine", "")]),
        "domain": extract_domain(result.get("url", "")),
        "publication_date": publication_date or None,
        "accessed_at": generated_at,
        "source_reliability": source_reliability,
        "information_credibility": credibility,
        "freshness": freshness,
        "verification": {
            "verified": bool(result.get("verified")),
            "verification_score": result.get("verification_score"),
            "matched": result.get("matched"),
            "total_terms": result.get("total_terms"),
            "key_terms": result.get("key_terms", []),
        },
        "v1_confidence": result.get("confidence_level"),
        "fusion_score": result.get("fusion_score"),
    }


def summarize_limits(results: list, evidence: list) -> list:
    """Summarize limitations that must be visible to downstream agents."""
    limits = []
    if not results:
        limits.append("No evidence results were collected; confidence must remain E/insufficient.")
        return limits
    if not any(item["verification"]["verified"] for item in evidence):
        limits.append("No evidence item passed reverse verification.")
    if len(evidence) == 1:
        limits.append("Only one deduplicated evidence item is available; independent corroboration is missing.")
    if any(item["freshness"]["status"] == "unknown" for item in evidence):
        limits.append("At least one evidence item has no detected publication date.")
    if any(item["source_reliability"]["grade"] == "unknown" for item in evidence):
        limits.append("At least one source domain is not classified by the reliability map.")
    return limits


def summarize_claim_confidence(evidence: list, limits: list) -> str:
    """Produce package-level confidence from evidence records."""
    credible = [
        item
        for item in evidence
        if item["verification"]["verified"]
        and item["source_reliability"]["grade"] in {"A", "B"}
        and item["information_credibility"]["grade"] in {"1", "2"}
    ]
    verified = [item for item in evidence if item["verification"]["verified"]]
    if not evidence:
        return "E"
    if len(credible) >= 2:
        return "A"
    if len(credible) >= 1 or len(verified) >= 2:
        return "B"
    if len(verified) == 1:
        return "C"
    if limits:
        return "D"
    return "E"


def build_claim_package(query: str, results: list, metadata: dict = None, generated_at: str = None) -> dict:
    """Build the v2 alpha claim-centric package for downstream agents."""
    metadata = metadata or {}
    generated_at = generated_at or utc_now_iso()
    evidence = [
        build_evidence_record(result, index, query, generated_at)
        for index, result in enumerate(results, start=1)
    ]
    limits = summarize_limits(results, evidence)
    confidence = summarize_claim_confidence(evidence, limits)
    supporting_ids = [item["evidence_id"] for item in evidence if item["verification"]["verified"]]
    weak_ids = [item["evidence_id"] for item in evidence if not item["verification"]["verified"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "query": query,
        "search": {
            "budget": metadata.get("budget"),
            "engines": metadata.get("engines", []),
            "total_raw": metadata.get("total_raw", 0),
            "total_fused": len(results),
        },
        "claims": [
            {
                "claim_id": "claim-1",
                "claim": query,
                "claim_type": detect_claim_type(query),
                "confidence": confidence,
                "supporting_evidence": supporting_ids,
                "weak_or_unverified_evidence": weak_ids,
                "counter_evidence": [],
                "limits": limits,
            }
        ],
        "evidence": evidence,
        "limitations": limits,
    }


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 3:
        print("Usage: python3 trust_model.py <query> <results_json>")
        sys.exit(1)
    with open(sys.argv[2], "r", encoding="utf-8") as f:
        data = json.load(f)
    print(json.dumps(build_claim_package(sys.argv[1], data), indent=2, ensure_ascii=False))
