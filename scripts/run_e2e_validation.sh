#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/media/msx/SD200/VSCODE/github/IA-Trade"
cd "$ROOT_DIR"

mkdir -p logs
LOG_FILE="logs/e2e_validation.log"

run_step() {
  local label="$1"
  shift

  echo "===== ${label} =====" | tee -a "$LOG_FILE"
  "$@" 2>&1 | tee -a "$LOG_FILE"
  echo | tee -a "$LOG_FILE"
}

{
  echo "===== E2E VALIDATION $(date -u +%Y-%m-%dT%H:%M:%SZ) ====="
  echo
} >> "$LOG_FILE"

run_step "PY_COMPILE" ./venv/bin/python -m py_compile \
  main.py \
  analysis/monte_carlo.py \
  analysis/parameter_sweep.py \
  analysis/paper_journal.py \
  analysis/sentiment_report.py \
  backtest/backtester.py \
  paper_trade.py \
  semi_auto.py

run_step "MAIN_BACKTEST" ./venv/bin/python main.py
run_step "WALK_FORWARD_QUICK" ./venv/bin/python analysis/walk_forward.py --train-days 365 --test-days 90 --step-days 90 --max-folds 3
run_step "PARAMETER_SWEEP_QUICK" ./venv/bin/python analysis/parameter_sweep.py --engine grid --profile quick --workers 1 --top 5
run_step "PAPER_TRADE_CSV_ONCE" ./venv/bin/python paper_trade.py --source csv --once --reset-state
run_step "PAPER_JOURNAL_DAILY" ./venv/bin/python analysis/paper_journal.py --period daily --stdout
run_step "SLIPPAGE_REPORT" ./venv/bin/python analysis/slippage_report.py
run_step "SENTIMENT_REPORT" ./venv/bin/python analysis/sentiment_report.py
run_step "SEMI_AUTO_DRY_RUN" ./venv/bin/python semi_auto.py --dry-run --dry-run-json --side BUY --size 0.001 --entry-price 100000 --stop-price 99000 --target-price 102000
run_step "UNIT_TESTS" ./venv/bin/python -m unittest tests/test_phase4_spot.py tests/test_sentiment_integration.py

echo "e2e_validation=PASS" | tee -a "$LOG_FILE"
