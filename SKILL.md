***

name: verified-search-pro
license: "MIT"
description: "面向深度调研和事实核查的可信研究助理。在宿主搜索能力的基础上，调用腾讯云联网搜索（WSA）、百度（千帆）、Tavily、必应、搜狗、DuckDuckGo 多引擎搜索，将资料清洗、降噪、交叉验证为 Markdown 报告与 claims-json/evidence-pack 证据包。触发场景：调研、验证、确认、政策追踪、资料质检、证据包、背调、交叉验证、多搜一下、搜一下、查一下。"
compatibility: "Requires Python 3.8+ and internet access. Optional API engines: TAVILY\_API\_KEY, TENCENTCLOUD\_SECRET\_ID + TENCENTCLOUD\_SECRET\_KEY, BAIDU\_API\_KEY (all unset falls back to free web engines). Optional: Node.js for WeChat fetching."
allowed-tools: "Read, Bash, Write, SearchReplace, RunCommand"
metadata:
version: "2.1.0"
author: "黄艾伦（那个谁）"
tags:
\- "搜索"
\- "信息验证"
\- "多引擎"
\- "交叉验证"
\- "降噪"
\- "信息源分级"
\- "Tavily"
\- "必应"
\- "搜狗"
\- "DuckDuckGo"
platforms:
\- "openclaw"
\- "claude-code"
\- "codex"
\- "hermes"
openclaw:
emoji: "🔍"
requires:
bins: \["python3"]
env: \["TAVILY\_API\_KEY", "TENCENTCLOUD\_SECRET\_ID", "TENCENTCLOUD\_SECRET\_KEY", "BAIDU\_API\_KEY"]
install: \[]
------------

# Verified Search Pro v2.1.0 · 可信研究助理

> 从“搜到资料”到“确认资料能不能用”。搜索工具负责找资料，本 Skill 负责质检资料。
> 默认交付：Markdown 给人阅读，claims-json/evidence-pack 给 agent、测试和后续工作流使用。平台适配：Codex / Claude Code / 通用 Prompt；OpenClaw 等个人环境作为可选示例。

***

## 触发方式

当用户请求涉及以下场景或关键词时，优先使用本 Skill 处理搜索与质检：

**触发场景**：确认真相、验证搜索、调研、政策追踪、机构/项目研究、信息验真、竞品追踪、人物/机构背调、多源比对。

**触发关键词**：调研、验证、确认、搜索、政策追踪、资料质检、证据包、背调、交叉验证、多搜一下、搜一下、查一下。

## 快速导航（Progressive Disclosure）

本 Skill 采用分层加载架构——按需读取，避免上下文膨胀。默认使用 `--budget auto` 控制输出大小（256k 为上限），由轻量规则选择 `lite / standard / deep`，自动匹配任务规模。

**表述纪律**：本文件只给索引与铁律；凡涉及引擎清单、场景策略、配置步骤等易变细节，一律以 references 对应文件为唯一事实源，本文件不自行概括，避免两边表述漂移。

| 当前阶段                   | 加载文档                                                                      | 说明                                      |
| ---------------------- | ------------------------------------------------------------------------- | --------------------------------------- |
| **Phase 1: 任务拆解**      | `references/01-search-strategy.md`                                        | 路由逻辑、场景引擎表、查询拆分（引擎策略唯一事实源）            |
| **Phase 2-3: 搜索获取与降噪** | `references/02-source-ranking.md` + `references/04-noise-filtering.md`    | 信息源分级、降噪流程、去重规则                         |
| **Phase 4: 验真比对**      | `references/03-confidence-rubric.md` + `references/04-noise-filtering.md` | 置信度定级、交叉验证、矛盾处理                         |
| **Phase 5: 交付输出**      | `references/05-output-template.md` + `assets/report-template.md`          | Markdown + claims-json 默认交付             |
| **无 API 密钥或引擎被拦截**    | `references/06-fallback-guide.md`                                         | 降级方案（降级唯一事实源）                           |
| **API 配置**             | `references/10-api-setup.md`                                              | Tavily / 腾讯云 WSA / 百度千帆申请与配置引导          |
| **接入无专用适配的平台**         | `references/07-cross-platform.md`                                         | 通用 Prompt 注入（Claude Code / Codex 请改用 `.claude/` / `.codex/` 专用文件） |
| **2.1 方法论审计**          | `references/08-trust-quality-framework.md`                                | Claim-centric 验证、OSINT、ACH、SIFT、信号/噪声框架 |
| **2.1 评估基准**           | `references/09-evaluation-benchmark.md`                                   | benchmark 场景、质量指标、发布门禁                  |

