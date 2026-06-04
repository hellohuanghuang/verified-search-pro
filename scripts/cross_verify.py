#!/usr/bin/env python3
"""
Verified Search Pro · 交叉验证与置信度定级
职责：提取关键实体、反向验证、多源一致性检查、置信度定级
纯 Python 标准库
"""

import re

def extract_entities(query: str) -> list:
    """从查询中提取关键实体（中文词、英文专有词、数字）"""
    entities = re.findall(r'[\u4e00-\u9fff]{2,}', query)  # 中文词
    entities += re.findall(r'[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*', query)  # 英文专有词
    entities += re.findall(r'\d{4}', query)  # 年份
    key_terms = [e.lower() for e in entities if len(e) >= 2]
    # 回退：如果实体太少，用空格分词
    if len(key_terms) < 2:
        key_terms = [w for w in query.lower().split() if len(w) > 3][:5]
    return key_terms

def verify_result(query: str, result: dict) -> dict:
    """对单个结果进行反向验证"""
    key_terms = extract_entities(query)
    content = (result.get("title", "") + " " + result.get("content", "")).lower()
    matches = sum(1 for t in key_terms if t in content)
    score = matches / len(key_terms) if key_terms else 0
    threshold = max(1, len(key_terms) * 0.4)
    verified = matches >= threshold
    return {
        "verification_score": score,
        "verified": verified,
        "key_terms": key_terms,
        "matched": matches,
        "total_terms": len(key_terms),
    }

def check_consistency(results: list) -> dict:
    """检查多源一致性"""
    if len(results) < 2:
        return {"consistent": True, "notes": "单一来源，无法一致性检查"}
    
    # 简单一致性检查：看标题和内容中是否有共同的关键词
    all_titles = [r.get("title", "").lower() for r in results]
    all_contents = [r.get("content", "").lower() for r in results]
    
    # 提取共同词（简单实现）
    common_words = set()
    for title in all_titles:
        words = set(re.findall(r'\b\w+\b', title))
        if not common_words:
            common_words = words
        else:
            common_words &= words
    
    consistency_score = len(common_words) / max(len(all_titles[0].split()), 1) if all_titles else 0
    
    return {
        "consistent": consistency_score > 0.1,
        "consistency_score": consistency_score,
        "common_words": list(common_words)[:10],
        "notes": "多源一致性检查完成",
    }

def grade_confidence(result: dict, consistency: dict) -> str:
    """定级置信度 A-E"""
    verification = result.get("verification_score", 0)
    sources = len(result.get("sources", []))
    domain_score = result.get("domain_score", 0.5)
    
    # A: 多源验证 + 高域名评分 + 高验证分
    if sources >= 2 and domain_score >= 0.8 and verification >= 0.7:
        return "A"
    # B: 单源权威或多源一般 + 中验证分
    if (sources >= 2 or domain_score >= 0.8) and verification >= 0.5:
        return "B"
    # C: 单源一般 + 验证通过
    if verification >= 0.4:
        return "C"
    # D: 验证分低或存在矛盾
    if verification < 0.4 or not consistency.get("consistent", True):
        return "D"
    # E: 明确问题
    return "E"

def cross_verify_all(query: str, results: list) -> list:
    """对所有结果进行交叉验证和置信度定级"""
    # 先验证每个结果
    for r in results:
        v = verify_result(query, r)
        r.update(v)
    
    # 一致性检查
    consistency = check_consistency(results)
    
    # 定级
    for r in results:
        r["confidence_level"] = grade_confidence(r, consistency)
    
    return results

if __name__ == "__main__":
    import sys
    import json
    if len(sys.argv) < 3:
        print("Usage: python3 cross_verify.py <query> <results_json>")
        sys.exit(1)
    query = sys.argv[1]
    with open(sys.argv[2], "r", encoding="utf-8") as f:
        results = json.load(f)
    verified = cross_verify_all(query, results)
    print(json.dumps(verified, indent=2, ensure_ascii=False))