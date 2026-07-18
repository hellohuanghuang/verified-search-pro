# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.1.1] - 2026-07-19

### Fixed

- **示例脚本权限测试对 zip 分发渠道脱敏**：GitHub "Source code (zip)" 解压后 `examples/*.sh` 丢失 Unix 可执行位，导致 `python3 -m unittest discover -s tests` 首次运行失败 3 个用例（QA 报告复现确认）。`tests/test_examples.py` 改为分层断言——git 工作区内要求索引 100755 且工作区带可执行位（防 +x 回归），非 git 环境（zip 解压）降级为存在性/可读性校验并在断言信息中给出修复指引。
- `.claude/CLAUDE.md` 与 `.codex/instructions.md` 版本行的 "(beta)" 残留清除（v2.1.0 定稿时遗漏）。

### Docs / Release Process

- `examples/README.md` 新增 zip 用户指引（`bash examples/xxx.sh` 或 `chmod +x examples/*.sh`）。
- `CONTRIBUTING.md` 发布门禁新增第 6 条：每次 Release 必须附加 `git archive` 构建的官方 tar.gz（保留可执行位）。
- v2.1.0 Release 已补挂官方 `verified-search-pro-2.1.0.tar.gz`；本版本发布时同步附挂。

---

## [2.1.0] - 2026-07-18

### Release Status

- **v2.1.0 正式版**。由 v2.1.0-beta.5 定稿；本条目不含新增代码变更（定稿提交仅更新版本号、发布状态表述与稳定基线）。稳定基线自 v2.0.0 升级为 v2.1.0。全部功能与修复内容见 [2.1.0-beta] ~ [2.1.0-beta.5] 及 [2.0.1] / [2.0.2] 条目。

### Release Gates（门禁分层，2026-07-18 甲方裁定）

- 门禁分两层：**API 层保质量下限（硬卡点），免费层保可用性底线（记录不卡点）**——免费引擎受目标站点反爬策略影响存在日际波动，其产出质量不作为发布卡点（已写入 `CONTRIBUTING.md` 发布门禁章节）。
- 单元测试：276 全部通过。
- API 路径：`tencent_wsa,tavily` 6/6 通过（全部产出可信结论）。
- 免费路径：6/6 查询均产出结构完整证据包（可用性底线守住）；可信结论 5/6——"2026 年新能源车销量增长"受 DuckDuckGo 验证码、必应相关性日际波动与"新能源车/新能源汽车"缩写鸿沟叠加影响为 D 级，非代码回归；同义词/缩写归一已列入 backlog。

### Docs（发布前审计修订）

- `references/01-search-strategy.md` 同步至 v2.1.0 底盘现实：新增"路由逻辑"说明（全并发+融合 / 首选辅助为权重建议 / 备份仅存于特定降级链 / 宿主为输入通道非引擎）；场景表补 `baidu_api`、宿主搜索全场景首选化；移除已放弃的搜狗微信通道与旧百度 HTML 残留表述。
- `references/06-fallback-guide.md`：降级梯队补 `baidu_api`，分层表述统一为"宿主地基 → L1 → L2"；移除失效的 `--engines baidu` 示例与旧百度残留。
- `references/10-api-setup.md`：公众号边界表述修正（不再指向已放弃的搜狗微信）。
- `README.md`：故障排查表移除旧百度 HTML 行，改为免费引擎通用反爬说明。

## [2.1.0-beta.5] - 2026-07-18

### Changed

- **LLM 概念提取优先序显性化（甲方审计裁定）**：`cross_verify.extract_entities` 的 key_terms 顺序从"原句 → n-gram → … → concepts（队尾）"调整为"**原句 → concepts → n-gram → …**"。评分行为本已正确（verify_result 有 concepts 时以 concepts 为唯一评分基准），本次将顺序语义固化为契约：保证任何"取前 N"的消费场景（证据报告展示、未来下游截断）中 LLM 概念都优先可见，明确其主力地位而非候补；n-gram 保留为无 concepts 时的兜底分析能力。docstring 已写明该设计契约防止未来回归。

### Tests

- 274 → 276 个测试全部通过（新增 concepts 顺序契约、concepts 与 n-gram 去重 2 个用例）。

## [2.1.0-beta.4] - 2026-07-18

### Added

- **微信抓取 Node 脚本补入仓库（打包缺口修复）**：新增 `scripts/wechat_fetch/wx-article-fetch.js`——此前 `wechat_fetch.py` 引用的 Node 子进程脚本从未入库，任何干净 clone 下微信抓取均静默降级。脚本零 npm 依赖（仅 Node 标准库 http/https/zlib），支持浏览器 UA、重定向跟随（≤5）、gzip/deflate 解压、8MB 响应上限、标题（og:title → rich_media_title → `<title>`）与正文（`div#js_content` 去标签纯文本 + HTML 实体解码）提取；识别删除/违规/参数错误/反爬验证等平台拦截页并返回人话错误。`is_available()` 自此在干净 clone 下返回 True，功能真实可用。
- **微信抓取测试 fixture**：`tests/fixtures/wechat_article.html`（正常文章页）与 `tests/fixtures/wechat_deleted.html`（已删除页）。

