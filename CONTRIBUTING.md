# 贡献指南

感谢你对 Verified Search Pro 的兴趣！本指南帮助你快速加入贡献。

## 开发环境

- Python 3.8+
- 可选：`TAVILY_API_KEY`（没有也能跑大部分测试）
- 可选：Node.js（只在抓取微信文章内容时需要）

```bash
git clone https://github.com/hellohuanghuang/verified-search-pro.git
cd verified-search-pro
python3 -m unittest discover -s tests
```

## 提交前 Checklist

- [ ] 运行 `python3 -m unittest discover -s tests` 全部通过
- [ ] 如果是新功能，补充对应的单元测试
- [ ] 如果是修复 bug，先写能复现的测试再修代码
- [ ] 如果是文档改动，确保 `tests/test_docs_policy.py` 通过
- [ ] 保持纯 Python 标准库优先，不引入新的第三方依赖（除非经过讨论）

## 发布门禁

任何版本发布（含 beta 标记）前，必须依次通过以下门禁。门禁分两层（2026-07-18 甲方裁定）：**API 层保质量下限，免费层保可用性底线**——免费引擎受目标站点反爬策略影响存在日际波动（验证码、相关性漂移），其产出质量不作为发布卡点。

1. **全量单元测试通过**：
   ```bash
   python3 -m unittest discover -s tests
   ```
2. **API 路径 benchmark 门禁（质量门禁，硬卡点）**：维护者发版前必跑，evaluate 必须全过（exit 0，6/6 可信结论）：
   ```bash
   python3 benchmark/run.py --engines tencent_wsa,tavily --output-dir benchmark/results-api
   # 已配置 BAIDU_API_KEY 时可含 baidu_api：
   # python3 benchmark/run.py --engines tencent_wsa,tavily,baidu_api --output-dir benchmark/results-api
   python3 benchmark/evaluate.py --summary benchmark/results-api/summary.json
   ```
3. **免费引擎路径 benchmark 门禁（可用性门禁）**：无需任何 API Key，默认可跑；要求每条查询均产出结构完整的证据包（引擎健康状态有记录、evidence 流程跑通），可信结论数量记录于发布说明但不作为卡点：
   ```bash
   python3 benchmark/run.py            # 默认免费引擎组 duckduckgo,sogou,bing_cn
   python3 benchmark/evaluate.py       # 记录通过率；不强制全过
   ```
4. **中文查询必须携带 concepts**：`benchmark/queries.json` 中每条查询的 `concepts` 字段为必填（对照现有 6 条示例）；新增中文查询不带 concepts 视为违规调用，不得合入。
5. **运行产物与基线纪律**：`benchmark/results*/` 为本地运行产物，一律不入库（`.gitignore` 已排除）；`benchmark/fixtures/` 是唯一的 golden report 基线，任何基线变更必须在 PR 中说明理由并经甲方/维护者审核（背景见 `benchmark/fixtures/README.md`）。

## 如何添加新搜索引擎

1. 在 `config/default.json` 的 `web_engines` 中添加引擎配置。
2. 在 `scripts/html_parser.py` 中实现对应的解析函数 `parse_xxx`，并在 `PARSERS` 中注册。
3. 在 `tests/fixtures/` 中添加该引擎的 HTML fixture。
4. 在 `tests/test_html_parser.py` 中补充测试。
5. 更新 `README.md` 的引擎列表。

## 如何添加新域名评级

1. 在 `config/default.json` 的 `domain_ranking` 中找到合适分类（authoritative / media / ugc / high_risk）。
2. 添加域名和分数，分数范围建议 0.0–1.0。
3. 在 `tests/test_domain_registry.py` 中补充测试。
4. 更新 `references/02-source-ranking.md` 说明理由。

## 如何提交 Benchmark 查询

1. 在 `benchmark/queries.json` 中添加查询和 `expected` 条件。
2. 运行 `python3 benchmark/run.py` 生成结果。
3. 运行 `python3 benchmark/evaluate.py` 检查是否通过门禁。
4. 在 PR 中说明查询覆盖的场景和期望行为。

## 代码风格

- 使用 4 空格缩进。
- 函数和类添加中文或英文 docstring。
- 保持零第三方依赖，优先使用 Python 标准库。
- 对复杂逻辑先写测试再实现。

## 行为准则

请保持友善、尊重和建设性。我们欢迎新手开发者，任何问题都可以在 issue 中提出。
