import config


def market_type():
    return str(getattr(config, "EXCHANGE_MARKET_TYPE", "spot")).lower()


def shorts_enabled():
    return bool(getattr(config, "ENABLE_SHORTS", False))


def supports_signal(signal):
    signal = str(signal).upper()
    if signal == "BUY":
        return True
    if signal == "SELL":
        return shorts_enabled()
    return False


def market_label():
    return f"{market_type()}|shorts={'on' if shorts_enabled() else 'off'}"


def symbol_assets(symbol):
    parts = symbol.split("/")
    if len(parts) != 2:
        return symbol, ""
    return parts[0], parts[1]
