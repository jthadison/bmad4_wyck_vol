"""
Execution Risk Gate - Story 23.11

Pre-flight risk enforcement that checks ALL risk limits before any order
is submitted to a broker. This is the last line of defense before real money
is at risk.

Hard Limits (NON-NEGOTIABLE):
  - Max risk per trade: 2.0% of portfolio
  - Max portfolio heat: 10.0% of portfolio
  - Max campaign risk: 5.0% of portfolio
  - Max correlated risk: 6.0% of portfolio

Author: Story 23.11
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional

import structlog

from src.models.order import Order

logger = structlog.get_logger(__name__)


# Hard limits - NON-NEGOTIABLE
MAX_TRADE_RISK_PCT = Decimal("2.0")
MAX_PORTFOLIO_HEAT_PCT = Decimal("10.0")
MAX_CAMPAIGN_RISK_PCT = Decimal("5.0")
MAX_CORRELATED_RISK_PCT = Decimal("6.0")


class RiskCheckResult(str, Enum):
    """Result of a pre-flight risk check."""

    PASSED = "PASSED"
    BLOCKED = "BLOCKED"


@dataclass
class RiskViolation:
    """Details of a single risk limit violation."""

    limit_name: str
    current_value: Decimal
    limit_value: Decimal
    message: str


@dataclass
class PreFlightResult:
    """Result of pre-flight risk gate check."""

    result: RiskCheckResult
    order_id: str
    symbol: str
    violations: list[RiskViolation] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.result == RiskCheckResult.PASSED

    @property
    def blocked(self) -> bool:
        return self.result == RiskCheckResult.BLOCKED


@dataclass
class PortfolioState:
    """
    Current portfolio state for risk checks.

    This is provided by the caller (e.g., broker router) and represents
    the current state of the portfolio at the time of the risk check.
    """

    account_equity: Decimal
    current_heat_pct: Decimal = Decimal("0")
    current_campaign_risk_pct: Decimal = Decimal("0")
    current_correlated_risk_pct: Decimal = Decimal("0")


class ExecutionRiskGate:
    """
    Pre-flight risk gate that validates orders against hard risk limits
    before they are submitted to any broker.

    This is the final enforcement layer. Even if upstream validation
    passed an order, this gate will block it if any hard limit would
    be violated.

    All limits are NON-NEGOTIABLE and cannot be overridden.
    """

    def __init__(self) -> None:
        self._logger = logger.bind(component="execution_risk_gate")
        self._logger.info(
            "execution_risk_gate_initialized",
            max_trade_risk_pct=str(MAX_TRADE_RISK_PCT),
            max_portfolio_heat_pct=str(MAX_PORTFOLIO_HEAT_PCT),
            max_campaign_risk_pct=str(MAX_CAMPAIGN_RISK_PCT),
            max_correlated_risk_pct=str(MAX_CORRELATED_RISK_PCT),
        )

    def check_order(
        self,
        order: Order,
        portfolio_state: PortfolioState,
        trade_risk_pct: Decimal,
        campaign_risk_pct: Optional[Decimal] = None,
        correlated_risk_pct: Optional[Decimal] = None,
    ) -> PreFlightResult:
        """
        Run all pre-flight risk checks on an order.

        Args:
            order: The order to validate.
            portfolio_state: Current portfolio state.
            trade_risk_pct: Risk percentage this trade represents.
            campaign_risk_pct: Projected campaign risk after this trade (if applicable).
            correlated_risk_pct: Projected correlated risk after this trade (if applicable).

        Returns:
            PreFlightResult with pass/block decision and violation details.
        """
        violations: list[RiskViolation] = []

        # Check 1: Trade risk limit (2.0%)
        if trade_risk_pct > MAX_TRADE_RISK_PCT:
            violations.append(
                RiskViolation(
                    limit_name="trade_risk",
                    current_value=trade_risk_pct,
                    limit_value=MAX_TRADE_RISK_PCT,
                    message=f"Trade risk {trade_risk_pct}% exceeds max {MAX_TRADE_RISK_PCT}%",
                )
            )

        # Check 2: Portfolio heat limit (10.0%)
        projected_heat = portfolio_state.current_heat_pct + trade_risk_pct
        if projected_heat > MAX_PORTFOLIO_HEAT_PCT:
            violations.append(
                RiskViolation(
                    limit_name="portfolio_heat",
                    current_value=projected_heat,
                    limit_value=MAX_PORTFOLIO_HEAT_PCT,
                    message=(
                        f"Portfolio heat would be {projected_heat}% "
                        f"(current {portfolio_state.current_heat_pct}% + "
                        f"trade {trade_risk_pct}%), exceeds max {MAX_PORTFOLIO_HEAT_PCT}%"
                    ),
                )
            )

        # Check 3: Campaign risk limit (5.0%)
        if campaign_risk_pct is not None and campaign_risk_pct > MAX_CAMPAIGN_RISK_PCT:
            violations.append(
                RiskViolation(
                    limit_name="campaign_risk",
                    current_value=campaign_risk_pct,
                    limit_value=MAX_CAMPAIGN_RISK_PCT,
                    message=f"Campaign risk {campaign_risk_pct}% exceeds max {MAX_CAMPAIGN_RISK_PCT}%",
                )
            )

        # Check 4: Correlated risk limit (6.0%)
        if correlated_risk_pct is not None and correlated_risk_pct > MAX_CORRELATED_RISK_PCT:
            violations.append(
                RiskViolation(
                    limit_name="correlated_risk",
                    current_value=correlated_risk_pct,
                    limit_value=MAX_CORRELATED_RISK_PCT,
                    message=(
                        f"Correlated risk {correlated_risk_pct}% "
                        f"exceeds max {MAX_CORRELATED_RISK_PCT}%"
                    ),
                )
            )

        result = RiskCheckResult.BLOCKED if violations else RiskCheckResult.PASSED
        preflight = PreFlightResult(
            result=result,
            order_id=str(order.id),
            symbol=order.symbol,
            violations=violations,
        )

        if preflight.blocked:
            self._logger.warning(
                "order_blocked_by_risk_gate",
                order_id=str(order.id),
                symbol=order.symbol,
                violation_count=len(violations),
                violations=[
                    {
                        "limit": v.limit_name,
                        "current": str(v.current_value),
                        "limit_value": str(v.limit_value),
                    }
                    for v in violations
                ],
            )
        else:
            self._logger.info(
                "order_passed_risk_gate",
                order_id=str(order.id),
                symbol=order.symbol,
                trade_risk_pct=str(trade_risk_pct),
            )

        return preflight
