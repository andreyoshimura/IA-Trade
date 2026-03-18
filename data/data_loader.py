import ccxt
import pandas as pd
from utils.exchange_factory import build_binance_exchange

exchange = build_binance_exchange(ccxt)

def get_ohlcv(symbol, timeframe, limit=200):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=[
        'timestamp','open','high','low','close','volume'
    ])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df
