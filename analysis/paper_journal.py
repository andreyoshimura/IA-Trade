"""
paper_journal.py

Gera resumo diário ou semanal a partir dos logs do paper trade.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta

import pandas as pd

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import config
from notifier.telegram import send_message


def parse_args():
    parser = argparse.ArgumentParser(description="Diario automatico do paper trade")
    parser.add_argument("--period", choices=["daily", "weekly"], default="daily")
    parser.add_argument("--date", help="Data base no formato YYYY-MM-DD")
    parser.add_argument("--stdout", action="store_true", help="Imprime o relatorio alem de salvar")
    parser.add_argument("--send-telegram", action="store_true", help="Envia o relatorio via Telegram")
    return parser.parse_args()


def ensure_report_dir():
    os.makedirs(config.PAPER_REPORT_DIR, exist_ok=True)


def parse_base_date(raw_date):
    if raw_date:
        return datetime.strptime(raw_date, "%Y-%m-%d").date()
    return datetime.utcnow().date()


def load_trades():
    if not os.path.exists(config.PAPER_TRADE_LOG):
        return pd.DataFrame()

    df = pd.read_csv(config.PAPER_TRADE_LOG)
    if df.empty:
        return df

    df["entry_timestamp"] = pd.to_datetime(df["entry_timestamp"], utc=True).dt.tz_localize(None)
    df["exit_timestamp"] = pd.to_datetime(df["exit_timestamp"], utc=True).dt.tz_localize(None)
    numeric_cols = ["entry", "exit", "stop", "target", "size", "pnl", "capital_after"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_events():
    if not os.path.exists(config.PAPER_EVENT_LOG):
        return pd.DataFrame()

    rows = []
    with open(config.PAPER_EVENT_LOG, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_localize(None)
    return df


def compute_window(period, base_date):
    start = pd.Timestamp(base_date)
    if period == "weekly":
        start = start - pd.Timedelta(days=start.weekday())
        end = start + pd.Timedelta(days=7)
    else:
        end = start + pd.Timedelta(days=1)
    return start, end


def filter_by_window(df, column, start, end):
    if df.empty:
        return df
    return df[(df[column] >= start) & (df[column] < end)].copy()


def summarize_trades(df):
    if df.empty:
        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "winrate": 0.0,
            "net_pnl": 0.0,
            "avg_pnl": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "final_capital": None,
        }

    wins = int((df["pnl"] > 0).sum())
    losses = int((df["pnl"] < 0).sum())
    trades = len(df)
    return {
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "winrate": round(wins / trades * 100, 2),
        "net_pnl": round(df["pnl"].sum(), 2),
        "avg_pnl": round(df["pnl"].mean(), 2),
        "best_trade": round(df["pnl"].max(), 2),
        "worst_trade": round(df["pnl"].min(), 2),
        "final_capital": round(df.iloc[-1]["capital_after"], 2),
    }


def summarize_events(df):
    if df.empty:
        return {"cycles": 0, "entries": 0, "exits": 0, "errors": 0}

    return {
        "cycles": int((df["event"] == "cycle_complete").sum()),
        "entries": int((df["event"] == "entry").sum()),
        "exits": int((df["event"] == "exit").sum()),
        "errors": int(df["event"].isin(["runner_error", "notification_error"]).sum()),
    }


def render_report(period, start, end, trade_summary, event_summary, trades_df):
    lines = [
        f"# Paper Trade {period.capitalize()} Report",
        "",
        f"Window: {start.date()} to {(end - pd.Timedelta(seconds=1)).date()}",
        "",
        "## Trading Summary",
        f"- Trades fechados: {trade_summary['trades']}",
        f"- Wins: {trade_summary['wins']} | Losses: {trade_summary['losses']} | Winrate: {trade_summary['winrate']}%",
        f"- PnL liquido: {trade_summary['net_pnl']}",
        f"- PnL medio: {trade_summary['avg_pnl']}",
        f"- Melhor trade: {trade_summary['best_trade']}",
        f"- Pior trade: {trade_summary['worst_trade']}",
        f"- Capital final: {trade_summary['final_capital'] if trade_summary['final_capital'] is not None else 'n/d'}",
        "",
        "## Operations Summary",
        f"- Ciclos processados: {event_summary['cycles']}",
        f"- Entradas: {event_summary['entries']}",
        f"- Saidas: {event_summary['exits']}",
        f"- Erros operacionais: {event_summary['errors']}",
    ]

    if not trades_df.empty:
        lines.extend(
            [
                "",
                "## Closed Trades",
            ]
        )
        for _, row in trades_df.iterrows():
            lines.append(
                f"- {row['exit_timestamp']}: {row['type']} {row['exit_reason']} pnl={row['pnl']:.2f} capital={row['capital_after']:.2f}"
            )

    return "\n".join(lines) + "\n"


def build_report_filename(period, start):
    ensure_report_dir()
    return os.path.join(
        config.PAPER_REPORT_DIR,
        f"paper_{period}_{start.date().isoformat()}.md",
    )


def maybe_send_telegram(report, enabled):
    if not enabled:
        return False

    if not config.ENABLE_NOTIFICATIONS:
        print("telegram_skipped=ENABLE_NOTIFICATIONS_false")
        return False

    try:
        sent = send_message(report[:4000])
    except Exception as exc:
        print(f"telegram_error={exc}")
        return False

    if sent:
        print("telegram_sent=true")
    else:
        print("telegram_sent=false")
    return sent


def run():
    args = parse_args()
    base_date = parse_base_date(args.date)
    start, end = compute_window(args.period, base_date)

    trades_df = filter_by_window(load_trades(), "exit_timestamp", start, end)
    events_df = filter_by_window(load_events(), "timestamp", start, end)

    sorted_trades_df = trades_df.sort_values("exit_timestamp") if "exit_timestamp" in trades_df.columns else trades_df

    report = render_report(
        args.period,
        start,
        end,
        summarize_trades(trades_df),
        summarize_events(events_df),
        sorted_trades_df,
    )

    output_path = build_report_filename(args.period, start)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(report)

    if args.stdout:
        print(report)

    maybe_send_telegram(report, args.send_telegram)
    print(f"saved_report={output_path}")


if __name__ == "__main__":
    run()
