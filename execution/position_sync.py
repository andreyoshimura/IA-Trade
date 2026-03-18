from execution.models import BrokerPosition, ReconciliationResult


def reconcile_state(local_position, broker_position: BrokerPosition | None, broker_orders, quantity_tolerance: float):
    local_size = abs(float(local_position.get("size", 0.0))) if local_position else 0.0
    broker_size = abs(float(broker_position.size)) if broker_position else 0.0
    order_count = len(broker_orders or [])

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

    if local_position and order_count == 0:
        issues.append("position_without_protective_orders")

    if not local_position and broker_position:
        issues.append("broker_position_without_local_state")

    return ReconciliationResult(
        in_sync=len(issues) == 0,
        local_position_size=local_size,
        broker_position_size=broker_size,
        open_orders_local=0 if not local_position else max(0, 2),
        open_orders_broker=order_count,
        issues=issues,
    )
