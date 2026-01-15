"""
Unit Tests for Metrics Base Models (Story 18.7.1).

Tests EquityPoint, DrawdownPeriod, and MetricResult dataclasses.

Author: Story 18.7.1
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.backtesting.metrics_core.base import DrawdownPeriod, EquityPoint, MetricResult


class TestEquityPoint:
    """Tests for EquityPoint dataclass."""

    def test_create_equity_point(self):
        """Test creating an EquityPoint."""
        ts = datetime.now(UTC)
        value = Decimal("100000.50")

        point = EquityPoint(timestamp=ts, value=value)

        assert point.timestamp == ts
        assert point.value == value

    def test_equity_point_immutable(self):
        """Test that EquityPoint is frozen (immutable)."""
        point = EquityPoint(timestamp=datetime.now(UTC), value=Decimal("100"))

        with pytest.raises(Exception):  # FrozenInstanceError
            point.value = Decimal("200")  # type: ignore[misc]

    def test_equity_point_equality(self):
        """Test EquityPoint equality comparison."""
        ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        point1 = EquityPoint(timestamp=ts, value=Decimal("100"))
        point2 = EquityPoint(timestamp=ts, value=Decimal("100"))

        assert point1 == point2

    def test_equity_point_different_values(self):
        """Test EquityPoint inequality."""
        ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        point1 = EquityPoint(timestamp=ts, value=Decimal("100"))
        point2 = EquityPoint(timestamp=ts, value=Decimal("200"))

        assert point1 != point2


class TestDrawdownPeriod:
    """Tests for DrawdownPeriod dataclass."""

    def test_create_complete_drawdown_period(self):
        """Test creating a complete (recovered) drawdown period."""
        peak_date = datetime(2024, 1, 1, tzinfo=UTC)
        trough_date = datetime(2024, 1, 15, tzinfo=UTC)
        recovery_date = datetime(2024, 2, 1, tzinfo=UTC)

        period = DrawdownPeriod(
            peak_date=peak_date,
            trough_date=trough_date,
            recovery_date=recovery_date,
            peak_value=Decimal("115000"),
            trough_value=Decimal("103500"),
            drawdown_pct=Decimal("10.0000"),
            duration_days=14,
            recovery_days=17,
        )

        assert period.peak_date == peak_date
        assert period.trough_date == trough_date
        assert period.recovery_date == recovery_date
        assert period.peak_value == Decimal("115000")
        assert period.trough_value == Decimal("103500")
        assert period.drawdown_pct == Decimal("10.0000")
        assert period.duration_days == 14
        assert period.recovery_days == 17

    def test_create_ongoing_drawdown_period(self):
        """Test creating an ongoing (not recovered) drawdown period."""
        peak_date = datetime(2024, 1, 1, tzinfo=UTC)
        trough_date = datetime(2024, 1, 15, tzinfo=UTC)

        period = DrawdownPeriod(
            peak_date=peak_date,
            trough_date=trough_date,
            peak_value=Decimal("100000"),
            trough_value=Decimal("90000"),
            drawdown_pct=Decimal("10.0000"),
            duration_days=14,
            recovery_date=None,
            recovery_days=None,
        )

        assert period.recovery_date is None
        assert period.recovery_days is None

    def test_drawdown_period_defaults(self):
        """Test DrawdownPeriod default values."""
        period = DrawdownPeriod(
            peak_date=datetime.now(UTC),
            trough_date=datetime.now(UTC),
            peak_value=Decimal("100"),
            trough_value=Decimal("90"),
            drawdown_pct=Decimal("10"),
            duration_days=5,
        )

        assert period.recovery_date is None
        assert period.recovery_days is None


class TestMetricResult:
    """Tests for MetricResult dataclass."""

    def test_create_metric_result_basic(self):
        """Test creating a basic MetricResult."""
        result = MetricResult(
            name="max_drawdown",
            value=Decimal("15.5"),
        )

        assert result.name == "max_drawdown"
        assert result.value == Decimal("15.5")
        assert result.metadata is None

    def test_create_metric_result_with_metadata(self):
        """Test creating a MetricResult with metadata."""
        metadata = {
            "peak_value": Decimal("115000"),
            "trough_value": Decimal("103500"),
        }

        result = MetricResult(
            name="max_drawdown",
            value=Decimal("10.0"),
            metadata=metadata,
        )

        assert result.metadata == metadata
        assert result.metadata["peak_value"] == Decimal("115000")

    def test_metric_result_empty_metadata(self):
        """Test MetricResult with empty metadata dict."""
        result = MetricResult(
            name="test_metric",
            value=Decimal("0"),
            metadata={},
        )

        assert result.metadata == {}
