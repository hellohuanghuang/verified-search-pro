#!/usr/bin/env python3
"""
Verified Search Pro · HTML 解析器
支持：百度、必应、搜狗、搜狗微信搜索、DuckDuckGo
基于 html.parser 状态机实现，保留正则作为兜底。
纯 Python 标准库，零外部依赖。
"""

import html.parser
import re
import urllib.parse
import urllib.request

import sogou_url_decoder


# 仅含疑问词/虚词的结果标题过滤词（避免必应把"如何"当标题）
_QUESTION_ONLY_WORDS = {
    "如何", "怎样", "怎么", "为什么", "怎么个", "为何", "哪", "哪些", "哪个", "什么",
    "哪里", "哪儿", "谁", "多少", "几", "怎样", "能", "可以", "吗", "呢",
}


def _is_question_only_title(title: str) -> bool:
    """判断标题是否只由疑问词/虚词组成（必应降级结果常见）。"""
    if not title:
        return True
    cleaned = re.sub(r"[^\u4e00-\u9fff\w]", "", title.strip())
    if not cleaned:
        return True
    return cleaned in _QUESTION_ONLY_WORDS


def _strip_tags(text: str) -> str:
    """移除 HTML 标签并解码常见实体。"""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ').replace('&quot;', '"').replace('&lt;', '<').replace('&gt;', '>')
    return text.strip()


def _resolve_sogou_link(url: str, timeout: float = 5) -> str:
    """
    尝试解密搜狗 /link?url=... 加密链接。
    使用 sogou_url_decoder 从中间页 JS 提取真实 URL；失败则返回原始完整 URL。
    """
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if not url.startswith("/link?"):
        return url
    try:
        return sogou_url_decoder.resolve_sogou_link(url, timeout=timeout, referer="https://www.sogou.com/web")
    except Exception:
        return "https://www.sogou.com" + url


# 保留别名以兼容旧调用
def _normalize_url(url: str, engine: str = "") -> str:
    """URL 归一化：处理百度加密 URL、搜狗加密 URL 等。"""
    if not url:
        return ""
    # 搜狗 /link?url=... 中的 url 参数是加密 token，不是真实目标 URL，优先用解密器
    if engine == "sogou" and url.startswith("/link?"):
        return _resolve_sogou_link(url)
    if url.startswith("/url?") or url.startswith("/link?"):
        m = re.search(r'[?&]url=([^\u0026]+)', url)
        if m:
            decoded = urllib.parse.unquote(m.group(1))
            # 只有解码后是完整 URL 才返回；否则仍按相对路径处理
            if decoded.startswith("http://") or decoded.startswith("https://"):
                return decoded
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
    # 必应可能使用 b_algo、b_ans、 broader b_results 等容器
    blocks = re.findall(r'<li[^\u003e]*class="b_algo"[^\u003e]*\u003e(.*?)\u003c/li\u003e', html_text, re.DOTALL | re.IGNORECASE)
    if not blocks:
        blocks = re.findall(r'<li[^\u003e]*class="b_ans"[^\u003e]*\u003e(.*?)\u003c/li\u003e', html_text, re.DOTALL | re.IGNORECASE)
    if not blocks:
        blocks = re.findall(r'<ol[^\u003e]*id="b_results"[^\u003e]*\u003e(.*?)\u003c/ol\u003e', html_text, re.DOTALL | re.IGNORECASE)
    for block in (blocks[:8] if isinstance(blocks, list) else [blocks[:8]]):
        if not block:
            continue
        m = re.search(r'<h2[^\u003e]*\u003e\s*\u003ca[^\u003e]*href="([^"]*)"[^\u003e]*\u003e(.*?)\u003c/a\u003e\s*\u003c/h2\u003e', block, re.DOTALL | re.IGNORECASE)
        if not m:
            m = re.search(r'<a[^\u003e]*href="([^"]*)"[^\u003e]*\u003e(.*?)\u003c/a\u003e', block, re.DOTALL | re.IGNORECASE)
        if m:
            url = _normalize_url(m.group(1))
            title = _strip_tags(m.group(2))
            sm = re.search(r'<p[^\u003e]*\u003e(.*?)\u003c/p\u003e', block, re.DOTALL | re.IGNORECASE)
            snippet = _strip_tags(sm.group(1)) if sm else ""
            if title and url and not _is_question_only_title(title):
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
            url = _normalize_url(m.group(1), engine="sogou")
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
            url = _normalize_url(m.group(1), engine="sogou")
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
    """解析必应搜索结果，支持 b_algo、b_ans、b_results 等容器。"""
    result_selectors = [
        {"tag": "li", "class": "b_algo"},
        {"tag": "li", "class": "b_ans"},
        {"tag": "div", "class": "b_ground"},
        {"tag": "ol", "id_prefix": "b_results"},
    ]
    title_selectors = [
        {"tag": "h2"},
        {"tag": "h3"},
    ]
    snippet_selectors = [
        {"tag": "p"},
        {"tag": "div", "class": "b_caption"},
    ]
    results = _extract_with_parser(html_text, result_selectors, title_selectors, snippet_selectors)
    if not results:
        results = _legacy_parse_bing(html_text)
    # 过滤仅含疑问词的标题
    return [r for r in results if not _is_question_only_title(r.get("title", ""))]


def parse_sogou(html_text: str) -> list:
    """解析搜狗搜索结果，并尝试解密 /link?url=... 加密链接。"""
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
    # 对搜狗结果尝试解密加密链接
    for r in results:
        if r.get("url", "").startswith("/link?"):
            r["url"] = _resolve_sogou_link(r["url"])
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
    # html.duckduckgo.com 返回的结果行
    if not blocks:
        blocks = re.findall(
            r'<div[^>]*class="web-result[^"]*"[^>]*>(.*?)</div>\s*(?=<div[^>]*class="web-result|</div>\s*$)',
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
    # 先基于 HTML 结构解析，再正则兜底
    result_selectors = [
        {"tag": "article", "class": "result"},
        {"tag": "div", "class": "result__body"},
        {"tag": "div", "class": "result"},
        {"tag": "div", "class": "web-result"},
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
