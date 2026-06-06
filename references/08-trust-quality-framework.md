# Trust Quality Framework for v2.0

## 目标

Verified Search Pro 2.0 的核心对象不是网页结果，而是可审计的 evidence-pack。每个可信 claim 必须保留来源、时间、证据链、反证状态和置信度依据；每个非可信但有价值的材料必须单独标注用途，避免把搜索排序、观点热度或历史材料误当成真实性排序。

## 方法论锚点

| 方法 | 引入方式 | 对应风险 |
|------|---------|----------|
| OSINT investigation cycle | 先定义问题、范围、采集计划、验证步骤和报告边界 | 漫无目的扩搜、证据链断裂 |
| Berkeley Protocol | 记录来源、采集时间、上下文和保存方式 | 结果不可复核、网页漂移 |
| ACH (Analysis of Competing Hypotheses) | 对高风险 claim 同时维护支持证据和反证证据 | 只找支持材料、确认偏误 |
| Admiralty-style two-axis grading | 分离 source reliability 与 information credibility | 权威来源偶发错误、低级来源偶发有效 |
| SIFT/lateral reading | 离开原网页查发布者、找更好覆盖、追溯原始语境 | 被包装精美的二手语料误导 |
| Signal/noise framing | 将重复转载、营销语、SEO 内容视为噪声，不计作独立确认 | 热度污染置信度 |

## 2.0 Evidence-Pack Contract

每个 evidence-pack 至少包含：

- `claim`: 最小可验证陈述，避免把多个事实混成一句。
- `claim_type`: fact, forecast, interpretation, profile, policy, market, technical。
- `source_evidence`: 支持来源列表，保留 URL、标题、发布时间、访问时间、发布者身份。
- `counter_evidence`: 反证、冲突、辟谣或缺口。
- `source_reliability`: 来源可靠性，A-F 或 unknown。
- `information_credibility`: 内容可信度，1-6 或 unknown。
- `confidence`: A-E，必须由来源可靠性、内容可信度、独立确认数和反证状态共同决定。
- `freshness`: 是否满足主题的时效窗口。
- `limits`: 明确哪些部分尚未验证。
- `perspective_map`: 多元观点和代表性说法，只作背景、假设和发散线索。
- `common_misconceptions`: 明确错误、常见误区或噪声样本，只作负面语料。
- `controversies_uncertainties`: 无法定论的争议、矛盾和能力边界。
- `temporal_evolution`: 信息的时间线，区分当前证据、历史背景和可能失效信息。
- `agent_handoff`: 告诉后续 agent 哪些内容可当结论，哪些只能当上下文。

## 非可信材料的价值分类

| 分类 | 价值 | 红线 |
|------|------|------|
| 观点地图 | 展示复杂性、多元立场、矛盾张力和发散方向 | 不代表事实成立 |
| 常见误区 | 识别噪声特征、反面逻辑和错误传播路径 | 不可复述为真实结论 |
| 争议不确定 | 说明能力边界，把判断权交还给用户和后续 agent | 不用平均立场伪造定论 |
| 时间演进 | 保存过去成立但现在可能失效的信息，用于趋势判断 | 不把历史材料当当前事实 |

## 上下文预算原则

256k 是硬红线，不是目标值。Skill 输出必须默认低于红线很多，并预留系统提示词、用户任务、对话历史和后续推理空间。默认 `standard`；短任务使用 `lite`，只有用户明确要求深度资料包时才使用 `deep`。

## 控制点

1. Query design: 先拆 claim，再决定搜索引擎和语言范围。
2. Collection: 保留原始结果池，不直接覆盖或丢弃低分结果。
3. Fusion: 去重时区分同源转载、聚合页和独立来源。
4. Verification: 对关键 claim 做正向支持和反向证伪。
5. Reporting: 输出以 evidence-pack 为单位，而不是以网页列表为单位。

## 2.0 升级判据

- 置信度不能只由域名分和关键词命中决定。
- 多源确认必须验证来源独立性，同一通稿的复制不算多源。
- 缺少发布日期或原始出处时，默认降低 freshness 或 credibility。
- 搜索失败、Tavily 缺失、网页解析失败都必须进入报告的 limitations。
- 高风险主题必须显示反证路径：搜过什么、没找到什么、仍不确定什么。

## Source Anchors

- UN/OHCHR and UC Berkeley Human Rights Center, Berkeley Protocol on Digital Open Source Investigations: https://digitallibrary.un.org/record/3973652
- Richards J. Heuer Jr., Psychology of Intelligence Analysis, CIA Center for the Study of Intelligence: https://www.cia.gov/resources/csi/books-monographs/psychology-of-intelligence-analysis-2/
- NATO/STO discussion of Admiralty Code source reliability and information credibility: https://www.sto.nato.int/publications/STO%20Meeting%20Proceedings/STO-MP-IST-190/MP-IST-190-13.pdf
- Mike Caulfield, SIFT (The Four Moves): https://hapgood.us/2019/06/19/sift-the-four-moves/
