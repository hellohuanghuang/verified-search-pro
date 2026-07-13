#!/usr/bin/env bash
# Verified Search Pro · 宿主搜索输入示例
# 用途：让 agent 把已经搜到的结果交给 VSP 做质检

set -euo pipefail

cd "$(dirname "$0")/.."

INPUT_FILE="${1:-examples/sample_host_results.json}"
QUERY="${2:-2026 年新能源汽车政策}"

if [[ ! -f "${INPUT_FILE}" ]]; then
  echo "[Error] Input file not found: ${INPUT_FILE}"
  echo "Creating a sample host_results.json for demo..."
  cat > "${INPUT_FILE}" <<'EOF'
{
  "results": [
    {
      "url": "https://www.gov.cn/zhengce/2026-01-01.htm",
      "title": "国务院发布 2026 年新能源汽车产业政策",
      "content": "国务院发布最新新能源汽车产业政策，明确补贴退坡时间表。",
      "engine": "host_search",
      "score": 0.95,
      "published_at": "2026-01-01",
      "author": "国务院"
    },
    {
      "url": "https://www.reuters.com/business/autos/electric-vehicles-2026",
      "title": "Global EV sales rise 30% in first half of 2026",
      "content": "Global electric vehicle sales grew by nearly a third in the first half of 2026.",
      "engine": "host_search",
      "score": 0.85,
      "published_at": "2026-01-02",
      "author": "Reuters"
    }
  ]
}
EOF
fi

echo "=== Host Input Quality Check: ${QUERY} ==="
python3 scripts/search_engine.py "${QUERY}" \
  --input-results "${INPUT_FILE}" \
  --engines none \
  --verify \
  --output claims-json
