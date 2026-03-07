"""
walk_forward.py

Validação walk-forward com múltiplas janelas temporais.

Fluxo:
1) divide o histórico em blocos sequenciais (treino/teste)
2) roda backtest em cada bloco
3) resume robustez out-of-sample
"""

import argparse
import os
import sys
from statistics import mean, median

import pandas as pd

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import config
from backtest.backtester import Backtester
from main import calculate_buy_hold_benchmark


CANDLES_PER_DAY_15M = 96


def load_15m_data():
    df = pd.read_csv(config.DATA_PATH)
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def build_1h_from_15m(df_15m):
    return (
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


def run_backtest_window(df_15m_window):
    df_1h_window = build_1h_from_15m(df_15m_window)
    bt = Backtester(df_1h_window, df_15m_window.reset_index(drop=True))
    return bt.run()


def parse_args():
    parser = argparse.ArgumentParser(description="Walk-forward validation em múltiplas janelas")
    parser.add_argument("--train-days", type=int, default=365)
    parser.add_argument("--test-days", type=int, default=90)
    parser.add_argument("--step-days", type=int, default=90)
    parser.add_argument("--max-folds", type=int, default=0, help="0 = sem limite")
    return parser.parse_args()


def run():
    args = parse_args()

    train_size = args.train_days * CANDLES_PER_DAY_15M
    test_size = args.test_days * CANDLES_PER_DAY_15M
    step_size = args.step_days * CANDLES_PER_DAY_15M

    df_15m = load_15m_data()

    print("===== WALK-FORWARD =====")
    print(f"train_days={args.train_days} test_days={args.test_days} step_days={args.step_days}")
    print(f"candles_15m={len(df_15m)}")

    fold_results = []
    fold = 0
    start = 0

    while (start + train_size + test_size) <= len(df_15m):
        fold += 1
        if args.max_folds > 0 and fold > args.max_folds:
            break

        train_start = start
        train_end = start + train_size
        test_start = train_end
        test_end = test_start + test_size

        train_df = df_15m.iloc[train_start:train_end].copy()
        test_df = df_15m.iloc[test_start:test_end].copy()

        train_res = run_backtest_window(train_df)
        test_res = run_backtest_window(test_df)

        benchmark = calculate_buy_hold_benchmark(test_df, config.CAPITAL)
        strategy_delta = None
        if "final_capital" in test_res:
            strategy_delta = round(test_res["final_capital"] - benchmark["final_capital"], 2)

        row = {
            "fold": fold,
            "train_start": str(train_df.iloc[0]["timestamp"]),
            "train_end": str(train_df.iloc[-1]["timestamp"]),
            "test_start": str(test_df.iloc[0]["timestamp"]),
            "test_end": str(test_df.iloc[-1]["timestamp"]),
            "train_final": train_res.get("final_capital"),
            "train_pf": train_res.get("profit_factor"),
            "train_dd": train_res.get("max_drawdown_pct"),
            "test_final": test_res.get("final_capital"),
            "test_pf": test_res.get("profit_factor"),
            "test_dd": test_res.get("max_drawdown_pct"),
            "test_trades": test_res.get("total_trades"),
            "test_vs_bh_delta": strategy_delta,
        }

        fold_results.append(row)

        print(
            f"fold={row['fold']} "
            f"test={row['test_start']}..{row['test_end']} "
            f"test_final={row['test_final']} test_pf={row['test_pf']} "
            f"test_dd={row['test_dd']} trades={row['test_trades']} "
            f"vs_bh_delta={row['test_vs_bh_delta']}"
        )

        start += step_size

    if not fold_results:
        print("Sem folds suficientes para a configuração informada.")
        return

    test_pf = [r["test_pf"] for r in fold_results if r["test_pf"] is not None]
    test_final = [r["test_final"] for r in fold_results if r["test_final"] is not None]
    test_dd = [r["test_dd"] for r in fold_results if r["test_dd"] is not None]
    test_trades = [r["test_trades"] for r in fold_results if r["test_trades"] is not None]

    pf_gt_1 = sum(1 for x in test_pf if x > 1)
    cap_gt_initial = sum(1 for x in test_final if x > config.CAPITAL)

    print("\n===== RESUMO WALK-FORWARD =====")
    print(f"folds: {len(fold_results)}")
    print(f"test_pf_mean: {round(mean(test_pf), 3)}")
    print(f"test_pf_median: {round(median(test_pf), 3)}")
    print(f"test_pf_gt_1_folds: {pf_gt_1}/{len(test_pf)}")
    print(f"test_final_mean: {round(mean(test_final), 2)}")
    print(f"test_final_median: {round(median(test_final), 2)}")
    print(f"test_final_gt_initial_folds: {cap_gt_initial}/{len(test_final)}")
    print(f"test_dd_mean_pct: {round(mean(test_dd), 2)}")
    print(f"test_dd_worst_pct: {round(min(test_dd), 2)}")
    print(f"test_trades_mean: {round(mean(test_trades), 1)}")


if __name__ == "__main__":
    run()
