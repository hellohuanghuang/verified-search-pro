# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.2] - 2026-07-16

### Fixed

- **必应 Cookie 会话管理 (BUG-001, P0)**：`network.py` 引入 `http.cookiejar.CookieJar` + `HTTPCookieProcessor`，必应搜索前先访问首页建立会话 Cookie，修复特定中文长尾查询（如"如何消除比熊的泪痕"）返回词典降级结果的问题。新增 `warmup_session()` 函数和 `use_cookies` 参数，零外部依赖。
- **n-gram 噪声过滤 (BUG-002, P1)**：`cross_verify.py` 在 scoring_terms 截断前过滤含虚词字符（的、了、是、在等）的 n-gram，使高价值术语（如"泪痕"）进入评分基准前 6，修复因噪声碎片挤占导致验证误判。
- **None 值防御 (BUG-003, P2)**：`cross_verify.py` 和 `result_fusion.py` 中 `result.get("title", "")` 改为 `(result.get("title") or "")`，修复 title/content 为 None 时的 TypeError 崩溃。
- **英文职位词断开 (BUG-004, P2)**：`cross_verify.py` 英文专有名词提取前先在 CEO/CTO/CFO 等职位词处断开，修复 "OpenAI CEO Sam Altman" 被当作单个 term 的问题。

### Added

- 外部测试回归套件 `tests/test_external_regression.py`，覆盖 BUG-001 ~ BUG-004 端到端场景。
- `tests/test_network.py` 新增 Cookie 会话管理测试。
- `tests/test_cross_verify.py` 新增 n-gram 过滤、None 防御、职位词断开测试。

### Tests

- 101 个现有测试全部通过（无回归）。
- 新增 14 个回归测试，总计 115 个测试全部通过。

## [2.0.1] - 2026-07-15

### Fixed

- **search_concepts 早返回 bug**：`extract_entities` 在收到 `search_concepts` 时直接返回 concepts 列表，跳过全部 n-gram 分析，导致中文搜索结果退化。修复为 concepts 追加到 n-gram 结果之后（补充而非替换）。
- **verify_result 评分逻辑**：有 concepts 时用 concepts 作为评分基准（精确），无 concepts 时用截断 n-gram 前 6 个（避免噪声膨胀）。同时加固 None 防御性处理。

### Added

- **中文 n-gram 分词**：将中文查询切分为 2-4 字片段，保留原句整句匹配，只过滤单独出现的停用词，不破坏专有名词和作品名。
- **DuckDuckGo 引擎**：新增 DuckDuckGo HTML 解析器（状态机 + 正则兜底），自动检测验证码页面并标记 blocked。
- **查询相关性过滤**：在 `result_fusion` 中根据查询关键词过滤完全无关的结果，零相关性时自动兜底放行。
- **Tavily 缺失提醒机制**：三层提醒——JSON `tips` 字段供 Agent 读取转告 / CLI stderr 一次性提醒（标记文件静默）/ `--doctor` 输出 4 步配置指引。
- **Agent 指令更新**：CLAUDE.md 和 instructions.md 添加中文查询概念提取指南和 tips 检查指令。

### Changed

- 默认引擎列表更新为 `tavily,duckduckgo,bing_cn,sogou`。
- `--doctor` 的 Tavily 状态增强：未配置时显示影响说明和 4 步配置指引。
- README 新增中文 `--search-concepts` 使用示例、`tips` 字段输出示例、DuckDuckGo 排障条目。

### Tests

- 101 个单元测试全部通过。
- 压力测试 20 项断言全部通过（6 个 extract_entities 场景 + 3 个 verify_result 场景 + 端到端测试）。

## [2.0.0] - 2026-07-14

### Release Status
- v2.0.0 stable release.
- Brings the v2 evidence-pack workflow to production-ready state after configuration, caching, retry, schema, and benchmark hardening.

### Added
- Hierarchical configuration system (`config/default.json`, user config, project config, `VSP_*` environment variables).
- SQLite-backed request cache (`scripts/cache.py`) with TTL and `--no-cache` CLI flag.
- Exponential-backoff retry with `Retry-After` support (`scripts/network.py`).
- `argparse`-based CLI with `--help`, `--version`, and strict parameter validation.
- `html.parser`-based HTML parser with regex fallback for Baidu, Bing, Sogou, and WeChat Sogou.
- Unified domain ranking registry (`scripts/domain_registry.py`) with user override support.
- Same-story (syndication) detection to avoid duplicate-source confidence inflation.
- JSON Schema for evidence-pack output (`schemas/evidence-pack.schema.json`).
- Example scripts (`examples/`) for fact-check, research report, and host-input workflows.
- Benchmark suite (`benchmark/`) with queries, runner, and evaluator.
- Community docs: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, GitHub issue templates.
- New test coverage for HTML parser, config, cache, network, domain registry, and schema.

