from dataclasses import asdict
from datetime import datetime

import config

from execution.models import OrderIntent


def utcnow_compact():
    return datetime.utcnow().strftime("%Y%m%d%H%M%S")


def build_bracket_order_intents(symbol, side, size, entry_price, stop_price, target_price):
    side = side.upper()
    exit_side = "SELL" if side == "BUY" else "BUY"
    client_prefix = f"{symbol.replace('/', '').lower()}-{utcnow_compact()}"

    return {
        "entry": OrderIntent(
            symbol=symbol,
            side=side,
            order_type=getattr(config, "LIVE_ENTRY_ORDER_TYPE", "LIMIT"),
            amount=size,
            price=entry_price,
            client_order_id=f"{client_prefix}-entry",
            metadata={"timeInForce": getattr(config, "LIVE_ENTRY_TIME_IN_FORCE", "GTC")},
        ),
        "stop": OrderIntent(
            symbol=symbol,
            side=exit_side,
            order_type=getattr(config, "LIVE_STOP_ORDER_TYPE", "STOP_MARKET"),
            amount=size,
            stop_price=stop_price,
            client_order_id=f"{client_prefix}-stop",
            reduce_only=True,
        ),
        "target": OrderIntent(
            symbol=symbol,
            side=exit_side,
            order_type=getattr(config, "LIVE_TARGET_ORDER_TYPE", "TAKE_PROFIT_MARKET"),
            amount=size,
            stop_price=target_price,
            client_order_id=f"{client_prefix}-target",
            reduce_only=True,
        ),
    }


def serialize_intents(intents):
    return {name: asdict(intent) for name, intent in intents.items()}
