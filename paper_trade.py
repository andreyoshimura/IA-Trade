"""
paper_trade.py

Runner de paper trade para operar sinais em tempo real sem enviar ordens.

Fluxo:
1) carrega candles do exchange ou CSV
2) calcula indicadores da estratégia
3) processa apenas candles ainda não vistos
4) simula entrada/saída, persistindo estado e logs
"""

import argparse
import csv
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

import config
from data.data_loader import get_ohlcv
from notifier.telegram import send_message
from risk.risk_manager import calculate_position
from strategy.breakout_structural import check_signal, prepare_indicators
from strategy.sentiment_filter import SentimentFilter
from utils.execution_costs import build_slippage_context, calculate_execution_details
from utils.market_mode import market_label, supports_signal


def parse_args():
    parser = argparse.ArgumentParser(description="Paper trade runner")
    parser.add_argument("--source", choices=["exchange", "csv"], default="exchange")
    parser.add_argument("--once", action="store_true", help="Processa candles pendentes e encerra")
    parser.add_argument("--reset-state", action="store_true", help="Ignora estado anterior e reinicia")
    parser.add_argument("--csv-path", default=config.DATA_PATH)
    parser.add_argument("--limit", type=int, default=config.PAPER_OHLCV_LIMIT)
    return parser.parse_args()


@dataclass
class PaperTradeRuntime:
    capital: float
    last_processed_timestamp: str | None = None
    last_exit_timestamp: str | None = None
    position: dict | None = None

    @classmethod
    def from_state(cls, state):
        return cls(
            capital=float(state.get("capital", config.PAPER_TRADE_CAPITAL)),
            last_processed_timestamp=state.get("last_processed_timestamp"),
            last_exit_timestamp=state.get("last_exit_timestamp"),
            position=state.get("position"),
        )

    def to_state(self):
        return {
            "capital": round(self.capital, 8),
            "last_processed_timestamp": self.last_processed_timestamp,
            "last_exit_timestamp": self.last_exit_timestamp,
            "position": self.position,
            "updated_at": utcnow_iso(),
        }


def utcnow_iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def ensure_log_dir():
    os.makedirs(config.PAPER_LOG_DIR, exist_ok=True)


def load_state(reset_state):
    if reset_state or not os.path.exists(config.PAPER_STATE_FILE):
        return PaperTradeRuntime(capital=config.PAPER_TRADE_CAPITAL)

    with open(config.PAPER_STATE_FILE, "r", encoding="utf-8") as fh:
        return PaperTradeRuntime.from_state(json.load(fh))


def save_state(runtime):
    ensure_log_dir()
    with open(config.PAPER_STATE_FILE, "w", encoding="utf-8") as fh:
        json.dump(runtime.to_state(), fh, indent=2)


def append_csv(path, row, fieldnames):
    ensure_log_dir()
    file_exists = os.path.exists(path)
    with open(path, "a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def append_jsonl(path, row):
    ensure_log_dir()
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=True) + "\n")


def notify(text):
    if not config.ENABLE_NOTIFICATIONS:
        return

    try:
        send_message(text)
    except Exception as exc:
        append_jsonl(
            config.PAPER_EVENT_LOG,
            {
                "event": "notification_error",
                "message": str(exc),
                "timestamp": utcnow_iso(),
            },
        )


def log_event(event, **payload):
    row = {"event": event, "timestamp": utcnow_iso()}
    row.update(payload)
    append_jsonl(config.PAPER_EVENT_LOG, row)


def signal_log_fieldnames():
    return [
        "timestamp",
        "action",
        "signal",
        "close",
        "atr",
        "capital",
        "stop",
        "target",
        "size",
        "entry_slippage_rate",
        "sentiment_score",
    ]


def build_sentiment_filter():
    if not getattr(config, "ENABLE_SENTIMENT_FILTER", False):
        return None
    return SentimentFilter(
        api_key=getattr(config, "SENTIMENT_API_KEY", None),
        language=getattr(config, "SENTIMENT_NEWS_LANGUAGE", "en"),
        lookback_days=int(getattr(config, "SENTIMENT_LOOKBACK_DAYS", 3)),
        max_articles=int(getattr(config, "SENTIMENT_MAX_ARTICLES", 20)),
    )


