# Verified Search Pro Benchmark

可复验的 benchmark 门禁，用于验证 VSP 在不同查询类型上的表现。

## 结构

```
benchmark/
├── queries.json      # 标准查询集（中文查询必须带 concepts 字段）
├── run.py            # 运行所有查询并保存结果
├── evaluate.py       # 评估结果是否通过门禁
├── fixtures/         # golden report 基线（tencent_wsa+tavily 双 API 路径，2026-07-17 固化，已审核）
└── results*/         # 本地运行产物，不入库（.gitignore 已排除）
```

## 运行 benchmark

```bash
# 1. 运行查询（默认免费引擎组 duckduckgo,sogou,bing_cn，无需任何 API Key）
python3 benchmark/run.py

# 2. 评估结果（默认读取 benchmark/results/summary.json）
python3 benchmark/evaluate.py

# 3. API 路径（需已配置对应 API Key；输出目录与评估 summary 需成对指定）
python3 benchmark/run.py --engines tencent_wsa,tavily --output-dir benchmark/results-api
python3 benchmark/evaluate.py --summary benchmark/results-api/summary.json
# 已配置 BAIDU_API_KEY 时可加入 baidu_api：
# python3 benchmark/run.py --engines tencent_wsa,tavily,baidu_api --output-dir benchmark/results-api
```

基线说明与变更规则见 `fixtures/README.md`；发版前必须执行的完整门禁见 `CONTRIBUTING.md`「发布门禁」一节。

## 查询覆盖场景

| ID | 场景 | 说明 |
|----|------|------|
| fresh-fact | 新鲜事实 | 验证具体事实能否得到可信结论 |
| policy-claim | 政策声明 | 验证政策类查询的置信度 |
| perspective-mapping | 观点映射 | 验证争议性话题能生成 perspective_map |
| source-laundering | 来源去重 | 验证多源转载不会错误提升置信度 |
| temporal-drift | 时间演进 | 验证历史 vs 当前证据被正确区分 |
| technical-claim | 技术声明 | 验证技术类查询的局限性标注 |

## 贡献新查询

1. 在 `queries.json` 中添加新查询和 `expected` 条件。
2. 运行 `python3 benchmark/run.py` 生成结果。
3. 人工审核结果后，如需作为回归基线，放入 `fixtures/`。
4. 提交 PR 时说明查询设计的理由。
