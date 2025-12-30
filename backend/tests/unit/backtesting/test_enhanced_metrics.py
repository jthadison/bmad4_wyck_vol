"""
Unit tests for EnhancedMetricsCalculator (Story 12.6A, 12.8).

Tests all 7 calculation methods:
- calculate_pattern_performance
- calculate_monthly_returns
- calculate_drawdown_periods
- calculate_risk_metrics
- calculate_campaign_performance
- calculate_trade_streaks
- identify_extreme_trades

Author: Story 12.8 Task 6
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.enhanced_metrics import EnhancedMetricsCalculator
from src.models.backtest import BacktestPosition, BacktestTrade, EquityCurvePoint


def make_trade(
    symbol="AAPL",
    pattern=None,
    entry_date=None,
    exit_date=None,
    days_duration=3,
    pnl=Decimal("200.00"),
    r_multiple=Decimal("2.0"),
    **kwargs
):
    """Helper to create BacktestTrade with defaults."""
    entry_date = entry_date or datetime(2024, 1, 1)
    if exit_date is None:
        exit_date = entry_date + timedelta(days=days_duration)

    return BacktestTrade(
        trade_id=uuid4(),
        position_id=uuid4(),
        symbol=symbol,
        pattern_type=pattern,
        entry_timestamp=entry_date,
        entry_price=Decimal("150.00"),
        exit_timestamp=exit_date,
        exit_price=Decimal("152.00"),
        quantity=100,
        side="LONG",
        realized_pnl=pnl,
        commission=Decimal("5.00"),
        slippage=Decimal("2.00"),
        r_multiple=r_multiple,
        **kwargs
    )


def make_equity_point(timestamp, value):
    """Helper to create EquityCurvePoint."""
    value_dec = Decimal(str(value))
    return EquityCurvePoint(
        timestamp=timestamp,
        equity_value=value_dec,
        portfolio_value=value_dec,
        cash=value_dec / 2,  # Assume 50% cash
        positions_value=value_dec / 2,  # Assume 50% in positions
    )


def make_position(symbol="AAPL", quantity=100, current_price=Decimal("150.00")):
    """Helper to create BacktestPosition."""
    entry_time = datetime(2024, 1, 1)
    return BacktestPosition(
        position_id=uuid4(),
        symbol=symbol,
        side="LONG",
        quantity=quantity,
        average_entry_price=Decimal("148.00"),
        current_price=current_price,
        entry_timestamp=entry_time,
        last_updated=entry_time,
        unrealized_pnl=Decimal("200.00"),
    )


@pytest.fixture
def calculator():
    """Create calculator instance."""
    return EnhancedMetricsCalculator()


class TestPatternPerformance:
    """Test calculate_pattern_performance method."""

    def test_empty_trades_list(self, calculator):
        """Test with empty trades list returns empty results."""
        result = calculator.calculate_pattern_performance([])
        assert result == []

    def test_trades_without_patterns(self, calculator):
        """Test with trades that have no pattern_type."""
        trades = [
            make_trade(pattern=None),
            make_trade(pattern=None),
        ]
        result = calculator.calculate_pattern_performance(trades)
        assert result == []

    def test_single_pattern_all_winners(self, calculator):
        """Test pattern with all winning trades."""
        trades = [
            make_trade(pattern="SPRING", pnl=Decimal("100.00"), r_multiple=Decimal("2.0")),
            make_trade(pattern="SPRING", pnl=Decimal("150.00"), r_multiple=Decimal("3.0")),
            make_trade(pattern="SPRING", pnl=Decimal("200.00"), r_multiple=Decimal("4.0")),
        ]

        result = calculator.calculate_pattern_performance(trades)

        assert len(result) == 1
        perf = result[0]
        assert perf.pattern_type == "SPRING"
        assert perf.total_trades == 3
        assert perf.winning_trades == 3
        assert perf.losing_trades == 0
        assert perf.win_rate == Decimal("1.0")  # 100%
        assert perf.avg_r_multiple == Decimal("3.0")  # (2+3+4)/3
        assert perf.total_pnl == Decimal("450.00")
        assert perf.best_trade_pnl == Decimal("200.00")
        assert perf.worst_trade_pnl == Decimal("100.00")

    def test_single_pattern_mixed_results(self, calculator):
        """Test pattern with winning and losing trades."""
        trades = [
            make_trade(pattern="UTAD", pnl=Decimal("200.00"), r_multiple=Decimal("2.0")),
            make_trade(pattern="UTAD", pnl=Decimal("-100.00"), r_multiple=Decimal("-1.0")),
            make_trade(pattern="UTAD", pnl=Decimal("300.00"), r_multiple=Decimal("3.0")),
        ]

        result = calculator.calculate_pattern_performance(trades)

        assert len(result) == 1
        perf = result[0]
        assert perf.total_trades == 3
        assert perf.winning_trades == 2
        assert perf.losing_trades == 1
        # Win rate should be approximately 0.6667 (2/3)
        assert abs(perf.win_rate - (Decimal("2") / Decimal("3"))) < Decimal("0.0001")
        assert perf.total_pnl == Decimal("400.00")
        # Profit factor = total_wins/abs(total_losses) = 500/100 = 5.0
        assert perf.profit_factor == Decimal("5")

    def test_multiple_patterns(self, calculator):
        """Test multiple different patterns."""
        trades = [
            make_trade(pattern="SPRING", pnl=Decimal("100.00")),
            make_trade(pattern="SPRING", pnl=Decimal("200.00")),
            make_trade(pattern="SOS", pnl=Decimal("150.00")),
            make_trade(pattern="LPS", pnl=Decimal("-50.00")),
        ]

        result = calculator.calculate_pattern_performance(trades)

        assert len(result) == 3  # SPRING, SOS, LPS
        # Sorted by total_trades descending
        assert result[0].pattern_type == "SPRING"
        assert result[0].total_trades == 2
        assert result[1].total_trades == 1
        assert result[2].total_trades == 1

    def test_trade_duration_calculation(self, calculator):
        """Test average trade duration calculation."""
        entry = datetime(2024, 1, 1)
        trades = [
            make_trade(
                pattern="TEST",
                entry_date=entry,
                exit_date=entry + timedelta(hours=24),  # 1 day
            ),
            make_trade(
                pattern="TEST",
                entry_date=entry,
                exit_date=entry + timedelta(hours=48),  # 2 days
            ),
        ]

        result = calculator.calculate_pattern_performance(trades)

        assert len(result) == 1
        # Avg duration = (24 + 48) / 2 = 36 hours
        assert result[0].avg_trade_duration_hours == Decimal("36.0")


class TestMonthlyReturns:
    """Test calculate_monthly_returns method."""

    def test_empty_equity_curve(self, calculator):
        """Test with empty equity curve."""
        result = calculator.calculate_monthly_returns([], [])
        assert result == []

    def test_single_month(self, calculator):
        """Test single month with multiple points."""
        equity_curve = [
            make_equity_point(datetime(2024, 1, 1), 100000),
            make_equity_point(datetime(2024, 1, 15), 105000),
            make_equity_point(datetime(2024, 1, 31), 110000),
        ]
        trades = [
            make_trade(
                entry_date=datetime(2024, 1, 5),
                exit_date=datetime(2024, 1, 10),
                pnl=Decimal("500.00")
            ),
        ]

        result = calculator.calculate_monthly_returns(equity_curve, trades)

        assert len(result) == 1
        monthly = result[0]
        assert monthly.year == 2024
        assert monthly.month == 1
        assert monthly.month_label == "Jan 2024"
        # Return: (110000 - 100000) / 100000 * 100 = 10%
        assert monthly.return_pct == Decimal("10.0000")
        assert monthly.trade_count == 1
        assert monthly.winning_trades == 1
        assert monthly.losing_trades == 0

    def test_multiple_months(self, calculator):
        """Test multiple months."""
        equity_curve = [
            # January
            make_equity_point(datetime(2024, 1, 1), 100000),
            make_equity_point(datetime(2024, 1, 31), 105000),
            # February
            make_equity_point(datetime(2024, 2, 1), 105000),
            make_equity_point(datetime(2024, 2, 29), 103000),
        ]
        trades = [
            make_trade(
                entry_date=datetime(2024, 1, 15),
                exit_date=datetime(2024, 1, 20),
                pnl=Decimal("500.00")
            ),
            make_trade(
                entry_date=datetime(2024, 2, 10),
                exit_date=datetime(2024, 2, 15),
                pnl=Decimal("-200.00")
            ),
        ]

        result = calculator.calculate_monthly_returns(equity_curve, trades)

        assert len(result) == 2
        # January: +5%
        assert result[0].month == 1
        assert result[0].return_pct == Decimal("5.0000")
        assert result[0].winning_trades == 1
        # February: -1.9047...%
        assert result[1].month == 2
        assert abs(result[1].return_pct - Decimal("-1.9048")) < Decimal("0.0001")
        assert result[1].losing_trades == 1

    def test_month_with_single_point(self, calculator):
        """Test month with only one equity point is skipped."""
        equity_curve = [
            make_equity_point(datetime(2024, 1, 1), 100000),
            make_equity_point(datetime(2024, 2, 1), 105000),
            make_equity_point(datetime(2024, 2, 28), 110000),
        ]

        result = calculator.calculate_monthly_returns(equity_curve, [])

        # Only February should be included (has 2 points)
        assert len(result) == 1
        assert result[0].month == 2


class TestDrawdownPeriods:
    """Test calculate_drawdown_periods method."""

    def test_empty_equity_curve(self, calculator):
        """Test with empty equity curve."""
        result = calculator.calculate_drawdown_periods([])
        assert result == []

    def test_single_point(self, calculator):
        """Test with single equity point."""
        equity_curve = [make_equity_point(datetime(2024, 1, 1), 100000)]
        result = calculator.calculate_drawdown_periods(equity_curve)
        assert result == []

    def test_no_drawdown_always_rising(self, calculator):
        """Test with always rising equity."""
        equity_curve = [
            make_equity_point(datetime(2024, 1, 1), 100000),
            make_equity_point(datetime(2024, 1, 2), 101000),
            make_equity_point(datetime(2024, 1, 3), 102000),
        ]

        result = calculator.calculate_drawdown_periods(equity_curve)
        assert result == []

    def test_single_drawdown_with_recovery(self, calculator):
        """Test single drawdown that recovers."""
        equity_curve = [
            make_equity_point(datetime(2024, 1, 1), 100000),  # Peak
            make_equity_point(datetime(2024, 1, 5), 95000),   # Trough
            make_equity_point(datetime(2024, 1, 10), 101000), # Recovery
        ]

        result = calculator.calculate_drawdown_periods(equity_curve)

        assert len(result) == 1
        dd = result[0]
        # DrawdownPeriod model enforces UTC timezone, so compare with UTC-aware datetimes
        assert dd.peak_date == datetime(2024, 1, 1, tzinfo=timezone.utc)
        assert dd.trough_date == datetime(2024, 1, 5, tzinfo=timezone.utc)
        assert dd.recovery_date == datetime(2024, 1, 10, tzinfo=timezone.utc)
        assert dd.peak_value == Decimal("100000")
        assert dd.trough_value == Decimal("95000")
        # Drawdown: (100000 - 95000) / 100000 * 100 = 5%
        assert dd.drawdown_pct == Decimal("5.0000")
        assert dd.duration_days == 4  # Jan 1 to Jan 5
        assert dd.recovery_duration_days == 5  # Jan 5 to Jan 10

    def test_multiple_drawdowns(self, calculator):
        """Test multiple drawdown events."""
        equity_curve = [
            make_equity_point(datetime(2024, 1, 1), 100000),  # Peak 1
            make_equity_point(datetime(2024, 1, 5), 90000),   # Trough 1
            make_equity_point(datetime(2024, 1, 10), 105000), # Recovery 1 & Peak 2
            make_equity_point(datetime(2024, 1, 15), 98000),  # Trough 2
            make_equity_point(datetime(2024, 1, 20), 110000), # Recovery 2
        ]

        result = calculator.calculate_drawdown_periods(equity_curve)

        assert len(result) == 2
        # Sorted by drawdown_pct descending
        # DD1: 10%, DD2: 6.67%
        assert result[0].drawdown_pct == Decimal("10.0000")
        assert result[1].drawdown_pct < Decimal("6.7000")

    def test_uncovered_drawdown(self, calculator):
        """Test drawdown that hasn't recovered yet."""
        equity_curve = [
            make_equity_point(datetime(2024, 1, 1), 100000),  # Peak
            make_equity_point(datetime(2024, 1, 5), 90000),   # Trough
            make_equity_point(datetime(2024, 1, 10), 92000),  # Still below peak
        ]

        result = calculator.calculate_drawdown_periods(equity_curve)

        assert len(result) == 1
        dd = result[0]
        assert dd.recovery_date is None
        assert dd.recovery_duration_days is None
        assert dd.drawdown_pct == Decimal("10.0000")


