"""
Unit tests for MetricsFacade (Story 18.7.3).

Tests:
- Facade initialization
- Delegation to sub-calculators
- Full metrics calculation

Author: Story 18.7.3
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.metrics_core.facade import MetricsFacade
from src.models.backtest import BacktestMetrics, BacktestTrade, EquityCurvePoint


@pytest.fixture
def facade():
    """Fixture for MetricsFacade."""
    return MetricsFacade()


@pytest.fixture
def sample_equity_curve():
    """Sample equity curve for testing."""
    return [
        EquityCurvePoint(
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            equity_value=Decimal("100000"),
            portfolio_value=Decimal("100000"),
            cash=Decimal("100000"),
            positions_value=Decimal("0"),
        ),
        EquityCurvePoint(
            timestamp=datetime(2024, 1, 15, tzinfo=UTC),
            equity_value=Decimal("105000"),
            portfolio_value=Decimal("105000"),
            cash=Decimal("100000"),
            positions_value=Decimal("5000"),
        ),
        EquityCurvePoint(
            timestamp=datetime(2024, 1, 31, tzinfo=UTC),
            equity_value=Decimal("110000"),
            portfolio_value=Decimal("110000"),
            cash=Decimal("100000"),
            positions_value=Decimal("10000"),
        ),
    ]


@pytest.fixture
def sample_trades():
    """Sample trades for testing."""
    return [
        BacktestTrade(
            trade_id=uuid4(),
            position_id=uuid4(),
            symbol="AAPL",
            side="LONG",
            quantity=100,
            entry_price=Decimal("150.00"),
            exit_price=Decimal("160.00"),
            entry_timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            exit_timestamp=datetime(2024, 1, 15, tzinfo=UTC),
            realized_pnl=Decimal("1000.00"),
            commission=Decimal("1.00"),
            slippage=Decimal("0.50"),
            r_multiple=Decimal("2.0"),
        ),
        BacktestTrade(
            trade_id=uuid4(),
            position_id=uuid4(),
            symbol="AAPL",
            side="LONG",
            quantity=100,
            entry_price=Decimal("160.00"),
            exit_price=Decimal("155.00"),
            entry_timestamp=datetime(2024, 1, 16, tzinfo=UTC),
            exit_timestamp=datetime(2024, 1, 25, tzinfo=UTC),
            realized_pnl=Decimal("-500.00"),
            commission=Decimal("1.00"),
            slippage=Decimal("0.50"),
            r_multiple=Decimal("-1.0"),
        ),
    ]


class TestFacadeInitialization:
    """Test facade initialization."""

    def test_default_initialization(self):
        """Test facade initializes with default risk-free rate."""
        facade = MetricsFacade()
        assert facade.risk_free_rate == Decimal("0.02")

    def test_custom_risk_free_rate(self):
        """Test facade with custom risk-free rate."""
        facade = MetricsFacade(risk_free_rate=Decimal("0.05"))
        assert facade.risk_free_rate == Decimal("0.05")

    def test_sub_calculators_initialized(self):
        """Test that all sub-calculators are initialized."""
        facade = MetricsFacade()
        assert facade._drawdown is not None
        assert facade._risk is not None
        assert facade._returns is not None
        assert facade._trades is not None
        assert facade._equity is not None


class TestCalculateMetrics:
    """Test full metrics calculation."""

    def test_calculate_metrics_with_data(self, facade, sample_equity_curve, sample_trades):
        """Test metrics calculation with valid data."""
        metrics = facade.calculate_metrics(
            equity_curve=sample_equity_curve,
            trades=sample_trades,
            initial_capital=Decimal("100000"),
        )

        assert isinstance(metrics, BacktestMetrics)
        assert metrics.total_trades == 2
        assert metrics.winning_trades == 1
        assert metrics.losing_trades == 1
        assert metrics.win_rate == Decimal("0.5")
        # Return pct is calculated from equity curve (100k -> 110k = 10%)
        assert abs(metrics.total_return_pct - Decimal("10")) < Decimal("0.01")

    def test_calculate_metrics_empty_equity(self, facade, sample_trades):
        """Test metrics with empty equity curve."""
        metrics = facade.calculate_metrics(
            equity_curve=[],
            trades=sample_trades,
            initial_capital=Decimal("100000"),
        )

        assert metrics.total_trades == 2
        assert metrics.total_return_pct == Decimal("0")

    def test_calculate_metrics_empty_trades(self, facade, sample_equity_curve):
        """Test metrics with no trades."""
        metrics = facade.calculate_metrics(
            equity_curve=sample_equity_curve,
            trades=[],
            initial_capital=Decimal("100000"),
        )

        assert metrics.total_trades == 0
        assert metrics.winning_trades == 0
        assert metrics.losing_trades == 0
        assert metrics.win_rate == Decimal("0")
        assert abs(metrics.total_return_pct - Decimal("10")) < Decimal("0.01")

    def test_calculate_metrics_empty_all(self, facade):
        """Test metrics with no data at all."""
        metrics = facade.calculate_metrics(
            equity_curve=[],
            trades=[],
            initial_capital=Decimal("100000"),
        )

        assert metrics.total_trades == 0
        assert metrics.total_return_pct == Decimal("0")


class TestDelegatedMethods:
    """Test delegated calculation methods."""

    def test_calculate_win_rate(self, facade):
        """Test win rate delegation."""
        assert facade.calculate_win_rate(60, 100) == Decimal("0.6")

    def test_calculate_profit_factor(self, facade, sample_trades):
        """Test profit factor delegation."""
        # 1000 profit / 500 loss = 2.0
        result = facade.calculate_profit_factor(sample_trades)
        assert result == Decimal("2")

    def test_calculate_avg_r_multiple(self, facade, sample_trades):
        """Test avg R-multiple delegation."""
        # (2.0 + (-1.0)) / 2 = 0.5
        result = facade.calculate_avg_r_multiple(sample_trades)
        assert result == Decimal("0.5")

    def test_calculate_sharpe_ratio(self, facade, sample_equity_curve):
        """Test Sharpe ratio delegation."""
        result = facade.calculate_sharpe_ratio(sample_equity_curve)
        assert isinstance(result, Decimal)

    def test_calculate_sharpe_ratio_insufficient_data(self, facade):
        """Test Sharpe ratio with insufficient data."""
        result = facade.calculate_sharpe_ratio([])
        assert result == Decimal("0")

    def test_calculate_max_drawdown(self, facade):
        """Test max drawdown delegation."""
        equity_curve = [
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                equity_value=Decimal("100000"),
                portfolio_value=Decimal("100000"),
                cash=Decimal("100000"),
                positions_value=Decimal("0"),
            ),
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 15, tzinfo=UTC),
                equity_value=Decimal("110000"),
                portfolio_value=Decimal("110000"),  # Peak
                cash=Decimal("100000"),
                positions_value=Decimal("10000"),
            ),
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 31, tzinfo=UTC),
                equity_value=Decimal("99000"),
                portfolio_value=Decimal("99000"),  # Trough
                cash=Decimal("100000"),
                positions_value=Decimal("-1000"),
            ),
        ]
        max_dd, duration = facade.calculate_max_drawdown(equity_curve)

        # Drawdown: (110000 - 99000) / 110000 = 10%
        assert max_dd == Decimal("10")
        assert duration == 16  # Days from Jan 15 to Jan 31

    def test_calculate_max_drawdown_empty(self, facade):
        """Test max drawdown with empty curve."""
        max_dd, duration = facade.calculate_max_drawdown([])
        assert max_dd == Decimal("0")
        assert duration == 0

    def test_calculate_cagr(self, facade):
        """Test CAGR delegation."""
        result = facade.calculate_cagr(
            final_value=Decimal("121000"),
            initial_capital=Decimal("100000"),
            start_date=datetime(2024, 1, 1, tzinfo=UTC),
            end_date=datetime(2026, 1, 1, tzinfo=UTC),
        )
        # ~10% CAGR over 2 years
        assert abs(result - Decimal("0.10")) < Decimal("0.01")

    def test_calculate_total_return_pct(self, facade):
        """Test total return percentage delegation."""
        result = facade.calculate_total_return_pct(
            final_value=Decimal("125000"),
            initial_capital=Decimal("100000"),
        )
        assert result == Decimal("25")


class TestEdgeCases:
    """Test edge cases."""

    def test_single_equity_point(self, facade, sample_trades):
        """Test with single equity point."""
        equity_curve = [
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                equity_value=Decimal("100000"),
                portfolio_value=Decimal("100000"),
                cash=Decimal("100000"),
                positions_value=Decimal("0"),
            )
        ]
        metrics = facade.calculate_metrics(
            equity_curve=equity_curve,
            trades=sample_trades,
            initial_capital=Decimal("100000"),
        )

        assert metrics.total_return_pct == Decimal("0")

    def test_all_winning_trades(self, facade, sample_equity_curve):
        """Test with all winning trades."""
        trades = [
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="LONG",
                quantity=100,
                entry_price=Decimal("150.00"),
                exit_price=Decimal("160.00"),
                entry_timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                exit_timestamp=datetime(2024, 1, 5, tzinfo=UTC),
                realized_pnl=Decimal("1000.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
                r_multiple=Decimal("2.0"),
            ),
        ]
        metrics = facade.calculate_metrics(
            equity_curve=sample_equity_curve,
            trades=trades,
            initial_capital=Decimal("100000"),
        )

        assert metrics.win_rate == Decimal("1.0")
        assert metrics.profit_factor == Decimal("0")  # No losses -> converted to 0

    def test_all_losing_trades(self, facade, sample_equity_curve):
        """Test with all losing trades."""
        trades = [
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="LONG",
                quantity=100,
                entry_price=Decimal("150.00"),
                exit_price=Decimal("140.00"),
                entry_timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                exit_timestamp=datetime(2024, 1, 5, tzinfo=UTC),
                realized_pnl=Decimal("-1000.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
                r_multiple=Decimal("-2.0"),
            ),
        ]
        metrics = facade.calculate_metrics(
            equity_curve=sample_equity_curve,
            trades=trades,
            initial_capital=Decimal("100000"),
        )

        assert metrics.win_rate == Decimal("0")
        assert metrics.profit_factor == Decimal("0")
