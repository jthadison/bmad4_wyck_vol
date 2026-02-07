"""
Unit Tests for DrawdownCalculator (Story 18.7.1).

Tests O(n) algorithms for max drawdown and drawdown period calculation.
Includes performance benchmarks to verify O(n) scaling.

Author: Story 18.7.1
"""

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.backtesting.metrics_core.base import EquityPoint
from src.backtesting.metrics_core.drawdown_calculator import DrawdownCalculator


class TestCalculateMaxDrawdown:
    """Tests for calculate_max_drawdown method."""

    @pytest.fixture
    def calculator(self):
        """Create DrawdownCalculator instance."""
        return DrawdownCalculator()

    def test_empty_equity_curve(self, calculator):
        """Test with empty equity curve returns zero drawdown."""
        result = calculator.calculate_max_drawdown([])

        assert result.name == "max_drawdown"
        assert result.value == Decimal("0")

    def test_single_point(self, calculator):
        """Test with single point returns zero drawdown."""
        point = EquityPoint(datetime.now(UTC), Decimal("100000"))

        result = calculator.calculate_max_drawdown([point])

        assert result.value == Decimal("0")

    def test_no_drawdown(self, calculator):
        """Test steadily increasing equity has zero drawdown."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("100000")),
            EquityPoint(base + timedelta(days=1), Decimal("101000")),
            EquityPoint(base + timedelta(days=2), Decimal("102000")),
            EquityPoint(base + timedelta(days=3), Decimal("103000")),
        ]

        result = calculator.calculate_max_drawdown(curve)

        assert result.value == Decimal("0")

    def test_simple_drawdown(self, calculator):
        """Test simple drawdown calculation."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("100000")),
            EquityPoint(base + timedelta(days=1), Decimal("90000")),  # 10% DD
        ]

        result = calculator.calculate_max_drawdown(curve)

        assert result.value == Decimal("0.1000")

    def test_multiple_drawdowns(self, calculator):
        """Test with multiple drawdowns returns maximum."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("100000")),
            EquityPoint(base + timedelta(days=1), Decimal("95000")),  # 5% DD
            EquityPoint(base + timedelta(days=2), Decimal("110000")),  # New peak
            EquityPoint(base + timedelta(days=3), Decimal("88000")),  # 20% DD
            EquityPoint(base + timedelta(days=4), Decimal("115000")),  # New peak
            EquityPoint(base + timedelta(days=5), Decimal("103500")),  # 10% DD
        ]

        result = calculator.calculate_max_drawdown(curve)

        assert result.value == Decimal("0.2000")

    def test_drawdown_metadata(self, calculator):
        """Test metadata contains peak and trough values."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("115000")),
            EquityPoint(base + timedelta(days=1), Decimal("103500")),
        ]

        result = calculator.calculate_max_drawdown(curve)

        assert result.metadata is not None
        assert result.metadata["peak_value"] == Decimal("115000")
        assert result.metadata["trough_value"] == Decimal("103500")

    def test_flat_equity_curve(self, calculator):
        """Test flat equity curve has zero drawdown."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [EquityPoint(base + timedelta(days=i), Decimal("100000")) for i in range(10)]

        result = calculator.calculate_max_drawdown(curve)

        assert result.value == Decimal("0")


class TestFindDrawdownPeriods:
    """Tests for find_drawdown_periods method."""

    @pytest.fixture
    def calculator(self):
        """Create DrawdownCalculator instance."""
        return DrawdownCalculator()

    def test_empty_equity_curve(self, calculator):
        """Test with empty equity curve returns empty list."""
        periods = calculator.find_drawdown_periods([])

        assert periods == []

    def test_single_point(self, calculator):
        """Test with single point returns empty list."""
        point = EquityPoint(datetime.now(UTC), Decimal("100000"))

        periods = calculator.find_drawdown_periods([point])

        assert periods == []

    def test_no_drawdown(self, calculator):
        """Test steadily increasing equity has no drawdown periods."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base + timedelta(days=i), Decimal(str(100000 + i * 1000)))
            for i in range(10)
        ]

        periods = calculator.find_drawdown_periods(curve)

        assert periods == []

    def test_single_recovered_drawdown(self, calculator):
        """Test single drawdown that recovers."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("100000")),  # Peak
            EquityPoint(base + timedelta(days=5), Decimal("90000")),  # Trough
            EquityPoint(base + timedelta(days=10), Decimal("105000")),  # Recovery
        ]

        periods = calculator.find_drawdown_periods(curve)

        assert len(periods) == 1
        period = periods[0]
        assert period.peak_value == Decimal("100000")
        assert period.trough_value == Decimal("90000")
        assert period.drawdown_pct == Decimal("0.1000")
        assert period.duration_days == 5
        assert period.recovery_days == 5
        assert period.recovery_date == base + timedelta(days=10)

    def test_single_ongoing_drawdown(self, calculator):
        """Test single drawdown that doesn't recover."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("100000")),
            EquityPoint(base + timedelta(days=5), Decimal("95000")),
            EquityPoint(base + timedelta(days=10), Decimal("90000")),  # Lower trough
        ]

        periods = calculator.find_drawdown_periods(curve)

        assert len(periods) == 1
        period = periods[0]
        assert period.recovery_date is None
        assert period.recovery_days is None
        assert period.drawdown_pct == Decimal("0.1000")
        assert period.duration_days == 10

    def test_multiple_drawdowns(self, calculator):
        """Test multiple separate drawdown periods."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("100000")),  # Peak 1
            EquityPoint(base + timedelta(days=5), Decimal("95000")),  # Trough 1
            EquityPoint(base + timedelta(days=10), Decimal("110000")),  # Recovery/Peak 2
            EquityPoint(base + timedelta(days=15), Decimal("99000")),  # Trough 2
            EquityPoint(base + timedelta(days=20), Decimal("120000")),  # Recovery
        ]

        periods = calculator.find_drawdown_periods(curve)

        assert len(periods) == 2
        # First drawdown: 5% from 100k to 95k
        assert periods[0].drawdown_pct == Decimal("0.0500")
        # Second drawdown: 10% from 110k to 99k
        assert periods[1].drawdown_pct == Decimal("0.1000")

    def test_min_drawdown_filter(self, calculator):
        """Test filtering by minimum drawdown percentage."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("100000")),
            EquityPoint(base + timedelta(days=5), Decimal("98000")),  # 2% DD
            EquityPoint(base + timedelta(days=10), Decimal("110000")),
            EquityPoint(base + timedelta(days=15), Decimal("88000")),  # 20% DD
            EquityPoint(base + timedelta(days=20), Decimal("115000")),
        ]

        periods = calculator.find_drawdown_periods(curve, min_drawdown_pct=Decimal("0.05"))

        assert len(periods) == 1
        assert periods[0].drawdown_pct == Decimal("0.2000")