***

## v2.1 产品边界

* **用户视角**：可信研究助理，先找资料，再把资料质检成可复核的研究包。

* **Agent 视角**：资料前处理器，输出精简、带标签、可继续推理的上下文，而不是原始链接堆。

* **搜索底盘**：够用且稳；分层为「宿主搜索地基（`--input-results`，最基础的兜底）→ L1 API 主力（tencent\_wsa 中文主力 + baidu\_api 百度官方源 + tavily 国际/英文向）→ L2 免费 HTML 引擎兜底（DuckDuckGo、必应、搜狗；头条为低频熔断引擎，不进默认列表）」，Google 暂不进入默认能力。场景级引擎选择以 `references/01-search-strategy.md` 为唯一事实源。

* **安全分区**：区分可信结论、观点地图、常见误区、争议不确定、时间演进，非可信材料不得被自动提升为事实。

* **性能边界**：不轮询所有搜索源，不默认抓全文，不绕过验证码或登录限制。

***

## 核心工作流（5 阶 16 步）

### Phase 1: 任务拆解（检查点 1）

**目标**：理解用户需求，拆解信息模块，确定搜索策略。

| 步骤  | 动作                                                                                      | 输出   |
| --- | --------------------------------------------------------------------------------------- | ---- |
| 1.1 | 分析用户意图：事实核查？调研？追踪？                                                                      | 意图分类 |
| 1.2 | 拆解信息模块：事实、观点、误区、争议、时间演进分别需要什么？                                                          | 模块清单 |
| 1.3 | 按 `references/01-search-strategy.md` 的路由逻辑与场景表确定引擎组合；确认宿主输入（`--input-results`）是否可用      | 引擎策略 |
| 1.4 | 生成搜索关键词：主查询 + 变体查询                                                                      | 查询列表 |
| 1.5 | **强制**：调用 `scripts/search_engine.py` 前，先用 LLM 提取 2-5 个核心搜索概念，并通过 `--search-concepts` 传入 | 概念列表 |

**检查点 1**：`interactive` 模式下向用户确认；`batch` 模式下连续执行并在报告中汇总。

**关键约束**：

* 如果用户输入是中文自然语言疑问句，**必须先提取核心概念**，再调用 `search_engine.py`。

* 直接传入中文原句而不带 `--search-concepts` 被视为**违规调用**。

* 脚本会在 stderr 输出警告，Agent 应主动补全 concepts，不得忽略。

**示例**：

* 输入："如何消除比熊泪痕？"

* 概念：`"比熊,泪痕,消除方法"`

* 调用：

  ```bash
  python3 scripts/search_engine.py "如何消除比熊泪痕？" --search-concepts "比熊,泪痕,消除方法" --verify --output claims-json
  ```

**加载**：`references/01-search-strategy.md` 获取完整策略指南。

***

### Phase 2: 搜索获取（检查点 2）

**目标**：并行搜索多引擎，收集原始结果。

| 步骤  | 动作                                    | 输出    |
| --- | ------------------------------------- | ----- |
| 2.1 | 并行调用所选引擎，并读取 `--input-results` 宿主搜索结果 | 原始结果池 |
| 2.2 | 记录来源引擎、时间戳、原始得分和 engine health        | 元数据   |
| 2.3 | 微信文章特殊处理（如需要）                         | 内容抓取  |
| 2.4 | 汇总原始结果数量与来源分布                         | 统计摘要  |

**检查点 2**：`interactive` 模式下确认；默认 `auto` 由 agent 判断是否需要停顿。

**调用脚本**：`scripts/search_engine.py`（主入口）

***

### Phase 3: 降噪清洗（检查点 3）

**目标**：去重、过滤、分级，保留高质量信息。

