#!/usr/bin/env node
/**
 * Verified Search Pro · 微信公众号文章抓取
 * 职责：抓取公开的微信文章（mp.weixin.qq.com/s/...），输出 JSON 到 stdout。
 * 零 npm 依赖，仅使用 Node.js 标准库（http/https/zlib），与技能"零第三方依赖"原则一致。
 *
 * 用法：node wx-article-fetch.js --url <url> [--format json] [--timeout <ms>]
 * 输出契约（与 scripts/wechat_fetch.py 对应）：
 *   成功：{"success": true, "title": "...", "content": "...", "url": "..."}
 *   失败：{"success": false, "error": "...", "url": "..."}
 * 只在 stdout 打印一行 JSON；调试信息一律走 stderr。
 */

'use strict';

const http = require('http');
const https = require('https');
const zlib = require('zlib');

const WECHAT_HOST = 'mp.weixin.qq.com';
const MAX_REDIRECTS = 5;
const MAX_BODY_BYTES = 8 * 1024 * 1024; // 8MB 上限，防异常大页面撑爆内存

const UA =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ' +
  '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36';

// ── 入参解析 ────────────────────────────────────────────────
function parseArgs(argv) {
  const args = { url: '', format: 'json', timeout: 30000 };
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const val = argv[i + 1];
    if (key === '--url' && val) { args.url = val; i += 1; }
    else if (key === '--format' && val) { args.format = val; i += 1; }
    else if (key === '--timeout' && val) {
      const t = parseInt(val, 10);
      if (!Number.isNaN(t) && t > 0) args.timeout = t;
      i += 1;
    }
  }
  return args;
}

// ── URL 防御：与 Python 侧 is_wechat_url 同口径（域名精确匹配 + /s/ 路径）──
function isWechatArticleUrl(raw) {
  let parsed;
  try {
    parsed = new URL(raw.includes('://') ? raw : `https://${raw}`);
  } catch (_) {
    return false;
  }
  return parsed.hostname.replace(/\.$/, '').toLowerCase() === WECHAT_HOST
    && parsed.pathname.startsWith('/s/');
}

// ── HTTP(S) 抓取（跟随重定向，处理 gzip/deflate）──────────────
function fetchPage(rawUrl, timeout, redirectsLeft) {
  return new Promise((resolve, reject) => {
    let parsed;
    try {
      parsed = new URL(rawUrl);
    } catch (_) {
      reject(new Error('URL 无法解析'));
      return;
    }
    const transport = parsed.protocol === 'http:' ? http : https;
    const req = transport.get(
      {
        hostname: parsed.hostname,
        port: parsed.port || (parsed.protocol === 'http:' ? 80 : 443),
        path: parsed.pathname + parsed.search,
        headers: {
          'User-Agent': UA,
          'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
          'Accept-Language': 'zh-CN,zh;q=0.9',
          'Accept-Encoding': 'gzip, deflate, identity',
          'Referer': 'https://weixin.sogou.com/',
        },
        timeout,
      },
      (res) => {
        // 重定向
        if ([301, 302, 303, 307, 308].includes(res.statusCode) && res.headers.location) {
          res.resume();
          if (redirectsLeft <= 0) {
            reject(new Error('重定向次数过多'));
            return;
          }
          const next = new URL(res.headers.location, rawUrl).toString();
          resolve(fetchPage(next, timeout, redirectsLeft - 1));
          return;
        }
        if (res.statusCode !== 200) {
          res.resume();
          reject(new Error(`HTTP ${res.statusCode}`));
          return;
        }
        const chunks = [];
        let total = 0;
        res.on('data', (c) => {
          total += c.length;
          if (total > MAX_BODY_BYTES) {
            req.destroy(new Error('响应体过大'));
            return;
          }
          chunks.push(c);
        });
        res.on('end', () => {
          let buf = Buffer.concat(chunks);
          const enc = (res.headers['content-encoding'] || '').toLowerCase();
          try {
            if (enc === 'gzip') buf = zlib.gunzipSync(buf);
            else if (enc === 'deflate') buf = zlib.inflateSync(buf);
          } catch (_) {
            reject(new Error('响应解压失败'));
            return;
          }
          resolve({ html: buf.toString('utf8'), finalUrl: rawUrl });
        });
        res.on('error', reject);
      },
    );
    req.on('timeout', () => req.destroy(new Error('抓取超时')));
    req.on('error', (e) => reject(e));
  });
}