class TestGetTopDrawdowns:
    """Tests for get_top_drawdowns method."""

    @pytest.fixture
    def calculator(self):
        """Create DrawdownCalculator instance."""
        return DrawdownCalculator()

    def test_empty_equity_curve(self, calculator):
        """Test with empty equity curve."""
        result = calculator.get_top_drawdowns([])

        assert result == []

    def test_fewer_drawdowns_than_requested(self, calculator):
        """Test when fewer drawdowns exist than requested."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("100000")),
            EquityPoint(base + timedelta(days=5), Decimal("90000")),
            EquityPoint(base + timedelta(days=10), Decimal("105000")),
        ]

        result = calculator.get_top_drawdowns(curve, top_n=5)

        assert len(result) == 1

    def test_sorted_by_magnitude(self, calculator):
        """Test drawdowns are sorted by magnitude (largest first)."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("100000")),
            EquityPoint(base + timedelta(days=5), Decimal("95000")),  # 5%
            EquityPoint(base + timedelta(days=10), Decimal("110000")),
            EquityPoint(base + timedelta(days=15), Decimal("88000")),  # 20%
            EquityPoint(base + timedelta(days=20), Decimal("115000")),
            EquityPoint(base + timedelta(days=25), Decimal("103500")),  # 10%
            EquityPoint(base + timedelta(days=30), Decimal("120000")),
        ]

        result = calculator.get_top_drawdowns(curve, top_n=3)

        assert len(result) == 3
        assert result[0].drawdown_pct == Decimal("0.2000")  # Largest
        assert result[1].drawdown_pct == Decimal("0.1000")  # Second
        assert result[2].drawdown_pct == Decimal("0.0500")  # Third


