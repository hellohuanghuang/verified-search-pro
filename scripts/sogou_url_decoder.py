#!/usr/bin/env python3
"""
Verified Search Pro · 搜狗加密链接解密器

搜狗搜索结果中的 URL 通常以 /link?url=... 形式给出，需要先访问一个中间页，
从返回的 JavaScript 中提取真实的目标 URL。本模块不依赖外部 execjs，仅使用
Python 标准库进行正则解析和字符串操作。

主要流程：
1. 接收加密的 /link?url=... 路径。
2. 添加 k/h 参数，访问搜狗中间页。
3. 从中间页 HTML 中提取 location.replace(...) 或类似 JS 跳转中的真实 URL。
4. 对验证码等异常情况进行异常处理。
"""

import re
import urllib.parse
import urllib.request


class SogouUrlDecodeError(Exception):
    """搜狗链接解密失败。"""
    pass


def _add_kh_params(url: str, k: str = "1", h: str = "1") -> str:
    """在 /link?url=... 后追加 k=1 和 h=1 参数，搜狗中间页通常需要。"""
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    if "k" not in query:
        query["k"] = [k]
    if "h" not in query:
        query["h"] = [h]
    new_query = urllib.parse.urlencode(query, doseq=True)
    return urllib.parse.urlunparse(parsed._replace(query=new_query))


def _extract_url_from_js(html_text: str) -> str:
    """
    从中间页 HTML/JS 中提取真实 URL。
    优先匹配 location.replace("url")、location.href="url"、window.location="url"。
    """
    if not html_text:
        return ""
    # 常见形式：location.replace('...') 或 location.replace("...")
    patterns = [
        r'location\.replace\(\s*["\']([^"\']+)["\']\s*\)',
        r'location\.href\s*=\s*["\']([^"\']+)["\']',
        r'window\.location\s*=\s*["\']([^"\']+)["\']',
        r'url\s*=\s*["\']([^"\']+)["\']',
    ]
    for pat in patterns:
        m = re.search(pat, html_text, re.IGNORECASE)
        if m:
            candidate = m.group(1)
            # 搜狗中间页的真实 URL 通常以 http:// 或 https:// 开头，
            # 有时以变量拼接形式出现，这里做基本过滤。
            if candidate.startswith("http://") or candidate.startswith("https://"):
                return candidate
            # 处理相对 URL 拼接
            if candidate.startswith("/"):
                return "https://www.sogou.com" + candidate
    return ""


def decode_sogou_url(encrypted_url: str, referer: str = "", headers: dict = None, timeout: float = 5) -> str:
    """
    解密搜狗 /link?url=... 加密链接。

    参数：
        encrypted_url: 搜狗搜索结果中的加密 URL（如 /link?url=dn9a_... 或完整 URL）。
        referer: 可选，设置 Referer 头减少被拦截概率。
        headers: 可选，自定义请求头。
        timeout: 请求超时秒数。

    返回：
        真实目标 URL。

    异常：
        当遇到验证码、解析失败或网络异常时抛出 SogouUrlDecodeError。
    """
    if not encrypted_url:
        raise SogouUrlDecodeError("encrypted_url 为空")

    if encrypted_url.startswith("http://") or encrypted_url.startswith("https://"):
        if "/link?" not in encrypted_url:
            return encrypted_url
        full_url = encrypted_url
    else:
        if not encrypted_url.startswith("/link?"):
            raise SogouUrlDecodeError(f"不认识的搜狗加密 URL 格式: {encrypted_url}")
        full_url = "https://www.sogou.com" + encrypted_url

    full_url = _add_kh_params(full_url)

    req_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
    }
    if referer:
        req_headers["Referer"] = referer
    if headers:
        req_headers.update(headers)

    try:
        req = urllib.request.Request(full_url, method="GET", headers=req_headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            final_url = resp.geturl() or full_url
    except urllib.error.HTTPError as e:
        # 搜狗中间页 403/302 有时直接跳到了验证码或登录页
        if e.code in (302, 403, 503):
            body = e.read().decode("utf-8", errors="ignore") if e.fp else ""
            if _is_captcha_page(body):
                raise SogouUrlDecodeError("搜狗返回验证码页面，解密被中断")
            raise SogouUrlDecodeError(f"搜狗中间页 HTTP {e.code}: 可能需要验证码")
        raise SogouUrlDecodeError(f"请求搜狗中间页失败: HTTP {e.code}")
    except Exception as e:
        raise SogouUrlDecodeError(f"请求搜狗中间页失败: {type(e).__name__}: {e}")

    # 如果已经直接跳转到真实 URL
    if final_url and "/link?" not in final_url and final_url != full_url:
        return final_url

    # 从 JS 中提取真实 URL
    real_url = _extract_url_from_js(html)
    if real_url:
        return real_url

    # 检查验证码/反爬
    if _is_captcha_page(html):
        raise SogouUrlDecodeError("搜狗返回验证码页面，解密被中断")

    raise SogouUrlDecodeError("无法从搜狗中间页解析出真实 URL")


def _is_captcha_page(html_text: str) -> bool:
    """判断返回内容是否为搜狗验证码或安全验证页。"""
    lowered = (html_text or "").lower()
    signatures = (
        "请输入验证码", "antispider", "您的访问出错了", "captcha", "安全验证",
        "验证码", "访问过于频繁", "刷新重试",
    )
    return any(sig in lowered for sig in signatures)


def resolve_sogou_link(encrypted_url: str, timeout: float = 5, referer: str = "") -> str:
    """
    兼容旧函数名的搜狗链接解密封装，失败时返回完整 sogou URL 或原始路径。
    """
    try:
        return decode_sogou_url(encrypted_url, referer=referer, timeout=timeout)
    except SogouUrlDecodeError:
        if encrypted_url.startswith("/"):
            return "https://www.sogou.com" + encrypted_url
        return encrypted_url


if __name__ == "__main__":
    # 简单自测：不发起网络，只验证正则提取
    sample = '''<script>window.location.replace("https://zhihu.com/question/123");</script>'''
    print(_extract_url_from_js(sample))
