import ccxt
import pandas as pd
from config import API_KEY, API_SECRET

exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'options': {'defaultType': 'future'}
})

def get_ohlcv(symbol, timeframe, limit=200):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=[
        'timestamp','open','high','low','close','volume'
    ])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df
