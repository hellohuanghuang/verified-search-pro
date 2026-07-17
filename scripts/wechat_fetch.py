#!/usr/bin/env python3
"""
Verified Search Pro · 微信文章抓取
职责：调用 Node.js 脚本抓取微信公众号文章内容
可选依赖：需要 Node.js 和 wx-article-fetch.js，缺失时跳过
"""

import os
import json
import subprocess
import sys
from urllib.parse import urlparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WECHAT_FETCH_SCRIPT = os.path.join(SCRIPT_DIR, "wechat_fetch/wx-article-fetch.js")

_WECHAT_HOST = "mp.weixin.qq.com"

def is_wechat_url(url: str) -> bool:
    """检查是否为微信公众号文章 URL（域名精确匹配）。

    防仿冒：mp.weixin.qq.com.evil.com（后缀域名）、
    mp.weixin.qq.com@evil.com（userinfo 伪装）、路径含域名字符串等均拒绝。
    无 scheme 的裸 URL 按 https 兜底解析，保持既有宽松入口。
    """
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if not url:
        return False
    parsed = urlparse(url if "://" in url else f"https://{url}")
    try:
        host = (parsed.hostname or "").rstrip(".")
        _ = parsed.port  # 端口混淆（如 :443.evil.com）在此抛 ValueError
    except ValueError:
        return False
    return host == _WECHAT_HOST and parsed.path.startswith("/s/")

def is_available() -> bool:
    """检查微信抓取是否可用"""
    return os.path.exists(WECHAT_FETCH_SCRIPT)

def fetch_article(url: str, timeout: int = 30000) -> dict:
    """抓取微信文章内容"""
    if not is_available():
        return {"error": "微信抓取脚本不存在", "url": url}
    if not is_wechat_url(url):
        return {"error": "非微信文章 URL", "url": url}
    
    cmd = [
        "node", WECHAT_FETCH_SCRIPT,
        "--url", url,
        "--format", "json",
        "--timeout", str(timeout)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return {"error": f"脚本执行失败 (code={result.returncode})", "url": url, "stderr": result.stderr[:200]}
        
        lines = result.stdout.strip().split('\n')
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if 'success' in data:
                    if data.get('success'):
                        return {
                            "title": data.get('title', ''),
                            "content": data.get('content', ''),
                            "url": data.get('url', url),
                            "source": "wechat_fetch",
                        }
                    else:
                        return {"error": data.get('error', '微信抓取失败'), "url": url}
            except json.JSONDecodeError:
                continue
        return {"error": "无法解析响应", "url": url}
    except subprocess.TimeoutExpired:
        return {"error": "抓取超时", "url": url}
    except Exception as e:
        return {"error": f"异常: {str(e)}", "url": url}

def enrich_results(results: list) -> list:
    """为微信文章抓取完整内容"""
    for r in results:
        url = r.get("url", "")
        if is_wechat_url(url):
            data = fetch_article(url)
            if "error" not in data:
                r["full_content"] = data.get("content", "")
                r["fetch_source"] = "wechat_fetch"
            else:
                r["fetch_error"] = data.get("error", "")
    return results

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 wechat_fetch.py <url>")
        sys.exit(1)
    url = sys.argv[1]
    result = fetch_article(url)
    print(json.dumps(result, indent=2, ensure_ascii=False))