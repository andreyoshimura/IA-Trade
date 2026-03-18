import io
import json
from dataclasses import dataclass
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import config
from execution.models import BrokerPosition
from execution.position_sync import reconcile_state
from execution.safety_guard import SafetyGuard
from semi_auto import (
    build_live_entry_state,
    mark_live_state_exit_orders_submitted,
    mark_live_state_exit_submission_failed,
    place_spot_exit_orders,
    resolve_spot_exit_amount,
    run,
    run_dry_run,
    sync_spot_live_state,
    update_live_state_from_entry_order,
    validate_bracket_args,
)
from execution.live_executor import build_spot_execution_plan


class FakeExchange:
    def amount_to_precision(self, symbol, amount):
        return f"{amount:.8f}"


class FakeBroker:
    def __init__(self, position_size):
        self.exchange = FakeExchange()
        self.position_size = position_size
        self.last_oco_payload = None

    def fetch_position(self, symbol):
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
        self.last_oco_payload = {
            "symbol": symbol,
            "amount": amount,
            "take_profit_price": take_profit_price,
            "stop_price": stop_price,
            "stop_limit_price": stop_limit_price,
            "client_order_id_prefix": client_order_id_prefix,
        }
        return self.last_oco_payload


class FakeLifecycleBroker(FakeBroker):
    def __init__(self, position_size, entry_order):
        super().__init__(position_size=position_size)
        self.entry_order = entry_order

    def fetch_order(self, order_id, symbol):
        return self.entry_order


class Args:
    def __init__(self, side="BUY", size=0.00008, entry_price=100.0, stop_price=95.0, target_price=110.0):
        self.side = side
        self.size = size
        self.entry_price = entry_price
        self.stop_price = stop_price
        self.target_price = target_price


@dataclass
class EntryOrder:
    order_id: str = "entry-1"
    symbol: str = config.SYMBOL
    side: str = "BUY"
    order_type: str = "LIMIT"
    status: str = "CLOSED"
    amount: float = 0.4
    filled: float = 0.4
    remaining: float = 0.0
    price: float = 100.0
    average: float = 100.0
    reduce_only: bool = False
    raw: dict | None = None

    def __post_init__(self):
        if self.raw is None:
            self.raw = {"id": self.order_id}


