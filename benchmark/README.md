# Verified Search Pro Benchmark

可复验的 benchmark 门禁，用于验证 VSP 在不同查询类型上的表现。

## 结构

```
benchmark/
├── queries.json      # 标准查询集
├── run.py            # 运行所有查询并保存结果
├── evaluate.py       # 评估结果是否通过门禁
└── fixtures/         # golden report 基线（待社区贡献）
```

## 运行 benchmark

```bash
# 1. 运行查询（默认使用 bing_cn，无需 Tavily key）
python3 benchmark/run.py

# 2. 评估结果
python3 benchmark/evaluate.py
```

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