class TestRiskMetrics:
    """Test calculate_risk_metrics method."""

    def test_empty_snapshots(self, calculator):
        """Test with empty position snapshots."""
        result = calculator.calculate_risk_metrics([], Decimal("100000"))
        assert result is None

    def test_zero_initial_capital(self, calculator):
        """Test with zero initial capital."""
        snapshots = [(datetime(2024, 1, 1), [make_position()])]
        result = calculator.calculate_risk_metrics(snapshots, Decimal("0"))
        assert result is None

    def test_single_position(self, calculator):
        """Test with single position snapshot."""
        pos = make_position(quantity=100, current_price=Decimal("150.00"))
        snapshots = [(datetime(2024, 1, 1), [pos])]

        result = calculator.calculate_risk_metrics(snapshots, Decimal("100000"))

        assert result is not None
        assert result.max_concurrent_positions == 1
        assert result.avg_concurrent_positions == Decimal("1")
        # Portfolio heat: 1 position * 2% = 2%
        assert result.max_portfolio_heat == Decimal("2.0")
        # Position size: 100 * 150 / 100000 * 100 = 15%
        assert result.max_position_size_pct == Decimal("15")

    def test_multiple_concurrent_positions(self, calculator):
        """Test with multiple concurrent positions."""
        snapshot1 = (
            datetime(2024, 1, 1),
            [
                make_position(symbol="AAPL", quantity=100, current_price=Decimal("150.00")),
                make_position(symbol="TSLA", quantity=50, current_price=Decimal("200.00")),
            ]
        )
        snapshot2 = (
            datetime(2024, 1, 2),
            [make_position(symbol="AAPL", quantity=100, current_price=Decimal("155.00"))]
        )

        result = calculator.calculate_risk_metrics([snapshot1, snapshot2], Decimal("100000"))

        assert result.max_concurrent_positions == 2
        assert result.avg_concurrent_positions == Decimal("1.5")  # (2 + 1) / 2
        # Max heat: 2 positions * 2% = 4%
        assert result.max_portfolio_heat == Decimal("4.0")


