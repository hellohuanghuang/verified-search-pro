#!/usr/bin/env python3
"""
Verified Search Pro · HTML 解析器
支持：百度、必应、搜狗、搜狗微信搜索
基于 html.parser 状态机实现，保留正则作为兜底。
纯 Python 标准库，零外部依赖。
"""

import html.parser
import re


def _strip_tags(text: str) -> str:
    """移除 HTML 标签并解码常见实体。"""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ').replace('&quot;', '"').replace('&lt;', '<').replace('&gt;', '>')
    return text.strip()


def _normalize_url(url: str) -> str:
    """URL 归一化：处理百度加密 URL 等。"""
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


class _ResultExtractor(html.parser.HTMLParser):
    """通用 HTML 搜索结果提取器。"""

    def __init__(
        self,
        result_selectors: list,
        title_selectors: list,
        snippet_selectors: list,
    ):
        super().__init__()
        self.result_selectors = result_selectors
        self.title_selectors = title_selectors
        self.snippet_selectors = snippet_selectors

        self._tag_stack = []
        self._in_result = False
        self._result_depth = 0
        self._results = []
        self._current = None
        self._capture_target = None  # 'title' | 'snippet' | None
        self._capture_buffer = []

    def _matches(self, tag: str, attrs: list, selectors: list) -> bool:
        attrs_dict = dict(attrs)
        for selector in selectors:
            if selector.get("tag") and selector["tag"] != tag:
                continue
            classes = attrs_dict.get("class", "")
            if isinstance(classes, str):
                classes = classes.split()
            if selector.get("class") and selector["class"] not in classes:
                continue
            if selector.get("id_prefix") and not attrs_dict.get("id", "").startswith(selector["id_prefix"]):
                continue
            return True
        return False

    def handle_starttag(self, tag, attrs):
        self._tag_stack.append(tag)

        if self._in_result:
            if self._current and not self._current.get("url") and tag == "a":
                attrs_dict = dict(attrs)
                href = attrs_dict.get("href", "")
                if href:
                    self._current["url_raw"] = href
            if self._current and self._capture_target is None:
                if self._matches(tag, attrs, self.title_selectors):
                    self._capture_target = "title"
                    self._capture_buffer = []
                elif self._matches(tag, attrs, self.snippet_selectors):
                    self._capture_target = "snippet"
                    self._capture_buffer = []
            return

        if self._matches(tag, attrs, self.result_selectors):
            self._in_result = True
            self._result_depth = len(self._tag_stack)
            self._current = {"title": "", "url": "", "snippet": ""}
            self._capture_target = None
            self._capture_buffer = []

    def handle_endtag(self, tag):
        if self._in_result:
            if self._capture_target == "title" and tag in {"a", "h2", "h3"}:
                self._current["title"] = _strip_tags("".join(self._capture_buffer))
                if self._current.get("url_raw"):
                    self._current["url"] = _normalize_url(self._current["url_raw"])
                self._capture_target = None
                self._capture_buffer = []
            elif self._capture_target == "snippet" and tag in {"div", "p", "span"}:
                self._current["snippet"] = _strip_tags("".join(self._capture_buffer))
                self._capture_target = None
                self._capture_buffer = []

            if len(self._tag_stack) <= self._result_depth:
                if self._current.get("title") and self._current.get("url"):
                    self._results.append({
                        "url": self._current["url"],
                        "title": self._current["title"],
                        "content": self._current["snippet"],
                    })
                self._in_result = False
                self._current = None

        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()
        elif tag in self._tag_stack:
            # 处理未闭合标签的栈对齐
            self._tag_stack = self._tag_stack[:self._tag_stack.index(tag)]

    def handle_data(self, data):
        if self._capture_target:
            self._capture_buffer.append(data)

    def get_results(self) -> list:
        return self._results


def _extract_with_parser(
    html_text: str,
    result_selectors: list,
    title_selectors: list,
    snippet_selectors: list,
) -> list:
    parser = _ResultExtractor(result_selectors, title_selectors, snippet_selectors)
    parser.feed(html_text)
    return parser.get_results()


def _legacy_parse_baidu(html_text: str) -> list:
    """原正则解析，作为兜底。"""
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


def _legacy_parse_bing(html_text: str) -> list:
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


def _legacy_parse_sogou(html_text: str) -> list:
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


def _legacy_parse_wechat_sogou(html_text: str) -> list:
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


def parse_baidu(html_text: str) -> list:
    """解析百度搜索结果。"""
    result_selectors = [
        {"tag": "div", "class": "result"},
        {"tag": "div", "class": "c-container"},
    ]
    title_selectors = [
        {"tag": "h3"},
    ]
    snippet_selectors = [
        {"tag": "div", "class": "content"},
        {"tag": "div", "class": "abstract"},
        {"tag": "div", "class": "c-abstract"},
    ]
    results = _extract_with_parser(html_text, result_selectors, title_selectors, snippet_selectors)
    if not results:
        results = _legacy_parse_baidu(html_text)
    return results


