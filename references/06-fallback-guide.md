# 降级方案指南

## 场景 1: 无 API 引擎密钥

**检测**: `TAVILY_API_KEY` / `TENCENTCLOUD_SECRET_ID` / `BAIDU_API_KEY` 均未配置

**调用方式**: 有 Key 时由各适配器直接调用官方 REST API（如 `scripts/tavily_adapter.py` 调用 Tavily direct REST API）；不依赖用户另装外部工具或插件。

**降级**: 自动跳过未配置的 API 引擎（状态 `skipped`），切换为免费 Web 搜索（DuckDuckGo/必应/搜狗）或宿主输入结果；输出 JSON 的 `tips` 字段给出带链接的分步配置引导（`tavily_missing` / `tencent_wsa_missing` / `baidu_api_missing`）

**影响**: 结果质量可能降低，但流程完整

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

## 场景 5: 免费引擎安全验证或反爬

**检测**: HTML 中出现验证码、安全验证、异常流量、验证跳转等特征（搜狗/必应/DuckDuckGo/头条均可能触发）

**降级**: 标注 `engine_status: blocked`，跳过该引擎，继续使用其余可用引擎或宿主输入结果；DuckDuckGo 被拦截时自动降级 `bing_int` → `bing_cn`

**重要边界**: 不绕过验证码、不伪造 Cookie、不使用代理池、不承诺云服务器稳定抓取微信公众号全文

**解释**: blocked 代表搜索渠道被拦截，不代表资料不存在。evidence-pack 必须把该限制写入 `limitations`。

## 场景 6: 宿主搜索结果已可用

**检测**: 用户提供 `--input-results host_results.json`

**处理**: 直接读取宿主搜索结果并进入去重、验证、分级；不调用宿主搜索 runtime

**适用**: OpenClaw/Kimi Search 等环境中，agent 已经完成搜索，希望 VSP 负责资料质检

## 场景 7: 所有 Web 引擎故障

**检测**: 所有 Web 引擎返回空结果

**降级**: 如果 API 引擎或宿主输入可用，继续处理；否则报错

## 降级优先级

搜索底盘分层：**宿主搜索地基 → L1 API 主力 → L2 免费 HTML 引擎兜底**。宿主搜索输入（`--input-results`）始终是首选输入源，不占用引擎配额、不受反爬限制，以下梯队仅指 VSP 自主搜索时的顺序：

```
第 1 梯队（L1 API 主力）：tencent_wsa（已配置时，中文主力）/ baidu_api（已配置时，百度官方源）→ tavily（已配置时，国际/英文向）
第 2 梯队（L2 免费 HTML）：duckduckgo
第 3 梯队（L2 免费 HTML）：bing_cn / sogou
最后：无网络或全部不可用（提示手动搜索或提供手动材料）
```

**组合形态**（从高到低）：

```
1. 宿主搜索 + API 引擎（tencent_wsa / baidu_api / tavily）+ Web 引擎（全功能）
2. 宿主搜索 + VSP 质检（不额外搜索）
3. 宿主搜索 + Web 引擎（无 API Key）
4. 仅 Web 引擎（无 API Key，无宿主）
5. 仅 API 引擎（无 Web 引擎，无宿主）
6. 无网络（提示手动搜索或提供手动材料）
```

API 引擎未配置时，输出 JSON 的 `tips` 字段会给出 `tencent_wsa_missing` / `baidu_api_missing` / `tavily_missing` 引导，配置步骤见 `references/10-api-setup.md`。

## Google 可选策略

Google 暂不作为默认搜索源。未来可加入 `google_cse` 可选适配，但必须显式配置 API key、搜索引擎 ID、网络/代理和配额；未配置时不影响默认搜索流程。

## 配置建议

对于无 API 密钥的环境，建议配置：
```bash
# 仅使用免费 Web 引擎
python3 search_engine.py "query" --engines duckduckgo,bing_cn,sogou
```

对于受限环境，建议最小配置：
```bash
# 最小依赖：仅需 Python 3.8+
python3 search_engine.py "query" --engines duckduckgo --budget lite
```

对于宿主 agent 已搜索的环境：
```bash
python3 search_engine.py "query" --input-results host_results.json --engines none --output claims-json
```