class TestCampaignPerformance:
    """Test calculate_campaign_performance method."""

    def test_empty_trades(self, calculator):
        """Test with empty trades list."""
        result = calculator.calculate_campaign_performance([])
        assert result == []

    def test_complete_accumulation_campaign(self, calculator):
        """Test detection of complete Accumulation campaign."""
        base_date = datetime(2024, 1, 1)
        patterns = ["PS", "SC", "AR", "SPRING", "SOS", "JUMP"]

        trades = [
            make_trade(
                symbol="AAPL",
                pattern=pattern,
                entry_date=base_date + timedelta(days=i * 7),
            )
            for i, pattern in enumerate(patterns)
        ]

        result = calculator.calculate_campaign_performance(trades)

        assert len(result) == 1
        campaign = result[0]
        assert campaign.symbol == "AAPL"
        assert campaign.campaign_type == "ACCUMULATION"
        assert campaign.status == "COMPLETED"
        assert campaign.patterns_traded == 6

    def test_failed_campaign(self, calculator):
        """Test detection of failed campaign."""
        trades = [
            make_trade(pattern="PS"),
            make_trade(pattern="SC"),
            make_trade(pattern="AR"),
            # Stops here - failed to reach Phase D
        ]

        result = calculator.calculate_campaign_performance(trades)

        assert len(result) == 1
        assert result[0].status == "FAILED"
        assert result[0].failure_reason == "PHASE_D_NOT_REACHED"