### Changed
- `SKILL.md` frontmatter now conforms to Anthropic Agent Skills spec (`name`, `description`, `license`, `compatibility`, `metadata`).
- `_meta.json` bumped to `2.0.0` and references the evidence-pack schema.
- `.claude/CLAUDE.md` and `.codex/instructions.md` updated for stable v2.0.0 and MCP-ready output.
- `README.md` rewritten with 5-minute quickstart, output example, troubleshooting, and contribution guide.
- Default CLI behavior now uses configuration system instead of hardcoded constants.

### Fixed
- `--help` now exits 0 and prints usage instead of failing with missing query.
- Unknown CLI arguments now emit a warning instead of being silently ignored.
- URL deduplication now merges source engines instead of dropping duplicates.
- Domain scoring now rejects substring matches (e.g. `fake-reuters.com` does not match `reuters.com`).

### Safety / Performance Notes
- VSP does not attempt to bypass captcha, login walls, cookie checks, or anti-bot systems.
- VSP does not probe every possible engine on each run; it records health only for selected engines and provided host inputs.
- Full content is used only when already supplied or explicitly fetched.
- Cache and retry are implemented with pure Python standard libraries; no new third-party dependencies.

## [2.0.0-alpha.2] - 2026-06-08

### Release Status
- Public alpha update based on real OpenClaw + host-search testing.
- Keeps the implementation lightweight: no embedded Kimi Search runtime, no crawler bypass, no persistent health database.

### Added
- `--input-results` for host-provided search results from environments such as OpenClaw/Kimi agents.
- `--budget auto` with rule-based budget selection for fact checks, standard research, and multidimensional/controversial research.
- `--checkpoint auto|batch|interactive` metadata for adaptive agent workflows.
- Engine health status in JSON/evidence-pack output, including blocked, skipped, failed, empty, and ok states.
- Baidu security-challenge detection so captcha pages are reported as blocked instead of ordinary zero-result searches.
- Source attribution fields for author, source type, host fetch source, original source URL, and full-content availability.

### Changed
- Default budget behavior is now auto-first while preserving manual `lite / standard / deep`.
- Checkpoints are now adaptive rather than mandatory for every environment.
- Host search is documented as an optional input channel, not a public-version dependency.

### Safety / Performance Notes
- VSP does not attempt to bypass captcha, login walls, cookie checks, or anti-bot systems.
- VSP does not probe every possible engine on each run; it records health only for selected engines and provided host inputs.
- Full content is used only when already supplied or explicitly fetched.

## [2.0.0-alpha.1] - 2026-06-07

### Release Status
- Public alpha for the v2 evidence-pack workflow.
- Uses SemVer pre-release versioning so the branch is clearly on the v2 line without claiming stable `2.0.0` readiness.
- Keeps v1.0.0 as the stable baseline while v2 alpha receives benchmark, adapter, and real-task validation.

### Added
- `claims-json`/evidence-pack release story for human-readable Markdown plus machine-readable agent handoff.
- Trust-quality framework covering source reliability, content credibility, contradiction handling, temporal status, and limitations.
- Evaluation benchmark plan and release gates for v2 quality checks.
- Adapter guidance for Codex, Claude Code, generic prompts, and optional OpenClaw / Hermes usage.

### Changed
- Public metadata now advertises `2.0.0-alpha.1`.
- README, SKILL frontmatter, changelog, report template, and adapter docs now describe the same v2 alpha release status.
- OpenClaw, Hermes, Feishu, Notion, Google Docs, and Obsidian are framed as optional adapters rather than required public-version dependencies.

### Known Release Risks
- Alpha has not yet completed broad real-task benchmark coverage.
- Cross-platform adapter docs are aligned, but installation still needs validation in each target agent environment.
- Optional Tavily and Node.js paths can change output quality or feature coverage depending on local credentials and runtime availability.

## [1.0.0] - 2026-06-05

### Added
- Initial production release of Verified Search Pro
- Multi-engine parallel search: Tavily + Baidu + Bing + Sogou
- HTML parsers for Baidu, Bing, Sogou search results (pure Python standard library)
- Result fusion with URL deduplication, content fingerprinting, and text similarity
- Cross-verification with key entity extraction and relevance scoring
- Confidence rubric (A-E levels) with automatic grading
- Source ranking system (A-E tiers) with domain authority scoring
- Automatic fallback to web-only search when Tavily is unavailable
- WeChat article fetching via Node.js subprocess
- Cross-platform support: OpenClaw / Claude Code / Codex / Hermes
- Complete production file structure: _meta.json, LICENSE, README.md, CHANGELOG.md
- Progressive disclosure architecture: references loaded on demand
- Checkpoint mechanism between phases (user confirmation required)

### Technical
- Zero third-party Python dependencies (urllib, threading, json, re, hashlib, difflib)
- ThreadPoolExecutor for parallel engine execution
- Graceful error handling with engine health tracking
- Configurable budget levels: minimal (5 results), balanced (10), comprehensive (20)

### Documentation
- 7 reference documents covering search strategy, source ranking, confidence rubric, noise filtering, output template, fallback guide, and cross-platform adaptation
- Claude Code and Codex adapter files
- Report template for structured output
