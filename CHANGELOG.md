# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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
