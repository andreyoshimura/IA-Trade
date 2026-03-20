"""
slippage_report.py

Resume o comportamento do slippage efetivo registrado no paper trade.
"""

import argparse
import os
import sys

import pandas as pd

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import config
from analysis.log_dedup import dedupe_trade_rows


DEFAULT_COLUMNS = [
    "entry_timestamp",
    "exit_timestamp",
    "type",
    "exit_reason",
    "pnl",
    "entry_slippage_rate",
    "exit_slippage_rate",
    "fees",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Resumo de slippage do paper trade")
    parser.add_argument("--start-date", help="Data inicial no formato YYYY-MM-DD")
    parser.add_argument("--end-date", help="Data final no formato YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=0, help="Limita a quantidade de trades mais recentes")
    parser.add_argument("--csv", default="", help="Salva os trades filtrados em CSV")
    return parser.parse_args()


def load_trades():
    if not os.path.exists(config.PAPER_TRADE_LOG):
        return pd.DataFrame()

    df = pd.read_csv(config.PAPER_TRADE_LOG)
    if df.empty:
        return df

    for col in ["entry_timestamp", "exit_timestamp"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True, errors="coerce").dt.tz_localize(None)

    numeric_cols = [
        "entry",
        "exit",
        "stop",
        "target",
        "size",
        "pnl",
        "capital_after",
        "entry_slippage_rate",
        "exit_slippage_rate",
        "entry_exec_price",
        "exit_exec_price",
        "fees",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df, _ = dedupe_trade_rows(df)
    return df


def filter_trades(df, start_date=None, end_date=None, limit=0):
    if df.empty:
        return df

    filtered = df.copy()

    if start_date:
        filtered = filtered[filtered["exit_timestamp"] >= pd.Timestamp(start_date)]
    if end_date:
        filtered = filtered[filtered["exit_timestamp"] < pd.Timestamp(end_date) + pd.Timedelta(days=1)]

    filtered = filtered.sort_values("exit_timestamp")

    if limit > 0:
        filtered = filtered.tail(limit)

    return filtered.reset_index(drop=True)


def safe_percentile(series, percentile):
    clean = series.dropna()
    if clean.empty:
        return None
    return round(float(clean.quantile(percentile / 100)), 8)


def summarize_side(series):
    clean = series.dropna()
    if clean.empty:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "p75": None,
            "p90": None,
            "p95": None,
            "max": None,
        }

    return {
        "count": int(clean.count()),
        "mean": round(float(clean.mean()), 8),
        "median": round(float(clean.median()), 8),
        "p75": safe_percentile(clean, 75),
        "p90": safe_percentile(clean, 90),
        "p95": safe_percentile(clean, 95),
        "max": round(float(clean.max()), 8),
    }


def render_summary(df):
    if df.empty:
        return "Nenhum trade encontrado para o filtro informado."

    entry_summary = summarize_side(df["entry_slippage_rate"])
    exit_summary = summarize_side(df["exit_slippage_rate"])
    fee_total = round(float(df["fees"].fillna(0).sum()), 8)
    pnl_total = round(float(df["pnl"].fillna(0).sum()), 8)

    lines = [
        "===== SLIPPAGE REPORT =====",
        f"trades={len(df)}",
        f"window_start={df.iloc[0]['exit_timestamp']}",
        f"window_end={df.iloc[-1]['exit_timestamp']}",
        f"pnl_total={pnl_total}",
        f"fees_total={fee_total}",
        "",
        "entry_slippage:",
        f"  count={entry_summary['count']}",
        f"  mean={entry_summary['mean']}",
        f"  median={entry_summary['median']}",
        f"  p75={entry_summary['p75']}",
        f"  p90={entry_summary['p90']}",
        f"  p95={entry_summary['p95']}",
        f"  max={entry_summary['max']}",
        "",
        "exit_slippage:",
        f"  count={exit_summary['count']}",
        f"  mean={exit_summary['mean']}",
        f"  median={exit_summary['median']}",
        f"  p75={exit_summary['p75']}",
        f"  p90={exit_summary['p90']}",
        f"  p95={exit_summary['p95']}",
        f"  max={exit_summary['max']}",
        "",
        "by_exit_reason:",
    ]

    grouped = (
        df.groupby("exit_reason", dropna=False)
        .agg(
            trades=("exit_reason", "size"),
            pnl=("pnl", "sum"),
            fees=("fees", "sum"),
            entry_slippage_mean=("entry_slippage_rate", "mean"),
            exit_slippage_mean=("exit_slippage_rate", "mean"),
        )
        .reset_index()
    )

    for _, row in grouped.iterrows():
        lines.append(
            "  "
            f"reason={row['exit_reason']} "
            f"trades={int(row['trades'])} "
            f"pnl={round(float(row['pnl']), 8)} "
            f"fees={round(float(row['fees']), 8)} "
            f"entry_mean={round(float(row['entry_slippage_mean']), 8) if pd.notna(row['entry_slippage_mean']) else None} "
            f"exit_mean={round(float(row['exit_slippage_mean']), 8) if pd.notna(row['exit_slippage_mean']) else None}"
        )

    lines.extend(
        [
            "",
            "recent_trades:",
        ]
    )

    for _, row in df.tail(10).iterrows():
        lines.append(
            "  "
            f"{row['exit_timestamp']} {row['type']} {row['exit_reason']} "
            f"pnl={round(float(row['pnl']), 8)} "
            f"entry_slip={round(float(row['entry_slippage_rate']), 8) if pd.notna(row['entry_slippage_rate']) else None} "
            f"exit_slip={round(float(row['exit_slippage_rate']), 8) if pd.notna(row['exit_slippage_rate']) else None}"
        )

    return "\n".join(lines)


def maybe_save_csv(df, path):
    if not path:
        return
    export_columns = [col for col in DEFAULT_COLUMNS if col in df.columns]
    df.to_csv(path, index=False, columns=export_columns)
    print(f"saved_csv={path}")


def run():
    args = parse_args()
    trades = load_trades()
    filtered = filter_trades(
        trades,
        start_date=args.start_date,
        end_date=args.end_date,
        limit=args.limit,
    )

    print(render_summary(filtered))
    if not filtered.empty:
        maybe_save_csv(filtered, args.csv)


if __name__ == "__main__":
    run()
