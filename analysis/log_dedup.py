"""
Helpers para deduplicar logs de paper trade reprocessados.
"""

import pandas as pd


TRADE_DEDUPE_KEYS = ["entry_timestamp", "exit_timestamp", "type", "entry", "exit", "size", "pnl"]
SIGNAL_DEDUPE_KEYS = ["timestamp", "action", "signal", "close", "atr", "capital", "stop", "target", "size", "entry_slippage_rate"]


def dedupe_rows(df: pd.DataFrame, keys: list[str]) -> tuple[pd.DataFrame, int]:
    if df is None or df.empty:
        return df, 0
    existing = [key for key in keys if key in df.columns]
    if not existing:
        return df.copy(), 0
    before = len(df)
    deduped = df.drop_duplicates(subset=existing).copy()
    removed = before - len(deduped)
    return deduped.reset_index(drop=True), removed


def dedupe_trade_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    return dedupe_rows(df, TRADE_DEDUPE_KEYS)


def dedupe_signal_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if df is None or df.empty:
        return df, 0
    working = df.copy()
    if "sentiment_score" in working.columns:
        score_numeric = pd.to_numeric(working["sentiment_score"], errors="coerce")
        working["__score_present"] = score_numeric.notna().astype(int)
        working["__score_value"] = score_numeric.fillna(-999999)
        working = working.sort_values(["__score_present", "__score_value"], ascending=[False, False])
    deduped, removed = dedupe_rows(working, SIGNAL_DEDUPE_KEYS)
    for col in ["__score_present", "__score_value"]:
        if col in deduped.columns:
            deduped = deduped.drop(columns=[col])
    return deduped, removed
