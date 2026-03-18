#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/media/msx/SD200/VSCODE/github/IA-Trade"
cd "$ROOT_DIR"

mkdir -p logs

{
  echo "===== SENTIMENT CYCLE $(date -u +%Y-%m-%dT%H:%M:%SZ) ====="
  ./venv/bin/python paper_trade.py --source exchange --once
  echo
  ./venv/bin/python analysis/sentiment_report.py --limit 50
  echo
} >> logs/sentiment_cycle.log 2>&1
