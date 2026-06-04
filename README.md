# Verified Search Pro · 生产级多引擎验证搜索

> 从"搜到信息"到"确认信息"。多引擎并行、自动融合去重、反向验证、置信度定级。

---

## 项目简介

Verified Search Pro 是一套面向深度调研、信息验真、竞品追踪的生产级搜索系统。

**核心能力**：
- **多引擎并行搜索**：Tavily（AI 搜索）+ 百度/必应/搜狗（Web 搜索）
- **智能融合去重**：URL 归一化 + 内容指纹 + 文本相似度，三重去重
- **反向验证**：提取关键实体，验证结果内容相关性
- **置信度定级**：A-E 五级，从"多权威确认"到"明确不实"
- **信息源分级**：A（权威官方）→ E（匿名论坛），自动权重调整
- **降级适配**：无 Tavily 时自动切换为纯 Web 引擎，无外部依赖时可用标准库运行

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

### OpenClaw（原生平台）

1. 将本 skill 目录复制到 OpenClaw 的 skills 目录
2. 配置 `skills.entries.verified-search-pro.scriptPath` 指向 `scripts/search_engine.py`
3. 在对话中提及上述触发关键词，AI 自动加载 SKILL.md 并按工作流执行

### Claude Code

1. 将 `.claude/CLAUDE.md` 复制到项目根目录的 `.claude/` 文件夹
2. Claude Code 自动读取并应用上下文

### Codex

1. 将 `.codex/instructions.md` 复制到项目根目录的 `.codex/` 文件夹
2. Codex 自动加载系统指令

### 其他平台（通用 Prompt）

将 `references/07-cross-platform.md` 中的通用 Prompt 模板作为 system prompt 注入。

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
- 生成结构化报告
- 交付飞书文档或本地文件

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
│   └── 07-cross-platform.md         ← 跨平台迁移指南
│
├── assets/                           ← 模板资源
│   └── report-template.md            ← 搜索报告 Markdown 模板
│
├── .claude/
│   └── CLAUDE.md                     ← Claude Code 适配入口
└── .codex/
    └── instructions.md             ← Codex 适配入口
```

---

## 版本信息

- **当前版本**：v1.0.0
- **作者**：黄艾伦（黄璜）的AI助理 · 小A
- **许可证**：MIT
- **创建日期**：2026-06-05
- **更新日志**：`CHANGELOG.md`

---

## 技术说明

### 跨平台兼容性

| 平台 | 依赖要求 | 状态 |
|------|---------|------|
| OpenClaw | Python 3.8+ | ✅ 原生支持 |
| Claude Code | Python 3.8+ | ✅ 适配 |
| Codex | Python 3.8+ | ✅ 适配 |
| Hermes | Python 3.8+ | ✅ 适配 |

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

# 预算控制（minimal/balanced/comprehensive）
python3 scripts/search_engine.py "query" --budget comprehensive

# 抓取微信文章内容
python3 scripts/search_engine.py "query" --fetch-content
```

---

## 方法论来源

- 黄艾伦信息搜索方法论（多元验证、反向论证、语义分析）
- Nuwa Skill 检查点机制与质量控制
- Tavily 高级搜索 API 最佳实践

---

*本工具持续迭代中。欢迎通过飞书或邮件反馈建议。*
