from dataclasses import asdict
from datetime import datetime

import config

from execution.models import OrderIntent, SpotExecutionPlan
from utils.market_mode import market_type, shorts_enabled


def utcnow_compact():
    return datetime.utcnow().strftime("%Y%m%d%H%M%S")


def build_bracket_order_intents(symbol, side, size, entry_price, stop_price, target_price):
    side = side.upper()
    if market_type() == "spot" and side != "BUY":
        raise ValueError("spot_mode_only_supports_buy_entries")
    if side == "SELL" and not shorts_enabled():
        raise ValueError("short_entries_disabled")

    exit_side = "SELL" if side == "BUY" else "BUY"
    client_prefix = f"{symbol.replace('/', '').lower()}-{utcnow_compact()}"
    stop_order_type = getattr(config, "LIVE_STOP_ORDER_TYPE", "STOP_LOSS_LIMIT")
    target_order_type = getattr(config, "LIVE_TARGET_ORDER_TYPE", "LIMIT")
    stop_limit_offset_pct = float(getattr(config, "LIVE_STOP_LIMIT_OFFSET_PCT", 0.0))
    stop_limit_price = None

    if stop_order_type == "STOP_LOSS_LIMIT":
        stop_limit_price = stop_price * (1 - stop_limit_offset_pct) if side == "BUY" else stop_price * (1 + stop_limit_offset_pct)

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
            order_type=stop_order_type,
            amount=size,
            price=stop_limit_price,
            stop_price=stop_price,
            client_order_id=f"{client_prefix}-stop",
            reduce_only=market_type() != "spot",
        ),
        "target": OrderIntent(
            symbol=symbol,
            side=exit_side,
            order_type=target_order_type,
            amount=size,
            price=target_price,
            client_order_id=f"{client_prefix}-target",
            reduce_only=market_type() != "spot",
        ),
    }


def serialize_intents(intents):
    return {name: asdict(intent) for name, intent in intents.items()}


def build_spot_execution_plan(symbol, side, size, entry_price, stop_price, target_price):
    intents = build_bracket_order_intents(symbol, side, size, entry_price, stop_price, target_price)
    return SpotExecutionPlan(
        entry=intents["entry"],
        stop=intents["stop"],
        target=intents["target"],
        submit_exits_after_fill=True,
    )
