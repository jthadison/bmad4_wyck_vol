"""
Unit tests for TradeStatisticsCalculator (Story 18.7.3).

Tests:
- Win rate calculation
- Profit factor calculation
- Average R-multiple calculation
- Expectancy calculation
- Trade statistics aggregation

Author: Story 18.7.3
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

import pytest

from src.backtesting.metrics_core.trade_statistics import (
    TradeStatistics,
    TradeStatisticsCalculator,
)


@dataclass
class MockTrade:
    """Mock trade for testing."""

    realized_pnl: Decimal
    r_multiple: Optional[Decimal] = None


@pytest.fixture
def calculator():
    """Fixture for TradeStatisticsCalculator."""
    return TradeStatisticsCalculator()


class TestCalculateWinRate:
    """Test win rate calculation."""

    def test_win_rate_zero_trades(self, calculator):
        """Test win rate with zero trades."""
        assert calculator.calculate_win_rate(0, 0) == Decimal("0")

    def test_win_rate_60_percent(self, calculator):
        """Test 60% win rate."""
        assert calculator.calculate_win_rate(60, 100) == Decimal("0.6")

    def test_win_rate_100_percent(self, calculator):
        """Test 100% win rate."""
        assert calculator.calculate_win_rate(10, 10) == Decimal("1.0")

    def test_win_rate_zero_percent(self, calculator):
        """Test 0% win rate."""
        assert calculator.calculate_win_rate(0, 10) == Decimal("0")

    def test_win_rate_fractional(self, calculator):
        """Test win rate with fractional result."""
        result = calculator.calculate_win_rate(1, 3)
        expected = Decimal("1") / Decimal("3")
        assert result == expected


class TestCalculateProfitFactor:
    """Test profit factor calculation."""

    def test_profit_factor_empty_trades(self, calculator):
        """Test profit factor with no trades."""
        assert calculator.calculate_profit_factor([]) == Decimal("0")

    def test_profit_factor_no_losses(self, calculator):
        """Test profit factor with no losing trades (capped at 999.99)."""
        trades = [MockTrade(realized_pnl=Decimal("100"))]
        assert calculator.calculate_profit_factor(trades) == Decimal("999.99")

    def test_profit_factor_no_wins(self, calculator):
        """Test profit factor with no winning trades."""
        trades = [MockTrade(realized_pnl=Decimal("-100"))]
        assert calculator.calculate_profit_factor(trades) == Decimal("0")

    def test_profit_factor_2_to_1(self, calculator):
        """Test profit factor of 2.0."""
        trades = [
            MockTrade(realized_pnl=Decimal("200")),
            MockTrade(realized_pnl=Decimal("-100")),
        ]
        assert calculator.calculate_profit_factor(trades) == Decimal("2")

    def test_profit_factor_mixed_trades(self, calculator):
        """Test profit factor with multiple wins and losses."""
        trades = [
            MockTrade(realized_pnl=Decimal("500")),
            MockTrade(realized_pnl=Decimal("-200")),
            MockTrade(realized_pnl=Decimal("300")),
            MockTrade(realized_pnl=Decimal("-100")),
        ]
        # Gross profit: 800, Gross loss: 300
        # Profit factor: 800/300 = 2.666...
        result = calculator.calculate_profit_factor(trades)
        expected = Decimal("800") / Decimal("300")
        assert result == expected


class TestCalculateAvgRMultiple:
    """Test average R-multiple calculation."""

    def test_avg_r_multiple_empty_trades(self, calculator):
        """Test avg R-multiple with no trades."""
        assert calculator.calculate_avg_r_multiple([]) is None

    def test_avg_r_multiple_no_r_set(self, calculator):
        """Test avg R-multiple when no trades have r_multiple."""
        trades = [
            MockTrade(realized_pnl=Decimal("100"), r_multiple=None),
        ]
        assert calculator.calculate_avg_r_multiple(trades) is None

    def test_avg_r_multiple_single_trade(self, calculator):
        """Test avg R-multiple with single trade."""
        trades = [MockTrade(realized_pnl=Decimal("100"), r_multiple=Decimal("2.0"))]
        assert calculator.calculate_avg_r_multiple(trades) == Decimal("2.0")

    def test_avg_r_multiple_mixed(self, calculator):
        """Test avg R-multiple with mixed results."""
        trades = [
            MockTrade(realized_pnl=Decimal("200"), r_multiple=Decimal("2.0")),
            MockTrade(realized_pnl=Decimal("-100"), r_multiple=Decimal("-1.0")),
            MockTrade(realized_pnl=Decimal("300"), r_multiple=Decimal("3.0")),
        ]
        # Average: (2 - 1 + 3) / 3 = 4/3
        expected = Decimal("4") / Decimal("3")
        assert calculator.calculate_avg_r_multiple(trades) == expected

    def test_avg_r_multiple_ignores_none(self, calculator):
        """Test that trades without r_multiple are ignored."""
        trades = [
            MockTrade(realized_pnl=Decimal("200"), r_multiple=Decimal("2.0")),
            MockTrade(realized_pnl=Decimal("-100"), r_multiple=None),  # Ignored
            MockTrade(realized_pnl=Decimal("300"), r_multiple=Decimal("4.0")),
        ]
        # Average: (2 + 4) / 2 = 3
        assert calculator.calculate_avg_r_multiple(trades) == Decimal("3")


class TestCalculateExpectancy:
    """Test expectancy calculation."""

    def test_expectancy_empty_trades(self, calculator):
        """Test expectancy with no trades."""
        assert calculator.calculate_expectancy([]) is None

    def test_expectancy_no_r_multiple(self, calculator):
        """Test expectancy when no r_multiple set."""
        trades = [MockTrade(realized_pnl=Decimal("100"), r_multiple=None)]
        assert calculator.calculate_expectancy(trades) is None

    def test_expectancy_all_wins(self, calculator):
        """Test expectancy with all winning trades."""
        trades = [
            MockTrade(realized_pnl=Decimal("200"), r_multiple=Decimal("2.0")),
            MockTrade(realized_pnl=Decimal("300"), r_multiple=Decimal("3.0")),
        ]
        # Win rate: 100%, Avg win: 2.5R, Avg loss: 0
        # Expectancy: 1.0 * 2.5 - 0 * 0 = 2.5
        expected = Decimal("2.5")
        assert calculator.calculate_expectancy(trades) == expected

    def test_expectancy_all_losses(self, calculator):
        """Test expectancy with all losing trades."""
        trades = [
            MockTrade(realized_pnl=Decimal("-100"), r_multiple=Decimal("-1.0")),
            MockTrade(realized_pnl=Decimal("-200"), r_multiple=Decimal("-2.0")),
        ]
        # Win rate: 0%, Loss rate: 100%, Avg loss: 1.5R
        # Expectancy: 0 * 0 - 1.0 * 1.5 = -1.5
        expected = Decimal("-1.5")
        assert calculator.calculate_expectancy(trades) == expected

    def test_expectancy_mixed(self, calculator):
        """Test expectancy with mixed wins and losses."""
        trades = [
            MockTrade(realized_pnl=Decimal("200"), r_multiple=Decimal("2.0")),
            MockTrade(realized_pnl=Decimal("300"), r_multiple=Decimal("3.0")),
            MockTrade(realized_pnl=Decimal("-100"), r_multiple=Decimal("-1.0")),
        ]
        # Win rate: 2/3, Loss rate: 1/3
        # Avg win: (2+3)/2 = 2.5R, Avg loss: 1R
        # Expectancy: (2/3 * 2.5) - (1/3 * 1) = 5/3 - 1/3 = 4/3
        expected = Decimal("4") / Decimal("3")
        result = calculator.calculate_expectancy(trades)
        assert abs(result - expected) < Decimal("0.0001")


class TestCalculateStatistics:
    """Test comprehensive statistics calculation."""

    def test_statistics_empty_trades(self, calculator):
        """Test statistics with no trades."""
        stats = calculator.calculate_statistics([])

        assert isinstance(stats, TradeStatistics)
        assert stats.total_trades == 0
        assert stats.winning_trades == 0
        assert stats.losing_trades == 0
        assert stats.breakeven_trades == 0
        assert stats.win_rate == Decimal("0")
        assert stats.profit_factor == Decimal("0")
        assert stats.avg_r_multiple is None
        assert stats.expectancy is None
        assert stats.gross_profit == Decimal("0")
        assert stats.gross_loss == Decimal("0")
        assert stats.total_pnl == Decimal("0")

    def test_statistics_single_winning_trade(self, calculator):
        """Test statistics with single winning trade."""
        trades = [MockTrade(realized_pnl=Decimal("500"), r_multiple=Decimal("2.0"))]
        stats = calculator.calculate_statistics(trades)

        assert stats.total_trades == 1
        assert stats.winning_trades == 1
        assert stats.losing_trades == 0
        assert stats.breakeven_trades == 0
        assert stats.win_rate == Decimal("1.0")
        assert stats.profit_factor == Decimal("999.99")  # No losses, capped
        assert stats.avg_r_multiple == Decimal("2.0")
        assert stats.expectancy == Decimal("2.0")  # 100% win rate * 2R
        assert stats.gross_profit == Decimal("500")
        assert stats.gross_loss == Decimal("0")
        assert stats.total_pnl == Decimal("500")

    def test_statistics_mixed_trades(self, calculator):
        """Test statistics with mixed trades."""
        trades = [
            MockTrade(realized_pnl=Decimal("500"), r_multiple=Decimal("2.0")),
            MockTrade(realized_pnl=Decimal("-200"), r_multiple=Decimal("-1.0")),
            MockTrade(realized_pnl=Decimal("1000"), r_multiple=Decimal("3.0")),
            MockTrade(realized_pnl=Decimal("0"), r_multiple=Decimal("0")),  # Breakeven
        ]
        stats = calculator.calculate_statistics(trades)

        assert stats.total_trades == 4
        assert stats.winning_trades == 2
        assert stats.losing_trades == 1
        assert stats.breakeven_trades == 1
        assert stats.win_rate == Decimal("0.5")  # 2/4
        assert stats.gross_profit == Decimal("1500")
        assert stats.gross_loss == Decimal("200")
        assert stats.total_pnl == Decimal("1300")
        # Profit factor: 1500/200 = 7.5
        assert stats.profit_factor == Decimal("7.5")

    def test_statistics_all_losing_trades(self, calculator):
        """Test statistics with all losing trades."""
        trades = [
            MockTrade(realized_pnl=Decimal("-100"), r_multiple=Decimal("-0.5")),
            MockTrade(realized_pnl=Decimal("-200"), r_multiple=Decimal("-1.0")),
        ]
        stats = calculator.calculate_statistics(trades)

        assert stats.total_trades == 2
        assert stats.winning_trades == 0
        assert stats.losing_trades == 2
        assert stats.win_rate == Decimal("0")
        assert stats.profit_factor == Decimal("0")  # No profits
        assert stats.gross_profit == Decimal("0")
        assert stats.gross_loss == Decimal("300")
        assert stats.total_pnl == Decimal("-300")


class TestEdgeCases:
    """Test edge cases."""

    def test_very_small_pnl(self, calculator):
        """Test with very small P&L values."""
        trades = [
            MockTrade(realized_pnl=Decimal("0.0001"), r_multiple=Decimal("0.01")),
        ]
        stats = calculator.calculate_statistics(trades)

        assert stats.winning_trades == 1
        assert stats.gross_profit == Decimal("0.0001")

    def test_very_large_pnl(self, calculator):
        """Test with very large P&L values."""
        trades = [
            MockTrade(realized_pnl=Decimal("1000000000"), r_multiple=Decimal("100")),
            MockTrade(realized_pnl=Decimal("-500000000"), r_multiple=Decimal("-50")),
        ]
        stats = calculator.calculate_statistics(trades)

        assert stats.profit_factor == Decimal("2")

    def test_decimal_precision(self, calculator):
        """Test decimal precision is maintained."""
        trades = [
            MockTrade(realized_pnl=Decimal("333.33"), r_multiple=Decimal("1.111")),
            MockTrade(realized_pnl=Decimal("-111.11"), r_multiple=Decimal("-0.370")),
        ]
        stats = calculator.calculate_statistics(trades)

        # Verify we don't lose precision
        assert stats.gross_profit == Decimal("333.33")
        assert stats.gross_loss == Decimal("111.11")
