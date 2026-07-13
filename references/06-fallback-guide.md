# 降级方案指南

## 场景 1: 无 Tavily API Key

**检测**: `os.environ.get("TAVILY_API_KEY")` 为 None

**调用方式**: 有 Key 时由 `scripts/tavily_adapter.py` 直接调用 Tavily direct REST API；不依赖用户另装外部 Tavily 工具或相邻目录脚本。

**降级**: 自动切换为可用 Web 搜索（必应/搜狗/可用百度）或宿主输入结果

**影响**: 结果质量可能降低，但流程完整

**提示**: 日志中标注 `[Tavily unavailable, using web-only fallback]`

**自检**:
```bash
python3 scripts/search_engine.py --doctor
```

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

## 场景 5: 百度/微信安全验证或反爬

**检测**: HTML 中出现验证码、安全验证、异常流量、验证跳转等特征

**降级**: 标注 `engine_status: blocked`，跳过该引擎，继续使用 Tavily、必应、搜狗或宿主输入结果

**重要边界**: 不绕过验证码、不伪造 Cookie、不使用代理池、不承诺云服务器稳定抓取百度/微信公众号全文

**解释**: blocked 代表搜索渠道被拦截，不代表资料不存在。evidence-pack 必须把该限制写入 `limitations`。

## 场景 6: 宿主搜索结果已可用

**检测**: 用户提供 `--input-results host_results.json`

**处理**: 直接读取宿主搜索结果并进入去重、验证、分级；不调用宿主搜索 runtime

**适用**: OpenClaw/Kimi Search 等环境中，agent 已经完成搜索，希望 VSP 负责资料质检

## 场景 7: 所有 Web 引擎故障

**检测**: 所有 Web 引擎返回空结果

**降级**: 如果 Tavily 或宿主输入可用，继续处理；否则报错

## 降级优先级

```
1. Tavily + 可用 Web 引擎 + 宿主输入（全功能）
2. 宿主输入 + VSP 质检（不额外搜索）
3. 仅 Web 引擎（无 Tavily）
4. 仅 Tavily（无 Web 引擎）
5. 无网络（提示手动搜索或提供手动材料）
```

## Google 可选策略

Google 暂不作为默认搜索源。未来可加入 `google_cse` 可选适配，但必须显式配置 API key、搜索引擎 ID、网络/代理和配额；未配置时不影响默认搜索流程。

## 配置建议

对于无 Tavily 的环境，建议配置：
```bash
# 仅使用 Web 引擎
python3 search_engine.py "query" --engines bing_cn,sogou
```

对于受限环境，建议最小配置：
```bash
# 最小依赖：仅需 Python 3.8+
python3 search_engine.py "query" --engines baidu --budget lite
```

对于宿主 agent 已搜索的环境：
```bash
python3 search_engine.py "query" --input-results host_results.json --engines none --output claims-json
```