def evaluate_sentiment_trade(sentiment_filter, signal):
    if sentiment_filter is None:
        return True, None

    base_symbol = str(config.SYMBOL).split("/", 1)[0]
    threshold = float(getattr(config, "SENTIMENT_THRESHOLD", 0.2))
    return sentiment_filter.evaluate_trade(side=signal, symbol=base_symbol, threshold=threshold)


def load_market_data(source, csv_path, limit):
    if source == "csv":
        df_15m = pd.read_csv(csv_path)
        if limit > 0:
            df_15m = df_15m.tail(limit).copy()
    else:
        df_15m = get_ohlcv(config.SYMBOL, config.TIMEFRAME, limit=limit)

    df_15m["timestamp"] = pd.to_datetime(df_15m["timestamp"])
    numeric_cols = ["open", "high", "low", "close", "volume"]
    for col in numeric_cols:
        df_15m[col] = pd.to_numeric(df_15m[col], errors="coerce")

    df_15m = df_15m.dropna().sort_values("timestamp").reset_index(drop=True)
    df_1h = (
        df_15m.resample("1h", on="timestamp")
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .dropna()
        .reset_index()
    )
    return prepare_indicators(df_1h, df_15m)

def find_row_1h(df_1h, candle_timestamp):
    row_1h = df_1h.loc[df_1h["timestamp"] == candle_timestamp.floor("1h")]
    if row_1h.empty:
        return None
    return row_1h.iloc[-1]


def candle_cooldown_done(runtime, candle_timestamp):
    if not runtime.last_exit_timestamp:
        return True

    last_exit = pd.Timestamp(runtime.last_exit_timestamp)
    delta = candle_timestamp - last_exit
    candle_distance = int(delta.total_seconds() / (15 * 60))
    return candle_distance >= config.TRADE_COOLDOWN_CANDLES


def open_position(runtime, signal, row_15m, sentiment_score=None):
    entry = float(row_15m["close"])
    atr_value = float(row_15m["atr"])
    vol_mean = float(row_15m["vol_mean"]) if not np.isnan(row_15m["vol_mean"]) else None
    rolling_high = float(row_15m["rolling_high"]) if not np.isnan(row_15m["rolling_high"]) else None
    rolling_low = float(row_15m["rolling_low"]) if not np.isnan(row_15m["rolling_low"]) else None
    if np.isnan(atr_value):
        return None

    if signal == "BUY":
        stop = entry - atr_value * config.ATR_MULTIPLIER
        target = entry + abs(entry - stop) * config.RR_RATIO
    else:
        stop = entry + atr_value * config.ATR_MULTIPLIER
        target = entry - abs(entry - stop) * config.RR_RATIO

    size = calculate_position(entry, stop, runtime.capital, config.RISK_PER_TRADE)
    if size <= 0:
        return None

    position = {
        "type": signal,
        "entry": round(entry, 8),
        "stop": round(stop, 8),
        "target": round(target, 8),
        "size": round(size, 8),
        "entry_timestamp": row_15m["timestamp"].isoformat(),
        "capital_at_entry": round(runtime.capital, 8),
        "entry_context": build_slippage_context(
            price_reference=entry,
            atr_value=atr_value,
            volume_ratio=(float(row_15m["volume"]) / vol_mean) if vol_mean and vol_mean > 0 else None,
            breakout_distance=abs(entry - rolling_high) if signal == "BUY" and rolling_high else abs(entry - rolling_low) if signal == "SELL" and rolling_low else None,
        ),
    }
    runtime.position = position

    signal_row = {
        "timestamp": row_15m["timestamp"].isoformat(),
        "action": "ENTRY",
        "signal": signal,
        "close": round(entry, 8),
        "atr": round(atr_value, 8),
        "capital": round(runtime.capital, 8),
        "stop": position["stop"],
        "target": position["target"],
        "size": position["size"],
        "entry_slippage_rate": round(position["entry_context"].get("resolved_slippage_rate", 0.0), 8),
        "sentiment_score": round(float(sentiment_score), 8) if sentiment_score is not None else "",
    }
    append_csv(
        config.PAPER_SIGNAL_LOG,
        signal_row,
        signal_log_fieldnames(),
    )
    log_event("entry", **signal_row)
    notify(
        f"[PAPER] {signal} {config.SYMBOL}\n"
        f"Entrada: {entry:.2f}\nStop: {stop:.2f}\nTarget: {target:.2f}\nCapital: {runtime.capital:.2f}"
    )
    print(
        f"ENTRY {signal} ts={row_15m['timestamp']} entry={entry:.2f} "
        f"stop={stop:.2f} target={target:.2f} capital={runtime.capital:.2f}"
    )
    return position


