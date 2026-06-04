# 置信度定级标准（A-E）

## 定级标准

| 等级 | 名称 | 定义 | 使用规则 | 标注要求 |
|------|------|------|---------|---------|
| **A** | 已确认 | 2+ 权威来源独立确认 | 可直接引用，无需额外说明 | 标注来源即可 |
| **B** | 基本可信 | 1 权威来源或 2+ 一般来源一致 | 可引用，建议标注来源 | 标注"据 X 报道/研究显示" |
| **C** | 单一来源 | 单一来源，无矛盾 | 可引用，必须标注来源 | 标注"据 X 报道，尚未获其他来源确认" |
| **D** | 存疑 | 存在矛盾或辟谣信息 | 必须标注争议，不得作为定论 | 标注"存在争议：X 称...，但 Y 质疑..." |
| **E** | 不实 | 明确不实或无法验证 | 不使用，标注"信息不足" | 标注"此信息无法验证/已被辟谣" |

## 定级流程

```
1. 提取关键实体（查询中的核心名词）
2. 反向验证：结果内容是否包含这些实体？
3. 多源一致性：同一事实在不同来源中的表述是否一致？
4. 域名评分：来源的权威性如何？
5. 综合定级：按标准判定 A/B/C/D/E
```

## 定级算法

```python
def grade_confidence(result, consistency):
    verification = result.get("verification_score", 0)
    sources = len(result.get("sources", []))
    domain_score = result.get("domain_score", 0.5)
    
    # A: 多源验证 + 高域名评分 + 高验证分
    if sources >= 2 and domain_score >= 0.8 and verification >= 0.7:
        return "A"
    # B: 单源权威或多源一般 + 中验证分
    if (sources >= 2 or domain_score >= 0.8) and verification >= 0.5:
        return "B"
    # C: 单源一般 + 验证通过
    if verification >= 0.4:
        return "C"
    # D: 验证分低或存在矛盾
    if verification < 0.4 or not consistency.get("consistent", True):
        return "D"
    # E: 明确问题
    return "E"
```

## 宁少勿假原则

**信息不足时明确标注，不强行生成 A/B 级结论。**

示例：
- ❌ 错误："小鹏 GX 搭载了 4 颗激光雷达"（实际为 0 颗）
- ✅ 正确："关于小鹏 GX 激光雷达配置的信息存在不一致，多数来源称 0 颗，但某来源称 4 颗（置信度 D，待进一步验证）"

## 矛盾处理

当发现矛盾信息时：
1. 记录所有来源的表述
2. 标注置信度为 D
3. 不自行判断哪方正确
4. 交付时提示用户"存在争议，建议进一步核实"