| 步骤  | 动作                  | 输出    |
| --- | ------------------- | ----- |
| 3.1 | URL 归一化去重           | 去重结果  |
| 3.2 | 内容指纹去重（15 词 MD5）    | 去重结果  |
| 3.3 | 文本相似度去重（阈值 0.85）    | 去重结果  |
| 3.4 | 信息源分级过滤（A-E 级）      | 过滤后结果 |
| 3.5 | 域名权威性评分加权           | 加权排序  |
| 3.6 | 跨域名转载检测（same-story） | 转载标注  |

**检查点 3**：在 `batch` 模式下不打断用户，但必须在最终报告中交代降噪结果。

**加载**：`references/02-source-ranking.md` 获取信息源分级规则。
**加载**：`references/04-noise-filtering.md` 获取降噪流程细节。
**调用脚本**：`scripts/result_fusion.py`

***

### Phase 4: 验真比对（检查点 4）

**目标**：交叉验证，识别矛盾，定级置信度。

| 步骤  | 动作                    | 输出    |
| --- | --------------------- | ----- |
| 4.1 | 提取关键实体（中文词/英文专有词/数字）  | 实体列表  |
| 4.2 | 反向验证：检查结果内容是否包含关键实体   | 验证得分  |
| 4.3 | 多源一致性检查：同一事实在不同来源中的表述 | 一致性报告 |
| 4.4 | 矛盾信息标注：发现冲突时标记并说明     | 矛盾标注  |
| 4.5 | 置信度定级（A-E）            | 定级结果  |

**检查点 4**：高风险、范围模糊或证据冲突明显时使用 `interactive`；一般调研可连续执行。

**加载**：`references/03-confidence-rubric.md` 获取置信度定级标准。
**调用脚本**：`scripts/cross_verify.py`

***

### Phase 5: 要点定锚与交付

**目标**：提炼核心结论，生成结构化报告。

| 步骤  | 动作                                        | 输出           |
| --- | ----------------------------------------- | ------------ |
| 5.1 | 要点锚定：提炼可信结论，非可信材料分区放置                     | 要点清单         |
| 5.2 | 标注每个要点的置信度、来源可靠性、时效状态                     | 置信度标注        |
| 5.3 | 标注观点地图、常见误区、争议不确定、时间演进                    | 分区标注         |
| 5.4 | 生成 Markdown 报告和 claims-json/evidence-pack | 人读报告 + 机器读证据 |
| 5.5 | 按用户环境交付；默认保存本地文件                          | 交付确认         |

**加载**：`references/05-output-template.md` 获取输出规范。
**加载**：`assets/report-template.md` 获取报告模板。

***

## 信息源分级（内置铁律）

| 等级    | 来源类型                    | 使用规则          | 置信度    |
| ----- | ----------------------- | ------------- | ------ |
| **A** | 政府官网、权威媒体、学术期刊、品牌/机构官方  | 优先使用，可直接引用    | **高**  |
| **B** | 知名学者/评论员/媒体人的署名内容       | 可用，需确认作者身份    | **中高** |
| **C** | 一般 UGC（知乎高赞、一般公众号、行业论坛） | 仅作观点参考，必须交叉验证 | **中**  |
| **D** | 百科/未署名自媒体、内容农场          | 极度谨慎，仅用于基础概念  | **低**  |
| **E** | 匿名论坛、营销号、无来源截图          | 不使用           | **极低** |

**知乎/微信公众号/一般百科**：不一刀切排除，但默认降级到 C-D 级，需作者身份验证后提升。

**加载**：`references/02-source-ranking.md` 获取完整分级规则。

***

## 置信度定级（内置标准）

| 等级    | 定义                | 使用规则             |
| ----- | ----------------- | ---------------- |
| **A** | 2+ 权威来源独立确认       | 可直接引用，无需额外说明     |
| **B** | 1 权威来源或 2+ 一般来源一致 | 可引用，建议标注来源       |
| **C** | 单一来源，无矛盾          | 可引用，必须标注"据 X 报道" |
| **D** | 存在矛盾或辟谣信息         | 必须标注争议，不得作为定论    |
| **E** | 明确不实或无法验证         | 不使用，标注"信息不足"     |

**宁少勿假原则**：信息不足时明确标注，不强行生成 A/B 级结论。

**加载**：`references/03-confidence-rubric.md` 获取完整定级标准。

***

## 降级方案（内置适配）

