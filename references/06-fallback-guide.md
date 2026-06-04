# 降级方案指南

## 场景 1: 无 Tavily API Key

**检测**: `os.environ.get("TAVILY_API_KEY")` 为 None

**降级**: 自动切换为纯 Web 搜索（百度/必应/搜狗）

**影响**: 结果质量可能降低，但流程完整

**提示**: 日志中标注 `[Tavily unavailable, using web-only fallback]`

## 场景 2: 无网络连接

**检测**: 搜索请求超时或连接失败

**降级**: 返回错误提示，建议用户手动搜索

**输出**:
```json
{
  "error": "网络不可用，无法执行搜索",
  "suggestion": "请检查网络连接后重试，或手动搜索后提供内容"
}
```

## 场景 3: 无 Node.js（微信抓取）

**检测**: `os.path.exists("wx-article-fetch.js")` 为 False

**降级**: 跳过微信内容抓取，普通网页不受影响

**影响**: 微信公众号文章内容无法获取，但标题和链接仍可用

## 场景 4: 单个引擎故障

**检测**: 引擎连续失败 3 次

**降级**: 熔断该引擎 5 分钟，其他引擎继续工作

**恢复**: 引擎成功后重置失败计数

## 场景 5: 所有 Web 引擎故障

**检测**: 所有 Web 引擎返回空结果

**降级**: 如果 Tavily 可用，仅使用 Tavily；否则报错

## 降级优先级

```
1. Tavily + Web 引擎（全功能）
2. 仅 Web 引擎（无 Tavily）
3. 仅 Tavily（无 Web 引擎）
4. 无网络（提示手动搜索）
```

## 配置建议

对于无 Tavily 的环境，建议配置：
```bash
# 仅使用 Web 引擎
python3 search_engine.py "query" --engines baidu,bing,sogou
```

对于受限环境，建议最小配置：
```bash
# 最小依赖：仅需 Python 3.8+
python3 search_engine.py "query" --engines baidu --budget minimal
```
