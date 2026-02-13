"""
Broker Router (Story 23.7, 23.11, 23.13)

Routes orders to the appropriate broker adapter based on symbol classification.
Forex symbols route to MetaTrader, US stock symbols route to Alpaca.

Story 23.11: Added pre-flight risk gate check before order submission.
Story 23.13: Added kill switch state and close_all_positions().

Author: Story 23.7, 23.11, 23.13
"""

from datetime import UTC, datetime
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
        self._kill_switch_active = False
        self._kill_switch_activated_at: Optional[datetime] = None
        self._kill_switch_reason: Optional[str] = None

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
        # Kill switch check - block all new orders when active (Story 23.13)
        if self._kill_switch_active:
            logger.warning(
                "broker_router_order_blocked_kill_switch",
                order_id=str(order.id),
                symbol=order.symbol,
            )
            return ExecutionReport(
                order_id=order.id,
                platform_order_id="",
                platform="kill_switch",
                status=OrderStatus.REJECTED,
                filled_quantity=Decimal("0"),
                remaining_quantity=order.quantity,
                error_message="Kill switch is active - all new orders blocked",
            )

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

    def activate_kill_switch(self, reason: str = "Manual activation") -> None:
        """
        Activate the kill switch, blocking all new orders.

        Args:
            reason: Reason for activation
        """
        self._kill_switch_active = True
        self._kill_switch_activated_at = datetime.now(UTC)
        self._kill_switch_reason = reason
        logger.critical(
            "kill_switch_activated",
            reason=reason,
        )

    def deactivate_kill_switch(self) -> None:
        """Deactivate the kill switch, allowing new orders."""
        self._kill_switch_active = False
        self._kill_switch_activated_at = None
        self._kill_switch_reason = None
        logger.info("kill_switch_deactivated")

    def is_kill_switch_active(self) -> bool:
        """Return whether the kill switch is currently active."""
        return self._kill_switch_active

    def get_kill_switch_status(self) -> dict[str, object]:
        """
        Get current kill switch status.

        Returns:
            Dict with active flag, activated_at timestamp, and reason.
        """
        return {
            "active": self._kill_switch_active,
            "activated_at": self._kill_switch_activated_at.isoformat()
            if self._kill_switch_activated_at
            else None,
            "reason": self._kill_switch_reason,
        }

    async def close_all_positions(self) -> list[ExecutionReport]:
        """
        Close all positions across all connected brokers.

        Returns:
            Aggregated list of ExecutionReports from all adapters
        """
        all_reports: list[ExecutionReport] = []

        for name, adapter in [("mt5", self._mt5_adapter), ("alpaca", self._alpaca_adapter)]:
            if adapter is None:
                continue
            try:
                reports = await adapter.close_all_positions()
                all_reports.extend(reports)
                logger.info(
                    "broker_router_close_all_from_adapter",
                    adapter=name,
                    count=len(reports),
                )
            except Exception as e:
                logger.error(
                    "broker_router_close_all_adapter_error",
                    adapter=name,
                    error=str(e),
                )

        logger.info(
            "broker_router_close_all_positions_complete",
            total_reports=len(all_reports),
        )
        return all_reports