### Fixed

- **`is_wechat_url` 子串匹配防仿冒加固**：改为域名精确匹配（`urlparse` hostname 比对 `mp.weixin.qq.com` + `/s/` 路径前缀），拒绝 `mp.weixin.qq.com.evil.com`（后缀域名）、`mp.weixin.qq.com@evil.com`（userinfo 伪装）、域名出现在路径中、非法端口混淆等仿冒形式；保留 http/大写/无 scheme 裸 URL/FQDN 尾点等真实变体的识别。Node 脚本侧内置同口径防御（纵深防御）。

### Tests

- 272 → 274 个测试全部通过（`is_wechat_url` 加固新增 2 个用例组：7 种仿冒形式拒绝 + 6 种真实变体接受）。
- Node 脚本冒烟验证（本地 HTTP 服务 + fixture）：URL 防御 5 项、标题/正文/实体解码/拦截页识别 6 项、真实网络链路（直连/302 跟随/finalUrl/重定向超限/不可达报错）5 项，共 16 项全部通过；真实微信服务器访问（无效文章 token）返回结构化人话错误"链接无效或文章已过期（微信返回：参数错误）"。

## [2.1.0-beta.3] - 2026-07-18

### Added

- **Web 引擎日期启发式提取（T1）**：新增 `scripts/date_extract.py`，从 title+snippet 文本与 URL 中提取发布日期——显式日期（中文 `2026年1月12日`、ISO、`2026/01/12`、英文序 `01/12/2026`）、相对日期（N 天/小时/周/个月前、昨天）、URL 日期路径（`/2026/01/12/`、`/20260112/`、`/2026-01-12/`）三类模式；合理性强校验拒绝未来日期（+2 天容忍）与早于 2005 年的日期。`scripts/search_engine.py` 在 Web 引擎结果归一化处接入，`published_at` 为空时补齐，不覆盖 API 引擎已提供的日期；只做 snippet/URL 启发式，不抓全文。
- **微信抓取 fixture 级测试（T4）**：新增 `tests/test_wechat_fetch.py`（14 个用例，mock Node 子进程），覆盖成功载荷映射、stdout 倒序 JSON 定位、业务失败、非零退出、无 Node 环境（FileNotFoundError）、超时、输入防御与 `enrich_results` 契约。

### Fixed

- **CHANGELOG v2.0.2 断档回填**：`7581982`（必应 Cookie 会话 + n-gram 噪声过滤 + None 防御 + 英文职位词断开）的条目在后续版本号统一中丢失，按该提交原始内容恢复 `[2.0.2] - 2026-07-16` 条目。
- **稳定基线表述过时**：`SKILL.md` 与 `references/07-cross-platform.md`（含英文 Prompt 模板）的"稳定基线：v1.0.0（2026-06-05）"修正为"v2.0.0（2026-07-14）"。
- **千帆 site 限定补录**：百度千帆适配器对照官方产品手册核验并补充站点限定能力（上批已单独提交 `03e3bce`，本条目仅作补录说明）。
- **README 与实现不符（干净 clone 走查发现）**：环境要求与外部依赖小节补齐腾讯云 WSA / 百度千帆并指向 `references/10-api-setup.md`；项目简介更新至 beta.2 口径；文件结构补录 `wsa_adapter.py` / `baidu_api_adapter.py` / `sogou_url_decoder.py` / `date_extract.py` / `references/10-api-setup.md` / `benchmark/fixtures/`。

### Changed

- **Web 引擎时效覆盖**：免费 HTML 引擎（bing_cn / sogou / duckduckgo / toutiao）结果不再普遍缺少 `published_at`，trust_model 中 freshness `unknown` 与"未检测到发布日期"限制标注的出现频率相应下降（文案不变）。

### Tests

- 225 → 272 个测试全部通过（新增 date_extract 33 个、wechat_fetch 14 个）。干净 clone 验证：macOS 系统 Python 3.9.6 下 `--doctor`、真实免费引擎查询与 `python3 -m unittest discover -s tests`（225）全部通过，无密钥/本地路径/缓存残留。

## [2.1.0-beta.2] - 2026-07-17

### Added

