"""
breakout_structural.py

Estratégia breakout estrutural com:
- EMA
- Inclinação
- Expansão de volatilidade
- Filtro ADX (regime de tendência)
"""

import pandas as pd
import numpy as np
import config


# ==============================
# INDICADORES
# ==============================

def calculate_adx(df, period=14):

    df["tr"] = np.maximum(
        df["high"] - df["low"],
        np.maximum(
            abs(df["high"] - df["close"].shift(1)),
            abs(df["low"] - df["close"].shift(1))
        )
    )

    df["+dm"] = np.where(
        (df["high"] - df["high"].shift(1)) >
        (df["low"].shift(1) - df["low"]),
        np.maximum(df["high"] - df["high"].shift(1), 0),
        0
    )

    df["-dm"] = np.where(
        (df["low"].shift(1) - df["low"]) >
        (df["high"] - df["high"].shift(1)),
        np.maximum(df["low"].shift(1) - df["low"], 0),
        0
    )

    tr_smooth = df["tr"].rolling(period).mean()
    plus_dm_smooth = df["+dm"].rolling(period).mean()
    minus_dm_smooth = df["-dm"].rolling(period).mean()

    plus_di = 100 * (plus_dm_smooth / tr_smooth)
    minus_di = 100 * (minus_dm_smooth / tr_smooth)

    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)

    df["adx"] = dx.rolling(period).mean()

    return df


def prepare_indicators(df_1h, df_15m):

 # 🔹 Evita SettingWithCopyWarning
    df_1h = df_1h.copy()
    df_15m = df_15m.copy()

    # EMA 1H
    df_1h["ema"] = df_1h["close"].ewm(span=config.EMA_PERIOD).mean()
    df_1h["ema_slope"] = df_1h["ema"].diff()

    # ADX 1H
    df_1h = calculate_adx(df_1h)

    # ATR 15m
    df_15m["tr"] = np.maximum(
        df_15m["high"] - df_15m["low"],
        np.maximum(
            abs(df_15m["high"] - df_15m["close"].shift(1)),
            abs(df_15m["low"] - df_15m["close"].shift(1))
        )
    )

    df_15m["atr"] = df_15m["tr"].rolling(config.ATR_PERIOD).mean()
    df_15m["atr_regime_mean"] = df_15m["atr"].rolling(config.ATR_EXPANSION_LOOKBACK).mean()

    # Breakout estrutural com janela anterior (exclui candle atual)
    df_15m["rolling_high"] = (
        df_15m["high"]
        .rolling(config.BREAKOUT_LOOKBACK)
        .max()
        .shift(1)
    )
    df_15m["rolling_low"] = (
        df_15m["low"]
        .rolling(config.BREAKOUT_LOOKBACK)
        .min()
        .shift(1)
    )

    # Volume médio na janela configurada
    df_15m["vol_mean"] = df_15m["volume"].rolling(config.VOLUME_LOOKBACK).mean()

    return df_1h, df_15m


# ==============================
# SINAL
# ==============================

def check_signal(row_1h, row_15m):
    if (
        pd.isna(row_1h["adx"]) or
        pd.isna(row_15m["rolling_high"]) or
        pd.isna(row_15m["vol_mean"]) or
        pd.isna(row_15m["atr"])
    ):
        return None

    # Filtro de regime: tendência forte
    if row_1h["adx"] < config.MIN_ADX:
        return None

    # Filtro de expansão de volatilidade:
    # evita operar em janelas de baixa energia onde breakout tende a falhar.
    if getattr(config, "ATR_EXPANSION_FILTER", False):
        if pd.isna(row_15m["atr_regime_mean"]):
            return None
        min_atr = row_15m["atr_regime_mean"] * config.ATR_EXPANSION_FACTOR
        if row_15m["atr"] < min_atr:
            return None

    # Tendência de alta
    if (
        row_1h["ema_slope"] > 0 and
        row_15m["close"] > (row_15m["rolling_high"] + row_15m["atr"] * config.BREAKOUT_BUFFER) and
        row_15m["volume"] > (row_15m["vol_mean"] * config.MIN_VOLUME_FACTOR)
    ):
        return "BUY"

    # Tendência de baixa
    if (
        row_1h["ema_slope"] < 0 and
        row_15m["close"] < (row_15m["rolling_low"] - row_15m["atr"] * config.BREAKOUT_BUFFER) and
        row_15m["volume"] > (row_15m["vol_mean"] * config.MIN_VOLUME_FACTOR)
    ):
        return "SELL"

    return None
