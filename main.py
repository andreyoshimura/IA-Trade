from backtest.backtester import Backtester
from data.data_loader import get_ohlcv

df_1h = get_ohlcv("BTC/USDT", "1h", 1000)
df_15m = get_ohlcv("BTC/USDT", "15m", 4000)

bt = Backtester(df_1h, df_15m)
results = bt.run()

print(results)
