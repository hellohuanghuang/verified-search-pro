# Verified Search Pro v2.1.1 · Trusted Research Assistant

> Search tools *find* material. Verified Search Pro *verifies* it — cleaning noise, cross-checking sources, and labeling confidence and uncertainty.
>
> [![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
> [![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)]()
> [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**中文文档**：[`README.md`](README.md) · **Version**: v2.1.1 (stable baseline: v2.1.1)

> **Positioning note**: VSP is Chinese-first. Default engines, the domain registry, and all report copy target Chinese research workflows. English queries are fully supported via Tavily and Bing International, but the default free fallbacks (Sogou, Bing CN) are optimized for Chinese.

---

## 5-Minute Quickstart

Verified Search Pro is a pure-Python-standard-library AI Skill. No dependencies to install.

### Requirements

- Python 3.8+
- Optional API engine keys — [`TAVILY_API_KEY`](https://tavily.com/) (international/English), `TENCENTCLOUD_SECRET_ID` + `TENCENTCLOUD_SECRET_KEY` (Tencent Cloud WSA, Chinese primary), `BAIDU_API_KEY` (Baidu Qianfan AI Search). With none configured, free web engines (DuckDuckGo / Bing CN / Sogou) still work — see `references/10-api-setup.md` (Chinese) for setup steps.
- Optional: Node.js (only needed to fetch full WeChat article content)

### Three steps

```bash
# 1. Clone
git clone https://github.com/hellohuanghuang/verified-search-pro.git
cd verified-search-pro

# 2. Check your environment
python3 scripts/search_engine.py --doctor

# 3. Generate your first evidence pack
python3 scripts/search_engine.py "your query" --verify --output claims-json
```

### Quick examples

```bash
# Fact check (lightweight)
python3 scripts/search_engine.py "who is the CEO of OpenAI" --budget lite --verify

# Deep research (more evidence)
python3 scripts/search_engine.py "solid-state battery technology roadmap 2026" \
  --budget deep --verify --output claims-json

# Chinese natural-language query: extract concepts first (recommended)
python3 scripts/search_engine.py "如何消除比熊的泪痕" \
  --search-concepts "比熊,泪痕,消除方法" --verify --output claims-json

# Quality-check results your agent already found
python3 scripts/search_engine.py "your query" --input-results host_results.json \
  --engines none --output claims-json
```

Run the tests:

```bash
python3 -m unittest discover -s tests
```

---

## What It Is

Verified Search Pro is a trusted-research Skill for deep research and fact-checking. Current release **v2.1.1** adds, on top of the v2.0.0 stable line: two new API engines (Tencent Cloud WSA and Baidu Qianfan, joining Tavily as the Tier-1 primary layer with automatic skip when unconfigured), Chinese search optimization, a DuckDuckGo engine with fallback, Bing Chinese question-query rewriting, Sogou link decryption, a low-frequency Toutiao engine, Chinese-localized limitation labels, mandatory LLM concept extraction, a stronger Tavily setup prompt — all while keeping zero third-party dependencies.

It does not replace Tavily, Exa, Perplexity, Kagi, or general search engines; it turns multi-source material into reviewable evidence packs and research conclusions.

- **Acquisition — host search first**: results your agent environment already found can be quality-checked via `--input-results` (with `--engines none` VSP needs no built-in engine at all — the most fundamental fallback); on top of that, optional API engines (Tavily / Tencent WSA / Baidu Qianfan) + free web engines (DuckDuckGo / Bing / Sogou) with graceful degradation
- **Chinese optimization**: n-gram segmentation (2–4 chars) + `--search-concepts` for AI-extracted keywords, avoiding whole-sentence matching noise
- **Missing-key guidance**: when an API engine is not configured, the JSON output carries a `tips` field so agents can naturally prompt the user to set it up
- **Host search input**: results already gathered by OpenClaw/Kimi agents can be quality-checked via `--input-results`
- **Smart fusion & dedup**: URL normalization + content fingerprint + text similarity + query-relevance filtering
- **Reverse verification**: key-entity extraction (n-gram + concepts) to verify content relevance
- **Confidence grading**: A–E, from "confirmed by multiple authorities" to "clearly false"
- **Source ranking**: A (authoritative/official) → E (anonymous forums), with automatic weighting
- **Intelligence sections**: trusted conclusions, perspective map, common misconceptions, controversies & uncertainties, temporal evolution — separately labeled
- **Default deliverables**: Markdown for humans, `claims-json` / evidence-pack for agents, tests, and downstream workflows

---

## Output Example

`--output claims-json` produces a structured evidence pack:

```json
{
  "schema_version": "v2-alpha.evidence-pack",
  "query": "your query",
  "research_mode": "fact",
  "search": { "budget": "lite", "evidence_returned": 5 },
  "claims": [{ "claim": "your query", "confidence": "B", "supporting_evidence": ["ev-1", "ev-2"] }],
  "trusted_conclusions": [],
  "perspective_map": { "items": [] },
  "common_misconceptions": [],
  "controversies_uncertainties": { "items": [] },
  "temporal_evolution": [],
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
  "limitations": [],
  "tips": [
    {
      "level": "info",
      "code": "tavily_missing",
      "msg": "Tavily AI search is not configured; using web search only...",
      "setup_url": "https://app.tavily.com"
    }
  ],
  "agent_handoff": { "recommended_use": [], "do_not_promote_to_fact": [] }
}
```

For human-readable reports, use `--output md` or see `assets/report-template.md`.

---

## When It Triggers

| Scenario | Example phrasings |
|---|---|
| **Deep research** | "research the XX industry" "market analysis" |
| **Fact checking** | "verify this" "is this true" "debunk" |
| **Competitor tracking** | "competitive analysis" "industry comparison" |
| **Policy tracking** | "latest policy" "regulatory changes" |
| **Background checks** | "company background" "founder history" |
| **Multi-source comparison** | "search more sources" "cross-verify" |

---

## How to Use

### General

1. Place this skill directory into your agent's skills/tools directory
2. Ensure Python 3.8+ is available
3. Run `python3 scripts/search_engine.py "query" --verify --output claims-json`
4. Use Markdown output or `assets/report-template.md` for human-readable reports

### Claude Code

1. Copy `.claude/CLAUDE.md` into your project's `.claude/` folder
2. Claude Code picks it up automatically

### Codex

1. Copy `.codex/instructions.md` into your project's `.codex/` folder
2. Codex loads it as system instructions

### Other platforms (generic prompt)

Inject the generic prompt template from `references/07-cross-platform.md` as a system prompt.

### OpenClaw (optional example)

OpenClaw is an optional adapter example, not a requirement. Point `scriptPath` to `scripts/search_engine.py` in this repository.

---

## Design Principles

- **Not a plain searcher**: search APIs find material; this Skill turns material into reviewable, handoff-ready, auditable evidence packs.
- **Zero-friction agent handoff**: call `scripts/search_engine.py` directly, or search with the host first and pass results via `--input-results`.
- **Context budget**: 256k is a hard ceiling; `auto` by default, with rule-based `lite / standard / deep` selection.
- **Adaptive checkpoints**: `auto` by default; switch to `interactive` for ambiguous, high-risk, or user-controlled tasks.
- **Non-trusted material still has value**: opinions, misconceptions, controversies, and stale information go into separate sections — background, negative samples, leads, or trend material — never auto-promoted to fact.
- **Google not default**: Google Custom Search remains a future optional adapter to avoid API/proxy/key friction for public installs.
- **Anti-bot boundaries**: captcha or security-check pages (Bing/Sogou/WeChat/Toutiao) are marked `blocked`; no captcha bypass, no forged cookies, no proxy pools.

---

## Core Workflow (5 phases, 16 steps)

### Phase 1: Task Decomposition (checkpoint 1)
- Analyze user intent, decompose information modules
- Choose search strategy and engine combination
- `--checkpoint auto|batch|interactive` decides whether user confirmation is needed

### Phase 2: Search & Acquisition (checkpoint 2)
- Parallel multi-engine search
- Read optional host-search JSON input
- Collect raw results
- Record engine health: `blocked / skipped / failed / empty / ok`

### Phase 3: Noise Reduction (checkpoint 3)
- Source-tier filtering
- Duplicate removal
- Low-quality content pruning
- `batch` mode never interrupts but the final report must disclose what was done

### Phase 4: Verification (checkpoint 4)
- Key-entity cross-verification
- Multi-source consistency checks
- Contradiction labeling
- Switch to `interactive` on high-risk or ambiguous scope

### Phase 5: Anchoring & Delivery
- Confidence grading (A–E)
- Key-point anchoring (core conclusions)
- Markdown report + `claims-json` evidence pack
- Local delivery by default; Feishu, Notion, Google Docs, Obsidian as optional adapters

---

## File Structure

```
verified-search-pro/
├── SKILL.md                          ← Core entry (triggers + workflow navigation)
├── _meta.json                        ← Metadata (version, author, platform adapters)
├── LICENSE                           ← MIT
├── CHANGELOG.md                      ← Version history
├── README.md                         ← Chinese documentation
├── README_EN.md                      ← This file
│
├── config/                           ← Hierarchical configuration
│   └── default.json                  ← Defaults (engines, domain tiers, budgets)
│
├── scripts/                          ← Executables (pure Python standard library)
│   ├── search_engine.py              ← Main entry: engine orchestration & fusion
│   ├── html_parser.py                ← HTML parsers (Bing/Sogou/DuckDuckGo/Toutiao)
│   ├── result_fusion.py              ← Fusion, dedup, scoring, same-story detection
│   ├── cross_verify.py               ← Reverse verification & confidence grading
│   ├── trust_model.py                ← Claim/evidence trust model
│   ├── domain_registry.py            ← Unified domain-tier registry
│   ├── config.py                     ← Config loader
│   ├── cache.py                      ← SQLite request cache
│   ├── network.py                    ← Exponential-backoff retry + POST + cookies
│   ├── date_extract.py               ← Heuristic publish-date extraction
│   ├── tavily_adapter.py             ← Tavily API adapter (optional)
│   ├── wsa_adapter.py                ← Tencent Cloud WSA adapter (optional, TC3 signing)
│   ├── baidu_api_adapter.py          ← Baidu Qianfan adapter (optional, Bearer auth)
│   ├── sogou_url_decoder.py          ← Sogou encrypted-link resolver
│   ├── wechat_fetch.py               ← WeChat article fetcher (drives Node.js)
│   └── wechat_fetch/                 ← WeChat Node fetch script (zero npm deps)
│       └── wx-article-fetch.js
│
├── references/                       ← Knowledge base (loaded on demand, Chinese)
│   ├── 01-search-strategy.md         ← Search strategy & engine selection
│   ├── 02-source-ranking.md          ← Source tiers (A–E) and usage rules
│   ├── 03-confidence-rubric.md       ← Confidence grading definitions
│   ├── 04-noise-filtering.md         ← Noise reduction & verification flow
│   ├── 05-output-template.md         ← Output template spec
│   ├── 06-fallback-guide.md          ← Degradation (no API engines / offline)
│   ├── 07-cross-platform.md          ← Cross-platform migration guide
│   ├── 08-trust-quality-framework.md ← v2 trust methodology
│   ├── 09-evaluation-benchmark.md    ← Evaluation benchmark & release gates
│   └── 10-api-setup.md               ← API setup guide (Tavily / WSA / Qianfan)
│
├── assets/                           ← Templates
│   └── report-template.md            ← Markdown report template
│
├── schemas/                          ← Structured-output schema
│   └── evidence-pack.schema.json     ← evidence-pack / claims-json JSON Schema
│
├── examples/                         ← Runnable example scripts
│   ├── fact_check.sh
│   ├── research_report.sh
│   └── host_input.sh
│
├── benchmark/                        ← Reproducible benchmark
│   ├── queries.json                  ← Standard query set
│   ├── run.py                        ← Runner (default: free engines)
│   ├── evaluate.py                   ← Gate evaluator
│   └── fixtures/                     ← Golden-report baselines (reviewed)
│
├── tests/                            ← unittest regression suite (274 tests)
│
├── .claude/                          ← Claude Code adapter
├── .codex/                           ← Codex adapter
└── .github/                          ← Issue templates
```

---

## Version

- **Current**: v2.1.1
- **Stable baseline**: v2.1.1 (2026-07-19)
- **Author**: 黄艾伦 (Huang Allen)
- **Changelog**: `CHANGELOG.md`

---

## Roadmap

| Version | Goals |
|---|---|
| v2.1 | Smarter query decomposition and supervisor–subagent research mode; SearXNG adapter |
| v2.2 | Optional MCP server wrapper exposing standardized tools |
| v3.0 | Lightweight semantic models for opinion clustering (may add optional dependencies) |

---

## Technical Notes

### Platform compatibility

| Platform | Requirements | Status |
|---|---|---|
| Generic prompt | Python 3.8+ | ✅ Default |
| Claude Code | Python 3.8+ | ✅ Adapted |
| Codex | Python 3.8+ | ✅ Adapted |
| OpenClaw / Hermes | Python 3.8+ | Optional adapter example |

### External dependencies

- **Tavily**: optional; enabled when `TAVILY_API_KEY` is set, otherwise automatic web-only fallback
- **Tencent Cloud WSA**: optional; enabled with `TENCENTCLOUD_SECRET_ID` + `TENCENTCLOUD_SECRET_KEY`
- **Baidu Qianfan AI Search**: optional; enabled with `BAIDU_API_KEY`
- Setup steps for all three: `references/10-api-setup.md`; when none are configured, free web engines are used and the `tips` field explains how to upgrade
- **Node.js**: only for WeChat article fetching; skipped when absent
- **Python packages**: zero third-party dependencies — standard library only (`urllib`, `threading`, `json`, `re`, `hashlib`, `difflib`)

---

## Usage Examples

```bash
# Basic search (auto engine selection)
python3 scripts/search_engine.py "XPeng VLA2.0 lidar"

# Multi-engine + reverse verification
python3 scripts/search_engine.py "query" --engines tavily,bing_cn --verify

# Budget control (lite/standard/deep; legacy minimal/balanced/comprehensive still work)
python3 scripts/search_engine.py "query" --budget deep

# Auto budget + adaptive checkpoints
python3 scripts/search_engine.py "query" --budget auto --checkpoint auto

# Evidence pack (via the claims-json compatibility entry)
python3 scripts/search_engine.py "query" --mode research --budget auto --verify --output claims-json

# Chinese natural-language query with extracted concepts (recommended, agent-enforced)
python3 scripts/search_engine.py "如何消除比熊的泪痕" \
  --search-concepts "比熊,泪痕,消除方法" --verify --output claims-json

# Host-search input (results already gathered by OpenClaw/Kimi agents)
python3 scripts/search_engine.py "query" --input-results host_results.json \
  --engines none --output claims-json

# First-run self-check
python3 scripts/search_engine.py --doctor

# Fetch WeChat article content
python3 scripts/search_engine.py "query" --fetch-content
```

---

## Methodology Sources

- Huang Allen's information-search methodology (multi-source verification, reverse argumentation, semantic analysis)
- Nuwa Skill checkpoint mechanism and quality control
- Tavily advanced search API best practices
- OSINT / ACH / SIFT / source-reliability methodology audit trail (see `references/08-trust-quality-framework.md`)

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Sogou returns 0 results or `blocked` | Target site served a captcha/security check | Retry with `--engines bing_cn` or `--engines tavily`; not a bug — VSP never bypasses captchas |
| Tavily returns nothing | `TAVILY_API_KEY` not set | Expected — automatic web-search fallback; get a free key at [tavily.com](https://tavily.com/); the `tips` field and `--doctor` show setup steps |
| DuckDuckGo empty | Anti-bot captcha triggered | VSP detects captcha pages and marks them `blocked`; switch engines and retry |
| WeChat fetch fails | Node.js not installed | Regular web search is unaffected; only `--fetch-content` needs Node.js |
| Empty JSON or confidence E | Query too specific, network unreachable, or all engines blocked | Check `--doctor`, broaden the query, or prepare `--input-results` manually |
| `--help` broken / unknown args silently ignored | You may be on an old version | Run from the latest repository; legacy CLI used hand-written parsing |

Still stuck? Open an issue and attach the output of `python3 scripts/search_engine.py --doctor`.

---

## Contributing

Contributions are very welcome — beginners included:

1. **Fork** and clone the repository.
2. **Run tests**: `python3 -m unittest discover -s tests` — all must pass.
3. **Pick an issue**: start with `good first issue`.
4. **Tests before code**: keep changes regression-free.
5. **Open a PR**: explain the motivation and how you verified it.

Good first contributions:

- Add HTML fixtures and tests for search engines
- Add trusted domains to the source-ranking registry
- Submit benchmark queries and golden reports
- Improve documentation for newcomers

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full guide, including release gates.

---

```bash
python3 -m unittest discover -s tests
```

---

*This tool is under active iteration. Default deliverables are local Markdown and claims-json; platform integrations are optional per user environment.*
