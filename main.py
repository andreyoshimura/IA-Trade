"""
main.py

Executa:
1) Backtest completo
2) Walk-forward (70% treino / 30% teste)
3) Monte Carlo no período de teste
"""

import pandas as pd
import config

from backtest.backtester import Backtester
from analysis.monte_carlo import run_monte_carlo


def load_data():

    df_15m = pd.read_csv(config.DATA_PATH)
    df_15m = df_15m.sort_values("timestamp").reset_index(drop=True)

    df_15m["timestamp"] = pd.to_datetime(df_15m["timestamp"])

    df_1h = df_15m.resample(
        "1h",
        on="timestamp"
    ).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    }).dropna().reset_index()

    return df_1h, df_15m


def split_data(df_1h, df_15m, train_ratio=0.7):

    split_index = int(len(df_15m) * train_ratio)

    df_15m_train = df_15m.iloc[:split_index]
    df_15m_test = df_15m.iloc[split_index:]

    split_1h_index = int(len(df_1h) * train_ratio)

    df_1h_train = df_1h.iloc[:split_1h_index]
    df_1h_test = df_1h.iloc[split_1h_index:]

    return df_1h_train, df_15m_train, df_1h_test, df_15m_test


def run_backtest(df_1h, df_15m, label):

    print(f"\n===== BACKTEST {label} =====")

    bt = Backtester(df_1h, df_15m)
    results = bt.run()

    for k, v in results.items():
        print(f"{k}: {v}")

    return bt


def run():

    df_1h, df_15m = load_data()

    # 1️⃣ Backtest completo
    bt_full = run_backtest(df_1h, df_15m, "COMPLETO")

    # 2️⃣ Walk-forward split
    df_1h_train, df_15m_train, df_1h_test, df_15m_test = split_data(df_1h, df_15m)

    bt_train = run_backtest(df_1h_train, df_15m_train, "TREINO (70%)")
    bt_test = run_backtest(df_1h_test, df_15m_test, "TESTE (30%)")

    # 3️⃣ Monte Carlo no período de teste
    trades_test = bt_test.get_trades()

    mc_results = run_monte_carlo(
        trades_test,
        initial_capital=config.CAPITAL,
        simulations=1000
    )

    print("\n===== MONTE CARLO (PERIODO TESTE) =====")
    for k, v in mc_results.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    run()
