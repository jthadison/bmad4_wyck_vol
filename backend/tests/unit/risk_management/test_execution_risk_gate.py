"""
Execution Risk Gate Unit Tests - Story 23.11

Tests the ExecutionRiskGate pre-flight risk enforcement:
- Order within all limits passes
- Order exceeding trade risk (>2%) is blocked
- Order exceeding portfolio heat (>10%) is blocked
- Order exceeding campaign risk (>5%) is blocked
- Order exceeding correlated risk (>6%) is blocked
- Blocked orders include correct reason details
- Multiple simultaneous limit violations

Coverage target: >= 95%
"""

from decimal import Decimal

import pytest

from src.models.order import Order, OrderSide, OrderType
from src.risk_management.execution_risk_gate import (
    MAX_CAMPAIGN_RISK_PCT,
    MAX_CORRELATED_RISK_PCT,
    MAX_PORTFOLIO_HEAT_PCT,
    MAX_TRADE_RISK_PCT,
    ExecutionRiskGate,
    PortfolioState,
    RiskCheckResult,
)


@pytest.fixture
def gate() -> ExecutionRiskGate:
    return ExecutionRiskGate()


@pytest.fixture
def sample_order() -> Order:
    return Order(
        platform="test",
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("100"),
    )


@pytest.fixture
def normal_portfolio() -> PortfolioState:
    return PortfolioState(
        account_equity=Decimal("100000"),
        current_heat_pct=Decimal("5.0"),
        current_campaign_risk_pct=Decimal("2.0"),
        current_correlated_risk_pct=Decimal("3.0"),
    )


class TestExecutionRiskGatePassCases:
    """Test orders that should pass all risk checks."""

    def test_order_within_all_limits_passes(
        self, gate: ExecutionRiskGate, sample_order: Order, normal_portfolio: PortfolioState
    ) -> None:
        """Order with risk within all limits should pass."""
        result = gate.check_order(
            order=sample_order,
            portfolio_state=normal_portfolio,
            trade_risk_pct=Decimal("1.0"),
            campaign_risk_pct=Decimal("3.0"),
            correlated_risk_pct=Decimal("4.0"),
        )
        assert result.passed
        assert result.result == RiskCheckResult.PASSED
        assert len(result.violations) == 0
        assert result.symbol == "AAPL"

    def test_order_at_exact_trade_limit_passes(
        self, gate: ExecutionRiskGate, sample_order: Order
    ) -> None:
        """Order at exactly 2.0% trade risk should pass (limit is >2.0% to block)."""
        portfolio = PortfolioState(
            account_equity=Decimal("100000"),
            current_heat_pct=Decimal("0"),
        )
        result = gate.check_order(
            order=sample_order,
            portfolio_state=portfolio,
            trade_risk_pct=MAX_TRADE_RISK_PCT,  # exactly 2.0%
        )
        assert result.passed

    def test_order_at_exact_heat_limit_passes(
        self, gate: ExecutionRiskGate, sample_order: Order
    ) -> None:
        """Order that brings heat to exactly 10.0% should pass (limit is >10.0% to block)."""
        portfolio = PortfolioState(
            account_equity=Decimal("100000"),
            current_heat_pct=Decimal("9.0"),
        )
        result = gate.check_order(
            order=sample_order,
            portfolio_state=portfolio,
            trade_risk_pct=Decimal("1.0"),  # 9.0 + 1.0 = 10.0%
        )
        assert result.passed

    def test_order_without_campaign_or_correlated_risk(
        self, gate: ExecutionRiskGate, sample_order: Order
    ) -> None:
        """Order without campaign/correlated risk provided should only check trade + heat."""
        portfolio = PortfolioState(
            account_equity=Decimal("100000"),
            current_heat_pct=Decimal("5.0"),
        )
        result = gate.check_order(
            order=sample_order,
            portfolio_state=portfolio,
            trade_risk_pct=Decimal("1.0"),
        )
        assert result.passed
        assert len(result.violations) == 0


