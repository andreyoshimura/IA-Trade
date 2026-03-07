"""
backtester.py

Motor principal de backtest.

Responsabilidades:
- Iterar candles
- Executar sinais da estratégia
- Aplicar gestão de risco
- Atualizar capital
- Calcular métricas finais
- Expor lista de trades para validação estatística
"""

import numpy as np
import config
from strategy.breakout_structural import prepare_indicators, check_signal
from risk.risk_manager import calculate_position


class Backtester:

    def __init__(self, df_1h, df_15m):

        # Preparar indicadores
        self.df_1h, self.df_15m = prepare_indicators(df_1h, df_15m)

        # Capital inicial
        self.initial_capital = config.CAPITAL

        # Capital dinâmico
        self.capital = config.CAPITAL

        # Lista de resultados individuais
        self.trades = []

    def run(self):

        position = None
        last_exit_index = -config.TRADE_COOLDOWN_CANDLES

        for i in range(100, len(self.df_15m)):

            idx_1h = int(i / 4)
            if idx_1h >= len(self.df_1h):
                break

            row_15m = self.df_15m.iloc[i]
            row_1h = self.df_1h.iloc[idx_1h]

            signal = check_signal(row_1h, row_15m)

            # ======================
            # ABERTURA
            # ======================

            cooldown_done = (i - last_exit_index) >= config.TRADE_COOLDOWN_CANDLES
            if position is None and signal and cooldown_done:

                entry = row_15m["close"]
                atr_value = row_15m["atr"]

                if np.isnan(atr_value):
                    continue

                if signal == "BUY":
                    stop = entry - atr_value * config.ATR_MULTIPLIER
                    target = entry + abs(entry - stop) * config.RR_RATIO
                else:
                    stop = entry + atr_value * config.ATR_MULTIPLIER
                    target = entry - abs(entry - stop) * config.RR_RATIO

                size = calculate_position(
                    entry,
                    stop,
                    self.capital,
                    config.RISK_PER_TRADE
                )

                position = {
                    "type": signal,
                    "entry": entry,
                    "stop": stop,
                    "target": target,
                    "size": size
                }

            # ======================
            # GERENCIAMENTO
            # ======================

            elif position:

                high = row_15m["high"]
                low = row_15m["low"]

                if position["type"] == "BUY":

                    if low <= position["stop"]:
                        trade_result = self._calculate_trade_result(
                            position_type="BUY",
                            entry_price=position["entry"],
                            exit_price=position["stop"],
                            size=position["size"],
                        )
                        self.capital += trade_result
                        self.trades.append(trade_result)
                        position = None
                        last_exit_index = i

                    elif high >= position["target"]:
                        trade_result = self._calculate_trade_result(
                            position_type="BUY",
                            entry_price=position["entry"],
                            exit_price=position["target"],
                            size=position["size"],
                        )
                        self.capital += trade_result
                        self.trades.append(trade_result)
                        position = None
                        last_exit_index = i

                elif position["type"] == "SELL":

                    if high >= position["stop"]:
                        trade_result = self._calculate_trade_result(
                            position_type="SELL",
                            entry_price=position["entry"],
                            exit_price=position["stop"],
                            size=position["size"],
                        )
                        self.capital += trade_result
                        self.trades.append(trade_result)
                        position = None
                        last_exit_index = i

                    elif low <= position["target"]:
                        trade_result = self._calculate_trade_result(
                            position_type="SELL",
                            entry_price=position["entry"],
                            exit_price=position["target"],
                            size=position["size"],
                        )
                        self.capital += trade_result
                        self.trades.append(trade_result)
                        position = None
                        last_exit_index = i

        return self.results()

    def _calculate_trade_result(self, position_type, entry_price, exit_price, size):
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

    # ======================
    # MÉTRICAS
    # ======================

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

    # ======================
    # EXPOSIÇÃO DOS TRADES
    # ======================

    def get_trades(self):
        """
        Retorna lista de resultados individuais.
        Necessário para Monte Carlo.
        """
        return self.trades
