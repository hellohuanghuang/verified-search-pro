# Verified Search Pro 示例

本目录包含可直接运行的示例脚本，帮助你快速体验 VSP 的核心能力。

## 示例列表

| 脚本 | 用途 | 说明 |
|------|------|------|
| `fact_check.sh` | 事实核查 | 轻量模式，快速验证一个具体事实 |
| `research_report.sh` | 深度调研 | 生成 Markdown 研究报告 |
| `host_input.sh` | 宿主输入质检 | 把 agent 已搜到的结果交给 VSP 验证 |

## 快速运行

```bash
# 事实核查
bash examples/fact_check.sh "OpenAI CEO 是谁"

# 深度调研
bash examples/research_report.sh "2026 年固态电池技术路线"

# 宿主输入质检（会自动生成示例输入文件）
bash examples/host_input.sh
```

## 输出说明

- `--output claims-json`：结构化证据包，适合 agent 消费
- `--output md`：Markdown 报告，适合人阅读
- `--output json`：原始融合结果

## 自定义查询

所有脚本都支持传入自定义查询作为第一个参数：

```bash
bash examples/fact_check.sh "Python 3.14 发布日期"
```
