"""
Unit tests for Enhanced Metrics Calculator (Story 12.6A - QA Fixed).

Comprehensive tests with proper fixtures for all calculation methods.

Author: Story 12.6A Task 20
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.enhanced_metrics import EnhancedMetricsCalculator
from src.models.backtest import (
    BacktestPosition,
    BacktestTrade,
    EquityCurvePoint,
)


@pytest.fixture
def calculator():
    """Create EnhancedMetricsCalculator instance."""
    return EnhancedMetricsCalculator()


def create_trade(
    symbol: str,
    pnl: Decimal,
    r_multiple: Decimal,
    pattern_type: str,
    hours_duration: int = 24,
    entry_price: Decimal = Decimal("100"),
    exit_date: datetime | None = None,
) -> BacktestTrade:
    """Helper to create BacktestTrade with all required fields."""
    base_time = datetime(2023, 1, 1, 9, 30, tzinfo=UTC)
    quantity = Decimal("100")
    exit_price = entry_price + (pnl / quantity)

    # Allow custom exit timestamp for monthly grouping tests
    exit_ts = exit_date if exit_date else base_time + timedelta(hours=hours_duration)

    return BacktestTrade(
        trade_id=uuid4(),
        position_id=uuid4(),
        symbol=symbol,
        side="LONG",
        quantity=quantity,
        entry_price=entry_price,
        exit_price=exit_price,
        entry_timestamp=base_time,
        exit_timestamp=exit_ts,
        realized_pnl=pnl,
        r_multiple=r_multiple,
        pattern_type=pattern_type,
        commission=Decimal("2.00"),
        slippage=Decimal("1.00"),
        entry_commission=Decimal("1.00"),
        exit_commission=Decimal("1.00"),
        entry_slippage=Decimal("0.50"),
        exit_slippage=Decimal("0.50"),
        total_commission=Decimal("2.00"),
        total_slippage=Decimal("1.00"),
        gross_pnl=pnl + Decimal("3.00"),
    )


@pytest.fixture
def sample_trades():
    """Create sample trades for testing with exits in Jan and Feb."""
    jan = datetime(2023, 1, 15, tzinfo=UTC)
    feb = datetime(2023, 2, 15, tzinfo=UTC)

    return [
        create_trade("AAPL", Decimal("300.00"), Decimal("2.0"), "SPRING", exit_date=jan),
        create_trade("MSFT", Decimal("-150.00"), Decimal("-1.0"), "SPRING", exit_date=jan),
        create_trade("GOOGL", Decimal("140.00"), Decimal("1.5"), "SOS", exit_date=feb),
        create_trade("TSLA", Decimal("500.00"), Decimal("3.0"), "LPS", exit_date=jan),
        create_trade("AMZN", Decimal("-200.00"), Decimal("-0.5"), "UTAD", exit_date=feb),
    ]


@pytest.fixture
def sample_equity_curve():
    """Create sample equity curve."""
    base_time = datetime(2023, 1, 1, tzinfo=UTC)
    points = []

    # January - gradual increase
    for day in range(31):
        value = Decimal("100000") + Decimal(str(day * 100))
        points.append(
            EquityCurvePoint(
                timestamp=base_time + timedelta(days=day),
                equity_value=value,
                portfolio_value=value,
                cash=value,
                positions_value=Decimal("0"),
                daily_return=Decimal("0"),
                cumulative_return=Decimal(str(day * 0.1)),
            )
        )

    # February - drawdown then recovery
    feb_base = base_time + timedelta(days=31)
    peak_value = points[-1].portfolio_value
    for day in range(28):
        if day < 14:
            value = peak_value - Decimal(str(day * 200))  # Drawdown
        else:
            value = peak_value - Decimal(str((28 - day) * 200))  # Recovery
        points.append(
            EquityCurvePoint(
                timestamp=feb_base + timedelta(days=day),
                equity_value=value,
                portfolio_value=value,
                cash=value,
                positions_value=Decimal("0"),
                daily_return=Decimal("0"),
                cumulative_return=Decimal(str((31 + day) * 0.1)),
            )
        )

    return points


class TestPatternPerformance:
    """Test pattern performance calculations."""

    def test_calculate_pattern_performance_basic(self, calculator, sample_trades):
        """Test basic pattern performance with field name fixes."""
        result = calculator.calculate_pattern_performance(sample_trades)

        assert len(result) > 0

        # Find SPRING pattern
        spring = next((p for p in result if p.pattern_type == "SPRING"), None)
        assert spring is not None
        assert spring.total_trades == 2
        assert spring.winning_trades == 1
        assert spring.losing_trades == 1
        assert spring.win_rate == Decimal("0.5")

        # Verify P&L fields (not R-multiples)
        assert spring.best_trade_pnl == Decimal("300.00")
        assert spring.worst_trade_pnl == Decimal("-150.00")

    def test_calculate_pattern_performance_empty(self, calculator):
        """Test with empty trade list."""
        result = calculator.calculate_pattern_performance([])
        assert len(result) == 0

    def test_calculate_pattern_performance_profit_factor(self, calculator, sample_trades):
        """Test profit factor calculation."""
        result = calculator.calculate_pattern_performance(sample_trades)
        spring = next((p for p in result if p.pattern_type == "SPRING"), None)

        # profit_factor = wins / losses = 300 / 150 = 2.0
        assert spring.profit_factor == Decimal("2.0")


class TestMonthlyReturns:
    """Test monthly return calculations."""

    def test_calculate_monthly_returns_basic(self, calculator, sample_equity_curve, sample_trades):
        """Test monthly return calculation."""
        result = calculator.calculate_monthly_returns(sample_equity_curve, sample_trades)

        assert len(result) >= 2  # At least Jan and Feb

        jan = next((m for m in result if m.month == 1), None)
        assert jan is not None
        assert jan.year == 2023
        assert jan.month_label == "Jan 2023"

    def test_calculate_monthly_returns_empty(self, calculator):
        """Test with empty inputs."""
        result = calculator.calculate_monthly_returns([], [])
        assert len(result) == 0


class TestDrawdownPeriods:
    """Test drawdown period calculations."""

    def test_calculate_drawdown_periods_basic(self, calculator, sample_equity_curve):
        """Test drawdown detection."""
        result = calculator.calculate_drawdown_periods(sample_equity_curve)

        assert len(result) > 0
        # Largest drawdown should be first (sorted by severity - most negative)
        assert result[0].drawdown_pct < Decimal("0")

    def test_calculate_drawdown_periods_empty(self, calculator):
        """Test with empty curve."""
        result = calculator.calculate_drawdown_periods([])
        assert len(result) == 0


class TestRiskMetrics:
    """Test risk metrics calculations."""

    def test_calculate_risk_metrics_basic(self, calculator):
        """Test basic risk metrics."""
        base_time = datetime(2023, 1, 1, tzinfo=UTC)

        snapshots = [
            (
                base_time,
                [
                    BacktestPosition(
                        position_id=uuid4(),
                        symbol="AAPL",
                        side="LONG",
                        quantity=100,
                        average_entry_price=Decimal("150.00"),
                        current_price=Decimal("152.00"),
                        entry_timestamp=base_time,
                        last_updated=base_time,
                        unrealized_pnl=Decimal("200.00"),
                    ),
                ],
            ),
        ]

        result = calculator.calculate_risk_metrics(snapshots, Decimal("100000"))
        assert result is not None
        assert result.max_concurrent_positions >= 1

    def test_calculate_risk_metrics_empty(self, calculator):
        """Test with no snapshots."""
        result = calculator.calculate_risk_metrics([], Decimal("100000"))
        assert result is None


class TestTradeStreaks:
    """Test trade streak calculations."""

    def test_calculate_trade_streaks_mixed(self, calculator):
        """Test streak calculation with mixed wins/losses."""
        trades = [
            create_trade("A", Decimal("100"), Decimal("1"), "SPRING", 24),  # Win
            create_trade("B", Decimal("200"), Decimal("1"), "SOS", 24),  # Win
            create_trade("C", Decimal("150"), Decimal("1"), "LPS", 24),  # Win (streak=3)
            create_trade("D", Decimal("-50"), Decimal("-1"), "UTAD", 24),  # Loss
            create_trade("E", Decimal("-75"), Decimal("-1"), "UTAD", 24),  # Loss (streak=2)
            create_trade("F", Decimal("100"), Decimal("1"), "SPRING", 24),  # Win
        ]

        win_streak, lose_streak = calculator.calculate_trade_streaks(trades)

        assert win_streak == 3  # Longest winning streak
        assert lose_streak == 2  # Longest losing streak

    def test_calculate_trade_streaks_empty(self, calculator):
        """Test with no trades."""
        win_streak, lose_streak = calculator.calculate_trade_streaks([])
        assert win_streak == 0
        assert lose_streak == 0


class TestExtremeTradeIdentification:
    """Test extreme trade identification."""

    def test_identify_extreme_trades(self, calculator, sample_trades):
        """Test identification of largest winner/loser."""
        winner, loser = calculator.identify_extreme_trades(sample_trades)

        assert winner is not None
        assert loser is not None

        # Largest winner should be TSLA +500
        assert winner.realized_pnl == Decimal("500.00")
        assert winner.symbol == "TSLA"

        # Largest loser should be AMZN -200
        assert loser.realized_pnl == Decimal("-200.00")
        assert loser.symbol == "AMZN"

    def test_identify_extreme_trades_empty(self, calculator):
        """Test with no trades."""
        winner, loser = calculator.identify_extreme_trades([])
        assert winner is None
        assert loser is None


class TestCampaignPerformance:
    """Test campaign performance (placeholder)."""

    def test_calculate_campaign_performance_placeholder(self, calculator, sample_trades):
        """Test campaign performance detection with WyckoffCampaignDetector."""
        result = calculator.calculate_campaign_performance(sample_trades)
        # Now uses WyckoffCampaignDetector - should detect campaigns from trades with pattern_type
        assert isinstance(result, list)
        # May or may not detect campaigns depending on pattern_type in sample_trades
        for campaign in result:
            assert hasattr(campaign, "campaign_type")
            assert hasattr(campaign, "symbol")
