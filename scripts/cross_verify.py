#!/usr/bin/env python3
"""
Verified Search Pro · 交叉验证与置信度定级
职责：提取关键实体、反向验证、多源一致性检查、置信度定级
纯 Python 标准库
"""

import re

# 最小停用词集合，只过滤单独出现的虚词，不破坏原句或专有名词
_STOP_WORDS = {
    "的", "了", "怎么", "如何", "为什么", "什么", "吗", "呢", "是", "在",
    "和", "或", "与", "有", "很", "非常", "一个", "这个", "那个", "可以",
    "应该", "需要", "能够", "已经", "没有", "不是", "不会", "不能",
}

# n-gram 中常见虚词单字，包含这些字符的 n-gram 通常是跨词噪声
# 用于 scoring_terms 截断前过滤，不影响 key_terms 的完整匹配能力
_STOP_CHARS = set("的了是在和或有很也都被把将让使到给对从向为以")

# 繁简映射表（常用单字对，约 200 个）
# 用于将繁体中文归一为简体中文，避免繁体源因字符不匹配导致验证失败
_TRADITIONAL_TO_SIMPLIFIED = {
    "國": "国", "學": "学", "術": "术", "醫": "医", "療": "疗", "藥": "药",
    "寵": "宠", "貓": "猫", "淚": "泪", "紅": "红", "腫": "肿", "發": "发",
    "細": "细", "質": "质", "遺": "遗", "傳": "传", "種": "种", "貴": "贵",
    "賓": "宾", "邊": "边", "薩": "萨", "營": "营", "養": "养", "飼": "饲",
    "糧": "粮", "餵": "喂", "潔": "洁", "齒": "齿", "驅": "驱", "蟲": "虫",
    "絕": "绝", "術": "术", "護": "护", "復": "复", "顧": "顾", "獸": "兽",
    "診": "诊", "師": "师", "執": "执", "專": "专", "業": "业", "認": "认",
    "證": "证", "評": "评", "價": "价", "費": "费", "標": "标", "準": "准",
    "務": "务", "態": "态", "環": "环", "設": "设", "備": "备", "進": "进",
    "薦": "荐", "預": "预", "約": "约", "掛": "挂", "號": "号", "間": "间",
    "門": "门", "觀": "观", "劑": "剂", "過": "过", "應": "应", "項": "项",
    "長": "长", "監": "监", "測": "测", "規": "规", "檢": "检", "聲": "声",
    "內": "内", "視": "视", "鏡": "镜", "組": "组", "織": "织", "斷": "断",
    "後": "后", "轉": "转", "風": "风", "險": "险", "級": "级", "惡": "恶",
    "瘤": "瘤", "療": "疗", "樂": "乐", "終": "终", "關": "关", "懷": "怀",
    "臨": "临", "殯": "殡", "紀": "纪", "險": "险", "賠": "赔", "範": "范",
    "圍": "围", "負": "负", "額": "额", "續": "续", "條": "条", "責": "责",
    "聲": "声", "準": "准", "審": "审", "時": "时", "帳": "帐", "糾": "纠",
    "紛": "纷", "處": "处", "訴": "诉",
}

def _normalize_traditional_chinese(text: str) -> str:
    """将繁体中文归一为简体中文，避免繁体源因字符不匹配导致验证失败。"""
    if not text:
        return text
    return "".join(_TRADITIONAL_TO_SIMPLIFIED.get(c, c) for c in text)

# 常见职位头衔，用于在英文专有名词提取前断开句子
# 避免 "OpenAI CEO Sam Altman" 被当作一个 term
_JOB_TITLE_RE = re.compile(
    r'\s+(?:CEO|CTO|CFO|COO|CIO|CMO|President|Vice\s+President|Senior|Junior|'
    r'Chief|Director|Manager|Founder|Co-Founder|Chairman|Officer|Head|Lead|'
    r'Principal|Staff|Engineer|Developer|Designer|Architect|Analyst|Consultant)\b'
)


def _generate_chinese_ngrams(text: str, n: int) -> list:
    """生成中文字符 n-gram，不破坏原句。"""
    chars = [c for c in text if "\u4e00" <= c <= "\u9fff"]
    return ["".join(chars[i:i + n]) for i in range(len(chars) - n + 1)]


