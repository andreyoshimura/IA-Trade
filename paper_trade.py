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


def calculate_trade_result(position_type, entry_price, exit_price, size):
    if size <= 0:
        return 0.0

    fee_rate = getattr(config, "FEE_RATE", 0.0)
    slippage_rate = getattr(config, "SLIPPAGE_RATE", 0.0)

    if position_type == "BUY":
        exec_entry = entry_price * (1 + slippage_rate)
        exec_exit = exit_price * (1 - slippage_rate)
        gross_result = (exec_exit - exec_entry) * size
    else:
        exec_entry = entry_price * (1 - slippage_rate)
        exec_exit = exit_price * (1 + slippage_rate)
        gross_result = (exec_entry - exec_exit) * size

    entry_notional = abs(exec_entry * size)
    exit_notional = abs(exec_exit * size)
    fees = (entry_notional + exit_notional) * fee_rate
    return gross_result - fees


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


def open_position(runtime, signal, row_15m):
    entry = float(row_15m["close"])
    atr_value = float(row_15m["atr"])
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
    }
    append_csv(
        config.PAPER_SIGNAL_LOG,
        signal_row,
        ["timestamp", "action", "signal", "close", "atr", "capital", "stop", "target", "size"],
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

    pnl = calculate_trade_result(
        position_type=position["type"],
        entry_price=float(position["entry"]),
        exit_price=float(exit_price),
        size=float(position["size"]),
    )
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


def process_new_candles(runtime, df_1h, df_15m):
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
        if runtime.position is None and signal and candle_cooldown_done(runtime, candle_timestamp):
            open_position(runtime, signal, row_15m)
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
            }
            append_csv(
                config.PAPER_SIGNAL_LOG,
                signal_row,
                ["timestamp", "action", "signal", "close", "atr", "capital", "stop", "target", "size"],
            )

        runtime.last_processed_timestamp = candle_timestamp.isoformat()
        processed += 1

    return processed


def run_once(runtime, source, csv_path, limit):
    df_1h, df_15m = load_market_data(source, csv_path, limit)
    processed = process_new_candles(runtime, df_1h, df_15m)
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
        f"timeframe={config.TIMEFRAME} poll={config.PAPER_POLL_INTERVAL_SECONDS}s"
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
