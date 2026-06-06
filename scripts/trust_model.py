#!/usr/bin/env python3
"""
Verified Search Pro · evidence-pack trust model
职责：将搜索结果转换为可审计的 claim / evidence 结构。
纯 Python 标准库，零外部依赖。
"""

import datetime
import re
import urllib.parse


SCHEMA_VERSION = "v2-alpha.evidence-pack"

BUDGET_PROFILES = {
    "lite": {
        "max_evidence": 5,
        "snippet_chars": 240,
        "max_context_tokens": 12000,
        "reserved_tokens": 64000,
    },
    "standard": {
        "max_evidence": 10,
        "snippet_chars": 480,
        "max_context_tokens": 32000,
        "reserved_tokens": 64000,
    },
    "deep": {
        "max_evidence": 20,
        "snippet_chars": 900,
        "max_context_tokens": 96000,
        "reserved_tokens": 64000,
    },
}

BUDGET_ALIASES = {
    "minimal": "lite",
    "balanced": "standard",
    "comprehensive": "deep",
    "lite": "lite",
    "standard": "standard",
    "deep": "deep",
}

SUPPORTED_MODES = {"auto", "fact", "perspective", "research"}

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


def normalize_budget(budget: str) -> str:
    """Normalize old and new budget names."""
    return BUDGET_ALIASES.get((budget or "standard").lower(), "standard")


def get_budget_profile(budget: str) -> dict:
    """Return the output profile that keeps agent handoff below the 256k red line."""
    canonical = normalize_budget(budget)
    profile = dict(BUDGET_PROFILES[canonical])
    profile["name"] = canonical
    profile["hard_red_line_tokens"] = 256000
    return profile


def truncate_text(text: str, limit: int) -> str:
    """Trim long snippets so evidence packs stay useful without flooding context."""
    value = text or ""
    if len(value) <= limit:
        return value
    if limit <= 3:
        return value[:limit]
    return value[: limit - 3].rstrip() + "..."


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


def detect_research_mode(query: str, requested_mode: str = "auto") -> str:
    """Choose the safest output mode for fact, viewpoint, or broad research tasks."""
    requested = (requested_mode or "auto").lower()
    if requested in SUPPORTED_MODES and requested != "auto":
        return requested

    lowered = query.lower()
    perspective_tokens = (
        "观点", "评价", "争议", "分歧", "矛盾", "批评", "支持", "反对", "误区",
        "看法", "舆论", "主观", "controversy", "debate", "opinion", "review",
        "criticism", "pros and cons",
    )
    research_tokens = (
        "调研", "研究", "分析", "追踪", "背景", "趋势", "路线", "国家公园",
        "文化公园", "policy research", "market research", "background check",
    )
    if any(token in query or token in lowered for token in perspective_tokens):
        return "perspective"
    if any(token in query or token in lowered for token in research_tokens):
        return "research"
    return "fact"