def extract_entities(query: str, search_concepts: list = None) -> list:
    """
    从查询中提取关键实体（中文词、英文专有词、数字）。

    search_concepts 作为 Agent 层 LLM 传入的补充概念，追加到 n-gram 结果之后，
    而非替换原查询分析。

    中文处理：保留原句，同时生成 2-gram 作为辅助候选，只过滤单独出现的停用词。
    英文处理：保留专有词（如 "The Beatles"）。
    """
    key_terms = []

    # 保留原查询本身（去首尾空白），用于整句匹配专有名词/作品名
    raw_query = query.strip()
    if raw_query:
        key_terms.append(raw_query.lower())

    # 中文 2-4 gram 辅助候选
    for n in (2, 3, 4):
        for gram in _generate_chinese_ngrams(raw_query, n):
            if gram not in _STOP_WORDS:
                key_terms.append(gram.lower())

    # 英文专有词（保留 "The Beatles" 这类带冠词的专有词）
    # 先在职位词处断开，避免 "OpenAI CEO Sam Altman" 被当作一个 term
    for segment in _JOB_TITLE_RE.split(raw_query):
        for term in re.findall(
            r'[A-Z][a-zA-Z]+(?:\s+(?:[A-Z][a-zA-Z]+|the|a|an|of|in|on|at|for|and|&|\.\.\.))*',
            segment,
        ):
            cleaned = term.strip().lower()
            if cleaned:
                key_terms.append(cleaned)

    # 4 位年份
    years = re.findall(r'\d{4}', raw_query)
    key_terms.extend(years)

    # 追加 Agent 层传入的搜索概念，作为补充而非替换
    if search_concepts:
        for concept in search_concepts:
            if not concept:  # 跳过 None 和空字符串
                continue
            c = str(concept).strip().lower()
            if c and c not in key_terms:
                key_terms.append(c)

    # 去重并过滤过短项
    seen = set()
    result = []
    for term in key_terms:
        if term in seen or len(term) < 2:
            continue
        seen.add(term)
        result.append(term)
    return result


def verify_result(query: str, result: dict, search_concepts: list = None) -> dict:
    """对单个结果进行反向验证。"""
    # 繁简归一：避免繁体源因字符不匹配导致验证失败
    normalized_query = _normalize_traditional_chinese(query)
    key_terms = extract_entities(normalized_query, search_concepts)
    content = ((result.get("title") or "") + " " + (result.get("content") or "")).lower()
    content = _normalize_traditional_chinese(content)

    # 评分基准选择：
    # - 有 search_concepts 时：用 concepts 作为评分基准（LLM 提取的精确概念，噪声低）
    # - 无 search_concepts 时：用 n-gram 截断前 6 个作为评分基准（噪声大需截断）
    # matched_terms 仍在完整 key_terms 中匹配，保留原句/专有名词匹配能力。
    if search_concepts:
        scoring_terms = [str(c).strip().lower() for c in search_concepts if str(c).strip()]
    else:
        scoring_terms = [
            t for t in key_terms
            if 2 <= len(t) <= 8 and not any(c in _STOP_CHARS for c in t)
        ][:6]
    if not scoring_terms:
        scoring_terms = key_terms

    matched = [t for t in key_terms if t in content]
    score_matches = [t for t in scoring_terms if t in content]
    matches = len(score_matches)
    capped_terms = len(scoring_terms)
    score = matches / capped_terms if capped_terms else 0
    # 阈值：至少命中一个核心概念，或命中比例达到 40%
    threshold = max(1, capped_terms * 0.4)
    verified = matches >= threshold
    return {
        "verification_score": score,
        "verified": verified,
        "key_terms": key_terms,
        "matched": len(matched),
        "total_terms": len(key_terms),
        "matched_terms": matched,
    }


def check_consistency(results: list) -> dict:
    """检查多源一致性"""
    if len(results) < 2:
        return {"consistent": True, "notes": "单一来源，无法一致性检查"}
    
    # 简单一致性检查：看标题和内容中是否有共同的关键词
    all_titles = [(r.get("title") or "").lower() for r in results]
    all_contents = [(r.get("content") or "").lower() for r in results]
    
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


def cross_verify_all(query: str, results: list, search_concepts: list = None) -> list:
    """对所有结果进行交叉验证和置信度定级"""
    # 先验证每个结果
    for r in results:
        v = verify_result(query, r, search_concepts)
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
    concepts = sys.argv[3].split(",") if len(sys.argv) > 3 else None
    with open(sys.argv[2], "r", encoding="utf-8") as f:
        results = json.load(f)
    verified = cross_verify_all(query, results, concepts)
    print(json.dumps(verified, indent=2, ensure_ascii=False))
