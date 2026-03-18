from execution.models import SafetyDecision


class SafetyGuard:
    def __init__(self, config_module):
        self.config = config_module

    def evaluate(
        self,
        runtime_capital,
        broker_orders,
        reconciliation,
        manual_confirmation_override=False,
        broker_error=None,
        live_state=None,
    ):
        reasons = []

        if not getattr(self.config, "ENABLE_LIVE_TRADING", False):
            reasons.append("live_trading_disabled")

        if getattr(self.config, "LIVE_REQUIRE_MANUAL_CONFIRMATION", True) and not manual_confirmation_override:
            reasons.append("manual_confirmation_required")

        max_orders = int(getattr(self.config, "LIVE_MAX_OPEN_ORDERS", 3))
        if len(broker_orders or []) > max_orders:
            reasons.append(f"too_many_open_orders>{max_orders}")

        initial_capital = float(getattr(self.config, "CAPITAL", 0.0))
        min_capital_ratio = float(getattr(self.config, "LIVE_MIN_CAPITAL_RATIO", 0.0))
        if initial_capital > 0 and runtime_capital < initial_capital * min_capital_ratio:
            reasons.append("capital_below_min_ratio")

        if broker_error:
            reasons.append("broker_unavailable")

        if reconciliation and not reconciliation.in_sync:
            reasons.append("broker_state_desync")

        if live_state:
            if live_state.get("last_exit_submission_error"):
                reasons.append("live_exit_submission_failed")

            if (
                live_state.get("entry_order_id")
                and live_state.get("entry_order_status") == "CLOSED"
                and not live_state.get("position_closed")
            ):
                if not live_state.get("exit_orders_submitted"):
                    reasons.append("live_position_without_submitted_exits")

        return SafetyDecision(allowed=len(reasons) == 0, reasons=reasons)
