import numpy as np


def run_monte_carlo(trade_returns, initial_capital=1000, simulations=1000):
    """
    Executa simulação Monte Carlo embaralhando a ordem dos retornos por trade.
    Os retornos devem ser relativos ao capital pré-trade para preservar
    o efeito de compounding em estratégias com sizing dinâmico.
    Protegido contra lista vazia.
    """

    if trade_returns is None or len(trade_returns) == 0:
        return {
            "mean_final_capital": initial_capital,
            "worst_final_capital": initial_capital,
            "best_final_capital": initial_capital,
            "mean_max_drawdown_pct": 0.0,
            "worst_drawdown_pct": 0.0,
        }

    trade_returns = np.asarray(trade_returns, dtype=float)

    final_capitals = []
    max_drawdowns = []

    rng = np.random.default_rng()

    for _ in range(simulations):
        sampled_returns = rng.choice(trade_returns, size=len(trade_returns), replace=True)
        equity = initial_capital * np.cumprod(1 + sampled_returns)

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
