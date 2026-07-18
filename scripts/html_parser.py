#!/usr/bin/env python3
"""
Verified Search Pro · HTML 解析器
支持：百度、必应、搜狗、搜狗微信搜索、DuckDuckGo、头条搜索
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
    """检测必应结果标题是否仅为疑问词，用于识别降级结果。"""
    if not title:
        return True
    cleaned = re.sub(r"[^\u4e00-\u9fff\w]", "", title.strip())
    if not cleaned:
        return True
    if cleaned in _QUESTION_ONLY_WORDS:
        return True
    # 检测"疑问词+汉语词语/汉语词典/百科"等降级模式
    degraded_patterns = ("汉语词语", "汉语词典", "汉语词汇", "百度百科", "的意思")
    return any(p in title for p in degraded_patterns)


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
        url_normalizer=None,
    ):
        super().__init__()
        self.result_selectors = result_selectors
        self.title_selectors = title_selectors
        self.snippet_selectors = snippet_selectors
        # URL 归一化钩子：默认 _normalize_url；搜狗等引擎可注入保留加密链接的变体
        self._url_normalizer = url_normalizer or _normalize_url

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
            # 真实页面中，兜底型外层容器（如必应 <ol id="b_results">）会包裹
            # 更具体的结果项（如 <li class="b_algo">）。外层壳尚未捕获到标题时
            # 遇到嵌套的结果容器，应放弃外层、以内层重新开始；否则整页结果会
            # 被合并成一条（标题互相覆盖、URL 跨块串扰）。
            if (
                self._current is not None
                and not self._current.get("title")
                and self._capture_target is None
                and self._matches(tag, attrs, self.result_selectors)
            ):
                self._result_depth = len(self._tag_stack)
                self._current = {"title": "", "url": "", "snippet": ""}
                self._capture_buffer = []
                return
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
                    self._current["url"] = self._url_normalizer(self._current["url_raw"])
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
    url_normalizer=None,
) -> list:
    parser = _ResultExtractor(
        result_selectors, title_selectors, snippet_selectors,
        url_normalizer=url_normalizer,
    )
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


def _preserve_sogou_link(url: str) -> str:
    """搜狗提取阶段的 URL 归一化：原样保留 /link?url=... 加密相对链接。

    真实搜狗结果页的主链接几乎都是 /link?url=... 形式；通用 _normalize_url
    会把这种无法直接解码的相对路径置为空串，导致整条结果在状态机里被丢弃
    （真实页 8 条经典结果因此只剩 1 条绝对链接结果）。这里保留原始路径，
    由 parse_sogou 末尾的 _resolve_sogou_link 统一解密。
    """
    if url and url.startswith("/link?"):
        return url
    return _normalize_url(url)


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
        # 真实搜狗页摘要容器：<div class="fz-mid space-txt ...">（每块一条）
        {"tag": "div", "class": "space-txt"},
        {"tag": "div", "id_prefix": "cacheresult_summary_"},
        {"tag": "p"},
    ]
    results = _extract_with_parser(
        html_text, result_selectors, title_selectors, snippet_selectors,
        url_normalizer=_preserve_sogou_link,
    )
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


# ── 头条搜索（so.toutiao.com）─────────────────────────────────────
#
# 真实页面结构（2026-07 实测两份样本，服务端渲染、无 Cookie 直接 GET 可得）：
# - 结果列表：<div id="results" class="result ...">，每个结果块是
#   <div class="result-content" real-index="N" id="card_<cell_type>-<模板>_<uuid>"
#        data-test-card-id="<cell_type>-<模板>">
# - 有机结果有两种模板（标题锚点每块有且仅有一个，实测确认）：
#   1. 网页/官网结果（id 前缀 card_67-，模板 default / homepage_official）：
#      标题链接 <a class="... l-card-title l-article-header ..." href="/search/jump?...">
#      摘要容器 <div class="... l-natural_summary ...">
#   2. 头条号内容结果（id 前缀 card_undefined-default，2026-07 "新能源汽车" 实测页）：
#      标题链接 <a class="... l-card-title h3" role="text" ...>（无 l-article-header，
#      嵌在 <div class="... l-card-title h3"> 包裹层内），
#      摘要容器 <div class="... l-paragraph ...">，来源为作者/媒体名
# - 阿拉丁卡片（cell_type=26：排行榜/百科/视频/车系等）：容器 id 前缀 card_26-，
#   标题链接无 l-article-header，不提取
# - 相关搜索框（20/21）与用户卡（58）：同样按容器 id 前缀排除
# - 两类实测页均未出现可稳定提取的发布时间字段，时间留空
#
# 头条结果 URL 是服务端签名的中间跳转链接 /search/jump?aid=...&jtoken=...：
# jtoken 与当次搜索会话绑定，无法也不应离线解析或逆向（合规铁律：
# 不伪造 Cookie、不逆向签名）。提取阶段原样保留该相对路径，不做任何改写；
# 如需可点击形式，消费方可自行拼接 https://so.toutiao.com 前缀。


def _preserve_toutiao_link(url: str) -> str:
    """头条提取阶段的 URL 归一化：原样保留 /search/jump?... 签名跳转链接。

    与搜狗 _preserve_sogou_link 同理：通用 _normalize_url 会把相对路径置空，
    导致整条结果被状态机丢弃。头条跳转链接不做解密/解析，原样保留。
    """
    if url and url.startswith("/search/jump?"):
        return url
    return _normalize_url(url)


# 头条相关搜索框等非结果标题（防御性过滤；正常选择器已不会命中）
_TOUTIAO_NON_RESULT_TITLES = {"大家都在搜", "相关搜索"}


def _legacy_parse_toutiao(html_text: str) -> list:
    """头条搜索正则兜底解析：按有机结果容器（card_67- / card_undefined-default）
    切分后提取标题链接与摘要。"""
    results = []
    # 仅切分有机结果块（id 前缀 card_67- 或 card_undefined-default），
    # 阿拉丁卡（26-*）、相关搜索框（20/21）、用户卡（58）天然排除
    block_pat = re.compile(
        r'<div[^>]*class="result-content[^"]*"[^>]*id="card_(?:67|undefined-default)[^"]*"[^>]*>'
        r'(.*?)(?=<div[^>]*class="result-content"|<div[^>]*id="predict-card|$)',
        re.DOTALL | re.IGNORECASE,
    )
    for block in block_pat.findall(html_text)[:8]:
        # 标题链接：两种模板分别为 l-article-header / l-card-title
        tm = re.search(
            r'<a\b[^>]*class="[^"]*l-article-header[^"]*"[^>]*>(.*?)</a>', block, re.DOTALL | re.IGNORECASE,
        ) or re.search(
            r'<a\b[^>]*class="[^"]*l-card-title[^"]*"[^>]*>(.*?)</a>', block, re.DOTALL | re.IGNORECASE,
        )
        if not tm:
            continue
        hm = re.search(r'href="([^"]*)"', tm.group(0))
        if not hm:
            continue
        # 原始 HTML 属性中的 &amp; 实体需还原（html.parser 路径会自动处理）
        url = _preserve_toutiao_link(hm.group(1).replace("&amp;", "&"))
        title = _strip_tags(tm.group(1))
        sm = re.search(
            r'<div[^>]*class="[^"]*l-natural_summary[^"]*"[^>]*>(.*?)</div>', block, re.DOTALL | re.IGNORECASE,
        ) or re.search(
            r'<div[^>]*class="[^"]*l-paragraph[^"]*"[^>]*>(.*?)</div>', block, re.DOTALL | re.IGNORECASE,
        )
        snippet = _strip_tags(sm.group(1)) if sm else ""
        if title and url:
            results.append({"url": url, "title": title, "content": snippet})
    return results


def parse_toutiao(html_text: str) -> list:
    """解析头条搜索结果（结构说明见上方区块注释）。"""
    result_selectors = [
        # 仅有机结果容器：67-*（网页/官网结果）与 undefined-default（头条号内容结果），
        # 按容器 id 前缀排除阿拉丁卡（26-*）、相关搜索框（20/21）、用户卡（58）
        {"tag": "div", "class": "result-content", "id_prefix": "card_67-"},
        {"tag": "div", "class": "result-content", "id_prefix": "card_undefined-default"},
    ]
    title_selectors = [
        {"tag": "a", "class": "l-article-header"},  # 67-* 模板
        {"tag": "a", "class": "l-card-title"},      # undefined-default 模板
    ]
    snippet_selectors = [
        {"tag": "div", "class": "l-natural_summary"},  # 67-* 模板
        {"tag": "div", "class": "l-paragraph"},        # undefined-default 模板
    ]
    results = _extract_with_parser(
        html_text, result_selectors, title_selectors, snippet_selectors,
        url_normalizer=_preserve_toutiao_link,
    )
    if not results:
        results = _legacy_parse_toutiao(html_text)
    # 防御性过滤：空标题 / 相关搜索框 / 站内搜索链接（非跳转非外链）
    filtered = []
    for r in results:
        title = (r.get("title") or "").strip()
        url = r.get("url") or ""
        if not title or title in _TOUTIAO_NON_RESULT_TITLES:
            continue
        if url.startswith("/search?"):
            continue
        filtered.append(r)
    return filtered


PARSERS = {
    "baidu": parse_baidu,
    "bing_cn": parse_bing,
    "bing_int": parse_bing,
    "sogou": parse_sogou,
    "wechat": parse_wechat_sogou,
    "duckduckgo": parse_duckduckgo,
    "toutiao": parse_toutiao,
}


def get_parser(engine_name: str):
    """获取指定引擎的解析器。"""
    return PARSERS.get(engine_name)
