#!/usr/bin/env python3
"""
Verified Search Pro · HTML 解析器
支持：百度、必应、搜狗、搜狗微信搜索
纯 Python 标准库，零外部依赖
"""

import re

def _strip_tags(text: str) -> str:
    """移除 HTML 标签并解码实体"""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ').replace('&quot;', '"').replace('&lt;', '<').replace('&gt;', '>')
    return text.strip()

def _normalize_url(url: str) -> str:
    """URL 归一化：处理百度加密 URL 等"""
    if not url:
        return ""
    import urllib.parse
    if url.startswith("/url?") or url.startswith("/link?"):
        m = re.search(r'[?&]url=([^\u0026]+)', url)
        if m:
            return urllib.parse.unquote(m.group(1))
    if url.startswith("/"):
        return ""
    return url

def parse_baidu(html_text: str) -> list:
    """解析百度搜索结果"""
    results = []
    patterns = [
        r'<div[^\u003e]*class="(?:result|c-container|content)[^"]*"[^\u003e]*\u003e(.*?)\u003c/div\u003e\s*(?=\u003cdiv[^\u003e]*class="(?:result|c-container|content)|\u003c/div\u003e\s*$)',
        r'<div[^\u003e]*class="(?:result|c-container)[^"]*"[^\u003e]*\u003e(.*?)\u003c/div\u003e',
    ]
    blocks = []
    for p in patterns:
        blocks = re.findall(p, html_text, re.DOTALL | re.IGNORECASE)
        if blocks:
            break
    for block in blocks[:8]:
        m = re.search(r'<h3[^\u003e]*\u003e\s*\u003ca[^\u003e]*href="([^"]*)"[^\u003e]*\u003e(.*?)\u003c/a\u003e\s*\u003c/h3\u003e', block, re.DOTALL | re.IGNORECASE)
        if not m:
            m = re.search(r'<a[^\u003e]*href="([^"]*)"[^\u003e]*\u003e(.*?)\u003c/a\u003e', block, re.DOTALL | re.IGNORECASE)
        if m:
            url = _normalize_url(m.group(1))
            title = _strip_tags(m.group(2))
            sm = re.search(r'<div[^\u003e]*class="(?:content|abstract|c-abstract)[^"]*"[^\u003e]*\u003e(.*?)\u003c/div\u003e', block, re.DOTALL | re.IGNORECASE)
            if not sm:
                sm = re.search(r'<span[^\u003e]*class="(?:content|abstract)[^"]*"[^\u003e]*\u003e(.*?)\u003c/span\u003e', block, re.DOTALL | re.IGNORECASE)
            snippet = _strip_tags(sm.group(1)) if sm else ""
            if title and url:
                results.append({"url": url, "title": title, "content": snippet})
    return results

def parse_bing(html_text: str) -> list:
    """解析必应搜索结果"""
    results = []
    blocks = re.findall(r'<li[^\u003e]*class="b_algo"[^\u003e]*\u003e(.*?)\u003c/li\u003e', html_text, re.DOTALL | re.IGNORECASE)
    for block in blocks[:8]:
        m = re.search(r'<h2[^\u003e]*\u003e\s*\u003ca[^\u003e]*href="([^"]*)"[^\u003e]*\u003e(.*?)\u003c/a\u003e\s*\u003c/h2\u003e', block, re.DOTALL | re.IGNORECASE)
        if not m:
            m = re.search(r'<a[^\u003e]*href="([^"]*)"[^\u003e]*\u003e(.*?)\u003c/a\u003e', block, re.DOTALL | re.IGNORECASE)
        if m:
            url = _normalize_url(m.group(1))
            title = _strip_tags(m.group(2))
            sm = re.search(r'<p[^\u003e]*\u003e(.*?)\u003c/p\u003e', block, re.DOTALL | re.IGNORECASE)
            snippet = _strip_tags(sm.group(1)) if sm else ""
            if title and url:
                results.append({"url": url, "title": title, "content": snippet})
    return results

