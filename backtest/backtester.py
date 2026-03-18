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
from strategy.breakout_structural import prepare_indicators
from risk.risk_manager import calculate_position
from utils.execution_costs import build_slippage_context, calculate_trade_result
from utils.market_mode import supports_signal


class Backtester:

    def __init__(self, df_1h, df_15m, prepared_data=False):

        # Permite reaproveitar features precomputadas em rotinas de sweep.
        if prepared_data:
            self.df_1h, self.df_15m = df_1h, df_15m
        else:
            self.df_1h, self.df_15m = prepare_indicators(df_1h, df_15m)

        # Capital inicial
        self.initial_capital = config.CAPITAL

        # Capital dinâmico
        self.capital = config.CAPITAL

        # Lista de resultados individuais
        self.trades = []
        self.trade_returns = []

    def run(self):

        position = None
        last_exit_index = -config.TRADE_COOLDOWN_CANDLES
        df_15m = self.df_15m
        df_1h = self.df_1h

        close_15m = df_15m["close"].to_numpy()
        high_15m = df_15m["high"].to_numpy()
        low_15m = df_15m["low"].to_numpy()
        volume_15m = df_15m["volume"].to_numpy()
        atr_15m = df_15m["atr"].to_numpy()
        rolling_high_15m = df_15m["rolling_high"].to_numpy()
        rolling_low_15m = df_15m["rolling_low"].to_numpy()
        vol_mean_15m = df_15m["vol_mean"].to_numpy()
        atr_regime_mean_15m = df_15m["atr_regime_mean"].to_numpy()

        adx_1h = df_1h["adx"].to_numpy()
        ema_slope_1h = df_1h["ema_slope"].to_numpy()

        for i in range(100, len(df_15m)):

            idx_1h = int(i / 4)
            if idx_1h >= len(df_1h):
                break

            adx_value = adx_1h[idx_1h]
            rolling_high = rolling_high_15m[i]
            rolling_low = rolling_low_15m[i]
            vol_mean = vol_mean_15m[i]
            atr_value = atr_15m[i]
            signal = None

            if not (
                np.isnan(adx_value) or
                np.isnan(rolling_high) or
                np.isnan(rolling_low) or
                np.isnan(vol_mean) or
                np.isnan(atr_value)
            ):
                if adx_value >= config.MIN_ADX:
                    if getattr(config, "ATR_EXPANSION_FILTER", False):
                        atr_regime_mean = atr_regime_mean_15m[i]
                        if not np.isnan(atr_regime_mean):
                            min_atr = atr_regime_mean * config.ATR_EXPANSION_FACTOR
                            atr_expansion_ok = atr_value >= min_atr
                        else:
                            atr_expansion_ok = False
                    else:
                        atr_expansion_ok = True

                    if atr_expansion_ok:
                        close_value = close_15m[i]
                        volume_value = volume_15m[i]
                        ema_slope_value = ema_slope_1h[idx_1h]
                        min_volume = vol_mean * config.MIN_VOLUME_FACTOR

                        if (
                            ema_slope_value > 0 and
                            close_value > (rolling_high + atr_value * config.BREAKOUT_BUFFER) and
                            volume_value > min_volume
                        ):
                            signal = "BUY"
                        elif (
                            ema_slope_value < 0 and
                            close_value < (rolling_low - atr_value * config.BREAKOUT_BUFFER) and
                            volume_value > min_volume
                        ):
                            signal = "SELL"

            # ======================
            # ABERTURA
            # ======================

            cooldown_done = (i - last_exit_index) >= config.TRADE_COOLDOWN_CANDLES
            if position is None and signal and cooldown_done and supports_signal(signal):

                entry = close_15m[i]

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
                    "size": size,
                    "entry_context": build_slippage_context(
                        price_reference=entry,
                        atr_value=atr_value,
                        volume_ratio=(volume_value / vol_mean) if vol_mean > 0 else None,
                        breakout_distance=abs(entry - rolling_high) if signal == "BUY" else abs(entry - rolling_low),
                    ),
                }

            # ======================
            # GERENCIAMENTO
            # ======================

            elif position:

                high = high_15m[i]
                low = low_15m[i]

                if position["type"] == "BUY":

                    if low <= position["stop"]:
                        capital_before_trade = self.capital
                        trade_result = self._calculate_trade_result(
                            position_type="BUY",
                            entry_price=position["entry"],
                            exit_price=position["stop"],
                            size=position["size"],
                            entry_context=position.get("entry_context"),
                            exit_context=build_slippage_context(
                                price_reference=position["stop"],
                                atr_value=atr_value,
                                volume_ratio=(volume_value / vol_mean) if vol_mean > 0 else None,
                                breakout_distance=abs(position["entry"] - position["stop"]),
                            ),
                        )
                        self.capital += trade_result
                        self.trades.append(trade_result)
                        self.trade_returns.append(trade_result / capital_before_trade if capital_before_trade > 0 else 0.0)
                        position = None
                        last_exit_index = i

                    elif high >= position["target"]:
                        capital_before_trade = self.capital
                        trade_result = self._calculate_trade_result(
                            position_type="BUY",
                            entry_price=position["entry"],
                            exit_price=position["target"],
                            size=position["size"],
                            entry_context=position.get("entry_context"),
                            exit_context=build_slippage_context(
                                price_reference=position["target"],
                                atr_value=atr_value,
                                volume_ratio=(volume_value / vol_mean) if vol_mean > 0 else None,
                                breakout_distance=abs(position["target"] - position["entry"]),
                            ),
                        )
                        self.capital += trade_result
                        self.trades.append(trade_result)
                        self.trade_returns.append(trade_result / capital_before_trade if capital_before_trade > 0 else 0.0)
                        position = None
                        last_exit_index = i

                elif position["type"] == "SELL":

                    if high >= position["stop"]:
                        capital_before_trade = self.capital
                        trade_result = self._calculate_trade_result(
                            position_type="SELL",
                            entry_price=position["entry"],
                            exit_price=position["stop"],
                            size=position["size"],
                            entry_context=position.get("entry_context"),
                            exit_context=build_slippage_context(
                                price_reference=position["stop"],
                                atr_value=atr_value,
                                volume_ratio=(volume_value / vol_mean) if vol_mean > 0 else None,
                                breakout_distance=abs(position["stop"] - position["entry"]),
                            ),
                        )
                        self.capital += trade_result
                        self.trades.append(trade_result)
                        self.trade_returns.append(trade_result / capital_before_trade if capital_before_trade > 0 else 0.0)
                        position = None
                        last_exit_index = i

                    elif low <= position["target"]:
                        capital_before_trade = self.capital
                        trade_result = self._calculate_trade_result(
                            position_type="SELL",
                            entry_price=position["entry"],
                            exit_price=position["target"],
                            size=position["size"],
                            entry_context=position.get("entry_context"),
                            exit_context=build_slippage_context(
                                price_reference=position["target"],
                                atr_value=atr_value,
                                volume_ratio=(volume_value / vol_mean) if vol_mean > 0 else None,
                                breakout_distance=abs(position["entry"] - position["target"]),
                            ),
                        )
                        self.capital += trade_result
                        self.trades.append(trade_result)
                        self.trade_returns.append(trade_result / capital_before_trade if capital_before_trade > 0 else 0.0)
                        position = None
                        last_exit_index = i

        return self.results()

    def _calculate_trade_result(self, position_type, entry_price, exit_price, size, entry_context=None, exit_context=None):
        return calculate_trade_result(
            position_type=position_type,
            entry_price=entry_price,
            exit_price=exit_price,
            size=size,
            entry_context=entry_context,
            exit_context=exit_context,
        )

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

    def get_trade_returns(self):
        """
        Retorna lista de retornos por trade sobre o capital pré-trade.
        Necessário para Monte Carlo com sizing dinâmico.
        """
        return self.trade_returns
