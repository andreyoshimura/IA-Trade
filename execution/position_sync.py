from execution.models import BrokerPosition, ReconciliationResult


def expected_local_size(local_position, live_state):
    if local_position:
        return abs(float(local_position.get("size", 0.0)))

    if not live_state:
        return 0.0

    entry_filled = live_state.get("entry_filled")
    if entry_filled is not None:
        return abs(float(entry_filled))

    return 0.0


def expected_local_order_count(local_position, live_state):
    if live_state:
        if live_state.get("exit_orders_submitted"):
            return 2
        if live_state.get("entry_order_id"):
            return 1

    return 0 if not local_position else 2


def normalize_broker_size(local_size, broker_size, dust_tolerance):
    if local_size == 0 and broker_size <= dust_tolerance:
        return 0.0

    return broker_size


def reconcile_state(
    local_position,
    broker_position: BrokerPosition | None,
    broker_orders,
    quantity_tolerance: float,
    live_state=None,
    dust_tolerance: float = 0.0,
):
    local_size = expected_local_size(local_position, live_state)
    broker_size_raw = abs(float(broker_position.size)) if broker_position else 0.0
    broker_size = normalize_broker_size(local_size, broker_size_raw, dust_tolerance)
    order_count = len(broker_orders or [])
    local_order_count = expected_local_order_count(local_position, live_state)

    issues = []

    if abs(local_size - broker_size) > quantity_tolerance:
        issues.append(
            f"position_size_mismatch local={round(local_size, 8)} broker={round(broker_size, 8)}"
        )

    if local_position and broker_position:
        local_side = str(local_position.get("type", "")).upper()
        broker_side = "BUY" if broker_position.side.lower() == "long" else "SELL"
        if local_side and local_side != broker_side:
            issues.append(f"position_side_mismatch local={local_side} broker={broker_side}")

    if local_size > 0 and local_order_count >= 2 and order_count == 0:
        issues.append("position_without_protective_orders")

    if local_size == 0 and broker_size > 0:
        issues.append("broker_position_without_local_state")

    return ReconciliationResult(
        in_sync=len(issues) == 0,
        local_position_size=local_size,
        broker_position_size=broker_size,
        open_orders_local=local_order_count,
        open_orders_broker=order_count,
        issues=issues,
    )
