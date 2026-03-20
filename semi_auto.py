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
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import config
from execution.broker import CCXTBroker
from execution.live_executor import (
    align_spot_exit_intents_to_fill,
    build_bracket_order_intents,
    build_spot_execution_plan,
    serialize_intents,
)
from execution.models import BrokerOrder, BrokerPosition
from execution.position_sync import reconcile_state
from execution.safety_guard import SafetyGuard
from notifier.telegram import send_message
from utils.market_mode import market_label, market_type, shorts_enabled


def parse_args():
    parser = argparse.ArgumentParser(description="Readiness check da Fase 4")
    parser.add_argument("--check-broker", action="store_true", help="Consulta saldo, posicao e ordens na exchange")
    parser.add_argument("--place-bracket", action="store_true", help="Envia entrada, stop e target reais")
    parser.add_argument("--sync-live", action="store_true", help="Sincroniza entry live e envia saidas apos fill")
    parser.add_argument("--dry-run", action="store_true", help="Simula o fluxo spot sem tocar a exchange")
    parser.add_argument("--side", choices=["BUY", "SELL"])
    parser.add_argument("--size", type=float)
    parser.add_argument("--entry-price", type=float)
    parser.add_argument("--stop-price", type=float)
    parser.add_argument("--target-price", type=float)
    parser.add_argument("--dry-run-filled-size", type=float, help="Quantidade preenchida simulada no dry-run")
    parser.add_argument("--dry-run-failure", action="store_true", help="Simula falha no envio de exits no dry-run")
    parser.add_argument("--dry-run-broker-error", action="store_true", help="Simula indisponibilidade do broker no dry-run")
    parser.add_argument("--dry-run-json", action="store_true", help="Emite payload JSON com o resultado do dry-run")
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


