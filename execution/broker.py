from abc import ABC, abstractmethod

import config

from execution.models import BrokerOrder, BrokerPosition, OrderIntent


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
    def place_order(self, intent: OrderIntent) -> BrokerOrder:
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, order_id: str, symbol: str) -> dict:
        raise NotImplementedError


class CCXTBroker(BrokerInterface):
    def __init__(self, exchange=None):
        self.exchange = exchange or self._build_exchange()

    def _build_exchange(self):
        import ccxt

        return ccxt.binance(
            {
                "apiKey": config.API_KEY,
                "secret": config.API_SECRET,
                "options": {"defaultType": "future"},
            }
        )

    def fetch_balance(self) -> dict:
        return self.exchange.fetch_balance()

    def fetch_open_orders(self, symbol: str) -> list[BrokerOrder]:
        orders = self.exchange.fetch_open_orders(symbol)
        return [self._map_order(order) for order in orders]

    def fetch_position(self, symbol: str) -> BrokerPosition | None:
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

    def place_order(self, intent: OrderIntent) -> BrokerOrder:
        params = dict(intent.metadata)
        if intent.reduce_only:
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
