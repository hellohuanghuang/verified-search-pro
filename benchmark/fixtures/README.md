# Golden Report 基线（benchmark/fixtures/）

本目录固化了 VSP 的 golden report 基线，作为后续迭代的回归对照基准。

## 基线来源

| 项目 | 说明 |
|------|------|
| 生成日期 | 2026-07-17 |
| 引擎组合 | `tencent_wsa,tavily`（双 API 真实路径，非 mock） |
| 查询集版本 | `benchmark/queries.json` 带 `concepts` 字段的版本（6 条中文查询，含 mode/budget/expected 门禁期望） |
| 生成方式 | `python3 benchmark/run.py --engines tencent_wsa,tavily --output-dir benchmark/results-api` |
| 审核状态 | 甲方已审核批准后固化 |

## 文件清单

- 6 个查询结果 JSON：与 `benchmark/queries.json` 中 6 条查询一一对应（fresh-fact / policy-claim / perspective-mapping / source-laundering / temporal-drift / technical-claim）
- `summary.json`：当次运行的聚合摘要。其中 `result_path` 字段保留生成时的原始相对路径记录（指向 `benchmark/results-api/`，属运行产物，未做改写）

## 内容检查结论（固化时已执行）

- 已 grep 确认**不含任何密钥**（无 `TAVILY_API_KEY` / `SECRET` / `AKID` / `bce-v3` / `ALTAK` / `tvly-` / `Bearer` 字样）
- 已确认**不含本机绝对路径**（无 `/Users/` 前缀字段）

## 用途与变更规则

1. 用作后续迭代的回归对照基准（如 prompt/解析器/信任模型变更前后 diff）。
2. **更换基线需甲方/维护者审核**，并在 PR 中说明理由（见 `CONTRIBUTING.md` 发布门禁）。
3. 注意：基线内容反映生成时点的代码行为。若后续版本对用户可见文案做合法变更（如 v2.1.0-beta.2 限制标注中文化），与基线 diff 时出现对应差异属预期，评估时应以最新 `evaluate.py` 门禁为准，而非逐字节比对。
4. `benchmark/results*/` 为本地运行产物，不入库；本目录是唯一入库的结果基线。
