# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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
