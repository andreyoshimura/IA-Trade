import config


def build_binance_exchange(ccxt_module):
    market = str(getattr(config, "EXCHANGE_MARKET_TYPE", "spot")).lower()

    exchange_config = {
        "apiKey": config.API_KEY,
        "secret": config.API_SECRET,
    }

    if market != "spot":
        exchange_config["options"] = {"defaultType": market}

    return ccxt_module.binance(exchange_config)