// ── HTML 实体解码（覆盖微信页面常见实体）──────────────────────
function decodeEntities(text) {
  return text
    .replace(/&#x([0-9a-fA-F]+);/g, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(parseInt(d, 10)))
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'")
    .replace(/&hellip;/g, '…')
    .replace(/&mdash;/g, '—')
    .replace(/&ndash;/g, '–')
    .replace(/&ldquo;|&rdquo;/g, '"')
    .replace(/&lsquo;|&rsquo;/g, "'")
    .replace(/&middot;/g, '·');
}

// ── 标题提取：og:title → rich_media_title → <title> ──────────
function extractTitle(html) {
  const og = html.match(/<meta\s+[^>]*property=["']og:title["'][^>]*content=["']([^"']*)["']/i)
    || html.match(/<meta\s+[^>]*content=["']([^"']*)["'][^>]*property=["']og:title["']/i);
  if (og && og[1].trim()) return decodeEntities(og[1].trim());
  const h1 = html.match(/<h1[^>]*class=["'][^"']*rich_media_title[^"']*["'][^>]*>([\s\S]*?)<\/h1>/i);
  if (h1) {
    const t = decodeEntities(h1[1].replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ').trim();
    if (t) return t;
  }
  const tag = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  if (tag) return decodeEntities(tag[1]).replace(/\s+/g, ' ').trim();
  return '';
}

// ── 正文提取：div#js_content，去标签留纯文本 ──────────────────
function extractContent(html) {
  const div = html.match(/<div[^>]*id=["']js_content["'][^>]*>([\s\S]*?)<\/div>\s*<script/i)
    || html.match(/<div[^>]*id=["']js_content["'][^>]*>([\s\S]*?)<\/div>\s*<\/div>/i)
    || html.match(/<div[^>]*id=["']js_content["'][^>]*>([\s\S]*)/i);
  if (!div) return '';
  let body = div[1];
  // 微信正文容器默认 visibility:hidden，内容仍在 HTML 中，直接解析即可
  body = body
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/p>|<\/section>|<\/h[1-6]>|<\/li>|<\/blockquote>/gi, '\n')
    .replace(/<[^>]+>/g, '');
  return decodeEntities(body)
    .replace(/[ \t\u00a0]+/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

// ── 平台拦截/异常页识别 ─────────────────────────────────────
function detectBlockPage(html) {
  const markers = [
    '该内容已被发布者删除',
    '此内容因违规无法查看',
    '此内容已被删',
    '参数错误',
    '操作频繁',
    '环境异常',
    '完成验证后，即可继续访问',
    'readtemplate?t=verify',
  ];
  for (const m of markers) {
    if (html.includes(m)) {
      if (m === '参数错误') return '链接无效或文章已过期（微信返回：参数错误）';
      if (m.includes('验证') || m.includes('频繁') || m.includes('异常') || m.includes('readtemplate')) {
        return '触发微信反爬验证，请稍后重试';
      }
      return m;
    }
  }
  // <title>环境异常</title> 一类独立验证页
  const t = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  if (t && /验证|环境异常/.test(t[1])) return '触发微信反爬验证，请稍后重试';
  return '';
}

// ── 主流程 ──────────────────────────────────────────────────
async function main() {
  const args = parseArgs(process.argv);
  const out = (obj) => { process.stdout.write(JSON.stringify(obj) + '\n'); };

  if (!args.url) {
    out({ success: false, error: '缺少 --url 参数' });
    process.exitCode = 1;
    return;
  }
  if (!isWechatArticleUrl(args.url)) {
    out({ success: false, error: '非微信文章 URL', url: args.url });
    process.exitCode = 1;
    return;
  }

  try {
    const { html, finalUrl } = await fetchPage(args.url, args.timeout, MAX_REDIRECTS);
    const blocked = detectBlockPage(html);
    if (blocked) {
      out({ success: false, error: blocked, url: finalUrl });
      return;
    }
    const title = extractTitle(html);
    const content = extractContent(html);
    if (!content) {
      out({ success: false, error: '未能提取正文（页面结构已变化或需验证）', url: finalUrl });
      return;
    }
    out({ success: true, title, content, url: finalUrl });
  } catch (e) {
    const msg = e && e.message ? e.message : String(e);
    out({ success: false, error: msg.includes('超时') ? '抓取超时' : `抓取失败: ${msg}`, url: args.url });
    process.exitCode = 1;
  }
}

if (require.main === module) {
  main();
}

// 导出内部函数供测试/复核使用（CLI 行为不受影响）
module.exports = {
  isWechatArticleUrl,
  decodeEntities,
  extractTitle,
  extractContent,
  detectBlockPage,
  fetchPage,
};
