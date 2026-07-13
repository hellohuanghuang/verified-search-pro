#!/usr/bin/env bash
# Verified Search Pro · 事实核查示例
# 用途：快速验证一个具体事实，输出 claims-json

set -euo pipefail

cd "$(dirname "$0")/.."

QUERY="${1:-OpenAI CEO 是谁}"

echo "=== Fact Check: ${QUERY} ==="
python3 scripts/search_engine.py "${QUERY}" \
  --mode fact \
  --budget lite \
  --verify \
  --output claims-json \
  --engines bing_cn
