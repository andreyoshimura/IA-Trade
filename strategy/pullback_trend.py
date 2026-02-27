from utils.indicators import ema, rsi, atr


def prepare_indicators(df_1h, df_15m):

    df_1h = df_1h.copy()
    df_15m = df_15m.copy()

    df_1h.loc[:, 'ema50'] = ema(df_1h, 50)
    df_15m.loc[:, 'ema20'] = ema(df_15m, 20)
    df_15m.loc[:, 'rsi'] = rsi(df_15m)
    df_15m.loc[:, 'atr'] = atr(df_15m)

    return df_1h, df_15m


def check_signal(row_1h, row_15m):

    trend_up = row_1h['close'] > row_1h['ema50']
    trend_down = row_1h['close'] < row_1h['ema50']

    pullback_buy = (
        row_15m['rsi'] < 40 and
        row_15m['close'] <= row_15m['ema20']
    )

    pullback_sell = (
        row_15m['rsi'] > 60 and
        row_15m['close'] >= row_15m['ema20']
    )

    if trend_up and pullback_buy:
        return "BUY"

    if trend_down and pullback_sell:
        return "SELL"

    return None
