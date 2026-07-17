# 跨平台适配指南

## 版本状态

- **当前公开版本**：v2.1.0-beta
- **发布状态**：v2.1.0-beta 测试版；用于验证 evidence-pack workflow、跨 agent 适配和 benchmark 门禁，不标记为稳定生产版。
- **稳定基线**：v1.0.0（2026-06-05）

## 默认原则

本 Skill 的公开版不绑定任何个人环境。默认依赖是 Python 3.8+、本地 Markdown 报告和 `claims-json`/evidence-pack 证据包；平台文档工具只作为可选交付适配。

宿主搜索工具（例如 OpenClaw/Kimi 环境内置搜索）通过 `--input-results` 输入 VSP，不作为公开版默认依赖，也不由 VSP 直接控制。

## 平台适配矩阵

| 平台 | 入口文件 | 加载方式 | 依赖 |
|------|---------|---------|------|
| **通用 Prompt** | `SKILL.md` / 本文件模板 | 注入 system prompt 或工具说明 | Python 3.8+ |
| **Claude Code** | `.claude/CLAUDE.md` | 放置于项目 `.claude/` 目录 | Python 3.8+ |
| **Codex** | `.codex/instructions.md` | 放置于项目 `.codex/` 目录 | Python 3.8+ |
| **OpenClaw / Hermes** | `SKILL.md` | 作为可选平台示例适配 | Python 3.8+ |

## 通用 Prompt 模板

```markdown
You are a verified search assistant. Your task is to execute multi-engine search,
result fusion, cross-verification, confidence grading, non-factual material labeling,
temporal tracking, and compact agent handoff.

Release status: Verified Search Pro v2.1.0-beta. Treat v1.0.0
as the stable baseline and do not present this beta as a stable production release.

## Workflow (5 phases, 16 steps)

### Phase 1: Task Decomposition
- Analyze user intent
- Break down information modules
- Determine search strategy
- Generate search queries
- **CHECKPOINT 1**: Use checkpoint=interactive when scope is unclear; batch can continue and summarize

### Phase 2: Search Acquisition
- Parallel search: selected engines only; optionally read host search input via --input-results
- Collect raw results with metadata
- Record engine_status: ok, empty, blocked, skipped, failed

### Phase 3: Noise Filtering
- URL deduplication
- Content fingerprint deduplication
- Text similarity deduplication
- Source ranking filtering
- In batch mode, do not interrupt; summarize filtering in final report

### Phase 4: Verification
- Extract key entities
- Cross-verify results
- Check multi-source consistency
- Grade confidence (A-E)
- Use interactive mode for high-risk or ambiguous tasks

### Phase 5: Delivery
- Anchor key findings
- Generate a Markdown report for humans and claims-json/evidence-pack for agents
- Separate trusted conclusions, perspective map, common misconceptions, controversies/uncertainties, and temporal evolution
- Deliver locally by default; use Feishu, Notion, Google Docs, or Obsidian only when the user environment supports it

## Source Ranking (A-E)
- A: Government/official/academic (high confidence)
- B: Named experts/verified authors (medium-high)
- C: General UGC (opinion only, cross-verify)
- D: Encyclopedia/unsigned (concept only)
- E: Anonymous/forums (do not use)

## Confidence Rubric (A-E)
- A: 2+ authoritative sources confirm
- B: 1 authoritative or 2+ general sources
- C: Single source, no contradiction
- D: Contradiction or disputed
- E: Unverified or debunked

## Principles
- "Better less than fake": Mark insufficient info clearly
- "Never fill gaps with speculation"
- "Always cite sources"
- "Flag contradictions, don't judge"
- Keep context below the 256k red line; use lite / standard / deep budgets
- Prefer --budget auto unless the user explicitly asks for a larger or smaller pack
- Use --checkpoint auto by default; batch for clear direct research, interactive for high-risk or ambiguous work
- Never promote perspective_map, common_misconceptions, controversies_uncertainties, or stale temporal items into facts

## Fallbacks
- No Tavily API key: Use web-only search
- No network: Prompt user for manual search
- No Node.js: Skip WeChat fetching
- Google is not enabled by default; treat it as a future optional adapter
- Baidu/WeChat captcha or security pages: mark blocked, do not bypass
- Host search: accepted only as --input-results JSON
```

## 文件迁移步骤

### 通用安装

1. 复制整个 skill 目录到目标 agent 支持的位置
2. 确保 `scripts/search_engine.py` 可从该目录运行
3. 默认使用 Markdown 和 `claims-json` 交付，不要求任何文档平台账号

### 宿主搜索输入

如果 OpenClaw、Kimi agent 或其他宿主环境已经完成搜索，将结果导出为 JSON 后再交给 VSP：

```bash
python3 scripts/search_engine.py "query" --input-results host_results.json --engines none --output claims-json
```

最低字段为 `url`、`title`、`content`、`engine`；可选字段为 `published_at`、`full_content`、`fetch_source`、`author`、`source_type`。

### Claude Code / Codex

1. Claude Code 可读取 `.claude/CLAUDE.md`
2. Codex 可读取 `.codex/instructions.md`
3. 两者都应引用同一套 `scripts/`、`references/` 和 `assets/`

### OpenClaw / Hermes 可选适配

如用户环境支持 OpenClaw 或 Hermes，可将平台配置指向仓库内的 `scripts/search_engine.py`。不要假设所有用户都有这些平台或相同路径。

### 注意事项

- **路径问题**: 使用相对仓库路径，避免写入个人机器路径
- **依赖问题**: 确保 Python 标准库可用（urllib, threading, json, re, hashlib, difflib）
- **Tavily**: 需要 API Key，无 Key 时降级为 Web 搜索
- **Node.js**: 仅微信抓取需要，无 Node.js 时跳过
- **Google**: 暂不进入默认能力；未来可作为显式配置的可选适配
- **百度/微信反爬**: 只标注 blocked 并降级，不绕过验证码或登录限制
- **自检**: `python3 scripts/search_engine.py --doctor`
