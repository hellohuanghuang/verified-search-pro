# API 配置引导手册

VSP 搜索底盘分层：**L0 自检引导 → L1 API 主力（tencent_wsa / baidu_api / tavily）→ L2 免费 HTML 引擎兜底（DuckDuckGo / 必应 / 搜狗）**。
未配置任何 API 引擎时仍可运行，但结果质量、时效元数据和中文覆盖会明显降低。建议首次使用先完成自检：

```bash
python3 scripts/search_engine.py --doctor
```

`--doctor` 输出中 `search.tavily`、`search.tencent_wsa` 与 `search.baidu_api` 会分别给出 `available` 状态与分步配置指引。

---

## Tavily（国际/英文向 AI 搜索）

| 项目 | 说明 |
|------|------|
| 申请入口 | https://app.tavily.com |
| 环境变量 | `TAVILY_API_KEY` |
| 免费额度 | 注册即送 1000 次/月（以官网页面为准） |

**配置步骤**：

1. 访问 https://app.tavily.com ，免费注册账号
2. 在 Dashboard 复制 API Key（以 `tvly-` 开头）
3. 设置环境变量：
   ```bash
   export TAVILY_API_KEY=tvly-xxxxxxxxxx
   ```
4. 重启当前 Agent/终端会话，使环境变量生效
5. 运行 `python3 scripts/search_engine.py --doctor` 验证，`search.tavily.available` 应为 `true`

---

## 腾讯云 WSA·联网搜索 API（中文主力）

| 项目 | 说明 |
|------|------|
| 产品入口 | https://cloud.tencent.com/product/wsa |
| 环境变量 | `TENCENTCLOUD_SECRET_ID` + `TENCENTCLOUD_SECRET_KEY` |
| 版本 | 标准版（standard）即可用；响应中 `Response.Version` 返回账户版本 |

**配置步骤**：

1. **注册腾讯云账号并完成个人实名认证**：访问 https://cloud.tencent.com ，注册后按指引完成个人实名
2. **开通「联网搜索 API」标准版**：在控制台进入联网搜索产品页开通。活动专区可每日领取免费调用额度（活动限时，以页面为准）
3. **创建密钥对**：访问管理（CAM）→ API 密钥管理 → 新建密钥，保存 SecretId / SecretKey（**SecretKey 只显示一次**，请立即妥善保存）
4. **设置环境变量**：
   ```bash
   export TENCENTCLOUD_SECRET_ID=AKIDxxxxxxxxxx
   export TENCENTCLOUD_SECRET_KEY=xxxxxxxxxx
   ```
5. **验证**：运行 `python3 scripts/search_engine.py --doctor`，`search.tencent_wsa.available` 应为 `true`

**标准版能力边界（重要，勿过度承诺）**：

| 维度 | 标准版（standard） |
|------|-------------------|
| 可用参数 | `Query`（必填）、`Mode`（0 自然检索 / 1 多模态 / 2 混合）、`Site`（域名限定）、`FromTime` / `ToTime`（秒级时间戳过滤） |
| 不可用参数 | `Cnt`、`Industry`、`Freshness`、`Deeplinks`（尊享/旗舰版专属，标准版请求不得携带） |
| 返回条数 | 由服务端决定，实测约 10 条，无法用参数控制 |
| 内容生态 | 偏腾讯系内容生态（腾讯网、企鹅号、搜狗系等） |
| 微信公众号 | **不包含**（官方 FAQ 明示），公众号内容请走搜狗微信引擎或宿主搜索输入 |
| 日期字段 | 返回 `date`（如 `2026-01-12 16:04:16`），VSP 已在适配层规范化为 ISO 日期 `YYYY-MM-DD` |

**常见错误码**：

| 错误码 | 含义 | VSP 引擎状态 |
|--------|------|-------------|
| `ResourceNotFound` | 未开通联网搜索服务 | `skipped / service_not_activated` |
| `UnauthorizedOperation` | 密钥错误或未授权 | `failed / unauthorized` |
| `RequestLimitExceeded` | 调用超限 | `blocked / rate_limit_exceeded` |

---

## 百度千帆 AI 搜索（百度搜索官方数据源）

| 项目 | 说明 |
|------|------|
| 申请入口 | https://console.bce.baidu.com/ai-search/qianfan/ais/console/apiKey |
| 环境变量 | `BAIDU_API_KEY`（Key 以 `bce-v3/ALTAK-` 开头） |
| 免费额度 | 每月 1500 次（按天发放约 50 次/天，官方产品手册口径），可开通按量后付费 |

**配置步骤**：

1. **注册百度智能云账号并完成个人实名认证**：访问 https://cloud.baidu.com ，注册后按指引完成个人实名
2. **创建 API Key**：进入千帆 AI 搜索「应用接入」页（ https://console.bce.baidu.com/ai-search/qianfan/ais/console/apiKey ），创建并复制 API Key
3. **设置环境变量**：
   ```bash
   export BAIDU_API_KEY=bce-v3/ALTAK-xxxxxxxxxx
   ```
4. **验证**：运行 `python3 scripts/search_engine.py --doctor`，`search.baidu_api.available` 应为 `true`

**能力说明**：

| 维度 | 说明 |
|------|------|
| 数据源 | 百度搜索官方数据源（千帆 AI 搜索 `baidu_search_v2`），补足百度系中文网页覆盖 |
| 请求参数 | `messages`（查询词）、`resource_type_filter`（web 类型 + `top_k`，默认 10 条、上限 50 条）、`search_filter`（时效过滤，可选） |
| 时效过滤 | 支持 `pd`（过去 24 小时）/ `pw`（过去 7 天）/ `pm`（过去 31 天）/ `py`（过去 365 天）快捷档，或 `YYYY-MM-DDtoYYYY-MM-DD` 自定义区间；底层通过 `search_filter.range.page_time` 的 `gte` / `lt` 实现（2026-07-18 真实验收：pw 档返回结果日期全部落在过去一周，自定义 2020 区间结果全部落在 2020 年内，服务端确实生效） |
| 站点限定 | `site` 参数（`search_filter.match.site`，与时效过滤可共存）按域名限定检索范围，子域名一并覆盖（实测：`people.com.cn` 命中 `cpc./js./sh.people.com.cn` 等子站，`www.gov.cn` 精确命中该站）。注意：**过宽的裸后缀（如 `gov.cn`）会返回空结果**，请填具体站点域名 |
| 日期字段 | 返回 `date`（如 `2026-01-12`），VSP 已在适配层规范化为 ISO 日期 `YYYY-MM-DD` |

**常见错误映射**：

| 错误 | 含义 | VSP 引擎状态 |
|------|------|-------------|
| HTTP 401 / 403 | API Key 错误、未授权或未开通服务 | `failed / unauthorized` |
| HTTP 429 | 调用超限 / 额度耗尽 | `blocked / rate_limit_exceeded` |
| 响应含 `code` / `message` | 业务错误（参数错误、服务异常等） | 按错误码映射，默认 `failed / api_error` |

---

## 配置优先级建议

1. **中文任务为主**：优先配置腾讯云 WSA 与百度千帆 AI 搜索，再按需配置 Tavily
2. **国际/英文任务为主**：优先配置 Tavily
3. **API 引擎均未配置**：VSP 自动降级为纯 Web 引擎（L2），输出 JSON 的 `tips` 字段会给出 `tencent_wsa_missing` / `baidu_api_missing` / `tavily_missing` 引导，Agent 应停下并引导用户按本手册配置
