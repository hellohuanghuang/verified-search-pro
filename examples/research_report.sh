#!/usr/bin/env bash
# Verified Search Pro · 深度调研示例
# 用途：对复杂主题生成 Markdown 研究报告

set -euo pipefail

cd "$(dirname "$0")/.."

QUERY="${1:-2026 年固态电池技术路线}"

echo "=== Research Report: ${QUERY} ==="
python3 scripts/search_engine.py "${QUERY}" \
  --mode research \
  --budget deep \
  --verify \
  --output md \
  --engines bing_cn,sogou
