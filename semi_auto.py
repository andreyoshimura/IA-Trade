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
from execution.live_executor import build_bracket_order_intents, build_spot_execution_plan, serialize_intents
from execution.position_sync import reconcile_state
from execution.safety_guard import SafetyGuard
from utils.market_mode import market_label, market_type, shorts_enabled


def parse_args():
    parser = argparse.ArgumentParser(description="Readiness check da Fase 4")
    parser.add_argument("--check-broker", action="store_true", help="Consulta saldo, posicao e ordens na exchange")
    parser.add_argument("--place-bracket", action="store_true", help="Envia entrada, stop e target reais")
    parser.add_argument("--sync-live", action="store_true", help="Sincroniza entry live e envia saidas apos fill")
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


def load_live_state():
    if not os.path.exists(config.LIVE_STATE_FILE):
        return {}

    with open(config.LIVE_STATE_FILE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_live_state(state):
    ensure_live_log_dir()
    with open(config.LIVE_STATE_FILE, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)


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
    if market_type() == "spot":
        min_entry_amount = float(getattr(config, "SPOT_LIVE_MIN_ENTRY_AMOUNT", 0.0))
        if min_entry_amount > 0 and args.size < min_entry_amount:
            raise ValueError(f"spot_entry_below_safe_minimum<{min_entry_amount}")

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


def place_spot_entry_order(broker, plan):
    return broker.place_order(plan.entry)


def place_spot_exit_orders(broker, live_state):
    stop_intent = live_state.get("pending_exit_intents", {}).get("stop")
    target_intent = live_state.get("pending_exit_intents", {}).get("target")

    if not stop_intent or not target_intent:
        raise ValueError("missing_pending_exit_intents")

    broker_position = broker.fetch_position(live_state["symbol"])
    if broker_position is None or broker_position.size <= 0:
        raise ValueError("missing_spot_position_for_exit")

    executable_amount = broker.exchange.amount_to_precision(live_state["symbol"], broker_position.size)
    executable_amount = float(executable_amount)
    if executable_amount <= 0:
        raise ValueError("executable_amount_below_minimum")

    return broker.place_spot_oco_exit(
        symbol=live_state["symbol"],
        amount=executable_amount,
        take_profit_price=float(target_intent["price"]),
        stop_price=float(stop_intent["stop_price"]),
        stop_limit_price=float(stop_intent["price"]),
        client_order_id_prefix=str(stop_intent.get("client_order_id", "spot-exit")).rsplit("-", 1)[0],
    )


def build_order_intent_from_state(raw):
    from execution.models import OrderIntent

    return OrderIntent(
        symbol=raw["symbol"],
        side=raw["side"],
        order_type=raw["order_type"],
        amount=raw["amount"],
        price=raw.get("price"),
        stop_price=raw.get("stop_price"),
        client_order_id=raw.get("client_order_id"),
        reduce_only=raw.get("reduce_only", False),
        metadata=raw.get("metadata", {}),
    )


def run():
    args = parse_args()
    local_state = build_local_state()
    live_state = load_live_state()
    local_position = local_state.get("position")

    broker_orders = []
    broker_position = None
    reconciliation = None
    broker = None
    broker_error = None

    must_check_broker = args.check_broker or args.place_bracket or args.sync_live

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

    if args.sync_live:
        if broker is None:
            print("live_sync_aborted=broker_unavailable")
            return

        entry_order_id = live_state.get("entry_order_id")
        if not entry_order_id:
            print("live_sync_aborted=no_live_entry_state")
            return

        entry_order = broker.fetch_order(entry_order_id, config.SYMBOL)
        live_state["entry_order_status"] = entry_order.status
        live_state["entry_filled"] = entry_order.filled
        live_state["updated_at"] = utcnow_iso()
        save_live_state(live_state)
        print(
            f"live_entry_status=id={entry_order.order_id} status={entry_order.status} "
            f"filled={entry_order.filled} remaining={entry_order.remaining}"
        )

        if str(entry_order.status).upper() != "CLOSED":
            append_live_log(
                "spot_entry_sync_pending",
                {
                    "symbol": config.SYMBOL,
                    "entry_order": asdict(entry_order),
                },
            )
            print("live_sync_status=entry_not_filled_yet")
            return

        if live_state.get("exit_orders_submitted"):
            print("live_sync_status=exits_already_submitted")
            return

        try:
            oco_order = place_spot_exit_orders(broker, live_state)
        except Exception as exc:
            append_live_log(
                "spot_exit_submission_failed",
                {
                    "symbol": config.SYMBOL,
                    "entry_order": asdict(entry_order),
                    "error": str(exc),
                },
            )
            live_state["last_exit_submission_error"] = str(exc)
            live_state["updated_at"] = utcnow_iso()
            save_live_state(live_state)
            print(f"live_sync_status=failed_to_submit_exits error={exc}")
            return

        live_state["entry_order_status"] = entry_order.status
        live_state["entry_filled"] = entry_order.filled
        live_state["exit_orders_submitted"] = True
        live_state["exit_orders"] = {"oco": oco_order}
        save_live_state(live_state)
        append_live_log(
            "spot_exit_orders_submitted",
            {
                "symbol": config.SYMBOL,
                "entry_order": asdict(entry_order),
                "exit_orders": live_state["exit_orders"],
            },
        )
        print("live_sync_status=exit_orders_submitted")
        print(f"oco_order={json.dumps(oco_order, ensure_ascii=True)}")
        return

    if not args.place_bracket:
        return

    try:
        validate_bracket_args(args)
    except ValueError as exc:
        print(f"order_submission_aborted={exc}")
        return

    if market_type() == "spot":
        spot_plan = build_spot_execution_plan(
            symbol=config.SYMBOL,
            side=args.side,
            size=args.size,
            entry_price=args.entry_price,
            stop_price=args.stop_price,
            target_price=args.target_price,
        )
        intents = {
            "entry": spot_plan.entry,
            "stop": spot_plan.stop,
            "target": spot_plan.target,
        }
    else:
        spot_plan = None
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

    if market_type() == "spot":
        try:
            entry_order = place_spot_entry_order(broker, spot_plan)
        except Exception as exc:
            append_live_log(
                "place_spot_entry_failed",
                {
                    "symbol": config.SYMBOL,
                    "intents": serialize_intents(intents),
                    "error": str(exc),
                },
            )
            print(f"order_submission_status=failed error={exc}")
            return

        append_live_log(
            "place_spot_entry_submitted",
            {
                "symbol": config.SYMBOL,
                "entry_order": asdict(entry_order),
                "pending_exit_intents": serialize_intents({"stop": spot_plan.stop, "target": spot_plan.target}),
                "note": "submit exits only after entry fill is confirmed",
            },
        )
        save_live_state(
            {
                "symbol": config.SYMBOL,
                "market_mode": market_label(),
                "entry_order_id": entry_order.order_id,
                "entry_order": asdict(entry_order),
                "pending_exit_intents": serialize_intents({"stop": spot_plan.stop, "target": spot_plan.target}),
                "exit_orders_submitted": False,
                "updated_at": utcnow_iso(),
            }
        )
        print("order_submission_status=submitted_entry_only")
        print(
            f"entry_order="
            f"id={entry_order.order_id} type={entry_order.order_type} side={entry_order.side} status={entry_order.status}"
        )
        print("pending_exits=stop_and_target_must_be_submitted_after_fill")
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