def close_position(runtime, row_15m, exit_reason, exit_price):
    position = runtime.position
    if not position:
        return

    execution = calculate_execution_details(
        position_type=position["type"],
        entry_price=float(position["entry"]),
        exit_price=float(exit_price),
        size=float(position["size"]),
        entry_context=position.get("entry_context"),
        exit_context=build_slippage_context(
            price_reference=float(exit_price),
            atr_value=float(row_15m["atr"]) if not np.isnan(row_15m["atr"]) else None,
            volume_ratio=(
                float(row_15m["volume"]) / float(row_15m["vol_mean"])
                if not np.isnan(row_15m["vol_mean"]) and float(row_15m["vol_mean"]) > 0
                else None
            ),
            breakout_distance=abs(float(exit_price) - float(position["entry"])),
        ),
    )
    pnl = execution["pnl"]
    runtime.capital += pnl
    runtime.last_exit_timestamp = row_15m["timestamp"].isoformat()

    trade_row = {
        "entry_timestamp": position["entry_timestamp"],
        "exit_timestamp": row_15m["timestamp"].isoformat(),
        "type": position["type"],
        "entry": position["entry"],
        "exit": round(float(exit_price), 8),
        "stop": position["stop"],
        "target": position["target"],
        "size": position["size"],
        "exit_reason": exit_reason,
        "pnl": round(pnl, 8),
        "capital_after": round(runtime.capital, 8),
        "entry_slippage_rate": round(execution["entry_slippage_rate"], 8),
        "exit_slippage_rate": round(execution["exit_slippage_rate"], 8),
        "entry_exec_price": round(execution["entry_exec_price"], 8),
        "exit_exec_price": round(execution["exit_exec_price"], 8),
        "fees": round(execution["fees"], 8),
    }
    append_csv(
        config.PAPER_TRADE_LOG,
        trade_row,
        [
            "entry_timestamp",
            "exit_timestamp",
            "type",
            "entry",
            "exit",
            "stop",
            "target",
            "size",
            "exit_reason",
            "pnl",
            "capital_after",
            "entry_slippage_rate",
            "exit_slippage_rate",
            "entry_exec_price",
            "exit_exec_price",
            "fees",
        ],
    )
    log_event("exit", **trade_row)
    notify(
        f"[PAPER] EXIT {position['type']} {config.SYMBOL}\n"
        f"Motivo: {exit_reason}\nPnL: {pnl:.2f}\nCapital: {runtime.capital:.2f}"
    )
    print(
        f"EXIT {position['type']} ts={row_15m['timestamp']} reason={exit_reason} "
        f"pnl={pnl:.2f} capital={runtime.capital:.2f}"
    )
    runtime.position = None


def manage_position(runtime, row_15m):
    position = runtime.position
    if not position:
        return

    high = float(row_15m["high"])
    low = float(row_15m["low"])

    if position["type"] == "BUY":
        if low <= float(position["stop"]):
            close_position(runtime, row_15m, "STOP", float(position["stop"]))
        elif high >= float(position["target"]):
            close_position(runtime, row_15m, "TARGET", float(position["target"]))
    else:
        if high >= float(position["stop"]):
            close_position(runtime, row_15m, "STOP", float(position["stop"]))
        elif low <= float(position["target"]):
            close_position(runtime, row_15m, "TARGET", float(position["target"]))


