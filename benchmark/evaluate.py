#!/usr/bin/env python3
"""
Verified Search Pro · Benchmark 评估器

读取 benchmark/results/summary.json 并对每个查询结果打分。
不依赖真实网络，只评估已生成的 evidence-pack。

用法：
    python3 benchmark/evaluate.py [--summary benchmark/results/summary.json]
"""

import argparse
import json
import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def confidence_value(confidence: str) -> int:
    """A=5, B=4, C=3, D=2, E=1"""
    return {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1}.get(confidence.upper(), 0)


def evaluate_result(result: dict) -> dict:
    """根据 expected 条件评估单个结果。"""
    expected = result.get("expected", {})
    if result.get("status") != "ok":
        return {
            "id": result.get("id"),
            "query": result.get("query"),
            "passed": False,
            "reason": f"run status: {result.get('status')}",
        }

    result_path = result.get("result_path", "")
    package = {}
    if result_path and os.path.exists(result_path):
        with open(result_path, "r", encoding="utf-8") as f:
            package = json.load(f)

    claim = package.get("claims", [{}])[0] if package.get("claims") else {}
    confidence = claim.get("confidence", "E")
    trusted = package.get("trusted_conclusions", [])
    perspective = package.get("perspective_map", {})
    temporal = package.get("temporal_evolution", [])
    limitations = package.get("limitations", [])
    evidence = package.get("evidence", [])
    search = package.get("search", {})

    checks = {}

    if "min_confidence" in expected:
        checks["min_confidence"] = confidence_value(confidence) >= confidence_value(expected["min_confidence"])

    if "must_have_trusted_conclusion" in expected:
        checks["must_have_trusted_conclusion"] = len(trusted) > 0

    if "max_evidence" in expected:
        checks["max_evidence"] = len(evidence) <= expected["max_evidence"]

    if "limitations_non_empty" in expected:
        checks["limitations_non_empty"] = len(limitations) > 0

    if "perspective_map_present" in expected:
        checks["perspective_map_present"] = perspective.get("status") == "present" and len(perspective.get("items", [])) > 0

    if "temporal_evolution_non_empty" in expected:
        checks["temporal_evolution_non_empty"] = len(temporal) > 0

    passed = all(checks.values()) if checks else True
    return {
        "id": result.get("id"),
        "query": result.get("query"),
        "passed": passed,
        "checks": checks,
        "confidence": confidence,
        "evidence_returned": len(evidence),
        "trusted_conclusions": len(trusted),
        "limitations": len(limitations),
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate VSP benchmark results")
    parser.add_argument(
        "--summary",
        default=os.path.join(ROOT, "benchmark", "results", "summary.json"),
        help="benchmark run summary file",
    )
    args = parser.parse_args()

    if not os.path.exists(args.summary):
        print(f"[Error] Summary not found: {args.summary}", file=sys.stderr)
        print("Run `python3 benchmark/run.py` first.", file=sys.stderr)
        sys.exit(1)

    with open(args.summary, "r", encoding="utf-8") as f:
        summary = json.load(f)

    evaluations = [evaluate_result(r) for r in summary.get("results", [])]
    passed = sum(1 for e in evaluations if e["passed"])
    total = len(evaluations)

    report = {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 2) if total else 0,
        "evaluations": evaluations,
    }

    print(json.dumps(report, indent=2, ensure_ascii=False))

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
