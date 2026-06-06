# Evaluation and Benchmark Plan for v2.0

## 目标

2.0 不能只声称“更可信”，必须通过可复验场景证明相对普通搜索和未使用本 skill 的 agent 输出有质量优势。

## Benchmark Sets

| Set | 场景 | 样例主题 | 主要风险 |
|-----|------|----------|----------|
| Fresh facts | 新近事实核查 | 产品发布、政策更新、融资动态 | 过时信息 |
| Conflicted claims | 多方表述冲突 | 公司争议、政策解读、事故原因 | 单边采信 |
| Source laundering | SEO/转载污染 | 行业报告、榜单、营销稿 | 伪多源 |
| Chinese web | 中文互联网复杂语料 | 微信、知乎、百度百科、地方官网 | 权威性错判 |
| Technical claims | 技术能力与版本 | API、模型、论文、开源项目 | 版本漂移 |
| Perspective mapping | 主观评价和争议观点 | 政策评价、机构口碑、项目争议 | 把观点误当事实 |
| Temporal drift | 信息动态演进 | 旧政策、历史规划、阶段性结论 | 过去正确、现在失效 |

## Metrics

- Coverage: 是否覆盖核心 claim、相关实体、时间窗口和关键反方查询。
- Precision: 交付结论中不可验证、过时或误导性 claim 的比例。
- Evidence traceability: 每条结论是否能追到原始来源或明确标注为二手来源。
- Independence: 多源确认是否来自独立发布者，而不是同一内容链。
- Contradiction handling: 是否显式呈现冲突来源和不确定性。
- Freshness: 是否按主题设定时效窗口并惩罚旧信息。
- Agent usability: Codex、Claude Code、OpenClaw、Hermes 是否能理解同一工作流。
- Context discipline: `lite / standard / deep` 是否控制 evidence-pack 大小，避免接近 256k 红线。
- Non-factual labeling: 观点、误区、争议和历史材料是否显著标注为不可直接当事实使用。

## Acceptance Gates

| Gate | 通过标准 |
|------|----------|
| Unit tests | core fusion, verification, parser fallback, CLI smoke tests pass |
| Golden reports | 至少 5 个 benchmark 主题生成固定结构报告 |
| Regression audit | v1 已知问题不回归，新增 v2 字段可解释 |
| Cross-agent load | 适配入口能指向同一 evidence-pack workflow |
| Release hygiene | 干净 clone 后无缓存、无本地路径、无密钥、README 可运行 |
| Context budget | 默认输出使用 standard，不把完整原始材料塞进 agent 上下文 |

## Golden Report Shape

每个 benchmark 报告必须包含：

1. Search scope and query plan
2. Trusted conclusion table with confidence and limitations
3. Evidence table with source reliability and information credibility
4. Perspective map, common misconceptions, controversies and temporal evolution
5. Final answer with cautious language and agent handoff notes

## Immediate Backlog

- Build fixture-based tests before replacing parser and scoring internals.
- Add a structured JSON output mode for evidence-pack handoff. (Started as `--output claims-json` in v2 alpha.)
- Replace single `domain_score` with separate reliability and credibility fields.
- Add publication date extraction and freshness scoring.
- Add same-story detection for syndicated articles and press release copies.
- Add cross-agent compatibility checks for `.codex`, `.claude`, `SKILL.md`, and generic prompt loading.