class Phase4SpotTests(unittest.TestCase):
    def test_resolve_spot_exit_amount_uses_smallest_safe_amount(self):
        live_state = {
            "entry_filled": 0.4,
            "pending_exit_intents": {
                "stop": {"amount": 0.5},
                "target": {"amount": 0.5},
            },
        }

        resolved = resolve_spot_exit_amount(0.9, live_state)

        self.assertEqual(resolved, 0.4)

    def test_place_spot_exit_orders_caps_exit_to_trade_size(self):
        broker = FakeBroker(position_size=0.9)
        live_state = {
            "symbol": config.SYMBOL,
            "entry_filled": 0.4,
            "pending_exit_intents": {
                "stop": {
                    "amount": 0.5,
                    "price": 95.0,
                    "stop_price": 96.0,
                    "client_order_id": "btc-stop-1",
                },
                "target": {
                    "amount": 0.5,
                    "price": 110.0,
                },
            },
        }

        place_spot_exit_orders(broker, live_state)

        self.assertIsNotNone(broker.last_oco_payload)
        self.assertEqual(broker.last_oco_payload["amount"], 0.4)

    def test_validate_bracket_args_rejects_spot_entry_below_safe_minimum(self):
        args = Args(size=0.00001)

        with self.assertRaisesRegex(ValueError, "spot_entry_below_safe_minimum"):
            validate_bracket_args(args)

    def test_validate_bracket_args_accepts_valid_spot_buy_bracket(self):
        args = Args(size=max(config.SPOT_LIVE_MIN_ENTRY_AMOUNT, 0.00008))

        with patch("semi_auto.market_type", return_value="spot"), patch("semi_auto.shorts_enabled", return_value=False):
            validate_bracket_args(args)

    def test_update_live_state_from_entry_order_persists_fill_data(self):
        live_state = {"symbol": config.SYMBOL}
        entry_order = EntryOrder(status="CLOSED", filled=0.4)

        updated = update_live_state_from_entry_order(live_state, entry_order)

        self.assertEqual(updated["entry_order_status"], "CLOSED")
        self.assertEqual(updated["entry_filled"], 0.4)
        self.assertIn("updated_at", updated)

    def test_mark_live_state_exit_submission_failed_records_error_context(self):
        live_state = {"symbol": config.SYMBOL}

        updated = mark_live_state_exit_submission_failed(live_state, ValueError("oco_failed"), 0.4)

        self.assertEqual(updated["last_exit_submission_error"], "oco_failed")
        self.assertEqual(updated["position_size_at_failed_exit"], 0.4)
        self.assertIn("updated_at", updated)

    def test_mark_live_state_exit_orders_submitted_clears_previous_error(self):
        live_state = {
            "symbol": config.SYMBOL,
            "last_exit_submission_error": "old_error",
            "position_size_at_failed_exit": 0.4,
        }

        updated = mark_live_state_exit_orders_submitted(live_state, {"orderListId": "123"})

        self.assertTrue(updated["exit_orders_submitted"])
        self.assertEqual(updated["exit_orders"], {"oco": {"orderListId": "123"}})
        self.assertIsNone(updated["last_exit_submission_error"])
        self.assertIsNone(updated["position_size_at_failed_exit"])
        self.assertIn("updated_at", updated)

    def test_reconcile_state_accepts_live_entry_pending_without_protective_orders_yet(self):
        broker_position = None
        broker_orders = [{"id": "entry-1"}]
        live_state = {
            "entry_order_id": "entry-1",
            "entry_order": {"amount": 0.4},
            "exit_orders_submitted": False,
        }

        result = reconcile_state(
            local_position=None,
            broker_position=broker_position,
            broker_orders=broker_orders,
            quantity_tolerance=0.00001,
            live_state=live_state,
        )

        self.assertTrue(result.in_sync)
        self.assertEqual(result.open_orders_local, 1)
        self.assertEqual(result.issues, [])

    def test_reconcile_state_accepts_live_spot_position_with_protective_orders(self):
        broker_position = BrokerPosition(symbol=config.SYMBOL, side="long", size=0.4)
        broker_orders = [{"id": "oco-stop"}, {"id": "oco-target"}]
        live_state = {
            "entry_filled": 0.4,
            "entry_order_id": "entry-1",
            "exit_orders_submitted": True,
        }

        result = reconcile_state(
            local_position=None,
            broker_position=broker_position,
            broker_orders=broker_orders,
            quantity_tolerance=0.00001,
            live_state=live_state,
        )

        self.assertTrue(result.in_sync)
        self.assertEqual(result.open_orders_local, 2)
        self.assertEqual(result.issues, [])

    def test_reconcile_state_flags_missing_protection_after_live_fill(self):
        broker_position = BrokerPosition(symbol=config.SYMBOL, side="long", size=0.4)
        live_state = {
            "entry_filled": 0.4,
            "entry_order_id": "entry-1",
            "exit_orders_submitted": True,
        }

        result = reconcile_state(
            local_position=None,
            broker_position=broker_position,
            broker_orders=[],
            quantity_tolerance=0.00001,
            live_state=live_state,
        )

        self.assertFalse(result.in_sync)
        self.assertIn("position_without_protective_orders", result.issues)

    def test_reconcile_state_ignores_broker_dust_without_local_state(self):
        broker_position = BrokerPosition(symbol=config.SYMBOL, side="long", size=0.00000993)

        result = reconcile_state(
            local_position=None,
            broker_position=broker_position,
            broker_orders=[],
            quantity_tolerance=0.00001,
            live_state={},
            dust_tolerance=0.00001,
        )

        self.assertTrue(result.in_sync)
        self.assertEqual(result.broker_position_size, 0.0)
        self.assertEqual(result.issues, [])

    def test_safety_guard_blocks_when_broker_is_unavailable(self):
        guard = SafetyGuard(config)

        decision = guard.evaluate(
            runtime_capital=config.CAPITAL,
            broker_orders=[],
            reconciliation=None,
            manual_confirmation_override=True,
            broker_error="api_down",
            live_state={},
        )

        self.assertFalse(decision.allowed)
        self.assertIn("broker_unavailable", decision.reasons)

    def test_safety_guard_blocks_when_live_exit_submission_failed(self):
        guard = SafetyGuard(config)

        decision = guard.evaluate(
            runtime_capital=config.CAPITAL,
            broker_orders=[],
            reconciliation=None,
            manual_confirmation_override=True,
            broker_error=None,
            live_state={"last_exit_submission_error": "oco_failed"},
        )

        self.assertFalse(decision.allowed)
        self.assertIn("live_exit_submission_failed", decision.reasons)

    def test_safety_guard_blocks_when_live_fill_has_no_exits_submitted(self):
        guard = SafetyGuard(config)

        decision = guard.evaluate(
            runtime_capital=config.CAPITAL,
            broker_orders=[],
            reconciliation=None,
            manual_confirmation_override=True,
            broker_error=None,
            live_state={
                "entry_order_id": "entry-1",
                "entry_order_status": "CLOSED",
                "exit_orders_submitted": False,
            },
        )

        self.assertFalse(decision.allowed)
        self.assertIn("live_position_without_submitted_exits", decision.reasons)

    def test_dry_run_spot_lifecycle_pending_then_submits_exits_after_fill(self):
        spot_plan = build_spot_execution_plan(
            symbol=config.SYMBOL,
            side="BUY",
            size=0.5,
            entry_price=100.0,
            stop_price=96.0,
            target_price=110.0,
        )
        entry_order = EntryOrder(status="OPEN", filled=0.0, remaining=0.5)
        broker = FakeLifecycleBroker(position_size=0.0, entry_order=entry_order)
        live_state = build_live_entry_state(entry_order, spot_plan)

        pending_result = sync_spot_live_state(broker, live_state)

        self.assertEqual(pending_result["status"], "entry_not_filled_yet")
        self.assertFalse(live_state["exit_orders_submitted"])
        self.assertNotIn("exit_orders", live_state)

        broker.position_size = 0.4
        broker.entry_order = EntryOrder(status="CLOSED", filled=0.4, remaining=0.0)

        filled_result = sync_spot_live_state(broker, live_state, broker_position=broker.fetch_position(config.SYMBOL))

        self.assertEqual(filled_result["status"], "exit_orders_submitted")
        self.assertTrue(live_state["exit_orders_submitted"])
        self.assertEqual(live_state["entry_filled"], 0.4)
        self.assertEqual(broker.last_oco_payload["amount"], 0.4)

    def test_dry_run_spot_lifecycle_records_exit_submission_failure(self):
        spot_plan = build_spot_execution_plan(
            symbol=config.SYMBOL,
            side="BUY",
            size=0.5,
            entry_price=100.0,
            stop_price=96.0,
            target_price=110.0,
        )
        broker = FakeLifecycleBroker(
            position_size=0.0,
            entry_order=EntryOrder(status="CLOSED", filled=0.4, remaining=0.0),
        )
        live_state = build_live_entry_state(EntryOrder(status="OPEN", filled=0.0, remaining=0.5), spot_plan)
        broker.position_size = 0.0

        failed_result = sync_spot_live_state(broker, live_state, broker_position=None)

        self.assertEqual(failed_result["status"], "failed_to_submit_exits")
        self.assertEqual(live_state["last_exit_submission_error"], "missing_spot_position_for_exit")

    def test_run_dry_run_prints_pending_and_filled_states(self):
        args = SimpleNamespace(
            side="BUY",
            size=0.5,
            entry_price=100.0,
            stop_price=96.0,
            target_price=110.0,
            dry_run_filled_size=0.4,
            dry_run_failure=False,
            dry_run_broker_error=False,
            dry_run_json=False,
        )

        with patch("sys.stdout", new_callable=io.StringIO) as stdout:
            run_dry_run(args)

        output = stdout.getvalue()
        self.assertIn("===== PHASE 4 DRY RUN =====", output)
        self.assertIn("dry_run_pending_status=entry_not_filled_yet", output)
        self.assertIn("dry_run_filled_status=exit_orders_submitted", output)
        self.assertIn("dry_run_oco_order=", output)
        self.assertIn("===== PHASE 4 DRY RUN READINESS =====", output)
        self.assertIn("readiness_result=PASS", output)

    def test_run_handles_dry_run_flag_without_touching_real_broker(self):
        args = SimpleNamespace(
            dry_run=True,
            check_broker=False,
            place_bracket=False,
            sync_live=False,
            side="BUY",
            size=0.5,
            entry_price=100.0,
            stop_price=96.0,
            target_price=110.0,
            dry_run_filled_size=0.4,
            dry_run_failure=False,
            dry_run_broker_error=False,
            dry_run_json=False,
            confirm_live=False,
        )

        with patch("semi_auto.parse_args", return_value=args), patch("sys.stdout", new_callable=io.StringIO) as stdout:
            run()

        output = stdout.getvalue()
        self.assertIn("===== PHASE 4 DRY RUN =====", output)

    def test_run_dry_run_can_simulate_exit_submission_failure(self):
        args = SimpleNamespace(
            side="BUY",
            size=0.5,
            entry_price=100.0,
            stop_price=96.0,
            target_price=110.0,
            dry_run_filled_size=0.4,
            dry_run_failure=True,
            dry_run_broker_error=False,
            dry_run_json=False,
        )

        with patch("sys.stdout", new_callable=io.StringIO) as stdout:
            run_dry_run(args)

        output = stdout.getvalue()
        self.assertIn("dry_run_filled_status=failed_to_submit_exits", output)
        self.assertIn("dry_run_filled_error=dry_run_exit_submission_failed", output)
        self.assertIn("readiness_result=FAIL", output)

    def test_run_dry_run_can_simulate_broker_unavailable(self):
        args = SimpleNamespace(
            side="BUY",
            size=0.5,
            entry_price=100.0,
            stop_price=96.0,
            target_price=110.0,
            dry_run_filled_size=0.4,
            dry_run_failure=False,
            dry_run_broker_error=True,
            dry_run_json=False,
        )

        with patch("sys.stdout", new_callable=io.StringIO) as stdout:
            run_dry_run(args)

        output = stdout.getvalue()
        self.assertIn("dry_run_pending_status=broker_unavailable", output)
        self.assertIn("dry_run_filled_status=broker_unavailable", output)
        self.assertIn("dry_run_pending_error=dry_run_broker_unavailable", output)
        self.assertIn("readiness_result=FAIL", output)

    def test_run_dry_run_can_emit_json_payload(self):
        args = SimpleNamespace(
            side="BUY",
            size=0.5,
            entry_price=100.0,
            stop_price=96.0,
            target_price=110.0,
            dry_run_filled_size=0.4,
            dry_run_failure=False,
            dry_run_broker_error=False,
            dry_run_json=True,
        )

        with patch("sys.stdout", new_callable=io.StringIO) as stdout:
            run_dry_run(args)

        output = stdout.getvalue()
        json_line = next(line for line in output.splitlines() if line.startswith("dry_run_json="))
        payload = json.loads(json_line.split("=", 1)[1])

        self.assertEqual(payload["readiness_result"], "PASS")
        self.assertEqual(payload["pending_status"], "entry_not_filled_yet")
        self.assertEqual(payload["filled_status"], "exit_orders_submitted")
        self.assertIn("checks", payload)

    def test_run_exits_zero_for_passing_dry_run_json(self):
        args = SimpleNamespace(
            dry_run=True,
            check_broker=False,
            place_bracket=False,
            sync_live=False,
            side="BUY",
            size=0.5,
            entry_price=100.0,
            stop_price=96.0,
            target_price=110.0,
            dry_run_filled_size=0.4,
            dry_run_failure=False,
            dry_run_broker_error=False,
            dry_run_json=True,
            confirm_live=False,
        )

        with patch("semi_auto.parse_args", return_value=args):
            with self.assertRaises(SystemExit) as exc:
                run()

        self.assertEqual(exc.exception.code, 0)

    def test_run_exits_one_for_failing_dry_run_json(self):
        args = SimpleNamespace(
            dry_run=True,
            check_broker=False,
            place_bracket=False,
            sync_live=False,
            side="BUY",
            size=0.5,
            entry_price=100.0,
            stop_price=96.0,
            target_price=110.0,
            dry_run_filled_size=0.4,
            dry_run_failure=True,
            dry_run_broker_error=False,
            dry_run_json=True,
            confirm_live=False,
        )

        with patch("semi_auto.parse_args", return_value=args):
            with self.assertRaises(SystemExit) as exc:
                run()

        self.assertEqual(exc.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
