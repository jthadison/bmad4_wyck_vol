"""
Broker Router (Story 23.7, 23.11)

Routes orders to the appropriate broker adapter based on symbol classification.
Forex symbols route to MetaTrader, US stock symbols route to Alpaca.

Story 23.11: Added pre-flight risk gate check before order submission.

Author: Story 23.7, 23.11
"""

from decimal import Decimal
from typing import Optional

import structlog

from src.brokers.base_adapter import TradingPlatformAdapter
from src.models.order import ExecutionReport, Order, OrderStatus
from src.risk_management.execution_risk_gate import (
    ExecutionRiskGate,
    PortfolioState,
    PreFlightResult,
)

logger = structlog.get_logger(__name__)

# Common forex pair symbols (6-character codes without separator)
# NOTE: Index symbols (US30, SPX500, NAS100, etc.) are currently classified as "stock"
# and route to Alpaca. If your broker setup routes indices to MT5, add them to this set
# or create a separate _INDEX_SYMBOLS set with MT5 routing.
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
        risk_gate: Optional[ExecutionRiskGate] = None,
    ):
        """
        Initialize BrokerRouter with optional broker adapters.

        Args:
            mt5_adapter: MetaTrader adapter for forex orders
            alpaca_adapter: Alpaca adapter for stock orders
            risk_gate: Pre-flight risk gate (Story 23.11). If None, a default is created.
        """
        self._mt5_adapter = mt5_adapter
        self._alpaca_adapter = alpaca_adapter
        self._risk_gate = risk_gate or ExecutionRiskGate()

        logger.info(
            "broker_router_initialized",
            has_mt5=mt5_adapter is not None,
            has_alpaca=alpaca_adapter is not None,
            has_risk_gate=True,
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

    def check_risk(
        self,
        order: Order,
        portfolio_state: PortfolioState,
        trade_risk_pct: Decimal,
        campaign_risk_pct: Optional[Decimal] = None,
        correlated_risk_pct: Optional[Decimal] = None,
    ) -> PreFlightResult:
        """
        Run pre-flight risk check on an order without submitting it.

        Args:
            order: Order to check.
            portfolio_state: Current portfolio state.
            trade_risk_pct: Risk percentage this trade represents.
            campaign_risk_pct: Projected campaign risk (optional).
            correlated_risk_pct: Projected correlated risk (optional).

        Returns:
            PreFlightResult with pass/block decision.
        """
        return self._risk_gate.check_order(
            order=order,
            portfolio_state=portfolio_state,
            trade_risk_pct=trade_risk_pct,
            campaign_risk_pct=campaign_risk_pct,
            correlated_risk_pct=correlated_risk_pct,
        )

    async def route_order(
        self,
        order: Order,
        portfolio_state: PortfolioState,
        trade_risk_pct: Decimal,
        campaign_risk_pct: Optional[Decimal] = None,
        correlated_risk_pct: Optional[Decimal] = None,
    ) -> ExecutionReport:
        """
        Route an order to the appropriate broker and execute it.

        Runs a pre-flight risk check first. If the check fails, the order is
        rejected without being sent to any broker. Risk parameters are required
        to enforce fail-closed behavior (Story 23.11).

        Args:
            order: Order to execute.
            portfolio_state: Current portfolio state (required).
            trade_risk_pct: Risk percentage this trade represents (required).
            campaign_risk_pct: Projected campaign risk (optional).
            correlated_risk_pct: Projected correlated risk (optional).

        Returns:
            ExecutionReport with execution result.
        """
        # Pre-flight risk check - fail-closed (Story 23.11)
        preflight = self._risk_gate.check_order(
            order=order,
            portfolio_state=portfolio_state,
            trade_risk_pct=trade_risk_pct,
            campaign_risk_pct=campaign_risk_pct,
            correlated_risk_pct=correlated_risk_pct,
        )
        if preflight.blocked:
            violation_msgs = "; ".join(v.message for v in preflight.violations)
            logger.warning(
                "broker_router_order_blocked_by_risk_gate",
                order_id=str(order.id),
                symbol=order.symbol,
                violations=violation_msgs,
            )
            return ExecutionReport(
                order_id=order.id,
                platform_order_id="",
                platform="risk_gate",
                status=OrderStatus.REJECTED,
                filled_quantity=Decimal("0"),
                remaining_quantity=order.quantity,
                error_message=f"Risk gate blocked: {violation_msgs}",
            )

        asset_class = classify_symbol(order.symbol)
        adapter = self.get_adapter(order.symbol)

        if adapter is None:
            logger.warning(
                "broker_router_no_adapter",
                symbol=order.symbol,
                asset_class=asset_class,
            )
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