def build_evidence_record(
    result: dict,
    index: int,
    query: str,
    generated_at: str,
    snippet_chars: int = 480,
) -> dict:
    """Build one evidence record from a fused result."""
    source_reliability = classify_source_reliability(result)
    publication_date = extract_publication_date(result)
    freshness = classify_freshness(query, publication_date, generated_at)
    credibility = classify_information_credibility(result, source_reliability, freshness)
    return {
        "evidence_id": f"ev-{index}",
        "url": result.get("url", ""),
        "title": result.get("title", ""),
        "snippet": truncate_text(result.get("content", ""), snippet_chars),
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


def build_claim_record(query: str, evidence: list, limits: list, mode: str) -> dict:
    """Build the compatibility claim record used by claims-json consumers."""
    confidence = summarize_claim_confidence(evidence, limits)
    supporting_ids = [item["evidence_id"] for item in evidence if item["verification"]["verified"]]
    weak_ids = [item["evidence_id"] for item in evidence if not item["verification"]["verified"]]
    trusted_status = "trusted_candidate" if confidence in {"A", "B", "C"} else "insufficient_or_uncertain"
    return {
        "claim_id": "claim-1",
        "claim": query,
        "claim_type": detect_claim_type(query),
        "research_mode": mode,
        "confidence": confidence,
        "status": trusted_status,
        "supporting_evidence": supporting_ids,
        "weak_or_unverified_evidence": weak_ids,
        "counter_evidence": [],
        "limits": limits,
        "use_as": "candidate_conclusion_only_when_confidence_is_A_to_C",
    }


def build_perspective_map(evidence: list, mode: str) -> dict:
    """Represent non-final viewpoints as useful but unsafe-to-promote context."""
    items = []
    perspective_mode = mode in {"perspective", "research"}
    for item in evidence:
        source_grade = item["source_reliability"]["grade"]
        credibility_grade = item["information_credibility"]["grade"]
        is_contextual = perspective_mode or source_grade in {"C", "D", "unknown"} or credibility_grade in {"3", "4", "6"}
        if not is_contextual:
            continue
        items.append({
            "perspective_id": f"view-{len(items) + 1}",
            "summary": item["title"],
            "stance": "not_classified",
            "representative_evidence": [item["evidence_id"]],
            "source_reliability": source_grade,
            "information_credibility": credibility_grade,
            "use_as": "background_or_hypothesis_only",
            "must_not_be_used_as_fact": True,
        })
    return {
        "status": "present" if items else "not_detected",
        "items": items,
        "agreements": [],
        "disagreements": [],
        "limitations": [
            "Perspective items are representative context, not verified conclusions.",
            "Stance classification is conservative until stronger semantic grouping is implemented.",
        ] if items else [],
    }


def build_common_misconceptions(evidence: list) -> list:
    """Collect weak signals that are useful as noise examples but unsafe as facts."""
    items = []
    for item in evidence:
        source_grade = item["source_reliability"]["grade"]
        credibility_grade = item["information_credibility"]["grade"]
        verified = item["verification"]["verified"]
        if verified and source_grade not in {"D"} and credibility_grade not in {"4"}:
            continue
        reason = "Evidence did not pass reverse verification."
        if source_grade == "D":
            reason = "Source tier is high-risk and should be treated as noise unless corroborated."
        elif credibility_grade == "4":
            reason = "Information credibility is doubtful against the query terms."
        items.append({
            "misconception_id": f"mis-{len(items) + 1}",
            "label": "potential_noise_or_misconception",
            "summary": item["title"],
            "evidence": [item["evidence_id"]],
            "reason": reason,
            "use_as": "negative_example_or_noise_pattern",
            "must_not_be_used_as_fact": True,
        })
    return items


def build_controversies_uncertainties(evidence: list, limits: list, mode: str) -> dict:
    """Expose uncertainty instead of forcing a false single answer."""
    items = []
    for limit in limits:
        items.append({
            "uncertainty_id": f"unc-{len(items) + 1}",
            "summary": limit,
            "evidence": [],
            "use_as": "boundary_condition",
            "requires_human_or_follow_up_review": True,
        })
    if mode == "perspective" and evidence:
        weak_ids = [
            item["evidence_id"]
            for item in evidence
            if not item["verification"]["verified"] or item["information_credibility"]["grade"] in {"3", "4", "6"}
        ]
        if weak_ids:
            items.append({
                "uncertainty_id": f"unc-{len(items) + 1}",
                "summary": "Some retrieved material is useful for viewpoint mapping but not strong enough for factual conclusion.",
                "evidence": weak_ids,
                "use_as": "viewpoint_context_only",
                "requires_human_or_follow_up_review": True,
            })
    return {
        "status": "present" if items else "not_detected",
        "items": items,
        "rule": "Do not resolve controversy by averaging sources; keep uncertainty visible.",
    }


def build_temporal_evolution(evidence: list) -> list:
    """Turn publication dates and staleness into a visible timeline."""
    timeline = []
    for item in evidence:
        freshness_status = item["freshness"]["status"]
        if freshness_status == "stale":
            temporal_status = "historical_or_possibly_outdated"
            use_as = "trend_or_history_only"
        elif freshness_status == "current":
            temporal_status = "current_snapshot"
            use_as = "current_evidence_candidate"
        else:
            temporal_status = "undated_context"
            use_as = "context_only_until_date_is_verified"
        timeline.append({
            "evidence_id": item["evidence_id"],
            "title": item["title"],
            "publication_date": item["publication_date"],
            "freshness_status": freshness_status,
            "temporal_status": temporal_status,
            "use_as": use_as,
        })
    return timeline


def build_agent_handoff(mode: str, budget: str, profile: dict, claims: list, evidence: list) -> dict:
    """Give downstream agents explicit rules for safe context use."""
    trusted_count = sum(1 for claim in claims if claim["confidence"] in {"A", "B", "C"})
    return {
        "research_mode": mode,
        "budget": budget,
        "context_budget": profile,
        "safe_context_summary": {
            "trusted_claim_candidates": trusted_count,
            "evidence_records": len(evidence),
        },
        "recommended_use": [
            "Use A-C claims as candidate conclusions with citations.",
            "Use perspective_map as background and hypothesis generation only.",
            "Use common_misconceptions as negative examples or noise signatures only.",
            "Use temporal_evolution to distinguish current evidence from historical context.",
        ],
        "do_not_promote_to_fact": [
            "perspective_map",
            "common_misconceptions",
            "controversies_uncertainties",
            "stale temporal_evolution items",
        ],
    }


def build_claim_package(
    query: str,
    results: list,
    metadata: dict = None,
    generated_at: str = None,
    mode: str = "auto",
    budget: str = None,
) -> dict:
    """Build the v2 alpha evidence package for humans, agents, and audits."""
    metadata = metadata or {}
    generated_at = generated_at or utc_now_iso()
    budget = normalize_budget(budget or metadata.get("budget"))
    requested_mode = mode if mode != "auto" else metadata.get("mode", "auto")
    mode = detect_research_mode(query, requested_mode)
    profile = get_budget_profile(budget)
    selected_results = results[: profile["max_evidence"]]
    evidence = [
        build_evidence_record(result, index, query, generated_at, profile["snippet_chars"])
        for index, result in enumerate(selected_results, start=1)
    ]
    limits = summarize_limits(results, evidence)
    if len(results) > len(selected_results):
        limits.append(
            f"Evidence output was capped by the {budget} context budget: "
            f"{len(selected_results)} of {len(results)} fused results returned."
        )
    claim = build_claim_record(query, evidence, limits, mode)
    claims = [claim]
    trusted_conclusions = [claim] if claim["confidence"] in {"A", "B", "C"} else []
    return {
        "schema_version": SCHEMA_VERSION,
        "compatible_schema_versions": ["v2-alpha.claim-package"],
        "generated_at": generated_at,
        "query": query,
        "research_mode": mode,
        "search": {
            "budget": budget,
            "engines": metadata.get("engines", []),
            "total_raw": metadata.get("total_raw", 0),
            "total_fused": len(results),
            "evidence_returned": len(evidence),
        },
        "context_budget": profile,
        "claims": claims,
        "trusted_conclusions": trusted_conclusions,
        "perspective_map": build_perspective_map(evidence, mode),
        "common_misconceptions": build_common_misconceptions(evidence),
        "controversies_uncertainties": build_controversies_uncertainties(evidence, limits, mode),
        "temporal_evolution": build_temporal_evolution(evidence),
        "evidence": evidence,
        "limitations": limits,
        "agent_handoff": build_agent_handoff(mode, budget, profile, claims, evidence),
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
