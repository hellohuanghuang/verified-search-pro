# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.1.0-beta.1] - 2026-07-17

### Fixed

- **"什么是"疑问前缀未完整剥离 (NEW-BUG-001)**：`scripts/search_engine.py` `_CHINESE_QUESTION_PREFIXES` 添加 `"什么是"` 并置于 `"什么"` 之前，确保最长匹配优先；同时增加边界检查，避免 `"什么时候"` 被误剥离。
- **必应降级标题检测范围过窄 (NEW-BUG-002)**：`scripts/html_parser.py` `_is_question_only_title` 增加降级模式检测（"汉语词语""汉语词典""汉语词汇""百度百科""的意思"），覆盖 `"如何（汉语词语）_百度百科"` 等真实降级标题。
- **engine_status 输出路径不一致 (NEW-BUG-003)**：`scripts/trust_model.py` `build_claim_package` 顶层新增 `engine_status` 字段，与 `--output json` 格式保持一致；嵌套 `search.engine_status` 保留向后兼容。
- **域名库中文权威域空白 (R-3)**：`config/default.json` 新增 10 个中文垂直领域权威域名（丁香医生、LAMCVET、蘑菇宠医、小荷健康、好大夫在线等），并将 cwbaike 标记为内容农场（D 级）。修复中文域名全 `unknown` 导致无法区分权威源和内容农场的问题。
- **繁简未归一导致反向分级 (R-2/R-4)**：`scripts/cross_verify.py` 新增 `_normalize_traditional_chinese()` 函数，内置 200 个常用繁简字对，验证前将繁体中文统一归一为简体中文。修复繁体权威源（LAMCVET、廖斯齊）因字符不匹配被误判为噪声、简体内容农场反而过验证的反向分级问题。
- **research 模式检测失效 (R-7)**：`scripts/trust_model.py` `research_tokens` 补充"调查/报告/综述/评估/比较/对比/现状/发展"等中文词，修复包含这些词的查询被按 fact 模式处理的问题。

### Changed

- **SKILL.md 快速导航**：将"256k 是上下文红线"改为"256k 为上限"，表述更面向用户。
- **宿主搜索定位提升**：`references/01-search-strategy.md` 中宿主搜索从"可选输入"提升为"首选输入源"，所有场景的辅助引擎均加入宿主搜索输入，新增"宿主搜索优先原则"说明。
- **降级优先级调整**：`references/06-fallback-guide.md` 降级优先级中宿主搜索从第 2 位提升到第 1-3 位，明确宿主搜索最可靠。
- **域名兜底规则**：`references/02-source-ranking.md` 新增兜底规则说明（未分类域名 unknown/gov 自动 A 级/edu 自动 A 级/动态评估）。
- **Google 策略表述**：`references/01-search-strategy.md` 从开发备注口吻改为面向用户的说明。
- **版本号残留清理**：`references/07-cross-platform.md` 和 `assets/report-template.md` 中的 v2.0.0-alpha.2 更新为 v2.1.0-beta。

### Added

- 新增 `tests/test_domain_registry_chinese.py`：8 个测试覆盖中文权威域名分级。
- 新增 `tests/test_trust_model.py`：10 个测试覆盖 research 模式检测。
- `tests/test_cross_verify.py` 追加 5 个繁简归一测试：繁体查询/简体内容双向匹配、归一化函数、混合内容。
- `tests/test_v2_1_regression.py` 追加 3 个新发现 bug 修复测试："什么是"前缀剥离、降级标题检测、engine_status 路径。

### Tests

- 148 个测试全部通过（含 26 个新增测试）。

## [2.1.0-beta] - 2026-07-16

### Release Status
- v2.1.0-beta public pre-release.
- Bumps the stable baseline from v1.0.0 to v2.0.0 and adds a batch of agent-experience and Chinese-search quality fixes.

### Added

- **Bing Chinese question-query rewriting** (`scripts/search_engine.py`): when a Chinese query starts with a question word (如何/怎样/怎么/为什么/etc.), VSP now issues multiple variants in parallel — original query, stripped query, concept-quoted query, and English translation — and merges/deduplicates the results.
- **Built-in mini translation dictionary** (`scripts/search_engine.py`): zero-external-API mapping for common Chinese pet/health terms (e.g. 比熊→bichon, 泪痕→tear stains, 消除→remove) used as a Bing international fallback.
- **Bing result-quality guard** (`scripts/search_engine.py` + `scripts/html_parser.py`): detects degraded Bing pages where titles contain only question words and marks the engine as `degraded`; falls back to `bing_int` with an English query.
- **Sogou encrypted-link decryption** (`scripts/html_parser.py`): `parse_sogou` now resolves `/link?url=...` links by following 302 redirects with a HEAD request; on failure it still returns a full `sogou.com` URL for source-ranking instead of a bare relative path.
- **DuckDuckGo HTML POST support and fallback** (`scripts/network.py` + `scripts/search_engine.py`):
  - New `fetch_post_with_retry` helper for POST-friendly HTML endpoints.
  - DuckDuckGo requests carry `DNT: 1` header.
  - If DuckDuckGo is marked `blocked`, VSP automatically falls back to `bing_int`.
  - `config/default.json` adds optional `searxng` engine configuration (disabled by default) for users who want an additional meta-search backend.
- **Mandatory LLM concept extraction** (`SKILL.md`, `.claude/CLAUDE.md`, `.codex/instructions.md`, `scripts/search_engine.py`):
  - Agent instructions now require extracting 2–5 core concepts before calling VSP.
  - Added a thinking template: `用户输入 → 核心概念(concepts) → 查询变体 → 调用 VSP 脚本`.
  - `search_engine.py` emits a stderr warning when a Chinese natural-language query is run without `--search-concepts`.
- **Stronger Tavily setup prompt** (`.claude/CLAUDE.md`, `.codex/instructions.md`):
  - When `tips` contains `tavily_missing`, the agent must stop, explain, explicitly ask the user whether to configure Tavily, and wait for input.
  - Provides concrete steps: https://app.tavily.com → free signup → copy API Key → `export TAVILY_API_KEY=tvly-...` → restart session → `python3 scripts/search_engine.py --doctor`.

### Changed

- **SKILL.md metadata cleanup**: removed "百度" tag and Baidu references; title and version strings now consistently read `v2.1.0-beta`; platform list no longer duplicates `codex`/`claude-code`.
- **README version refresh**: now describes the public version as v2.1.0-beta and updates the design-principles wording to be version-neutral.
- **`_meta.json`**: tags updated to 必应/搜狗/DuckDuckGo, description bumped to v2.1.0-beta.
- **`config/default.json`**: DuckDuckGo URL set to `https://html.duckduckgo.com/html/?q={}` with a `post_url` alternative; optional `searxng` backend added (disabled by default).

### Fixed

- **Bing parser robustness** (`scripts/html_parser.py`): `parse_bing` now recognizes `b_algo`, `b_ans`, `b_ground`, and the `b_results` container; legacy regex fallback covers the same selectors. Titles composed solely of question words are dropped.
- **DuckDuckGo parser coverage** (`scripts/html_parser.py`): strengthened `result__a`, `result__snippet`, and generic `div.result` selectors for the current HTML endpoint.

### Tests

- Added new regression tests covering:
  - Chinese question-query variant generation and Bing quality detection.
  - Sogou encrypted-link normalization/resolution.
  - DuckDuckGo blocked-status fallback logic.
  - Tavily `tavily_missing` tip structure and mandatory-prompt wording.
  - LLM concept-extraction warning when `--search-concepts` is missing for Chinese queries.
- Existing unit-test suite remains green.

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