def parse_sogou(html_text: str) -> list:
    """解析搜狗搜索结果"""
    results = []
    patterns = [
        r'<div[^\u003e]*class="(?:vr|rb|result)[^"]*"[^\u003e]*\u003e(.*?)\u003c/div\u003e\s*(?=\u003cdiv[^\u003e]*class="(?:vr|rb|result)|\u003c/div\u003e\s*$)',
        r'<div[^\u003e]*class="(?:vr|rb|result)[^"]*"[^\u003e]*\u003e(.*?)\u003c/div\u003e',
    ]
    blocks = []
    for p in patterns:
        blocks = re.findall(p, html_text, re.DOTALL | re.IGNORECASE)
        if blocks:
            break
    for block in blocks[:8]:
        m = re.search(r'<h3[^\u003e]*\u003e\s*\u003ca[^\u003e]*href="([^"]*)"[^\u003e]*\u003e(.*?)\u003c/a\u003e\s*\u003c/h3\u003e', block, re.DOTALL | re.IGNORECASE)
        if not m:
            m = re.search(r'<a[^\u003e]*href="([^"]*)"[^\u003e]*\u003e(.*?)\u003c/a\u003e', block, re.DOTALL | re.IGNORECASE)
        if m:
            url = _normalize_url(m.group(1))
            title = _strip_tags(m.group(2))
            sm = re.search(r'<p[^\u003e]*class="(?:str|abstract)[^"]*"[^\u003e]*\u003e(.*?)\u003c/p\u003e', block, re.DOTALL | re.IGNORECASE)
            snippet = _strip_tags(sm.group(1)) if sm else ""
            if title and url:
                results.append({"url": url, "title": title, "content": snippet})
    return results

def parse_wechat_sogou(html_text: str) -> list:
    """解析搜狗微信搜索结果"""
    results = []
    blocks = re.findall(r'<li[^\u003e]*id="sogou_vr_[^"]*"[^\u003e]*\u003e(.*?)\u003c/li\u003e', html_text, re.DOTALL | re.IGNORECASE)
    for block in blocks[:8]:
        m = re.search(r'<h3[^\u003e]*\u003e\s*\u003ca[^\u003e]*href="([^"]*)"[^\u003e]*\u003e(.*?)\u003c/a\u003e\s*\u003c/h3\u003e', block, re.DOTALL | re.IGNORECASE)
        if not m:
            m = re.search(r'<a[^\u003e]*href="([^"]*)"[^\u003e]*\u003e(.*?)\u003c/a\u003e', block, re.DOTALL | re.IGNORECASE)
        if m:
            url = _normalize_url(m.group(1))
            title = _strip_tags(m.group(2))
            sm = re.search(r'<p[^\u003e]*\u003e(.*?)\u003c/p\u003e', block, re.DOTALL | re.IGNORECASE)
            snippet = _strip_tags(sm.group(1)) if sm else ""
            if title and url:
                results.append({"url": url, "title": title, "content": snippet})
    return results

PARSERS = {
    "baidu": parse_baidu,
    "bing_cn": parse_bing,
    "bing_int": parse_bing,
    "sogou": parse_sogou,
    "wechat": parse_wechat_sogou,
}

def get_parser(engine_name: str):
    """获取指定引擎的解析器"""
    return PARSERS.get(engine_name)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python3 html_parser.py <engine> <html_file>")
        print("Engines: baidu, bing_cn, sogou, wechat")
        sys.exit(1)
    engine = sys.argv[1]
    with open(sys.argv[2], "r", encoding="utf-8") as f:
        html = f.read()
    parser = get_parser(engine)
    if parser:
        results = parser(html)
        print(f"Parsed {len(results)} results from {engine}")
        for r in results[:3]:
            print(f"  [{r['title'][:40]}] {r['url'][:60]}")
    else:
        print(f"Unknown engine: {engine}")