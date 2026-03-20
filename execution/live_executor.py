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


def align_spot_exit_intents_to_fill(entry_order, pending_exit_intents):
    if not pending_exit_intents:
        return pending_exit_intents

    filled_price = float(entry_order.average or entry_order.price or 0.0)
    planned_entry_price = float(entry_order.price or 0.0)
    if filled_price <= 0 or planned_entry_price <= 0:
        return pending_exit_intents

    stop_intent = dict(pending_exit_intents.get("stop", {}))
    target_intent = dict(pending_exit_intents.get("target", {}))
    if not stop_intent or not target_intent:
        return pending_exit_intents

    planned_stop_price = float(stop_intent.get("stop_price") or 0.0)
    planned_target_price = float(target_intent.get("price") or 0.0)
    if planned_stop_price <= 0 or planned_target_price <= 0:
        return pending_exit_intents

    stop_distance = abs(planned_entry_price - planned_stop_price)
    target_distance = abs(planned_target_price - planned_entry_price)
    if stop_distance <= 0 or target_distance <= 0:
        return pending_exit_intents

    if str(entry_order.side).upper() == "BUY":
        adjusted_stop_trigger = filled_price - stop_distance
        adjusted_target_price = filled_price + target_distance
        stop_limit_price = adjusted_stop_trigger * (1 - float(getattr(config, "LIVE_STOP_LIMIT_OFFSET_PCT", 0.0)))
    else:
        adjusted_stop_trigger = filled_price + stop_distance
        adjusted_target_price = filled_price - target_distance
        stop_limit_price = adjusted_stop_trigger * (1 + float(getattr(config, "LIVE_STOP_LIMIT_OFFSET_PCT", 0.0)))

    stop_intent["stop_price"] = adjusted_stop_trigger
    stop_intent["price"] = stop_limit_price
    target_intent["price"] = adjusted_target_price

    return {"stop": stop_intent, "target": target_intent}
