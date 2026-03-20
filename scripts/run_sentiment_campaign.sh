#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/media/msx/SD200/VSCODE/github/IA-Trade"
cd "$ROOT_DIR"

CYCLES="${1:-8}"
SLEEP_SECONDS="${2:-900}"
LOG_FILE="logs/sentiment_cycle.log"

mkdir -p logs

count_scored_signals() {
  ./venv/bin/python - <<'PY'
from analysis.sentiment_report import load_signals

df = load_signals()
if df.empty or 'sentiment_score' not in df.columns:
    print(0)
else:
    print(int(df['sentiment_score'].notna().sum()))
PY
}

BEFORE_COUNT="$(count_scored_signals)"

echo "===== SENTIMENT CAMPAIGN START $(date -u +%Y-%m-%dT%H:%M:%SZ) cycles=${CYCLES} sleep_seconds=${SLEEP_SECONDS} scored_before=${BEFORE_COUNT} =====" | tee -a "$LOG_FILE"

for ((i=1; i<=CYCLES; i++)); do
  echo "----- campaign_cycle=${i}/${CYCLES} started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ) -----" | tee -a "$LOG_FILE"
  ./scripts/run_sentiment_cycle.sh

  CURRENT_COUNT="$(count_scored_signals)"
  echo "campaign_cycle=${i}/${CYCLES} scored_signals_now=${CURRENT_COUNT}" | tee -a "$LOG_FILE"

  if (( i < CYCLES )); then
    echo "campaign_sleep_seconds=${SLEEP_SECONDS}" | tee -a "$LOG_FILE"
    sleep "$SLEEP_SECONDS"
  fi

done

AFTER_COUNT="$(count_scored_signals)"
DELTA=$((AFTER_COUNT - BEFORE_COUNT))
echo "===== SENTIMENT CAMPAIGN END $(date -u +%Y-%m-%dT%H:%M:%SZ) scored_after=${AFTER_COUNT} scored_delta=${DELTA} =====" | tee -a "$LOG_FILE"
