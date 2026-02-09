"""
Broker Router (Story 23.7)

Routes orders to the appropriate broker adapter based on symbol classification.
Forex symbols route to MetaTrader, US stock symbols route to Alpaca.

Author: Story 23.7
"""

from typing import Optional

import structlog

from src.brokers.base_adapter import TradingPlatformAdapter
from src.models.order import ExecutionReport, Order, OrderStatus

logger = structlog.get_logger(__name__)

# Common forex pair symbols (6-character codes without separator)
_FOREX_PAIRS = frozenset(
    {
        "EURUSD",
        "GBPUSD",
        "USDJPY",
        "USDCHF",
        "AUDUSD",
        "USDCAD",
        "NZDUSD",
        "EURGBP",
        "EURJPY",
        "GBPJPY",
        "AUDJPY",
        "EURAUD",
        "EURCHF",
        "AUDNZD",
        "NZDJPY",
        "GBPAUD",
        "GBPCAD",
        "EURNZD",
        "AUDCAD",
        "GBPNZD",
        "CADCHF",
        "CADJPY",
        "CHFJPY",
        "AUDCHF",
        "EURCAD",
        "NZDCAD",
        "NZDCHF",
        "XAUUSD",
        "XAGUSD",
    }
)


def classify_symbol(symbol: str) -> str:
    """
    Classify a symbol as 'forex' or 'stock'.

    Forex symbols are recognized by matching known forex pair patterns.
    Everything else is classified as a stock.

    Args:
        symbol: Trading symbol (e.g., "EURUSD", "AAPL")

    Returns:
        "forex" or "stock"
    """
    normalized = symbol.upper().replace("/", "").replace("-", "").replace(".", "")
    if normalized in _FOREX_PAIRS:
        return "forex"
    return "stock"


class BrokerRouter:
    """
    Routes orders to the correct broker adapter based on symbol type.

    Forex symbols are routed to MetaTrader (MT5).
    Stock symbols are routed to Alpaca.

    If no adapter is registered for a symbol's asset class, the order is rejected
    with a descriptive error rather than raising an exception.
    """

    def __init__(
        self,
        mt5_adapter: Optional[TradingPlatformAdapter] = None,
        alpaca_adapter: Optional[TradingPlatformAdapter] = None,
    ):
        """
        Initialize BrokerRouter with optional broker adapters.

        Args:
            mt5_adapter: MetaTrader adapter for forex orders
            alpaca_adapter: Alpaca adapter for stock orders
        """
        self._mt5_adapter = mt5_adapter
        self._alpaca_adapter = alpaca_adapter

        logger.info(
            "broker_router_initialized",
            has_mt5=mt5_adapter is not None,
            has_alpaca=alpaca_adapter is not None,
        )

    def get_adapter(self, symbol: str) -> Optional[TradingPlatformAdapter]:
        """
        Get the appropriate adapter for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            The broker adapter, or None if no adapter is available for this symbol type
        """
        asset_class = classify_symbol(symbol)
        if asset_class == "forex":
            return self._mt5_adapter
        return self._alpaca_adapter

    async def route_order(self, order: Order) -> ExecutionReport:
        """
        Route an order to the appropriate broker and execute it.

        Args:
            order: Order to execute

        Returns:
            ExecutionReport with execution result
        """
        asset_class = classify_symbol(order.symbol)
        adapter = self.get_adapter(order.symbol)

        if adapter is None:
            logger.warning(
                "broker_router_no_adapter",
                symbol=order.symbol,
                asset_class=asset_class,
            )
            from decimal import Decimal

            return ExecutionReport(
                order_id=order.id,
                platform_order_id="",
                platform="none",
                status=OrderStatus.REJECTED,
                filled_quantity=Decimal("0"),
                remaining_quantity=order.quantity,
                error_message=f"No broker adapter configured for {asset_class} symbol: {order.symbol}",
            )

        if not adapter.is_connected():
            logger.warning(
                "broker_router_adapter_not_connected",
                symbol=order.symbol,
                platform=adapter.platform_name,
            )

        logger.info(
            "broker_router_routing_order",
            order_id=str(order.id),
            symbol=order.symbol,
            asset_class=asset_class,
            platform=adapter.platform_name,
        )

        report = await adapter.place_order(order)

        logger.info(
            "broker_router_order_result",
            order_id=str(order.id),
            symbol=order.symbol,
            platform=adapter.platform_name,
            status=report.status,
        )

        return report