def parse_bing(html_text: str) -> list:
    """解析必应搜索结果。"""
    result_selectors = [
        {"tag": "li", "class": "b_algo"},
    ]
    title_selectors = [
        {"tag": "h2"},
    ]
    snippet_selectors = [
        {"tag": "p"},
    ]
    results = _extract_with_parser(html_text, result_selectors, title_selectors, snippet_selectors)
    if not results:
        results = _legacy_parse_bing(html_text)
    return results


def parse_sogou(html_text: str) -> list:
    """解析搜狗搜索结果。"""
    result_selectors = [
        {"tag": "div", "class": "vr"},
        {"tag": "div", "class": "rb"},
        {"tag": "div", "class": "result"},
        {"tag": "div", "class": "vrwrap"},
    ]
    title_selectors = [
        {"tag": "h3"},
    ]
    snippet_selectors = [
        {"tag": "p", "class": "str"},
        {"tag": "p", "class": "abstract"},
        {"tag": "p"},
    ]
    results = _extract_with_parser(html_text, result_selectors, title_selectors, snippet_selectors)
    if not results:
        results = _legacy_parse_sogou(html_text)
    return results


def _legacy_parse_duckduckgo(html_text: str) -> list:
    """DuckDuckGo HTML 版正则解析兜底。"""
    results = []
    # 新版 HTML 结果通常以 <article class="result"> 或 <div class="result__body"> 包裹
    blocks = re.findall(
        r'<article[^>]*class="[^"]*result[^"]*"[^>]*>(.*?)</article>',
        html_text, re.DOTALL | re.IGNORECASE,
    )
    if not blocks:
        blocks = re.findall(
            r'<div[^>]*class="[^"]*result__body[^"]*"[^>]*>(.*?)</div>\s*(?=<div[^>]*class="[^"]*result__body|</div>\s*$)',
            html_text, re.DOTALL | re.IGNORECASE,
        )
    if not blocks:
        blocks = re.findall(
            r'<div[^>]*class="[^"]*result[^"]*"[^>]*>(.*?)</div>\s*(?=<div[^>]*class="[^"]*result[^"]*"|</div>\s*$)',
            html_text, re.DOTALL | re.IGNORECASE,
        )
    for block in blocks[:8]:
        # 标题链接
        m = re.search(
            r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
            block, re.DOTALL | re.IGNORECASE,
        )
        if not m:
            m = re.search(
                r'<h2[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>\s*</h2>',
                block, re.DOTALL | re.IGNORECASE,
            )
        if not m:
            m = re.search(
                r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
                block, re.DOTALL | re.IGNORECASE,
            )
        if not m:
            continue
        url = _normalize_url(m.group(1))
        title = _strip_tags(m.group(2))
        # 摘要
        sm = re.search(
            r'<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>',
            block, re.DOTALL | re.IGNORECASE,
        )
        if not sm:
            sm = re.search(
                r'<div[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</div>',
                block, re.DOTALL | re.IGNORECASE,
            )
        if not sm:
            sm = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL | re.IGNORECASE)
        snippet = _strip_tags(sm.group(1)) if sm else ""
        if title and url:
            results.append({"url": url, "title": title, "content": snippet})
    return results


def parse_duckduckgo(html_text: str) -> list:
    """解析 DuckDuckGo HTML 版搜索结果。"""
    result_selectors = [
        {"tag": "article", "class": "result"},
        {"tag": "div", "class": "result__body"},
        {"tag": "div", "class": "result"},
    ]
    title_selectors = [
        {"tag": "a", "class": "result__a"},
        {"tag": "h2"},
        {"tag": "h3"},
    ]
    snippet_selectors = [
        {"tag": "a", "class": "result__snippet"},
        {"tag": "div", "class": "result__snippet"},
        {"tag": "p"},
    ]
    results = _extract_with_parser(html_text, result_selectors, title_selectors, snippet_selectors)
    if not results:
        results = _legacy_parse_duckduckgo(html_text)
    return results


def parse_wechat_sogou(html_text: str) -> list:
    """解析搜狗微信搜索结果。"""
    result_selectors = [
        {"tag": "li", "id_prefix": "sogou_vr_"},
    ]
    title_selectors = [
        {"tag": "h3"},
    ]
    snippet_selectors = [
        {"tag": "p"},
    ]
    results = _extract_with_parser(html_text, result_selectors, title_selectors, snippet_selectors)
    if not results:
        results = _legacy_parse_wechat_sogou(html_text)
    return results


PARSERS = {
    "baidu": parse_baidu,
    "bing_cn": parse_bing,
    "bing_int": parse_bing,
    "sogou": parse_sogou,
    "wechat": parse_wechat_sogou,
    "duckduckgo": parse_duckduckgo,
}


def get_parser(engine_name: str):
    """获取指定引擎的解析器。"""
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
