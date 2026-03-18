from dataclasses import dataclass, field


@dataclass
class OrderIntent:
    symbol: str
    side: str
    order_type: str
    amount: float
    price: float | None = None
    stop_price: float | None = None
    client_order_id: str | None = None
    reduce_only: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class BrokerOrder:
    order_id: str
    symbol: str
    side: str
    order_type: str
    status: str
    amount: float
    filled: float = 0.0
    remaining: float = 0.0
    price: float | None = None
    average: float | None = None
    reduce_only: bool = False
    raw: dict | None = None


@dataclass
class BrokerPosition:
    symbol: str
    side: str
    size: float
    entry_price: float | None = None
    unrealized_pnl: float | None = None
    raw: dict | None = None


@dataclass
class ReconciliationResult:
    in_sync: bool
    local_position_size: float
    broker_position_size: float
    open_orders_local: int
    open_orders_broker: int
    issues: list[str] = field(default_factory=list)


@dataclass
class SafetyDecision:
    allowed: bool
    reasons: list[str] = field(default_factory=list)


@dataclass
class SpotExecutionPlan:
    entry: OrderIntent
    stop: OrderIntent
    target: OrderIntent
    submit_exits_after_fill: bool = False