def save_reconciliation_snapshot(reconciliation, broker_error=None):
    ensure_live_log_dir()
    payload = {
        "updated_at": utcnow_iso(),
        "reconciliation": None,
        "broker_error": broker_error,
    }
    if reconciliation is not None:
        payload["reconciliation"] = {
            "in_sync": reconciliation.in_sync,
            "local_position_size": reconciliation.local_position_size,
            "broker_position_size": reconciliation.broker_position_size,
            "open_orders_local": reconciliation.open_orders_local,
            "open_orders_broker": reconciliation.open_orders_broker,
            "issues": reconciliation.issues,
        }
    with open(config.LIVE_CHECK_BROKER_FILE, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


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


def notify_live(text):
    if not getattr(config, "ENABLE_NOTIFICATIONS", False):
        return False

    try:
        send_message(text)
        return True
    except Exception as exc:
        append_live_log(
            "live_notification_failed",
            {
                "error": str(exc),
                "message": text,
            },
        )
        return False


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

    executable_amount = resolve_spot_exit_amount(broker_position.size, live_state)
    executable_amount = broker.exchange.amount_to_precision(live_state["symbol"], executable_amount)
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


def resolve_spot_exit_amount(position_size, live_state):
    pending_exit_intents = live_state.get("pending_exit_intents", {})
    planned_amounts = []

    for intent_name in ("stop", "target"):
        amount = pending_exit_intents.get(intent_name, {}).get("amount")
        if amount is not None:
            planned_amounts.append(float(amount))

    entry_filled = live_state.get("entry_filled")
    if entry_filled is not None:
        planned_amounts.append(float(entry_filled))

    if not planned_amounts:
        return float(position_size)

    return min(float(position_size), min(planned_amounts))


def update_live_state_from_entry_order(live_state, entry_order):
    live_state["entry_order_status"] = entry_order.status
    live_state["entry_filled"] = entry_order.filled
    live_state["updated_at"] = utcnow_iso()
    return live_state


def mark_live_state_exit_submission_failed(live_state, error, broker_position_size):
    live_state["last_exit_submission_error"] = str(error)
    live_state["position_size_at_failed_exit"] = broker_position_size
    live_state["updated_at"] = utcnow_iso()
    return live_state


def mark_live_state_exit_orders_submitted(live_state, oco_order):
    live_state["exit_orders_submitted"] = True
    live_state["exit_orders"] = {"oco": oco_order}
    live_state["last_exit_submission_error"] = None
    live_state["position_size_at_failed_exit"] = None
    live_state["updated_at"] = utcnow_iso()
    return live_state


def mark_live_state_position_closed(live_state, close_reason, exit_orders=None):
    live_state["position_closed"] = True
    live_state["close_reason"] = close_reason
    live_state["closed_at"] = utcnow_iso()
    live_state["closed_position_size"] = live_state.get("entry_filled")
    live_state["entry_filled"] = 0.0
    live_state["exit_orders_submitted"] = False
    live_state["pending_exit_intents"] = {}
    live_state["last_exit_submission_error"] = None
    live_state["position_size_at_failed_exit"] = None
    if exit_orders is not None:
        live_state["final_exit_orders"] = [asdict(order) for order in exit_orders]
    live_state["updated_at"] = utcnow_iso()
    return live_state


def build_live_entry_state(entry_order, spot_plan):
    return {
        "symbol": config.SYMBOL,
        "market_mode": market_label(),
        "entry_order_id": entry_order.order_id,
        "entry_order": asdict(entry_order),
        "pending_exit_intents": serialize_intents({"stop": spot_plan.stop, "target": spot_plan.target}),
        "exit_orders_submitted": False,
        "updated_at": utcnow_iso(),
    }


def fetch_live_exit_orders(broker, live_state):
    exit_order_refs = live_state.get("exit_orders", {}).get("oco", {}).get("orders", [])
    exit_orders = []

    for order_ref in exit_order_refs:
        order_id = str(order_ref.get("orderId"))
        if not order_id:
            continue
        exit_orders.append(broker.fetch_order(order_id, config.SYMBOL))

    return exit_orders


def resolve_spot_close_reason(exit_orders):
    closed_order = next((order for order in exit_orders if order.status == "CLOSED"), None)
    if closed_order is None:
        return None

    if closed_order.order_type == "STOP_LOSS_LIMIT":
        return "stop"
    if closed_order.order_type == "LIMIT":
        return "target"
    return "exit_filled"


def sync_spot_live_state(broker, live_state, broker_position=None, broker_orders=None):
    entry_order_id = live_state.get("entry_order_id")
    if not entry_order_id:
        return {"status": "no_live_entry_state", "live_state": live_state}

    entry_order = broker.fetch_order(entry_order_id, config.SYMBOL)
    update_live_state_from_entry_order(live_state, entry_order)
    dust_tolerance = float(getattr(config, "LIVE_BROKER_DUST_TOLERANCE", 0.0))
    broker_position_size = abs(float(broker_position.size)) if broker_position else 0.0

    if str(entry_order.status).upper() != "CLOSED":
        return {
            "status": "entry_not_filled_yet",
            "entry_order": entry_order,
            "live_state": live_state,
        }

    if (
        live_state.get("last_exit_submission_error")
        and broker_position_size <= dust_tolerance
        and not (broker_orders or [])
    ):
        mark_live_state_position_closed(live_state, "manual_close")
        return {
            "status": "position_closed",
            "entry_order": entry_order,
            "close_reason": "manual_close",
            "live_state": live_state,
        }

    if live_state.get("exit_orders_submitted"):
        exit_orders = fetch_live_exit_orders(broker, live_state)
        close_reason = resolve_spot_close_reason(exit_orders)
        if close_reason and broker_position_size <= dust_tolerance and not (broker_orders or []):
            mark_live_state_position_closed(live_state, close_reason, exit_orders=exit_orders)
            return {
                "status": "position_closed",
                "entry_order": entry_order,
                "close_reason": close_reason,
                "exit_orders": exit_orders,
                "live_state": live_state,
            }
        return {
            "status": "exits_already_submitted",
            "entry_order": entry_order,
            "live_state": live_state,
        }

    live_state["pending_exit_intents"] = align_spot_exit_intents_to_fill(
        entry_order,
        live_state.get("pending_exit_intents", {}),
    )

    try:
        oco_order = place_spot_exit_orders(broker, live_state)
    except Exception as exc:
        mark_live_state_exit_submission_failed(
            live_state,
            exc,
            broker_position.size if broker_position else None,
        )
        return {
            "status": "failed_to_submit_exits",
            "entry_order": entry_order,
            "error": exc,
            "live_state": live_state,
        }

    mark_live_state_exit_orders_submitted(live_state, oco_order)
    return {
        "status": "exit_orders_submitted",
        "entry_order": entry_order,
        "oco_order": oco_order,
        "live_state": live_state,
    }


class DryRunExchange:
    def amount_to_precision(self, symbol, amount):
        return f"{float(amount):.8f}"


class DryRunBroker:
    def __init__(self, entry_order, position_size=0.0, fail_exit_submission=False):
        self.exchange = DryRunExchange()
        self.entry_order = entry_order
        self.position_size = float(position_size)
        self.fail_exit_submission = fail_exit_submission

    def fetch_order(self, order_id, symbol):
        return self.entry_order

    def fetch_position(self, symbol):
        if self.position_size <= 0:
            return None
        return BrokerPosition(symbol=symbol, side="long", size=self.position_size)

    def place_spot_oco_exit(
        self,
        symbol,
        amount,
        take_profit_price,
        stop_price,
        stop_limit_price,
        client_order_id_prefix=None,
    ):
        if self.fail_exit_submission:
            raise ValueError("dry_run_exit_submission_failed")
        return {
            "symbol": symbol,
            "amount": amount,
            "take_profit_price": take_profit_price,
            "stop_price": stop_price,
            "stop_limit_price": stop_limit_price,
            "client_order_id_prefix": client_order_id_prefix,
            "mode": "dry_run",
        }


def build_dry_run_entry_order(status, size, filled, remaining, entry_price):
    return BrokerOrder(
        order_id="dryrun-entry-1",
        symbol=config.SYMBOL,
        side="BUY",
        order_type=getattr(config, "LIVE_ENTRY_ORDER_TYPE", "LIMIT"),
        status=status,
        amount=float(size),
        filled=float(filled),
        remaining=float(remaining),
        price=float(entry_price),
        average=float(entry_price),
        reduce_only=False,
        raw={"mode": "dry_run"},
    )


def run_dry_run(args):
    if market_type() != "spot":
        raise ValueError("dry_run_only_supported_in_spot_mode")

    validate_bracket_args(args)
    spot_plan = build_spot_execution_plan(
        symbol=config.SYMBOL,
        side=args.side,
        size=args.size,
        entry_price=args.entry_price,
        stop_price=args.stop_price,
        target_price=args.target_price,
    )

    pending_entry_order = build_dry_run_entry_order(
        status="OPEN",
        size=args.size,
        filled=0.0,
        remaining=args.size,
        entry_price=args.entry_price,
    )
    pending_state = build_live_entry_state(pending_entry_order, spot_plan)
    pending_broker = DryRunBroker(entry_order=pending_entry_order, position_size=0.0)
    if getattr(args, "dry_run_broker_error", False):
        pending_result = {"status": "broker_unavailable", "error": "dry_run_broker_unavailable", "live_state": deepcopy(pending_state)}
    else:
        pending_result = sync_spot_live_state(pending_broker, deepcopy(pending_state))

    filled_size = args.dry_run_filled_size if args.dry_run_filled_size is not None else args.size
    filled_entry_order = build_dry_run_entry_order(
        status="CLOSED",
        size=args.size,
        filled=filled_size,
        remaining=max(0.0, args.size - filled_size),
        entry_price=args.entry_price,
    )
    filled_state = build_live_entry_state(filled_entry_order, spot_plan)
    filled_broker = DryRunBroker(
        entry_order=filled_entry_order,
        position_size=filled_size,
        fail_exit_submission=getattr(args, "dry_run_failure", False),
    )
    if getattr(args, "dry_run_broker_error", False):
        filled_result = {"status": "broker_unavailable", "error": "dry_run_broker_unavailable", "live_state": deepcopy(filled_state)}
    else:
        filled_result = sync_spot_live_state(
            filled_broker,
            deepcopy(filled_state),
            broker_position=filled_broker.fetch_position(config.SYMBOL),
        )

    print("===== PHASE 4 DRY RUN =====")
    print(f"symbol={config.SYMBOL}")
    print(f"market_mode={market_label()}")
    print(f"dry_run_requested_size={args.size}")
    print(f"dry_run_filled_size={filled_size}")
    print(f"dry_run_pending_status={pending_result['status']}")
    print(f"dry_run_filled_status={filled_result['status']}")
    print(f"dry_run_entry_state={json.dumps(pending_state, ensure_ascii=True)}")
    print(f"dry_run_filled_state={json.dumps(filled_result['live_state'], ensure_ascii=True)}")
    if "oco_order" in filled_result:
        print(f"dry_run_oco_order={json.dumps(filled_result['oco_order'], ensure_ascii=True)}")
    if "error" in pending_result:
        print(f"dry_run_pending_error={pending_result['error']}")
    if "error" in filled_result:
        print(f"dry_run_filled_error={filled_result['error']}")
    checks, final_status = print_dry_run_readiness_summary(args, pending_result, filled_result)
    if getattr(args, "dry_run_json", False):
        payload = build_dry_run_json_payload(
            args=args,
            pending_state=pending_state,
            pending_result=pending_result,
            filled_result=filled_result,
            checks=checks,
            final_status=final_status,
        )
        print(f"dry_run_json={json.dumps(payload, ensure_ascii=True)}")
    return final_status


def build_dry_run_readiness_checks(args, pending_result, filled_result):
    checks = []
    checks.append(
        {
            "name": "spot_mode_supported",
            "ok": market_type() == "spot",
            "detail": market_label(),
        }
    )
    checks.append(
        {
            "name": "input_bracket_valid",
            "ok": True,
            "detail": f"side={args.side} size={args.size}",
        }
    )
    checks.append(
        {
            "name": "pending_entry_transitions",
            "ok": pending_result["status"] == "entry_not_filled_yet",
            "detail": pending_result["status"],
        }
    )
    checks.append(
        {
            "name": "filled_entry_transitions",
            "ok": filled_result["status"] == "exit_orders_submitted",
            "detail": filled_result["status"],
        }
    )
    checks.append(
        {
            "name": "exit_submission_simulated",
            "ok": "oco_order" in filled_result,
            "detail": filled_result.get("status"),
        }
    )
    checks.append(
        {
            "name": "no_simulated_broker_error",
            "ok": not getattr(args, "dry_run_broker_error", False),
            "detail": "enabled" if getattr(args, "dry_run_broker_error", False) else "disabled",
        }
    )
    checks.append(
        {
            "name": "no_simulated_exit_failure",
            "ok": not getattr(args, "dry_run_failure", False),
            "detail": "enabled" if getattr(args, "dry_run_failure", False) else "disabled",
        }
    )
    return checks


def print_dry_run_readiness_summary(args, pending_result, filled_result):
    checks = build_dry_run_readiness_checks(args, pending_result, filled_result)
    final_status = "PASS" if all(item["ok"] for item in checks) else "FAIL"
    print("===== PHASE 4 DRY RUN READINESS =====")
    for item in checks:
        status = "PASS" if item["ok"] else "FAIL"
        print(f"readiness_check={status} name={item['name']} detail={item['detail']}")
    print(f"readiness_result={final_status}")
    return checks, final_status


def build_dry_run_json_payload(args, pending_state, pending_result, filled_result, checks, final_status):
    payload = {
        "symbol": config.SYMBOL,
        "market_mode": market_label(),
        "requested_size": args.size,
        "filled_size": args.dry_run_filled_size if args.dry_run_filled_size is not None else args.size,
        "pending_status": pending_result["status"],
        "filled_status": filled_result["status"],
        "pending_state": pending_state,
        "filled_state": filled_result["live_state"],
        "checks": checks,
        "readiness_result": final_status,
    }
    if "oco_order" in filled_result:
        payload["oco_order"] = filled_result["oco_order"]
    if "error" in pending_result:
        payload["pending_error"] = str(pending_result["error"])
    if "error" in filled_result:
        payload["filled_error"] = str(filled_result["error"])
    return payload


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
    if args.dry_run:
        try:
            final_status = run_dry_run(args)
        except ValueError as exc:
            print(f"dry_run_aborted={exc}")
            if getattr(args, "dry_run_json", False):
                raise SystemExit(1)
            return
        if getattr(args, "dry_run_json", False):
            raise SystemExit(0 if final_status == "PASS" else 1)
        return

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
                live_state=live_state,
                dust_tolerance=float(getattr(config, "LIVE_BROKER_DUST_TOLERANCE", 0.0)),
            )
        except Exception as exc:
            broker_error = str(exc)
        save_reconciliation_snapshot(reconciliation, broker_error=broker_error)

    guard = SafetyGuard(config)
    capital = float(local_state.get("capital", config.PAPER_TRADE_CAPITAL))
    decision = guard.evaluate(
        runtime_capital=capital,
        broker_orders=broker_orders,
        reconciliation=reconciliation,
        manual_confirmation_override=args.confirm_live,
        broker_error=broker_error,
        live_state=live_state,
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

        sync_result = sync_spot_live_state(
            broker,
            live_state,
            broker_position=broker_position,
            broker_orders=broker_orders,
        )
        status = sync_result["status"]

        if status == "no_live_entry_state":
            print("live_sync_aborted=no_live_entry_state")
            return

        entry_order = sync_result.get("entry_order")
        save_live_state(live_state)
        if entry_order is not None:
            print(
                f"live_entry_status=id={entry_order.order_id} status={entry_order.status} "
                f"filled={entry_order.filled} remaining={entry_order.remaining}"
            )

        if status == "entry_not_filled_yet":
            append_live_log(
                "spot_entry_sync_pending",
                {
                    "symbol": config.SYMBOL,
                    "entry_order": asdict(entry_order),
                },
            )
            print("live_sync_status=entry_not_filled_yet")
            return

        if status == "exits_already_submitted":
            print("live_sync_status=exits_already_submitted")
            return

        if status == "position_closed":
            append_live_log(
                "spot_position_closed",
                {
                    "symbol": config.SYMBOL,
                    "entry_order": asdict(entry_order),
                    "close_reason": sync_result["close_reason"],
                    "final_exit_orders": live_state.get("final_exit_orders", []),
                },
            )
            notify_live(
                f"[LIVE] EXIT {config.SYMBOL}\n"
                f"Motivo: {sync_result['close_reason']}\n"
                f"Entry: {entry_order.average or entry_order.price}\n"
                f"Status final: fechado"
            )
            print(f"live_sync_status=position_closed close_reason={sync_result['close_reason']}")
            return

        if status == "failed_to_submit_exits":
            exc = sync_result["error"]
            append_live_log(
                "spot_exit_submission_failed",
                {
                    "symbol": config.SYMBOL,
                    "entry_order": asdict(entry_order),
                    "error": str(exc),
                },
            )
            print(f"live_sync_status=failed_to_submit_exits error={exc}")
            return

        oco_order = sync_result["oco_order"]
        append_live_log(
            "spot_exit_orders_submitted",
            {
                "symbol": config.SYMBOL,
                "entry_order": asdict(entry_order),
                "exit_orders": live_state["exit_orders"],
            },
        )
        notify_live(
            f"[LIVE] OCO ativa {config.SYMBOL}\n"
            f"Entry fill: {entry_order.average or entry_order.price}\n"
            f"Stop: {live_state['pending_exit_intents']['stop']['stop_price']}\n"
            f"Target: {live_state['pending_exit_intents']['target']['price']}"
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
        save_live_state(build_live_entry_state(entry_order, spot_plan))
        notify_live(
            f"[LIVE] ENTRY {entry_order.side} {config.SYMBOL}\n"
            f"Preco: {entry_order.average or entry_order.price}\n"
            f"Qtd: {entry_order.filled or entry_order.amount}\n"
            f"Status: {entry_order.status}"
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
