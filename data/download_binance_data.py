import requests
import pandas as pd
import time


SYMBOL = "BTCUSDT"
INTERVAL = "15m"
LIMIT = 1000  # máximo permitido por request
START_TIMESTAMP = 1609459200000  # 01 Jan 2021 em ms


def get_klines(symbol, interval, start_time):
    url = "https://api.binance.com/api/v3/klines"

    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": LIMIT,
        "startTime": start_time
    }

    response = requests.get(url, params=params)
    data = response.json()

    return data


def download_historical_data():
    all_data = []
    start_time = START_TIMESTAMP

    print("Baixando dados...")

    while True:
        data = get_klines(SYMBOL, INTERVAL, start_time)

        if not data:
            break

        all_data.extend(data)

        last_open_time = data[-1][0]
        start_time = last_open_time + 1

        print(f"Baixado até: {pd.to_datetime(last_open_time, unit='ms')}")

        time.sleep(0.5)

        if len(data) < LIMIT:
            break

    print("Download concluído.")
    return all_data


def save_to_csv(data):
    df = pd.DataFrame(data, columns=[
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_asset_volume",
        "number_of_trades",
        "taker_buy_base",
        "taker_buy_quote",
        "ignore"
    ])

    df = df[["timestamp", "open", "high", "low", "close", "volume"]]

    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

    df.to_csv("data/BTCUSDT_15m.csv", index=False)

    print("Arquivo salvo em data/BTCUSDT_15m.csv")


if __name__ == "__main__":
    data = download_historical_data()
    save_to_csv(data)
