import math

import config


def _to_positive_float(value):
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None

    if math.isnan(numeric) or numeric <= 0:
        return None

    return numeric


def build_slippage_context(price_reference, atr_value=None, volume_ratio=None, breakout_distance=None):
    context = {
        "price_reference": _to_positive_float(price_reference),
        "atr_value": _to_positive_float(atr_value),
        "volume_ratio": _to_positive_float(volume_ratio),
        "breakout_distance": _to_positive_float(breakout_distance),
    }
    context["resolved_slippage_rate"] = resolve_slippage_rate(context)
    return context


def resolve_slippage_rate(context=None):
    base_rate = max(0.0, float(getattr(config, "SLIPPAGE_RATE", 0.0)))
    if not getattr(config, "ENABLE_VARIABLE_SLIPPAGE", False):
        return base_rate

    context = context or {}
    price_reference = _to_positive_float(context.get("price_reference"))
    atr_value = _to_positive_float(context.get("atr_value"))
    volume_ratio = _to_positive_float(context.get("volume_ratio"))
    breakout_distance = _to_positive_float(context.get("breakout_distance"))

    slippage_rate = base_rate

    if price_reference and atr_value:
        atr_pct = atr_value / price_reference
        slippage_rate += atr_pct * float(getattr(config, "SLIPPAGE_ATR_WEIGHT", 0.0))

    if price_reference and breakout_distance:
        breakout_pct = breakout_distance / price_reference
        slippage_rate += breakout_pct * float(getattr(config, "SLIPPAGE_BREAKOUT_WEIGHT", 0.0))

    if volume_ratio:
        excess_volume = max(0.0, volume_ratio - 1.0)
        slippage_rate += excess_volume * float(getattr(config, "SLIPPAGE_VOLUME_WEIGHT", 0.0))

    min_rate = max(0.0, float(getattr(config, "SLIPPAGE_MIN_RATE", base_rate)))
    max_rate = max(min_rate, float(getattr(config, "SLIPPAGE_MAX_RATE", max(base_rate, min_rate))))
    return min(max(slippage_rate, min_rate), max_rate)


def calculate_trade_result(
    position_type,
    entry_price,
    exit_price,
    size,
    entry_context=None,
    exit_context=None,
):
    if size <= 0:
        return 0.0

    fee_rate = max(0.0, float(getattr(config, "FEE_RATE", 0.0)))
    entry_slippage_rate = resolve_slippage_rate(entry_context)
    exit_slippage_rate = resolve_slippage_rate(exit_context)

    if position_type == "BUY":
        exec_entry = entry_price * (1 + entry_slippage_rate)
        exec_exit = exit_price * (1 - exit_slippage_rate)
        gross_result = (exec_exit - exec_entry) * size
    else:
        exec_entry = entry_price * (1 - entry_slippage_rate)
        exec_exit = exit_price * (1 + exit_slippage_rate)
        gross_result = (exec_entry - exec_exit) * size

    entry_notional = abs(exec_entry * size)
    exit_notional = abs(exec_exit * size)
    fees = (entry_notional + exit_notional) * fee_rate
    return gross_result - fees


def calculate_execution_details(
    position_type,
    entry_price,
    exit_price,
    size,
    entry_context=None,
    exit_context=None,
):
    if size <= 0:
        return {
            "pnl": 0.0,
            "fee_rate": max(0.0, float(getattr(config, "FEE_RATE", 0.0))),
            "entry_slippage_rate": 0.0,
            "exit_slippage_rate": 0.0,
            "entry_exec_price": entry_price,
            "exit_exec_price": exit_price,
            "fees": 0.0,
            "gross_result": 0.0,
        }

    fee_rate = max(0.0, float(getattr(config, "FEE_RATE", 0.0)))
    entry_slippage_rate = resolve_slippage_rate(entry_context)
    exit_slippage_rate = resolve_slippage_rate(exit_context)

    if position_type == "BUY":
        exec_entry = entry_price * (1 + entry_slippage_rate)
        exec_exit = exit_price * (1 - exit_slippage_rate)
        gross_result = (exec_exit - exec_entry) * size
    else:
        exec_entry = entry_price * (1 - entry_slippage_rate)
        exec_exit = exit_price * (1 + exit_slippage_rate)
        gross_result = (exec_entry - exec_exit) * size

    entry_notional = abs(exec_entry * size)
    exit_notional = abs(exec_exit * size)
    fees = (entry_notional + exit_notional) * fee_rate
    pnl = gross_result - fees

    return {
        "pnl": pnl,
        "fee_rate": fee_rate,
        "entry_slippage_rate": entry_slippage_rate,
        "exit_slippage_rate": exit_slippage_rate,
        "entry_exec_price": exec_entry,
        "exit_exec_price": exec_exit,
        "fees": fees,
        "gross_result": gross_result,
    }
