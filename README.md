# Verified Search Pro v2.0.1 · 可信研究助理

> 搜索工具负责"找资料"，Verified Search Pro 负责"验资料"：清洗噪声、核对来源、标注置信度和不确定性。
>
> [![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
> [![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)]()
> [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 5 分钟上手

Verified Search Pro 是一个纯 Python 标准库的 AI Skill，无需安装任何依赖即可运行。

### 环境要求

- Python 3.8 或更高版本
- 可选：[`TAVILY_API_KEY`](https://tavily.com/)（没有也能用必应/百度/搜狗降级）
- 可选：Node.js（只在抓取微信文章内容时需要）

### 三步跑起来

```bash
# 1. 克隆仓库
git clone https://github.com/hellohuanghuang/verified-search-pro.git
cd verified-search-pro

# 2. 检查环境
python3 scripts/search_engine.py --doctor

# 3. 生成你的第一份证据包
python3 scripts/search_engine.py "你的查询" --verify --output claims-json
```

### 快速示例

```bash
# 事实核查（轻量）
python3 scripts/search_engine.py "OpenAI CEO 是谁" --budget lite --verify

# 深度调研（更多证据）
python3 scripts/search_engine.py "2026 年固态电池技术路线" --budget deep --verify --output claims-json

# 中文自然语言查询：先提取概念再搜索（推荐）
python3 scripts/search_engine.py "如何消除比熊的泪痕" \
  --search-concepts "比熊,泪痕,消除方法" --verify --output claims-json

# 用 agent 已经搜到的结果做质检
python3 scripts/search_engine.py "你的查询" --input-results host_results.json --engines none --output claims-json
```

跑完测试：

```bash
python3 -m unittest discover -s tests
```

---

## 项目简介

Verified Search Pro 是一套面向深度调研和事实核查的可信研究 Skill。当前公开版本是 **v2.0.1**：在 v2.0.0 稳定版基础上新增中文搜索优化、DuckDuckGo 引擎、Tavily 缺失提醒机制和 search_concepts 补充修复。

它不是要替代 Tavily、Exa、Perplexity、Kagi 或普通搜索引擎，而是把多来源资料整理成可复核的证据包和研究结论。

- **资料获取**：可调用 Tavily API（可选增强）+ 必应/搜狗/DuckDuckGo（Web 搜索），也可在无 Tavily 时降级
- **中文搜索优化**：n-gram 分词（2-4 字切片）+ `--search-concepts` 由 AI 提取核心关键词补充，避免中文整句匹配噪声
- **Tavily 缺失提醒**：未配置 Tavily 时自动在 JSON 输出 `tips` 字段，Agent 读取后自然提醒用户配置
- **宿主搜索输入**：OpenClaw/Kimi 等 agent 已经搜到的结果可通过 `--input-results` 交给 VSP 质检
- **智能融合去重**：URL 归一化 + 内容指纹 + 文本相似度 + 查询相关性过滤，四重去重
- **反向验证**：提取关键实体（n-gram + concepts），验证结果内容相关性
- **置信度定级**：A-E 五级，从"多权威确认"到"明确不实"
- **信息源分级**：A（权威官方）→ E（匿名论坛），自动权重调整
- **情报分区**：可信结论、观点地图、常见误区、争议不确定、时间演进分别标注
- **默认交付**：Markdown 给人阅读，`claims-json`/evidence-pack 给 agent、测试和后续工作流使用

---

## 输出示例

`--output claims-json` 会输出一个结构化证据包，关键字段如下：

```json
{
  "schema_version": "v2-alpha.evidence-pack",
  "query": "你的查询",
  "research_mode": "fact",
  "search": { "budget": "lite", "evidence_returned": 5 },
  "claims": [{ "claim": "你的查询", "confidence": "B", "supporting_evidence": ["ev-1", "ev-2"] }],
  "trusted_conclusions": [...],
  "perspective_map": { "items": [...] },
  "common_misconceptions": [...],
  "controversies_uncertainties": { "items": [...] },
  "temporal_evolution": [...],
  "evidence": [
    {
      "evidence_id": "ev-1",
      "url": "https://example.com/article",
      "title": "...",
      "snippet": "...",
      "source_reliability": { "grade": "A", "label": "authoritative source" },
      "information_credibility": { "grade": "1", "label": "confirmed by other sources" },
      "freshness": { "status": "current", "age_days": 12 }
    }
  ],
  "limitations": [...],
  "tips": [
    {
      "level": "info",
      "code": "tavily_missing",
      "msg": "Tavily AI 搜索未配置，当前仅使用 Web 搜索...",
      "setup_url": "https://app.tavily.com"
    }
  ],
  "agent_handoff": { "recommended_use": [...], "do_not_promote_to_fact": [...] }
}
```

需要人读报告时，使用 `--output md` 或参考 `assets/report-template.md`。

---

## 适用场景（触发条件）

在以下场景下，本 skill 会自动加载：

| 场景 | 关键词示例 |
|------|-----------|
| **深度调研** | "调研 XX 行业" "XX 赛道分析" "市场研究" |
| **信息验真** | "验证一下" "这是真的吗" "确认信息" "辟谣" |
| **竞品追踪** | "竞品分析" "对手动态" "行业对比" |
| **政策追踪** | "最新政策" "法规变化" "监管动态" |
| **人物/机构背调** | "背景调查" "公司信息" "创始人履历" |
| **多源比对** | "多搜一下" "交叉验证" "不同来源" |

---

## 如何使用

### 通用使用

1. 将本 skill 目录放入目标 agent 支持的 skills/tools 目录
2. 确保 Python 3.8+ 可用
3. 运行 `python3 scripts/search_engine.py "query" --verify --output claims-json` 生成证据包
4. 需要人读报告时使用 Markdown 输出或 `assets/report-template.md`

### Claude Code

1. 将 `.claude/CLAUDE.md` 复制到项目根目录的 `.claude/` 文件夹
2. Claude Code 自动读取并应用上下文

### Codex

1. 将 `.codex/instructions.md` 复制到项目根目录的 `.codex/` 文件夹
2. Codex 自动加载系统指令

### 其他平台（通用 Prompt）

将 `references/07-cross-platform.md` 中的通用 Prompt 模板作为 system prompt 注入。

### OpenClaw（可选示例）

OpenClaw 只是一个可选适配示例，不是公开版必需环境。若用户使用 OpenClaw，可将 `scriptPath` 指向本仓库内的 `scripts/search_engine.py`。

---

## 2.0 设计原则

- **不是普通搜索器**：搜索 API 负责找资料，本 Skill 负责把资料变成可复核、可交接、可审计的证据包。
- **Agent 零摩擦交接**：agent 可直接调用 `scripts/search_engine.py`，也可先用宿主搜索，再通过 `--input-results` 交给 VSP 做 evidence-pack。
- **上下文预算**：256k 是硬红线，默认 `auto`；轻量规则选择 `lite / standard / deep`，给系统提示词、用户任务和后续推理留下空间。
- **自适应检查点**：默认 `auto`，清晰调研可连续执行后汇报；模糊、高风险或用户要求控制时使用 `interactive`。
- **非可信材料也有价值**：观点、误区、争议和历史失效信息会进入独立分区，只能作为背景、负面样本、发散线索或趋势材料，不能自动当事实。
- **Google 暂不默认**：Google Custom Search 作为未来可选适配，不进入 2.0 默认能力，避免 API、代理、密钥和网络环境增加公开安装摩擦。
- **反爬边界**：百度/微信验证码或安全验证会被标注为 blocked，不做绕过验证码、伪造 Cookie 或代理池。

---

## 核心工作流（5 阶 16 步）

### Phase 1: 任务拆解（检查点 1）
- 分析用户意图，拆解信息模块
- 确定搜索策略与引擎组合
- 根据 `--checkpoint auto|batch|interactive` 判断是否需要用户确认

### Phase 2: 搜索获取（检查点 2）
- 并行调用多引擎搜索
- 读取可选宿主搜索 JSON 输入
- 原始结果收集
- 记录 engine health，区分 blocked、skipped、failed、empty、ok

### Phase 3: 降噪清洗（检查点 3）
- 信息源分级过滤
- 重复内容去重
- 低质量内容剔除
- `batch` 模式下不中断，但最终报告必须说明处理结果

### Phase 4: 验真比对（检查点 4）
- 关键实体交叉验证
- 多源一致性检查
- 矛盾信息标注
- 高风险或范围模糊时切换到 `interactive`

### Phase 5: 要点定锚与交付
- 置信度定级（A-E）
- 要点锚定（核心结论）
- 生成 Markdown 报告和 `claims-json` 证据包
- 默认本地交付；飞书、Notion、Google Docs、Obsidian 等作为可选适配

---

## 文件结构

```
verified-search-pro/
├── SKILL.md                          ← 核心入口（触发条件 + 工作流导航）
├── _meta.json                        ← 元数据（版本、作者、平台适配）
├── LICENSE                           ← MIT 许可证
├── CHANGELOG.md                      ← 版本变更日志
├── README.md                         ← 本文件
│
├── config/                           ← 默认配置与用户可覆盖项
│   └── default.json                  ← 默认配置（引擎、域名评级、预算）
│
├── scripts/                          ← 可执行脚本（纯 Python 标准库）
│   ├── search_engine.py              ← 主入口：多引擎调度与结果融合
│   ├── html_parser.py                ← HTML 解析器（必应/搜狗/DuckDuckGo，html.parser + 正则兜底）
│   ├── result_fusion.py              ← 结果融合、去重、评分排序、same-story 检测
│   ├── cross_verify.py               ← 反向验证与置信度定级
│   ├── trust_model.py                ← 2.0 claim/evidence 可信度结构化模型
│   ├── domain_registry.py            ← 统一域名评级注册表
│   ├── config.py                     ← 分层配置加载器
│   ├── cache.py                      ← SQLite 请求缓存
│   ├── network.py                    ← 指数退避重试网络层
│   ├── tavily_adapter.py             ← Tavily API 适配器（可选）
│   └── wechat_fetch.py               ← 微信文章抓取（调用 Node.js）
│
├── references/                       ← 核心知识库（按需加载）
│   ├── 01-search-strategy.md         ← 搜索策略与引擎选择指南
│   ├── 02-source-ranking.md         ← 信息源五级分类（A-E）与使用规则
│   ├── 03-confidence-rubric.md      ← 置信度定级标准（A-E 详细定义）
│   ├── 04-noise-filtering.md        ← 降噪与验真流程
│   ├── 05-output-template.md         ← 输出模板规范
│   ├── 06-fallback-guide.md         ← 降级方案（无 Tavily / 无网络）
│   ├── 07-cross-platform.md         ← 跨平台迁移指南
│   ├── 08-trust-quality-framework.md ← 2.0 可信搜索方法论框架
│   └── 09-evaluation-benchmark.md   ← 2.0 评估基准与发布门禁
│
├── assets/                           ← 模板资源
│   └── report-template.md            ← 搜索报告 Markdown 模板
│
├── schemas/                          ← 结构化输出 Schema
│   └── evidence-pack.schema.json     ← evidence-pack / claims-json JSON Schema
│
├── examples/                         ← 可直接运行的示例脚本
│   ├── fact_check.sh
│   ├── research_report.sh
│   └── host_input.sh
│
├── benchmark/                        ← 可复验 benchmark
│   ├── queries.json
│   ├── run.py
│   └── evaluate.py
│
├── tests/                            ← 标准库 unittest 回归测试
│   ├── test_result_fusion.py
│   ├── test_cross_verify.py
│   ├── test_search_engine_cli.py
│   ├── test_trust_model.py
│   ├── test_html_parser.py
│   ├── test_config.py
│   ├── test_cache.py
│   ├── test_network.py
│   ├── test_domain_registry.py
│   ├── test_schema.py
│   └── test_docs_policy.py
│
├── .claude/
│   └── CLAUDE.md                     ← Claude Code 适配入口
├── .codex/
│   └── instructions.md               ← Codex 适配入口
└── .github/                          ← GitHub issue 模板
    └── ISSUE_TEMPLATE/
```

---

## 版本信息

- **当前版本**：v2.0.1
- **稳定基线**：v2.0.0（2026-07-14）
- **作者**：黄艾伦（那个谁）
- **更新日志**：`CHANGELOG.md`

---

## Roadmap

| 版本 | 目标 |
|------|------|
| v2.1 | 更智能的查询拆分与主管-子代理研究模式；SearXNG 引擎适配 |
| v2.2 | 可选 MCP server 包装，暴露为标准化工具 |
| v3.0 | 考虑引入轻量语义模型做观点聚类（可能引入可选第三方依赖） |

---

## 技术说明

### 跨平台兼容性

| 平台 | 依赖要求 | 状态 |
|------|---------|------|
| 通用 Prompt | Python 3.8+ | ✅ 默认支持 |
| Claude Code | Python 3.8+ | ✅ 适配 |
| Codex | Python 3.8+ | ✅ 适配 |
| OpenClaw / Hermes | Python 3.8+ | 可选适配示例 |

### 外部依赖

- **Tavily**：可选。`TAVILY_API_KEY` 环境变量配置时启用，缺失时自动降级为纯 Web 搜索
- **Node.js**：仅微信文章抓取时需要。缺失时跳过微信内容抓取
- **Python 包**：零第三方包依赖，仅使用标准库（`urllib`, `threading`, `json`, `re`, `hashlib`, `difflib`）

---

## 使用示例

```bash
# 基础搜索（自动选择引擎）
python3 scripts/search_engine.py "小鹏汽车 VLA2.0 激光雷达"

# 多引擎 + 反向验证
python3 scripts/search_engine.py "query" --engines tavily,bing_cn --verify

# 预算控制（lite/standard/deep；旧 minimal/balanced/comprehensive 仍兼容）
python3 scripts/search_engine.py "query" --budget deep

# 自动预算 + 自适应检查点
python3 scripts/search_engine.py "query" --budget auto --checkpoint auto

# 2.0: 输出 evidence-pack（通过 claims-json 兼容入口）
python3 scripts/search_engine.py "query" --mode research --budget auto --verify --output claims-json

# 宿主搜索输入：例如 OpenClaw/Kimi agent 已经搜到的结果
python3 scripts/search_engine.py "query" --input-results host_results.json --engines none --output claims-json

# 首次运行自检
python3 scripts/search_engine.py --doctor

# 抓取微信文章内容
python3 scripts/search_engine.py "query" --fetch-content
```

---

## 方法论来源

- 黄艾伦信息搜索方法论（多元验证、反向论证、语义分析）
- Nuwa Skill 检查点机制与质量控制
- Tavily 高级搜索 API 最佳实践
- OSINT / ACH / SIFT / source reliability 方法论审计轨（见 `references/08-trust-quality-framework.md`）

## v2.0.1 更新说明

v2.0.1 是基于 v2.0.0 稳定版的问题修复和体验优化版本，主要解决中文搜索质量问题：

- **中文 n-gram 分词**：将中文查询切分为 2-4 字片段，避免整句匹配导致的噪声
- **search_concepts 补充机制**：AI 提取的核心关键词作为补充追加到 n-gram 结果，而非替换（修复了导致结果退化的关键 bug）
- **DuckDuckGo 引擎**：新增 DuckDuckGo HTML 解析器，作为 Tavily 不可用时的额外搜索源
- **查询相关性过滤**：在结果融合阶段过滤与搜索词完全无关的结果
- **Tavily 缺失提醒**：三层提醒机制（JSON tips → Agent 转告 / CLI stderr 一次性 / --doctor 配置指引）
- **验证评分双轨制**：有 concepts 时用精确概念评分，无 concepts 时用截断 n-gram 评分

101 个单元测试全部通过，压力测试 20 项断言全部通过。

## 常见失败排查

| 现象 | 原因 | 解决方案 |
|------|------|---------|
| 百度/搜狗返回 0 结果或 engine_status 显示 `blocked` | 搜索页面触发了验证码或安全验证 | 换 `--engines bing_cn` 或 `--engines tavily` 重试；这不是 bug，VSP 不会绕过验证码 |
| Tavily 没有返回结果 | 没有配置 `TAVILY_API_KEY` | 这是正常的，工具会自动降级为 Web 搜索；如需 Tavily，到 [tavily.com](https://tavily.com/) 申请免费 key；未配置时 VSP 会在 JSON 输出 `tips` 字段提醒，`--doctor` 可查看完整配置步骤 |
| DuckDuckGo 结果为空 | 触发了反爬验证码 | VSP 会自动检测验证码页面并标记 blocked，切换到其他引擎重试 |
| 微信文章抓取失败 | 当前环境没有 Node.js | 普通网页搜索不受影响；只有 `--fetch-content` 需要 Node.js |
| 输出 JSON 为空或 confidence 为 E | 查询太具体、网络不可达或所有引擎被 block | 检查 `--doctor` 输出，换更通用查询，或手动准备 `--input-results` |
| `--help` 不工作 / 非法参数被静默忽略 | 你当前可能在使用旧版本 | 请确认在最新版仓库中运行，旧版 CLI 使用手写参数解析 |

如果仍无法解决，欢迎提交 issue 时附上 `python3 scripts/search_engine.py --doctor` 的输出。

---

## 如何贡献

我们非常欢迎贡献！小白开发者也可以从下面几步开始：

1. **Fork 仓库** 并 clone 到本地。
2. **跑测试**：`python3 -m unittest discover -s tests`，确保全部通过。
3. **选一个 issue**：推荐先看 `good first issue` 标签。
4. **先写测试再改代码**：保持测试先行，确保不回归。
5. **提交 PR**：在 PR 描述里说明改动原因和验证方式。

常见贡献方向：

- 补充搜索引擎的 HTML fixture 和测试
- 增加新的可信域名到 source ranking
- 提交 benchmark 查询和 golden report
- 改进文档，让小白更容易上手

详细贡献指南见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

---

```bash
python3 -m unittest discover -s tests
```

---

*本工具持续迭代中。默认交付为本地 Markdown 与 claims-json，平台文档集成按用户环境选择。*
