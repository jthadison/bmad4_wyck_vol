"""
Unit tests for EquityAnalyzer (Story 18.7.3).

Tests:
- Equity metrics calculation
- Monthly returns calculation
- Equity curve validation

Author: Story 18.7.3
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.backtesting.metrics_core.base import EquityPoint
from src.backtesting.metrics_core.equity_analyzer import (
    EquityAnalyzer,
    EquityMetrics,
    MonthlyEquityReturn,
)


@pytest.fixture
def analyzer():
    """Fixture for EquityAnalyzer."""
    return EquityAnalyzer()


class TestCalculateEquityMetrics:
    """Test equity metrics calculation."""

    def test_empty_equity_curve(self, analyzer):
        """Test with empty equity curve."""
        metrics = analyzer.calculate_equity_metrics([])

        assert isinstance(metrics, EquityMetrics)
        assert metrics.start_date is None
        assert metrics.end_date is None
        assert metrics.start_value == Decimal("0")
        assert metrics.end_value == Decimal("0")
        assert metrics.total_return_pct == Decimal("0")
        assert metrics.total_days == 0
        assert metrics.trading_days == 0

    def test_single_point(self, analyzer):
        """Test with single equity point."""
        points = [EquityPoint(timestamp=datetime(2024, 1, 1, tzinfo=UTC), value=Decimal("100000"))]
        metrics = analyzer.calculate_equity_metrics(points)

        assert metrics.start_value == Decimal("100000")
        assert metrics.end_value == Decimal("100000")
        assert metrics.total_return_pct == Decimal("0")
        assert metrics.trading_days == 1

    def test_positive_return(self, analyzer):
        """Test with positive return."""
        points = [
            EquityPoint(timestamp=datetime(2024, 1, 1, tzinfo=UTC), value=Decimal("100000")),
            EquityPoint(timestamp=datetime(2024, 6, 1, tzinfo=UTC), value=Decimal("125000")),
        ]
        metrics = analyzer.calculate_equity_metrics(points)

        assert metrics.start_value == Decimal("100000")
        assert metrics.end_value == Decimal("125000")
        assert metrics.total_return_pct == Decimal("25.0000")  # 25%

    def test_negative_return(self, analyzer):
        """Test with negative return."""
        points = [
            EquityPoint(timestamp=datetime(2024, 1, 1, tzinfo=UTC), value=Decimal("100000")),
            EquityPoint(timestamp=datetime(2024, 6, 1, tzinfo=UTC), value=Decimal("80000")),
        ]
        metrics = analyzer.calculate_equity_metrics(points)

        assert metrics.total_return_pct == Decimal("-20.0000")  # -20%

    def test_total_days_calculation(self, analyzer):
        """Test total days between start and end."""
        points = [
            EquityPoint(timestamp=datetime(2024, 1, 1, tzinfo=UTC), value=Decimal("100000")),
            EquityPoint(timestamp=datetime(2024, 1, 31, tzinfo=UTC), value=Decimal("105000")),
        ]
        metrics = analyzer.calculate_equity_metrics(points)

        assert metrics.total_days == 30
        assert metrics.trading_days == 2


class TestCalculateMonthlyReturns:
    """Test monthly returns calculation."""

    def test_empty_equity_curve(self, analyzer):
        """Test with empty equity curve."""
        returns = analyzer.calculate_monthly_returns([])
        assert returns == []

    def test_single_point(self, analyzer):
        """Test with single point (insufficient data)."""
        points = [EquityPoint(timestamp=datetime(2024, 1, 1, tzinfo=UTC), value=Decimal("100000"))]
        returns = analyzer.calculate_monthly_returns(points)
        assert returns == []  # Need at least 2 points per month

    def test_single_month_return(self, analyzer):
        """Test monthly return for single month."""
        points = [
            EquityPoint(timestamp=datetime(2024, 1, 1, tzinfo=UTC), value=Decimal("100000")),
            EquityPoint(timestamp=datetime(2024, 1, 15, tzinfo=UTC), value=Decimal("102500")),
            EquityPoint(timestamp=datetime(2024, 1, 31, tzinfo=UTC), value=Decimal("105000")),
        ]
        returns = analyzer.calculate_monthly_returns(points)

        assert len(returns) == 1
        assert isinstance(returns[0], MonthlyEquityReturn)
        assert returns[0].year == 2024
        assert returns[0].month == 1
        assert returns[0].month_label == "Jan 2024"
        assert returns[0].start_equity == Decimal("100000")
        assert returns[0].end_equity == Decimal("105000")
        assert returns[0].return_pct == Decimal("5.0000")

    def test_multiple_months(self, analyzer):
        """Test monthly returns across multiple months."""
        points = [
            # January
            EquityPoint(timestamp=datetime(2024, 1, 1, tzinfo=UTC), value=Decimal("100000")),
            EquityPoint(timestamp=datetime(2024, 1, 31, tzinfo=UTC), value=Decimal("105000")),
            # February
            EquityPoint(timestamp=datetime(2024, 2, 1, tzinfo=UTC), value=Decimal("105000")),
            EquityPoint(timestamp=datetime(2024, 2, 29, tzinfo=UTC), value=Decimal("110000")),
            # March
            EquityPoint(timestamp=datetime(2024, 3, 1, tzinfo=UTC), value=Decimal("110000")),
            EquityPoint(timestamp=datetime(2024, 3, 31, tzinfo=UTC), value=Decimal("100000")),
        ]
        returns = analyzer.calculate_monthly_returns(points)

        assert len(returns) == 3

        # January: +5%
        assert returns[0].month == 1
        assert returns[0].return_pct == Decimal("5.0000")

        # February: ~4.76% (105k -> 110k)
        assert returns[1].month == 2
        assert abs(returns[1].return_pct - Decimal("4.7619")) < Decimal("0.0001")

        # March: ~-9.09% (110k -> 100k)
        assert returns[2].month == 3
        assert returns[2].return_pct < Decimal("0")

    def test_negative_monthly_return(self, analyzer):
        """Test month with negative return."""
        points = [
            EquityPoint(timestamp=datetime(2024, 1, 1, tzinfo=UTC), value=Decimal("100000")),
            EquityPoint(timestamp=datetime(2024, 1, 31, tzinfo=UTC), value=Decimal("90000")),
        ]
        returns = analyzer.calculate_monthly_returns(points)

        assert returns[0].return_pct == Decimal("-10.0000")

    def test_monthly_returns_sorted_by_date(self, analyzer):
        """Test that monthly returns are sorted chronologically."""
        # Unsorted input
        points = [
            EquityPoint(timestamp=datetime(2024, 3, 1, tzinfo=UTC), value=Decimal("110000")),
            EquityPoint(timestamp=datetime(2024, 1, 1, tzinfo=UTC), value=Decimal("100000")),
            EquityPoint(timestamp=datetime(2024, 3, 31, tzinfo=UTC), value=Decimal("115000")),
            EquityPoint(timestamp=datetime(2024, 1, 31, tzinfo=UTC), value=Decimal("105000")),
        ]
        returns = analyzer.calculate_monthly_returns(points)

        # Should be sorted by year-month
        assert len(returns) == 2
        assert returns[0].month == 1
        assert returns[1].month == 3


class TestValidateEquityCurve:
    """Test equity curve validation."""

    def test_empty_curve(self, analyzer):
        """Test validation of empty curve."""
        is_valid, messages = analyzer.validate_equity_curve([])

        assert is_valid is False
        assert "Empty equity curve" in messages

    def test_insufficient_data(self, analyzer):
        """Test validation with insufficient data."""
        points = [EquityPoint(timestamp=datetime(2024, 1, 1, tzinfo=UTC), value=Decimal("100000"))]
        is_valid, messages = analyzer.validate_equity_curve(points)

        assert is_valid is False
        assert any("Insufficient data" in msg for msg in messages)

    def test_valid_curve(self, analyzer):
        """Test validation of valid curve."""
        points = [
            EquityPoint(timestamp=datetime(2024, 1, 1, tzinfo=UTC), value=Decimal("100000")),
            EquityPoint(timestamp=datetime(2024, 1, 2, tzinfo=UTC), value=Decimal("101000")),
        ]
        is_valid, messages = analyzer.validate_equity_curve(points)

        assert is_valid is True
        assert messages == []

    def test_non_chronological(self, analyzer):
        """Test detection of non-chronological timestamps."""
        points = [
            EquityPoint(timestamp=datetime(2024, 1, 5, tzinfo=UTC), value=Decimal("100000")),
            EquityPoint(
                timestamp=datetime(2024, 1, 1, tzinfo=UTC), value=Decimal("101000")
            ),  # Before prev
        ]
        is_valid, messages = analyzer.validate_equity_curve(points)

        assert is_valid is False
        assert any("Non-chronological" in msg for msg in messages)

    def test_negative_value(self, analyzer):
        """Test detection of negative equity values."""
        points = [
            EquityPoint(timestamp=datetime(2024, 1, 1, tzinfo=UTC), value=Decimal("100000")),
            EquityPoint(timestamp=datetime(2024, 1, 2, tzinfo=UTC), value=Decimal("-1000")),
        ]
        is_valid, messages = analyzer.validate_equity_curve(points)

        assert is_valid is False
        assert any("Negative equity" in msg for msg in messages)


class TestEdgeCases:
    """Test edge cases."""

    def test_zero_initial_value(self, analyzer):
        """Test with zero initial value."""
        points = [
            EquityPoint(timestamp=datetime(2024, 1, 1, tzinfo=UTC), value=Decimal("0")),
            EquityPoint(timestamp=datetime(2024, 1, 31, tzinfo=UTC), value=Decimal("100000")),
        ]
        metrics = analyzer.calculate_equity_metrics(points)

        # Should handle zero initial without division error
        assert metrics.total_return_pct == Decimal("0")

    def test_same_start_end_date(self, analyzer):
        """Test with same start and end dates."""
        points = [
            EquityPoint(timestamp=datetime(2024, 1, 1, tzinfo=UTC), value=Decimal("100000")),
            EquityPoint(timestamp=datetime(2024, 1, 1, tzinfo=UTC), value=Decimal("105000")),
        ]
        metrics = analyzer.calculate_equity_metrics(points)

        assert metrics.total_days == 0
        assert metrics.total_return_pct == Decimal("5.0000")

    def test_decimal_precision(self, analyzer):
        """Test decimal precision is maintained."""
        points = [
            EquityPoint(timestamp=datetime(2024, 1, 1, tzinfo=UTC), value=Decimal("100000.123456")),
            EquityPoint(
                timestamp=datetime(2024, 1, 31, tzinfo=UTC), value=Decimal("105000.654321")
            ),
        ]
        metrics = analyzer.calculate_equity_metrics(points)

        # Should maintain precision
        assert metrics.start_value == Decimal("100000.123456")
        assert metrics.end_value == Decimal("105000.654321")
