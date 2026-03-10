#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/media/msx/SD200/VSCODE/github/IA-Trade"
cd "$ROOT_DIR"

mkdir -p logs
exec ./venv/bin/python paper_trade.py --source exchange >> logs/paper_trade_runner.log 2>&1