def process_new_candles(runtime, df_1h, df_15m, sentiment_filter=None):
    processed = 0

    for _, row_15m in df_15m.iterrows():
        candle_timestamp = row_15m["timestamp"]
        if runtime.last_processed_timestamp and candle_timestamp <= pd.Timestamp(runtime.last_processed_timestamp):
            continue

        row_1h = find_row_1h(df_1h, candle_timestamp)
        if row_1h is None:
            runtime.last_processed_timestamp = candle_timestamp.isoformat()
            continue

        manage_position(runtime, row_15m)

        signal = check_signal(row_1h, row_15m)
        if runtime.position is None and signal and supports_signal(signal) and candle_cooldown_done(runtime, candle_timestamp):
            sentiment_allowed, sentiment_score = evaluate_sentiment_trade(sentiment_filter, signal)
            if sentiment_allowed:
                open_position(runtime, signal, row_15m, sentiment_score=sentiment_score)
            else:
                signal_row = {
                    "timestamp": candle_timestamp.isoformat(),
                    "action": "SKIP_SENTIMENT_BLOCKED",
                    "signal": signal,
                    "close": round(float(row_15m["close"]), 8),
                    "atr": round(float(row_15m["atr"]), 8) if not np.isnan(row_15m["atr"]) else None,
                    "capital": round(runtime.capital, 8),
                    "stop": "",
                    "target": "",
                    "size": "",
                    "entry_slippage_rate": "",
                    "sentiment_score": round(float(sentiment_score), 8) if sentiment_score is not None else "",
                }
                append_csv(config.PAPER_SIGNAL_LOG, signal_row, signal_log_fieldnames())
                log_event("signal_blocked_by_sentiment", **signal_row)
        elif signal:
            signal_row = {
                "timestamp": candle_timestamp.isoformat(),
                "action": "SKIP",
                "signal": signal,
                "close": round(float(row_15m["close"]), 8),
                "atr": round(float(row_15m["atr"]), 8) if not np.isnan(row_15m["atr"]) else None,
                "capital": round(runtime.capital, 8),
                "stop": "",
                "target": "",
                "size": "",
                "entry_slippage_rate": "",
                "sentiment_score": "",
            }
            if not supports_signal(signal):
                signal_row["action"] = "SKIP_UNSUPPORTED_MARKET_MODE"
            append_csv(
                config.PAPER_SIGNAL_LOG,
                signal_row,
                signal_log_fieldnames(),
            )

        runtime.last_processed_timestamp = candle_timestamp.isoformat()
        processed += 1

    return processed


def run_once(runtime, source, csv_path, limit):
    df_1h, df_15m = load_market_data(source, csv_path, limit)
    processed = process_new_candles(runtime, df_1h, df_15m, sentiment_filter=build_sentiment_filter())
    log_event(
        "cycle_complete",
        source=source,
        processed=processed,
        capital=round(runtime.capital, 8),
        position_open=runtime.position is not None,
        last_processed_timestamp=runtime.last_processed_timestamp,
    )
    save_state(runtime)
    print(
        f"processed={processed} source={source} capital={runtime.capital:.2f} "
        f"position={'open' if runtime.position else 'flat'} "
        f"last_ts={runtime.last_processed_timestamp}"
    )


def run():
    args = parse_args()
    runtime = load_state(args.reset_state)

    if args.once:
        run_once(runtime, args.source, args.csv_path, args.limit)
        return

    print(
        f"paper trade iniciado source={args.source} symbol={config.SYMBOL} "
        f"timeframe={config.TIMEFRAME} poll={config.PAPER_POLL_INTERVAL_SECONDS}s "
        f"market_mode={market_label()}"
    )
    while True:
        try:
            run_once(runtime, args.source, args.csv_path, args.limit)
        except KeyboardInterrupt:
            save_state(runtime)
            print("\nencerrado pelo usuario")
            return
        except Exception as exc:
            log_event("runner_error", error=str(exc))
            print(f"runner_error={exc}", file=sys.stderr)

        time.sleep(config.PAPER_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
