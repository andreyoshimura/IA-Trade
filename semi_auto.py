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
from dataclasses import asdict
from datetime import datetime

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import config
from execution.broker import CCXTBroker
from execution.live_executor import build_bracket_order_intents, serialize_intents
from execution.position_sync import reconcile_state
from execution.safety_guard import SafetyGuard
from utils.market_mode import market_label, market_type, shorts_enabled


def parse_args():
    parser = argparse.ArgumentParser(description="Readiness check da Fase 4")
    parser.add_argument("--check-broker", action="store_true", help="Consulta saldo, posicao e ordens na exchange")
    parser.add_argument("--place-bracket", action="store_true", help="Envia entrada, stop e target reais")
    parser.add_argument("--side", choices=["BUY", "SELL"])
    parser.add_argument("--size", type=float)
    parser.add_argument("--entry-price", type=float)
    parser.add_argument("--stop-price", type=float)
    parser.add_argument("--target-price", type=float)
    parser.add_argument("--confirm-live", action="store_true", help="Confirma explicitamente o envio real")
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


def utcnow_iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def ensure_live_log_dir():
    os.makedirs(os.path.dirname(config.LIVE_ORDER_LOG), exist_ok=True)


def append_live_log(event, payload):
    ensure_live_log_dir()
    row = {"timestamp": utcnow_iso(), "event": event}
    row.update(payload)
    with open(config.LIVE_ORDER_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=True) + "\n")


def validate_bracket_args(args):
    required = {
        "side": args.side,
        "size": args.size,
        "entry_price": args.entry_price,
        "stop_price": args.stop_price,
        "target_price": args.target_price,
    }
    missing = [key for key, value in required.items() if value in (None, "")]
    if missing:
        raise ValueError(f"missing_arguments={missing}")

    if args.size <= 0:
        raise ValueError("size_must_be_positive")

    if market_type() == "spot" and args.side != "BUY":
        raise ValueError("spot_mode_only_supports_buy_entries")
    if args.side == "SELL" and not shorts_enabled():
        raise ValueError("short_entries_disabled")

    if args.side == "BUY":
        if not (args.stop_price < args.entry_price < args.target_price):
            raise ValueError("invalid_buy_bracket_prices")
    else:
        if not (args.target_price < args.entry_price < args.stop_price):
            raise ValueError("invalid_sell_bracket_prices")


def place_bracket_orders(broker, intents):
    placed_orders = {}
    try:
        placed_orders["entry"] = broker.place_order(intents["entry"])
        placed_orders["stop"] = broker.place_order(intents["stop"])
        placed_orders["target"] = broker.place_order(intents["target"])
        return placed_orders
    except Exception:
        if "entry" in placed_orders:
            try:
                broker.cancel_order(placed_orders["entry"].order_id, placed_orders["entry"].symbol)
            except Exception:
                pass
        raise


def run():
    args = parse_args()
    local_state = build_local_state()
    local_position = local_state.get("position")

    broker_orders = []
    broker_position = None
    reconciliation = None
    broker = None
    broker_error = None

    must_check_broker = args.check_broker or args.place_bracket

    if must_check_broker:
        try:
            broker = CCXTBroker()
            broker_orders = broker.fetch_open_orders(config.SYMBOL)
            broker_position = broker.fetch_position(config.SYMBOL)
            reconciliation = reconcile_state(
                local_position=local_position,
                broker_position=broker_position,
                broker_orders=broker_orders,
                quantity_tolerance=float(getattr(config, "LIVE_RECONCILE_QTY_TOLERANCE", 0.0)),
            )
        except Exception as exc:
            broker_error = str(exc)

    guard = SafetyGuard(config)
    capital = float(local_state.get("capital", config.PAPER_TRADE_CAPITAL))
    decision = guard.evaluate(
        runtime_capital=capital,
        broker_orders=broker_orders,
        reconciliation=reconciliation,
        manual_confirmation_override=args.confirm_live,
    )

    print("===== PHASE 4 READINESS =====")
    print(f"symbol={config.SYMBOL}")
    print(f"market_mode={market_label()}")
    print(f"live_trading_enabled={config.ENABLE_LIVE_TRADING}")
    print(f"manual_confirmation_required={config.LIVE_REQUIRE_MANUAL_CONFIRMATION}")
    print(f"runtime_capital={round(capital, 8)}")
    print(f"local_position_open={bool(local_position)}")
    print(format_reconciliation(reconciliation))
    print(f"broker_error={broker_error}")
    print(f"safety_allowed={decision.allowed}")
    print(f"safety_reasons={decision.reasons}")

    if not args.place_bracket:
        return

    try:
        validate_bracket_args(args)
    except ValueError as exc:
        print(f"order_submission_aborted={exc}")
        return

    intents = build_bracket_order_intents(
        symbol=config.SYMBOL,
        side=args.side,
        size=args.size,
        entry_price=args.entry_price,
        stop_price=args.stop_price,
        target_price=args.target_price,
    )

    append_live_log(
        "place_bracket_requested",
        {
            "symbol": config.SYMBOL,
            "intents": serialize_intents(intents),
            "safety_allowed": decision.allowed,
            "safety_reasons": decision.reasons,
            "broker_error": broker_error,
        },
    )

    if not decision.allowed:
        print("order_submission_aborted=safety_guard_blocked")
        return

    if broker is None:
        print("order_submission_aborted=broker_unavailable")
        return

    try:
        placed_orders = place_bracket_orders(broker, intents)
    except Exception as exc:
        append_live_log(
            "place_bracket_failed",
            {
                "symbol": config.SYMBOL,
                "intents": serialize_intents(intents),
                "error": str(exc),
            },
        )
        print(f"order_submission_status=failed error={exc}")
        return

    append_live_log(
        "place_bracket_submitted",
        {
            "symbol": config.SYMBOL,
            "orders": {name: asdict(order) for name, order in placed_orders.items()},
        },
    )
    print("order_submission_status=submitted")
    for name, order in placed_orders.items():
        print(
            f"{name}_order="
            f"id={order.order_id} type={order.order_type} side={order.side} status={order.status}"
        )


if __name__ == "__main__":
    run()