class TestExecutionRiskGateBlockCases:
    """Test orders that should be blocked by risk checks."""

    def test_trade_risk_exceeds_limit(
        self, gate: ExecutionRiskGate, sample_order: Order, normal_portfolio: PortfolioState
    ) -> None:
        """Order exceeding 2.0% trade risk should be blocked."""
        result = gate.check_order(
            order=sample_order,
            portfolio_state=normal_portfolio,
            trade_risk_pct=Decimal("2.5"),
        )
        assert result.blocked
        assert result.result == RiskCheckResult.BLOCKED
        assert len(result.violations) == 1
        assert result.violations[0].limit_name == "trade_risk"
        assert result.violations[0].current_value == Decimal("2.5")
        assert result.violations[0].limit_value == MAX_TRADE_RISK_PCT

    def test_portfolio_heat_exceeds_limit(
        self, gate: ExecutionRiskGate, sample_order: Order
    ) -> None:
        """Order that would push portfolio heat above 10.0% should be blocked."""
        portfolio = PortfolioState(
            account_equity=Decimal("100000"),
            current_heat_pct=Decimal("9.5"),
        )
        result = gate.check_order(
            order=sample_order,
            portfolio_state=portfolio,
            trade_risk_pct=Decimal("1.0"),  # 9.5 + 1.0 = 10.5% > 10%
        )
        assert result.blocked
        assert len(result.violations) == 1
        assert result.violations[0].limit_name == "portfolio_heat"
        assert result.violations[0].current_value == Decimal("10.5")
        assert result.violations[0].limit_value == MAX_PORTFOLIO_HEAT_PCT

    def test_campaign_risk_exceeds_limit(
        self, gate: ExecutionRiskGate, sample_order: Order, normal_portfolio: PortfolioState
    ) -> None:
        """Order exceeding 5.0% campaign risk should be blocked."""
        result = gate.check_order(
            order=sample_order,
            portfolio_state=normal_portfolio,
            trade_risk_pct=Decimal("1.0"),
            campaign_risk_pct=Decimal("5.5"),
        )
        assert result.blocked
        assert any(v.limit_name == "campaign_risk" for v in result.violations)
        campaign_v = next(v for v in result.violations if v.limit_name == "campaign_risk")
        assert campaign_v.current_value == Decimal("5.5")
        assert campaign_v.limit_value == MAX_CAMPAIGN_RISK_PCT

    def test_correlated_risk_exceeds_limit(
        self, gate: ExecutionRiskGate, sample_order: Order, normal_portfolio: PortfolioState
    ) -> None:
        """Order exceeding 6.0% correlated risk should be blocked."""
        result = gate.check_order(
            order=sample_order,
            portfolio_state=normal_portfolio,
            trade_risk_pct=Decimal("1.0"),
            correlated_risk_pct=Decimal("7.0"),
        )
        assert result.blocked
        assert any(v.limit_name == "correlated_risk" for v in result.violations)
        corr_v = next(v for v in result.violations if v.limit_name == "correlated_risk")
        assert corr_v.current_value == Decimal("7.0")
        assert corr_v.limit_value == MAX_CORRELATED_RISK_PCT


class TestExecutionRiskGateViolationDetails:
    """Test that blocked orders include correct details."""

    def test_blocked_order_includes_order_id(
        self, gate: ExecutionRiskGate, sample_order: Order, normal_portfolio: PortfolioState
    ) -> None:
        """Blocked result should include the order ID."""
        result = gate.check_order(
            order=sample_order,
            portfolio_state=normal_portfolio,
            trade_risk_pct=Decimal("3.0"),
        )
        assert result.order_id == str(sample_order.id)

    def test_blocked_order_includes_symbol(
        self, gate: ExecutionRiskGate, sample_order: Order, normal_portfolio: PortfolioState
    ) -> None:
        """Blocked result should include the symbol."""
        result = gate.check_order(
            order=sample_order,
            portfolio_state=normal_portfolio,
            trade_risk_pct=Decimal("3.0"),
        )
        assert result.symbol == "AAPL"

    def test_violation_message_contains_values(
        self, gate: ExecutionRiskGate, sample_order: Order, normal_portfolio: PortfolioState
    ) -> None:
        """Violation message should contain current and limit values."""
        result = gate.check_order(
            order=sample_order,
            portfolio_state=normal_portfolio,
            trade_risk_pct=Decimal("3.0"),
        )
        msg = result.violations[0].message
        assert "3.0" in msg
        assert "2.0" in msg


class TestExecutionRiskGateMultipleViolations:
    """Test multiple simultaneous limit violations."""

    def test_multiple_violations_all_reported(
        self, gate: ExecutionRiskGate, sample_order: Order
    ) -> None:
        """All violated limits should be reported, not just the first."""
        portfolio = PortfolioState(
            account_equity=Decimal("100000"),
            current_heat_pct=Decimal("9.5"),
        )
        result = gate.check_order(
            order=sample_order,
            portfolio_state=portfolio,
            trade_risk_pct=Decimal("3.0"),  # > 2.0% (blocked)
            campaign_risk_pct=Decimal("6.0"),  # > 5.0% (blocked)
            correlated_risk_pct=Decimal("7.0"),  # > 6.0% (blocked)
            # Heat: 9.5 + 3.0 = 12.5% > 10.0% (blocked)
        )
        assert result.blocked
        violation_names = {v.limit_name for v in result.violations}
        assert "trade_risk" in violation_names
        assert "portfolio_heat" in violation_names
        assert "campaign_risk" in violation_names
        assert "correlated_risk" in violation_names
        assert len(result.violations) == 4

    def test_two_violations_both_reported(
        self, gate: ExecutionRiskGate, sample_order: Order, normal_portfolio: PortfolioState
    ) -> None:
        """Two violations should both be reported."""
        result = gate.check_order(
            order=sample_order,
            portfolio_state=normal_portfolio,
            trade_risk_pct=Decimal("3.0"),  # > 2.0% (blocked)
            correlated_risk_pct=Decimal("7.0"),  # > 6.0% (blocked)
        )
        assert result.blocked
        assert len(result.violations) == 2


class TestPreFlightResultProperties:
    """Test PreFlightResult convenience properties."""

    def test_passed_property(self, gate: ExecutionRiskGate, sample_order: Order) -> None:
        portfolio = PortfolioState(account_equity=Decimal("100000"))
        result = gate.check_order(
            order=sample_order,
            portfolio_state=portfolio,
            trade_risk_pct=Decimal("1.0"),
        )
        assert result.passed is True
        assert result.blocked is False

    def test_blocked_property(self, gate: ExecutionRiskGate, sample_order: Order) -> None:
        portfolio = PortfolioState(account_equity=Decimal("100000"))
        result = gate.check_order(
            order=sample_order,
            portfolio_state=portfolio,
            trade_risk_pct=Decimal("3.0"),
        )
        assert result.blocked is True
        assert result.passed is False
