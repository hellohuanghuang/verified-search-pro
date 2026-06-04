# 降噪与验真流程

## 降噪流程（Phase 3）

### 步骤 1: URL 归一化去重
```python
def normalize_url(url):
    # 移除协议、www、尾部斜杠、跟踪参数
    url = re.sub(r'^https?://', '', url).lower()
    url = re.sub(r'^www\.', '', url)
    url = url.rstrip('/')
    url = re.sub(r'[?&](utm_|ref|source)=', '?', url)
    return url
```

### 步骤 2: 内容指纹去重（15 词 MD5）
```python
def content_fingerprint(title, content):
    combined = (title + " " + content[:100]).lower()
    combined = re.sub(r'[^\w\s]', '', combined)
    words = combined.split()[:15]
    return hashlib.md5(" ".join(words).encode()).hexdigest()[:16]
```

### 步骤 3: 文本相似度去重（阈值 0.85）
```python
def text_similarity(t1, t2):
    return SequenceMatcher(None, t1.lower(), t2.lower()).ratio()
# 标题相似度 > 0.9 或 内容相似度 > 0.85 → 视为重复
```

### 步骤 4: 信息源分级过滤
- 仅保留 A-C 级来源（D 级仅用于基础概念，E 级丢弃）
- 同一来源仅保留最高得分结果

### 步骤 5: 域名评分加权排序
```python
fusion_score = base_score * 0.4 + domain_score * 0.4 + source_bonus + 0.1
```

## 验真流程（Phase 4）

### 步骤 1: 提取关键实体
```python
entities = re.findall(r'[\u4e00-\u9fff]{2,}', query)  # 中文词
entities += re.findall(r'[A-Z][a-zA-Z]+', query)     # 英文专有词
entities += re.findall(r'\d{4}', query)                # 年份
```

### 步骤 2: 反向验证
```python
def verify_result(query, result):
    key_terms = extract_entities(query)
    content = (result["title"] + " " + result["content"]).lower()
    matches = sum(1 for t in key_terms if t in content)
    score = matches / len(key_terms) if key_terms else 0
    verified = matches >= max(1, len(key_terms) * 0.4)
    return score, verified
```

### 步骤 3: 多源一致性检查
- 比较不同来源对同一事实的表述
- 提取共同关键词
- 计算一致性得分

### 步骤 4: 矛盾信息标注
- 记录所有来源的表述
- 标注置信度为 D
- 不自行判断哪方正确

## 质量指标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 去重后保留率 | 30-50% | 原始结果的去重后比例 |
| 验证通过率 | >70% | 通过反向验证的结果比例 |
| A/B 级占比 | >30% | 高置信度结果占比 |
| D/E 级占比 | <20% | 低置信度/问题结果占比 |
