#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/media/msx/SD200/VSCODE/github/IA-Trade"
cd "$ROOT_DIR"

mkdir -p logs
exec ./venv/bin/python analysis/paper_journal.py --period daily --send-telegram >> logs/paper_journal.log 2>&1