### 场景 1: API 层自检（tencent\_wsa / baidu\_api / tavily 未配置）

* 自动检测 `TENCENTCLOUD_SECRET_ID` / `TENCENTCLOUD_SECRET_KEY`、`BAIDU_API_KEY` 与 `TAVILY_API_KEY` 环境变量

* 已配置的 API 引擎自动启用；未配置的全部跳过时，输出 JSON 的 `tips` 字段给出 `tencent_wsa_missing` / `baidu_api_missing` / `tavily_missing` 提示

* 读到提示时**阻塞式询问用户**，引导按 `references/10-api-setup.md` 完成配置，等待用户明确选择后再继续

* 用户选择跳过时：使用可用 Web 搜索（DuckDuckGo、必应、搜狗）

* 性能影响：结果质量与中文覆盖可能降低，但流程完整

### 场景 2: 无网络连接

* 检测网络可达性

* 不可达时：返回错误提示，建议手动搜索

### 场景 3: 无 Node.js（微信抓取）

* 微信文章抓取失败时跳过

* 普通网页内容不受影响

### 场景 4: 免费引擎（DuckDuckGo/必应/搜狗/头条）反爬或验证码

* 检测验证码、安全验证页或异常跳转

* 标注 `engine_status: blocked`，不当作普通 0 结果

* 不绕过验证码、伪造 Cookie 或使用代理池

**加载**：`references/06-fallback-guide.md` 获取完整降级方案。

***

## 输出规范（Output Spec）

### 默认输出

* **格式**：Markdown（`.md`）+ `claims-json`

* **编码**：UTF-8

* **标题层级**：严格使用 `#` / `##` / `###` / `####`，禁止跳级

* **语言**：跟随用户上下文；引用保留原文，必要时提供翻译或解释

* **语气**：专业、客观、有依据

### 2.1 结构化输出

* **格式**：`claims-json`

* **用途**：跨 agent 交接、benchmark 评估、证据链审计

* **包含**：可信结论、观点地图、常见误区、争议不确定、时间演进、evidence、source reliability、information credibility、freshness、limitations

* **Schema**：`schemas/evidence-pack.schema.json`

* **命令**：`python3 scripts/search_engine.py "query" --mode auto --budget auto --checkpoint auto --verify --output claims-json`

* **宿主输入**：`python3 scripts/search_engine.py "query" --input-results host_results.json --engines none --output claims-json`

* **自检**：`python3 scripts/search_engine.py --doctor`

### 交付方式

| 目标                                 | 处理方式             | 状态 |
| ---------------------------------- | ---------------- | -- |
| **本地 Markdown**                    | 默认保存或输出 `.md` 报告 | 默认 |
| **claims-json**                    | 默认输出可复核证据包       | 默认 |
| **飞书/Notion/Google Docs/Obsidian** | 按用户环境作为可选交付适配    | 可选 |

**加载**：`references/05-output-template.md` 获取输出规范。

***

## 检查点机制（自适应控制）

支持 `--checkpoint auto|batch|interactive`。默认 `auto`：清晰调研可连续执行后汇报阶段摘要；范围模糊、高风险或用户要求控制时切换 `interactive`；明确要求高效完成时使用 `batch`。检查点是质量控制机制，不是所有环境都必须机械停顿。

***

## 版本与元信息

* **当前版本**：v2.1.0

* **发布状态**：v2.1.0 正式版

* **稳定基线**：v2.1.0（2026-07-18）

* **作者**：黄艾伦（那个谁）

* **许可证**：MIT

* **创建日期**：2026-06-05

* **更新日志**：`CHANGELOG.md`

* **跨平台适配**：`references/07-cross-platform.md`（仅接入无专用适配的平台时读取；搜索运行时不加载）

* **MCP-ready**：输出有 JSON Schema，可被任意 agent / MCP server 消费

***

> **方法论来源**：黄艾伦信息搜索方法论（多元验证、反向论证、语义分析） + Nuwa Skill 检查点机制 + Tavily 高级搜索最佳实践 + OSINT / ACH / SIFT / source reliability 方法论审计轨
> **适用平台**：Codex / Claude Code / 通用 Prompt；OpenClaw / Hermes 等作为可选适配示例
> **技术约束**：纯 Python 标准库，零第三方依赖，Python 3.8+