- **腾讯云 WSA 引擎（tencent_wsa）**：`scripts/wsa_adapter.py` 接入腾讯云「联网搜索 API」（SearchPro，TC3-HMAC-SHA256 签名鉴权）。仅使用标准版能力边界内参数（Query/Mode/Site/FromTime/ToTime，不发送 Cnt 等尊享/旗舰版参数）；密钥缺失、服务未开通、调用超限分别映射为 `skipped/api_key_missing`、`skipped/service_not_activated`、`blocked/rate_limit_exceeded`；响应 `date` 字段在适配层规范化为 ISO 日期。
- **百度千帆 AI 搜索（baidu_api）**：`scripts/baidu_api_adapter.py` 接入千帆 `/v2/ai_search/web_search`（Bearer 鉴权，环境变量 `BAIDU_API_KEY`）。请求契约以百度官方 baidu-search Skill 源码为准：`resource_type_filter` 数组 + `top_k`（默认 10、上限 50）、`search_filter` 时效过滤（`pd`/`pw`/`pm`/`py` 快捷档与 `YYYY-MM-DDtoYYYY-MM-DD` 自定义区间）；摘要 `content` 优先、`snippet` 兜底；HTTP 401/403→`failed/unauthorized`、429→`blocked/rate_limit_exceeded`、响应顶层 `code/message` 业务错误映射为对应引擎健康状态。
- **头条搜索低频引擎（toutiao）**：`scripts/html_parser.py` 新增 `parse_toutiao`，双模板解析（`real-index` 结果容器 + undefined-default 卡片变体）；签名词 + 结构特征双重风控识别，命中即标记 `blocked` 并停止，绝不绕过验证码；已注册进 WEB_ENGINES 但不进入默认引擎列表。
- **API 配置引导手册**：`references/10-api-setup.md` 新增，覆盖 L1 三个 API 引擎（Tavily / 腾讯云 WSA / 百度千帆）的申请入口、配置步骤、能力边界与常见错误映射。
- **golden report 基线**：`benchmark/fixtures/` 固化 2026-07-17 生成的 `tencent_wsa,tavily` 双 API 真实路径 6 条查询结果与 summary（已确认无密钥、无本机绝对路径），作为后续迭代的回归对照基准；更换基线需甲方/维护者审核。
- **`--doctor` 与 tips 扩展**：doctor 输出新增 `tencent_wsa`、`baidu_api` 状态与分步配置指引；输出 JSON 的 `tips` 字段新增 `tencent_wsa_missing`、`baidu_api_missing` 引导。

### Fixed

- **必应真实环境解析失效**：`scripts/html_parser.py` 外层容器嵌套合并导致真实 SERP 仅解析出 1 条结果，修复后恢复 7 条（含真实样本 fixture 回归测试）。
- **搜狗真实环境加密链接被归一化丢弃**：`scripts/html_parser.py` 提取器在跳转链接解析前保留 `/link?url=...` 加密链接，修复真实环境 1→8 条的解析丢失（含真实样本 fixture 回归测试）。
- **WSA 日期格式导致 classify_freshness 崩溃**：WSA 返回 `YYYY-MM-DD HH:MM:SS` 格式使 `datetime.date.fromisoformat` 解析失败，在适配层源头规范化为 ISO 日期（`scripts/wsa_adapter.py` `_normalize_date`）。
- **限制标注等用户可见文案英译中**：`scripts/trust_model.py` 的 limitations（含引擎健康限制与预算截断提示）、source_reliability / information_credibility / freshness 的 reason、常见误区 reason、争议与不确定性 summary/rule、agent_handoff 使用指引等直接面向 Markdown 报告与 claims-json 的文案全部中文化；`label` / `use_as` / `status` 等机器枚举值保持不变。

### Changed

- **默认引擎列表升级**：`tavily,tencent_wsa,baidu_api,duckduckgo,bing_cn,sogou`——API 引擎在前（未配置密钥自动跳过并给出 tips 引导），免费 Web 引擎兜底。
- **降级链优先级重写**：API 引擎优先；DuckDuckGo 为第一兜底，被拦截/失败/空结果时自动降级 `bing_int` → `bing_cn`。
- **benchmark 运行器对齐 v2.1 调用契约**：`benchmark/run.py` 默认引擎组改为免费三引擎 `duckduckgo,sogou,bing_cn`，查询集携带 `concepts` 字段（中文查询合规调用契约）；`evaluate.py` 支持 `--summary` 指定评估目标。
- **流程文档**：`CONTRIBUTING.md` 新增「发布门禁」一节（全量单测 + 免费/API 双路径 benchmark 门禁 + concepts 强制 + 运行产物与基线纪律）；`benchmark/README.md` 更新结构说明与运行/评估命令。

### Tests

- 152 → 221 个测试全部通过。新增覆盖：腾讯云 WSA 适配器（签名确定性、错误映射、日期规范化）、百度千帆适配器（请求体契约、top_k 边界、时效过滤、业务错误映射）、头条解析与风控识别、必应/搜狗真实样本回归、限制标注中文化固化。

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