class TestTradeStreaks:
    """Test calculate_trade_streaks method."""

    def test_empty_trades(self, calculator):
        """Test with empty trades list."""
        result = calculator.calculate_trade_streaks([])
        assert result == (0, 0)

    def test_all_winners(self, calculator):
        """Test with all winning trades."""
        trades = [
            make_trade(pnl=Decimal("100.00")),
            make_trade(pnl=Decimal("200.00")),
            make_trade(pnl=Decimal("150.00")),
        ]

        result = calculator.calculate_trade_streaks(trades)
        assert result == (3, 0)  # 3 win streak, 0 lose streak

    def test_all_losers(self, calculator):
        """Test with all losing trades."""
        trades = [
            make_trade(pnl=Decimal("-100.00")),
            make_trade(pnl=Decimal("-50.00")),
        ]

        result = calculator.calculate_trade_streaks(trades)
        assert result == (0, 2)

    def test_mixed_streaks(self, calculator):
        """Test with mixed winning/losing streaks."""
        trades = [
            make_trade(exit_date=datetime(2024, 1, 1), pnl=Decimal("100.00")),  # Win
            make_trade(exit_date=datetime(2024, 1, 2), pnl=Decimal("200.00")),  # Win
            make_trade(exit_date=datetime(2024, 1, 3), pnl=Decimal("150.00")),  # Win
            make_trade(exit_date=datetime(2024, 1, 4), pnl=Decimal("-50.00")),  # Lose
            make_trade(exit_date=datetime(2024, 1, 5), pnl=Decimal("100.00")),  # Win
            make_trade(exit_date=datetime(2024, 1, 6), pnl=Decimal("-100.00")), # Lose
            make_trade(exit_date=datetime(2024, 1, 7), pnl=Decimal("-75.00")),  # Lose
        ]

        result = calculator.calculate_trade_streaks(trades)
        assert result == (3, 2)  # Longest win: 3, longest lose: 2

    def test_breakeven_counts_as_loss(self, calculator):
        """Test that breakeven (0 P&L) counts as losing streak."""
        trades = [
            make_trade(exit_date=datetime(2024, 1, 1), pnl=Decimal("100.00")),
            make_trade(exit_date=datetime(2024, 1, 2), pnl=Decimal("0.00")),  # Breakeven
            make_trade(exit_date=datetime(2024, 1, 3), pnl=Decimal("-50.00")),
        ]

        result = calculator.calculate_trade_streaks(trades)
        assert result == (1, 2)  # Breakeven counts as loss


