import numpy as np


def run_monte_carlo(trades, initial_capital=1000, simulations=1000):
    """
    Executa simulação Monte Carlo embaralhando a ordem dos trades.
    Protegido contra lista vazia.
    """

    # 🔴 Proteção contra lista vazia
    if trades is None or len(trades) == 0:
        return {
            "mean_final_capital": initial_capital,
            "worst_final_capital": initial_capital,
            "best_final_capital": initial_capital,
            "mean_max_drawdown_pct": 0.0,
            "worst_drawdown_pct": 0.0,
        }

    trades = np.array(trades)

    final_capitals = []
    max_drawdowns = []

    for _ in range(simulations):

        shuffled = np.random.permutation(trades)

        equity = np.cumsum(shuffled) + initial_capital

        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak

        final_capitals.append(equity[-1])
        max_drawdowns.append(drawdown.min() * 100)

    return {
        "mean_final_capital": round(np.mean(final_capitals), 2),
        "worst_final_capital": round(np.min(final_capitals), 2),
        "best_final_capital": round(np.max(final_capitals), 2),
        "mean_max_drawdown_pct": round(np.mean(max_drawdowns), 2),
        "worst_drawdown_pct": round(np.min(max_drawdowns), 2),
    }
