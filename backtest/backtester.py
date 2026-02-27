import numpy as np
from strategy.pullback_trend import prepare_indicators, check_signal
from risk.risk_manager import calculate_position
from config import CAPITAL


class Backtester:

    def __init__(self, df_1h, df_15m):
        self.df_1h, self.df_15m = prepare_indicators(df_1h, df_15m)
        self.initial_capital = CAPITAL
        self.capital = CAPITAL
        self.trades = []

    def run(self):

        position = None

        for i in range(100, len(self.df_15m)):

            idx_1h = int(i / 4)
            if idx_1h >= len(self.df_1h):
                break

            row_15m = self.df_15m.iloc[i]
            row_1h = self.df_1h.iloc[idx_1h]

            signal = check_signal(row_1h, row_15m)

            if position is None and signal:

                entry = row_15m['close']
                atr_value = row_15m['atr']

                if np.isnan(atr_value):
                    continue

                stop = entry - atr_value * 1.8 if signal == "BUY" else entry + atr_value * 1.8
                target = entry + abs(entry - stop) * 2.5 if signal == "BUY" else entry - abs(entry - stop) * 2.5

                size = calculate_position(entry, stop)

                position = {
                    "type": signal,
                    "entry": entry,
                    "stop": stop,
                    "target": target,
                    "size": size
                }

            elif position:

                high = row_15m['high']
                low = row_15m['low']

                if position["type"] == "BUY":

                    if low <= position["stop"]:
                        loss = (position["stop"] - position["entry"]) * position["size"]
                        self.capital += loss
                        self.trades.append(loss)
                        position = None

                    elif high >= position["target"]:
                        gain = (position["target"] - position["entry"]) * position["size"]
                        self.capital += gain
                        self.trades.append(gain)
                        position = None

                elif position["type"] == "SELL":

                    if high >= position["stop"]:
                        loss = (position["entry"] - position["stop"]) * position["size"]
                        self.capital += loss
                        self.trades.append(loss)
                        position = None

                    elif low <= position["target"]:
                        gain = (position["entry"] - position["target"]) * position["size"]
                        self.capital += gain
                        self.trades.append(gain)
                        position = None

        return self.results()

    def results(self):

        trades = np.array(self.trades)

        if len(trades) == 0:
            return {"error": "No trades executed"}

        equity_curve = np.cumsum(trades) + self.initial_capital
        peak = np.maximum.accumulate(equity_curve)
        drawdown = (equity_curve - peak) / peak
        max_drawdown = drawdown.min()

        winrate = np.sum(trades > 0) / len(trades)
        avg_win = trades[trades > 0].mean() if np.any(trades > 0) else 0
        avg_loss = trades[trades < 0].mean() if np.any(trades < 0) else 0

        expectancy = (winrate * avg_win) + ((1 - winrate) * avg_loss)

        profit_factor = (
            abs(trades[trades > 0].sum() / trades[trades < 0].sum())
            if np.any(trades < 0) else 0
        )

        return {
            "initial_capital": self.initial_capital,
            "final_capital": round(self.capital, 2),
            "total_trades": len(trades),
            "winrate": round(winrate, 3),
            "expectancy": round(expectancy, 4),
            "profit_factor": round(profit_factor, 3),
            "max_drawdown_pct": round(max_drawdown * 100, 2)
        }
