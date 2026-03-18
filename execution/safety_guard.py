from execution.models import SafetyDecision


class SafetyGuard:
    def __init__(self, config_module):
        self.config = config_module

    def evaluate(self, runtime_capital, broker_orders, reconciliation):
        reasons = []

        if not getattr(self.config, "ENABLE_LIVE_TRADING", False):
            reasons.append("live_trading_disabled")

        if getattr(self.config, "LIVE_REQUIRE_MANUAL_CONFIRMATION", True):
            reasons.append("manual_confirmation_required")

        max_orders = int(getattr(self.config, "LIVE_MAX_OPEN_ORDERS", 3))
        if len(broker_orders or []) > max_orders:
            reasons.append(f"too_many_open_orders>{max_orders}")

        initial_capital = float(getattr(self.config, "CAPITAL", 0.0))
        min_capital_ratio = float(getattr(self.config, "LIVE_MIN_CAPITAL_RATIO", 0.0))
        if initial_capital > 0 and runtime_capital < initial_capital * min_capital_ratio:
            reasons.append("capital_below_min_ratio")

        if reconciliation and not reconciliation.in_sync:
            reasons.append("broker_state_desync")

        return SafetyDecision(allowed=len(reasons) == 0, reasons=reasons)
