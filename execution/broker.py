from abc import ABC, abstractmethod

import config

from execution.models import BrokerOrder, BrokerPosition, OrderIntent
from utils.exchange_factory import build_binance_exchange
from utils.market_mode import market_type, symbol_assets


class BrokerInterface(ABC):
    @abstractmethod
    def fetch_balance(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def fetch_open_orders(self, symbol: str) -> list[BrokerOrder]:
        raise NotImplementedError

    @abstractmethod
    def fetch_position(self, symbol: str) -> BrokerPosition | None:
        raise NotImplementedError

    @abstractmethod
    def fetch_order(self, order_id: str, symbol: str) -> BrokerOrder:
        raise NotImplementedError

    @abstractmethod
    def place_order(self, intent: OrderIntent) -> BrokerOrder:
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, order_id: str, symbol: str) -> dict:
        raise NotImplementedError

    @abstractmethod
    def place_spot_oco_exit(self, symbol: str, amount: float, take_profit_price: float, stop_price: float, stop_limit_price: float, client_order_id_prefix: str | None = None) -> dict:
        raise NotImplementedError


class CCXTBroker(BrokerInterface):
    def __init__(self, exchange=None):
        self.exchange = exchange or self._build_exchange()

    def _build_exchange(self):
        import ccxt

        return build_binance_exchange(ccxt)

    def fetch_balance(self) -> dict:
        return self.exchange.fetch_balance()

    def fetch_open_orders(self, symbol: str) -> list[BrokerOrder]:
        orders = self.exchange.fetch_open_orders(symbol)
        return [self._map_order(order) for order in orders]

    def fetch_position(self, symbol: str) -> BrokerPosition | None:
        if market_type() == "spot":
            return self._fetch_spot_position(symbol)

        market_id = symbol.replace("/", "")
        try:
            positions = self.exchange.fetch_positions([symbol])
        except Exception:
            positions = self.exchange.fetch_positions()

        for position in positions:
            if position.get("symbol") == symbol or position.get("info", {}).get("symbol") == market_id:
                contracts = float(position.get("contracts") or position.get("positionAmt") or 0.0)
                if contracts == 0:
                    continue
                side = "long" if contracts > 0 else "short"
                return BrokerPosition(
                    symbol=symbol,
                    side=side,
                    size=abs(contracts),
                    entry_price=self._to_float(position.get("entryPrice") or position.get("entryPriceAvg")),
                    unrealized_pnl=self._to_float(position.get("unrealizedPnl")),
                    raw=position,
                )
        return None

    def fetch_order(self, order_id: str, symbol: str) -> BrokerOrder:
        order = self.exchange.fetch_order(order_id, symbol)
        return self._map_order(order)

    def _fetch_spot_position(self, symbol: str) -> BrokerPosition | None:
        base_asset, _ = symbol_assets(symbol)
        balance = self.fetch_balance()
        asset_balance = balance.get(base_asset, {})

        free_amount = self._to_float(asset_balance.get("free")) or 0.0
        used_amount = self._to_float(asset_balance.get("used")) or 0.0
        total_amount = free_amount + used_amount

        if total_amount <= 0:
            return None

        return BrokerPosition(
            symbol=symbol,
            side="long",
            size=total_amount,
            entry_price=None,
            unrealized_pnl=None,
            raw=asset_balance,
        )

    def place_order(self, intent: OrderIntent) -> BrokerOrder:
        params = dict(intent.metadata)
        if intent.reduce_only and market_type() != "spot":
            params["reduceOnly"] = True
        if intent.client_order_id:
            params["newClientOrderId"] = intent.client_order_id
        if intent.stop_price is not None:
            params["stopPrice"] = intent.stop_price

        order = self.exchange.create_order(
            symbol=intent.symbol,
            type=intent.order_type,
            side=intent.side.lower(),
            amount=intent.amount,
            price=intent.price,
            params=params,
        )
        return self._map_order(order)

    def cancel_order(self, order_id: str, symbol: str) -> dict:
        return self.exchange.cancel_order(order_id, symbol)

    def place_spot_oco_exit(self, symbol: str, amount: float, take_profit_price: float, stop_price: float, stop_limit_price: float, client_order_id_prefix: str | None = None) -> dict:
        market = self.exchange.market(symbol)
        quantity = self.exchange.amount_to_precision(symbol, amount)
        quantity_float = float(quantity)
        price = self.exchange.price_to_precision(symbol, take_profit_price)
        stop_price_value = self.exchange.price_to_precision(symbol, stop_price)
        stop_limit_price_value = self.exchange.price_to_precision(symbol, stop_limit_price)
        min_cost = float(market.get("limits", {}).get("cost", {}).get("min") or 0.0)
        if quantity_float <= 0:
            raise ValueError("spot_oco_quantity_rounded_to_zero")
        if min_cost > 0 and (quantity_float * float(price)) < min_cost:
            raise ValueError(
                f"spot_oco_notional_below_minimum quantity={quantity_float} price={price} min_cost={min_cost}"
            )

        params = {
            "symbol": market["id"],
            "side": "SELL",
            "quantity": quantity,
            "aboveType": "LIMIT_MAKER",
            "abovePrice": price,
            "belowType": "STOP_LOSS_LIMIT",
            "belowStopPrice": stop_price_value,
            "belowPrice": stop_limit_price_value,
            "belowTimeInForce": "GTC",
        }
        if client_order_id_prefix:
            params["listClientOrderId"] = f"{client_order_id_prefix}-oco"

        return self.exchange.privatePostOrderListOco(params)

    def _map_order(self, order: dict) -> BrokerOrder:
        return BrokerOrder(
            order_id=str(order.get("id")),
            symbol=order.get("symbol"),
            side=str(order.get("side", "")).upper(),
            order_type=str(order.get("type", "")).upper(),
            status=str(order.get("status", "")).upper(),
            amount=float(order.get("amount") or 0.0),
            filled=float(order.get("filled") or 0.0),
            remaining=float(order.get("remaining") or 0.0),
            price=self._to_float(order.get("price")),
            average=self._to_float(order.get("average")),
            reduce_only=bool(order.get("reduceOnly") or order.get("info", {}).get("reduceOnly", False)),
            raw=order,
        )

    def _to_float(self, value):
        try:
            return None if value is None else float(value)
        except (TypeError, ValueError):
            return None
