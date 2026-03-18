"""
sentiment_report.py

Resume os scores de sentimento registrados no paper trade.
"""

import argparse
import os
import sys

import pandas as pd

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import config


def parse_args():
    parser = argparse.ArgumentParser(description="Resumo dos scores de sentimento do paper trade")
    parser.add_argument("--start-date", help="Data inicial no formato YYYY-MM-DD")
    parser.add_argument("--end-date", help="Data final no formato YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=0, help="Limita a quantidade de sinais mais recentes")
    parser.add_argument("--csv", default="", help="Salva os sinais filtrados em CSV")
    return parser.parse_args()


def load_signals():
    if not os.path.exists(config.PAPER_SIGNAL_LOG):
        return pd.DataFrame()

    df = pd.read_csv(config.PAPER_SIGNAL_LOG)
    if df.empty:
        return df

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce").dt.tz_localize(None)

    for col in ["close", "atr", "capital", "stop", "target", "size", "entry_slippage_rate", "sentiment_score"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def filter_signals(df, start_date=None, end_date=None, limit=0):
    if df.empty:
        return df

    filtered = df.copy()
    if start_date:
        filtered = filtered[filtered["timestamp"] >= pd.Timestamp(start_date)]
    if end_date:
        filtered = filtered[filtered["timestamp"] < pd.Timestamp(end_date) + pd.Timedelta(days=1)]

    filtered = filtered.sort_values("timestamp")
    if limit > 0:
        filtered = filtered.tail(limit)
    return filtered.reset_index(drop=True)


def safe_quantile(series, q):
    clean = series.dropna()
    if clean.empty:
        return None
    return round(float(clean.quantile(q)), 8)


def render_summary(df):
    if df.empty:
        return "Nenhum sinal encontrado para o filtro informado."

    scored = df[df["sentiment_score"].notna()].copy()
    lines = [
        "===== SENTIMENT REPORT =====",
        f"signals={len(df)}",
        f"window_start={df.iloc[0]['timestamp']}",
        f"window_end={df.iloc[-1]['timestamp']}",
        f"scored_signals={len(scored)}",
        f"blocked_by_sentiment={int((df['action'] == 'SKIP_SENTIMENT_BLOCKED').sum())}",
        f"entries={int((df['action'] == 'ENTRY').sum())}",
    ]

    if scored.empty:
        lines.append("Nenhum sentiment_score numerico encontrado ainda.")
        return "\n".join(lines)

    scores = scored["sentiment_score"]
    lines.extend(
        [
            f"score_min={round(float(scores.min()), 8)}",
            f"score_p25={safe_quantile(scores, 0.25)}",
            f"score_p50={safe_quantile(scores, 0.50)}",
            f"score_p75={safe_quantile(scores, 0.75)}",
            f"score_max={round(float(scores.max()), 8)}",
            f"score_mean={round(float(scores.mean()), 8)}",
            "",
            "by_action:",
        ]
    )

    grouped = (
        scored.groupby("action", dropna=False)
        .agg(
            count=("action", "size"),
            score_mean=("sentiment_score", "mean"),
            score_median=("sentiment_score", "median"),
            score_min=("sentiment_score", "min"),
            score_max=("sentiment_score", "max"),
        )
        .reset_index()
    )
    for _, row in grouped.iterrows():
        lines.append(
            "  "
            f"action={row['action']} "
            f"count={int(row['count'])} "
            f"mean={round(float(row['score_mean']), 8)} "
            f"median={round(float(row['score_median']), 8)} "
            f"min={round(float(row['score_min']), 8)} "
            f"max={round(float(row['score_max']), 8)}"
        )

    min_signals = int(getattr(config, "SENTIMENT_MIN_SIGNALS_FOR_THRESHOLD", 20))
    enough_sample = len(scored) >= min_signals
    lines.extend(
        [
            "",
            f"threshold_sample_minimum={min_signals}",
            f"threshold_sample_ready={enough_sample}",
        ]
    )

    if enough_sample:
        suggestion = max(safe_quantile(scores.abs(), 0.75) or 0.0, 0.2)
        lines.extend(
            [
                f"suggested_threshold_floor={round(float(suggestion), 8)}",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "suggested_threshold_floor=insufficient_sample",
                "",
            ]
        )

    lines.extend(
        [
            "recent_scored_signals:",
        ]
    )
    for _, row in scored.tail(10).iterrows():
        lines.append(
            "  "
            f"{row['timestamp']} action={row['action']} signal={row.get('signal')} "
            f"score={round(float(row['sentiment_score']), 8)}"
        )

    return "\n".join(lines)


def maybe_save_csv(df, path):
    if not path:
        return
    df.to_csv(path, index=False)
    print(f"saved_csv={path}")


def run():
    args = parse_args()
    signals = load_signals()
    filtered = filter_signals(signals, start_date=args.start_date, end_date=args.end_date, limit=args.limit)
    print(render_summary(filtered))
    if not filtered.empty:
        maybe_save_csv(filtered, args.csv)


if __name__ == "__main__":
    run()
