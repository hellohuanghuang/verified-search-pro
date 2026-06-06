# Verified Search Pro · 可信研究助理

> 搜索工具负责“找资料”，Verified Search Pro 负责“验资料”：清洗噪声、核对来源、标注置信度和不确定性。

---

## 项目简介

Verified Search Pro 是一套面向深度调研和事实核查的可信研究 Skill。它不是要替代 Tavily、Exa、Perplexity、Kagi 或普通搜索引擎，而是把多来源资料整理成可复核的证据包和研究结论。

- **资料获取**：可调用 Tavily API（可选增强）+ 百度/必应/搜狗（Web 搜索），也可在无 Tavily 时降级
- **智能融合去重**：URL 归一化 + 内容指纹 + 文本相似度，三重去重
- **反向验证**：提取关键实体，验证结果内容相关性
- **置信度定级**：A-E 五级，从"多权威确认"到"明确不实"
- **信息源分级**：A（权威官方）→ E（匿名论坛），自动权重调整
- **情报分区**：可信结论、观点地图、常见误区、争议不确定、时间演进分别标注
- **默认交付**：Markdown 给人阅读，`claims-json`/evidence-pack 给 agent、测试和后续工作流使用

---

## 适用场景（触发条件）

在以下场景下，本 skill 会自动加载：

| 场景 | 关键词示例 |
|------|-----------|
| **国家公园/文化公园调研** | "国家公园政策" "国家文化公园建设" "保护规划" |
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
- **Agent 零摩擦交接**：agent 只需要调用 `scripts/search_engine.py`，脚本自行检测 Tavily、Node.js 和降级状态，不要求另装搜索插件。
- **上下文预算**：256k 是硬红线，默认 `standard`；`lite / standard / deep` 控制证据数量和摘要长度，给系统提示词、用户任务和后续推理留下空间。
- **非可信材料也有价值**：观点、误区、争议和历史失效信息会进入独立分区，只能作为背景、负面样本、发散线索或趋势材料，不能自动当事实。
- **Google 暂不默认**：Google Custom Search 作为未来可选适配，不进入 2.0 默认能力，避免 API、代理、密钥和网络环境增加公开安装摩擦。

---

## 核心工作流（5 阶 16 步）

### Phase 1: 任务拆解（检查点 1）
- 分析用户意图，拆解信息模块
- 确定搜索策略与引擎组合
- **用户确认后推进**

### Phase 2: 搜索获取（检查点 2）
- 并行调用多引擎搜索
- 原始结果收集
- **用户确认后推进**

### Phase 3: 降噪清洗（检查点 3）
- 信息源分级过滤
- 重复内容去重
- 低质量内容剔除
- **用户确认后推进**

### Phase 4: 验真比对（检查点 4）
- 关键实体交叉验证
- 多源一致性检查
- 矛盾信息标注
- **用户确认后推进**

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
├── scripts/                          ← 可执行脚本（纯 Python 标准库）
│   ├── search_engine.py              ← 主入口：多引擎调度与结果融合
│   ├── html_parser.py                ← HTML 解析器（百度/必应/搜狗）
│   ├── result_fusion.py              ← 结果融合、去重、评分排序
│   ├── cross_verify.py               ← 反向验证与置信度定级
│   ├── trust_model.py                ← 2.0 claim/evidence 可信度结构化模型
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
├── tests/                            ← 标准库 unittest 回归测试
│   ├── test_result_fusion.py
│   ├── test_cross_verify.py
│   ├── test_search_engine_cli.py
│   ├── test_trust_model.py
│   └── test_docs_policy.py
│
├── .claude/
│   └── CLAUDE.md                     ← Claude Code 适配入口
└── .codex/
    └── instructions.md             ← Codex 适配入口
```

---

## 版本信息

- **当前版本**：v1.0.0
- **作者**：黄艾伦（那个谁）
- **许可证**：MIT
- **创建日期**：2026-06-05
- **更新日志**：`CHANGELOG.md`

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
python3 scripts/search_engine.py "query" --engines tavily,baidu,bing --verify

# 预算控制（lite/standard/deep；旧 minimal/balanced/comprehensive 仍兼容）
python3 scripts/search_engine.py "query" --budget deep

# 2.0: 输出 evidence-pack（通过 claims-json 兼容入口）
python3 scripts/search_engine.py "query" --mode research --budget standard --verify --output claims-json

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

## 2.0 开发状态

当前 `main` 是 v1.0.0 基线。2.0 迭代目标是把结果列表升级为 evidence-pack workflow，补齐来源可靠性、内容可信度、反证路径、观点地图、误区标注、时间演进、跨 agent 兼容和 benchmark 评估门禁。

```bash
python3 -m unittest discover -s tests
```

---

*本工具持续迭代中。默认交付为本地 Markdown 与 claims-json，平台文档集成按用户环境选择。*
