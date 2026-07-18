#!/usr/bin/env python3
"""
Verified Search Pro · 网页日期启发式提取
职责：从 title+snippet 文本与 URL 中提取发布日期，输出 ISO 'YYYY-MM-DD'（失败返回空串）。
纯 Python 标准库，零外部依赖；只做 snippet/URL 启发式，不抓全文。

覆盖模式：
1. 显式日期文本：2026年1月12日 / 2026-01-12 / 2026/01/12 / 01/12/2026（英文序）
2. 相对日期：N天前 / N小时前 / N周前 / N个月前 / 昨天[ HH:MM]（以基准时间换算）
3. URL 日期路径：/2026/01/12/、/2026-01-12/、/20260112/
4. 合理性强校验：拒绝未来日期（容忍 +2 天时钟误差）与早于 2005 年的日期
   （网页内容日期早于 2005 多为误判）
"""

import calendar
import datetime
import re

MIN_YEAR = 2005
FUTURE_TOLERANCE_DAYS = 2

# ── 显式日期模式（按优先级排列，先命中先采用）──────────────────
# 注：月/日交替分支必须长分支在前（1[0-2] 先于 0?[1-9]），
# 否则 "12" 会被短分支抢先匹配为 "1"（正则交替不保证最长匹配）。
_EXPLICIT_PATTERNS = (
    # 2026年1月12日（"日"可省略，如"2026年1月12"）
    (re.compile(r"(20\d{2})\s*年\s*(1[0-2]|0?[1-9])\s*月\s*([12]\d|3[01]|0?[1-9])\s*日?"), "ymd"),
    # 2026-01-12 / 2026/01/12 / 2026.01.12
    (re.compile(r"(20\d{2})[-/.](1[0-2]|0?[1-9])[-/.]([12]\d|3[01]|0?[1-9])"), "ymd"),
    # 01/12/2026（英文序 月/日/年，年份在后才匹配，避免与 YYYY/MM/DD 混淆）
    (re.compile(r"\b(1[0-2]|0?[1-9])/([12]\d|3[01]|0?[1-9])/(20\d{2})\b"), "mdy"),
)

# ── 相对日期模式 ─────────────────────────────────────────────
_YESTERDAY_RE = re.compile(r"昨天(?:\s*\d{1,2}:\d{2})?")
_DAYS_AGO_RE = re.compile(r"(\d{1,4})\s*天前")
_WEEKS_AGO_RE = re.compile(r"(\d{1,3})\s*(?:周|星期)前")
_MONTHS_AGO_RE = re.compile(r"(\d{1,2})\s*个?月前")
_HOURS_AGO_RE = re.compile(r"(\d{1,3})\s*小时前")

# ── URL 日期路径模式 ─────────────────────────────────────────
_URL_PATTERNS = (
    re.compile(r"/(20\d{2})/(0[1-9]|1[0-2])/([12]\d|3[01]|0[1-9])(?=[/?.#]|$)"),  # /2026/01/12/
    re.compile(r"/(20\d{2})-(0[1-9]|1[0-2])-([12]\d|3[01]|0[1-9])(?=[/?.#]|$)"),  # /2026-01-12/
    re.compile(r"/(20\d{2})(0[1-9]|1[0-2])([12]\d|3[01]|0[1-9])(?=[/?.#]|$)"),    # /20260112/
)


def _now(now: datetime.datetime = None) -> datetime.datetime:
    return now or datetime.datetime.now()


def _valid_date(year: int, month: int, day: int, now: datetime.datetime) -> str:
    """构造并校验日期：非法、早于 2005、或超过 +2 天未来容忍均拒绝；合法返回 ISO 串。"""
    try:
        d = datetime.date(year, month, day)
    except ValueError:
        return ""
    if d.year < MIN_YEAR:
        return ""
    if (d - now.date()).days > FUTURE_TOLERANCE_DAYS:
        return ""
    return d.isoformat()


def _months_ago(now: datetime.datetime, months: int) -> datetime.date:
    """N 个月前的日期（按日历月回退，日序 clamp 到目标月最后一天）。"""
    year, month = now.year, now.month - months
    while month <= 0:
        month += 12
        year -= 1
    day = min(now.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


def extract_from_text(text: str, now: datetime.datetime = None) -> str:
    """从文本（title+snippet）提取发布日期；显式日期优先于相对日期，失败返回空串。"""
    text = (text or "").strip()
    if not text:
        return ""
    now = _now(now)

    for pattern, order in _EXPLICIT_PATTERNS:
        match = pattern.search(text)
        if match:
            if order == "ymd":
                year, month, day = (int(g) for g in match.groups())
            else:  # mdy 英文序
                month, day, year = (int(g) for g in match.groups())
            result = _valid_date(year, month, day, now)
            if result:
                return result
            # 命中但不合法（未来/古早/非法日期）→ 继续尝试后续模式，不直接放弃

    # 相对日期：昨天 → N天前 → N周前 → N个月前 → N小时前
    if _YESTERDAY_RE.search(text):
        return (now.date() - datetime.timedelta(days=1)).isoformat()
    match = _DAYS_AGO_RE.search(text)
    if match:
        return (now.date() - datetime.timedelta(days=int(match.group(1)))).isoformat()
    match = _WEEKS_AGO_RE.search(text)
    if match:
        return (now.date() - datetime.timedelta(weeks=int(match.group(1)))).isoformat()
    match = _MONTHS_AGO_RE.search(text)
    if match:
        return _months_ago(now, int(match.group(1))).isoformat()
    match = _HOURS_AGO_RE.search(text)
    if match:
        return (now - datetime.timedelta(hours=int(match.group(1)))).date().isoformat()
    return ""


def extract_from_url(url: str, now: datetime.datetime = None) -> str:
    """从 URL 日期路径提取发布日期；失败返回空串。"""
    url = (url or "").strip()
    if not url:
        return ""
    now = _now(now)
    for pattern in _URL_PATTERNS:
        match = pattern.search(url)
        if match:
            year, month, day = (int(g) for g in match.groups())
            result = _valid_date(year, month, day, now)
            if result:
                return result
    return ""


def extract_date(
    title: str = "",
    snippet: str = "",
    url: str = "",
    now: datetime.datetime = None,
) -> str:
    """
    综合入口：title+snippet 文本优先（显式 > 相对），其次 URL 日期路径。
    全部失败返回空串。now 可注入以便测试与按 accessed_at 基准换算。
    """
    now = _now(now)
    return (
        extract_from_text(f"{title or ''} {snippet or ''}", now=now)
        or extract_from_url(url, now=now)
    )


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print('Usage: python3 date_extract.py "title text" ["snippet"] ["url"]')
        sys.exit(1)
    title = sys.argv[1]
    snippet = sys.argv[2] if len(sys.argv) > 2 else ""
    url = sys.argv[3] if len(sys.argv) > 3 else ""
    print(json.dumps({"published_at": extract_date(title, snippet, url)}, ensure_ascii=False))