class TestIdentifyExtremeTrades:
    """Test identify_extreme_trades method."""

    def test_empty_trades(self, calculator):
        """Test with empty trades list."""
        result = calculator.identify_extreme_trades([])
        assert result == (None, None)

    def test_single_trade(self, calculator):
        """Test with single trade."""
        trade = make_trade(pnl=Decimal("100.00"))
        result = calculator.identify_extreme_trades([trade])

        winner, loser = result
        assert winner == trade
        assert loser == trade  # Same trade is both best and worst

    def test_multiple_trades(self, calculator):
        """Test with multiple trades."""
        trades = [
            make_trade(pnl=Decimal("100.00")),
            make_trade(pnl=Decimal("500.00")),  # Largest winner
            make_trade(pnl=Decimal("-200.00")), # Largest loser
            make_trade(pnl=Decimal("150.00")),
        ]

        winner, loser = result = calculator.identify_extreme_trades(trades)

        assert winner.realized_pnl == Decimal("500.00")
        assert loser.realized_pnl == Decimal("-200.00")

    def test_all_winners(self, calculator):
        """Test with all winning trades."""
        trades = [
            make_trade(pnl=Decimal("100.00")),
            make_trade(pnl=Decimal("300.00")),
            make_trade(pnl=Decimal("200.00")),
        ]

        winner, loser = calculator.identify_extreme_trades(trades)

        assert winner.realized_pnl == Decimal("300.00")
        # Even though all profitable, smallest is the "loser"
        assert loser.realized_pnl == Decimal("100.00")
