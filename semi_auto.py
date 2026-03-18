"""
semi_auto.py

Entrada segura para a infraestrutura base da Fase 4.
Nao envia ordens automaticamente; apenas avalia readiness operacional
e pode opcionalmente inspecionar o estado da exchange.
"""

import argparse
import json
import os
import sys

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import config
from execution.broker import CCXTBroker
from execution.position_sync import reconcile_state
from execution.safety_guard import SafetyGuard


def parse_args():
    parser = argparse.ArgumentParser(description="Readiness check da Fase 4")
    parser.add_argument("--check-broker", action="store_true", help="Consulta saldo, posicao e ordens na exchange")
    return parser.parse_args()


def build_local_state():
    if not os.path.exists(config.PAPER_STATE_FILE):
        return {}

    with open(config.PAPER_STATE_FILE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def format_reconciliation(reconciliation):
    if reconciliation is None:
        return "reconciliation=not_run"

    return (
        "reconciliation="
        f"in_sync={reconciliation.in_sync} "
        f"local_size={reconciliation.local_position_size} "
        f"broker_size={reconciliation.broker_position_size} "
        f"broker_orders={reconciliation.open_orders_broker} "
        f"issues={reconciliation.issues}"
    )


def run():
    args = parse_args()
    local_state = build_local_state()
    local_position = local_state.get("position")

    broker_orders = []
    broker_position = None
    reconciliation = None

    if args.check_broker:
        broker = CCXTBroker()
        broker_orders = broker.fetch_open_orders(config.SYMBOL)
        broker_position = broker.fetch_position(config.SYMBOL)
        reconciliation = reconcile_state(
            local_position=local_position,
            broker_position=broker_position,
            broker_orders=broker_orders,
            quantity_tolerance=float(getattr(config, "LIVE_RECONCILE_QTY_TOLERANCE", 0.0)),
        )

    guard = SafetyGuard(config)
    capital = float(local_state.get("capital", config.PAPER_TRADE_CAPITAL))
    decision = guard.evaluate(
        runtime_capital=capital,
        broker_orders=broker_orders,
        reconciliation=reconciliation,
    )

    print("===== PHASE 4 READINESS =====")
    print(f"symbol={config.SYMBOL}")
    print(f"live_trading_enabled={config.ENABLE_LIVE_TRADING}")
    print(f"manual_confirmation_required={config.LIVE_REQUIRE_MANUAL_CONFIRMATION}")
    print(f"runtime_capital={round(capital, 8)}")
    print(f"local_position_open={bool(local_position)}")
    print(format_reconciliation(reconciliation))
    print(f"safety_allowed={decision.allowed}")
    print(f"safety_reasons={decision.reasons}")


if __name__ == "__main__":
    run()