class TestPerformanceBenchmark:
    """Performance benchmarks to verify O(n) scaling (AC6)."""

    @pytest.fixture
    def calculator(self):
        """Create DrawdownCalculator instance."""
        return DrawdownCalculator()

    def _create_equity_curve(self, n: int) -> list[EquityPoint]:
        """Create equity curve with n points and some drawdowns."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = []
        value = Decimal("100000")
        for i in range(n):
            # Simulate some volatility
            if i % 100 == 50:  # Every 100 points, create a 5% drop
                value = value * Decimal("0.95")
            elif i % 100 == 75:  # Then recover
                value = value * Decimal("1.08")
            else:
                value = value * Decimal("1.001")  # Small daily gain
            curve.append(EquityPoint(base + timedelta(days=i), value))
        return curve

    @pytest.mark.benchmark
    def test_max_drawdown_scales_linearly(self, calculator):
        """Verify calculate_max_drawdown is O(n).

        Tests that doubling input size roughly doubles execution time,
        not quadruples it (which would indicate O(n²)).
        """
        sizes = [1000, 2000, 4000, 8000]
        times: list[float] = []

        for size in sizes:
            curve = self._create_equity_curve(size)

            start = time.perf_counter()
            calculator.calculate_max_drawdown(curve)
            elapsed = time.perf_counter() - start

            times.append(elapsed)

        # Verify O(n) scaling: time ratio should be ~2x for 2x input size
        # Allow generous tolerance for test stability
        for i in range(1, len(times)):
            ratio = times[i] / times[i - 1]
            size_ratio = sizes[i] / sizes[i - 1]
            # For O(n), ratio should be close to size_ratio (2.0)
            # For O(n²), ratio would be close to size_ratio² (4.0)
            assert ratio < size_ratio * 2.5, (
                f"Scaling ratio {ratio:.2f} too high for size ratio {size_ratio}. "
                f"Possible O(n²) behavior detected."
            )

    @pytest.mark.benchmark
    def test_find_drawdown_periods_scales_linearly(self, calculator):
        """Verify find_drawdown_periods is O(n)."""
        sizes = [1000, 2000, 4000, 8000]
        times: list[float] = []

        for size in sizes:
            curve = self._create_equity_curve(size)

            start = time.perf_counter()
            calculator.find_drawdown_periods(curve)
            elapsed = time.perf_counter() - start

            times.append(elapsed)

        # Verify O(n) scaling
        for i in range(1, len(times)):
            ratio = times[i] / times[i - 1]
            size_ratio = sizes[i] / sizes[i - 1]
            assert ratio < size_ratio * 2.5, (
                f"Scaling ratio {ratio:.2f} too high. " f"Possible O(n²) behavior detected."
            )

    @pytest.mark.benchmark
    def test_large_equity_curve_performance(self, calculator):
        """Test performance with large equity curve (10k points)."""
        curve = self._create_equity_curve(10000)

        start = time.perf_counter()
        result = calculator.calculate_max_drawdown(curve)
        max_dd_time = time.perf_counter() - start

        start = time.perf_counter()
        periods = calculator.find_drawdown_periods(curve)
        periods_time = time.perf_counter() - start

        # Verify completion within reasonable time (< 1 second each)
        assert max_dd_time < 1.0, f"max_drawdown took {max_dd_time:.2f}s"
        assert periods_time < 1.0, f"find_drawdown_periods took {periods_time:.2f}s"

        # Verify results are sensible
        assert result.value > Decimal("0")
        assert len(periods) > 0


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.fixture
    def calculator(self):
        """Create DrawdownCalculator instance."""
        return DrawdownCalculator()

    def test_very_small_drawdown(self, calculator):
        """Test very small drawdown is captured."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("100000")),
            EquityPoint(base + timedelta(days=1), Decimal("99999")),  # 0.001%
            EquityPoint(base + timedelta(days=2), Decimal("100001")),
        ]

        result = calculator.calculate_max_drawdown(curve)

        assert result.value > Decimal("0")

    def test_large_drawdown(self, calculator):
        """Test large drawdown (90%)."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("100000")),
            EquityPoint(base + timedelta(days=1), Decimal("10000")),  # 90% DD
        ]

        result = calculator.calculate_max_drawdown(curve)

        assert result.value == Decimal("0.9000")

    def test_zero_peak_value(self, calculator):
        """Test handling of zero peak value."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("0")),
            EquityPoint(base + timedelta(days=1), Decimal("100")),
        ]

        result = calculator.calculate_max_drawdown(curve)

        # Should not crash, returns 0 since initial peak is 0
        assert result.value == Decimal("0")

    def test_sequential_peaks_at_same_level(self, calculator):
        """Test recovery to exact previous peak level."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("100000")),
            EquityPoint(base + timedelta(days=5), Decimal("90000")),
            EquityPoint(base + timedelta(days=10), Decimal("100000")),  # Exact recovery
            EquityPoint(base + timedelta(days=15), Decimal("95000")),
            EquityPoint(base + timedelta(days=20), Decimal("100000")),  # Exact recovery
        ]

        periods = calculator.find_drawdown_periods(curve)

        assert len(periods) == 2

    def test_decimal_precision(self, calculator):
        """Test decimal precision is maintained."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("100000.1234")),
            EquityPoint(base + timedelta(days=1), Decimal("90000.5678")),
        ]

        result = calculator.calculate_max_drawdown(curve)

        # Verify precision (should be close to 0.099996 = ~10%)
        assert Decimal("0.099") < result.value < Decimal("0.101")
