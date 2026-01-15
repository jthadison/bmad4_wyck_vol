"""
Unit Tests for ReturnCalculator (Story 18.7.2).

Tests return calculations including total return, CAGR, and monthly/annual breakdowns.
Ensures Decimal precision is maintained throughout (AC6).

Author: Story 18.7.2
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.backtesting.metrics_core.base import EquityPoint
from src.backtesting.metrics_core.return_calculator import (
    AnnualReturn,
    MonthlyReturn,
    ReturnCalculator,
)


class TestCalculateTotalReturn:
    """Tests for calculate_total_return method."""

    @pytest.fixture
    def calculator(self) -> ReturnCalculator:
        """Create ReturnCalculator instance."""
        return ReturnCalculator()

    def test_empty_equity_curve(self, calculator: ReturnCalculator):
        """Test with empty equity curve."""
        result = calculator.calculate_total_return([])

        assert result.name == "total_return_pct"
        assert result.value == Decimal("0")
        assert "error" in result.metadata

    def test_single_point(self, calculator: ReturnCalculator):
        """Test with single equity point."""
        point = EquityPoint(datetime.now(UTC), Decimal("100000"))

        result = calculator.calculate_total_return([point])

        assert result.value == Decimal("0")

    def test_positive_return(self, calculator: ReturnCalculator):
        """Test positive total return calculation."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("100000")),
            EquityPoint(base + timedelta(days=365), Decimal("115000")),
        ]

        result = calculator.calculate_total_return(curve)

        assert result.value == Decimal("15.0000")
        assert result.metadata["initial_value"] == Decimal("100000")
        assert result.metadata["final_value"] == Decimal("115000")

    def test_negative_return(self, calculator: ReturnCalculator):
        """Test negative total return calculation."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("100000")),
            EquityPoint(base + timedelta(days=365), Decimal("85000")),
        ]

        result = calculator.calculate_total_return(curve)

        assert result.value == Decimal("-15.0000")

    def test_zero_initial_value(self, calculator: ReturnCalculator):
        """Test with zero initial value."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("0")),
            EquityPoint(base + timedelta(days=1), Decimal("100")),
        ]

        result = calculator.calculate_total_return(curve)

        assert result.value == Decimal("0")
        assert "error" in result.metadata


class TestCalculateCAGR:
    """Tests for calculate_cagr method (AC5)."""

    @pytest.fixture
    def calculator(self) -> ReturnCalculator:
        """Create ReturnCalculator instance."""
        return ReturnCalculator()

    def test_empty_equity_curve(self, calculator: ReturnCalculator):
        """Test with empty equity curve."""
        result = calculator.calculate_cagr([])

        assert result.name == "cagr"
        assert result.value == Decimal("0")

    def test_single_point(self, calculator: ReturnCalculator):
        """Test with single equity point."""
        point = EquityPoint(datetime.now(UTC), Decimal("100000"))

        result = calculator.calculate_cagr([point])

        assert result.value == Decimal("0")

    def test_one_year_return(self, calculator: ReturnCalculator):
        """Test CAGR over exactly one year."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("100000")),
            EquityPoint(base + timedelta(days=365), Decimal("120000")),
        ]

        result = calculator.calculate_cagr(curve)

        # 20% return over ~1 year = ~20% CAGR
        assert Decimal("0.19") < result.value < Decimal("0.21")

    def test_two_year_return(self, calculator: ReturnCalculator):
        """Test CAGR over two years."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("100000")),
            EquityPoint(base + timedelta(days=730), Decimal("121000")),  # 21% total
        ]

        result = calculator.calculate_cagr(curve)

        # 21% over 2 years = ~10% CAGR (sqrt(1.21) - 1)
        assert Decimal("0.09") < result.value < Decimal("0.11")

    def test_negative_cagr(self, calculator: ReturnCalculator):
        """Test negative CAGR."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("100000")),
            EquityPoint(base + timedelta(days=365), Decimal("80000")),
        ]

        result = calculator.calculate_cagr(curve)

        # -20% return over 1 year
        assert result.value < Decimal("0")
        assert result.value > Decimal("-0.25")

    def test_cagr_metadata(self, calculator: ReturnCalculator):
        """Test CAGR metadata contains expected values."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("100000")),
            EquityPoint(base + timedelta(days=365), Decimal("110000")),
        ]

        result = calculator.calculate_cagr(curve)

        assert "initial_value" in result.metadata
        assert "final_value" in result.metadata
        assert "years" in result.metadata
        assert result.metadata["years"] > Decimal("0.9")


class TestCalculateMonthlyReturns:
    """Tests for calculate_monthly_returns method (AC5)."""

    @pytest.fixture
    def calculator(self) -> ReturnCalculator:
        """Create ReturnCalculator instance."""
        return ReturnCalculator()

    def test_empty_equity_curve(self, calculator: ReturnCalculator):
        """Test with empty equity curve."""
        result = calculator.calculate_monthly_returns([])

        assert result == []

    def test_single_point(self, calculator: ReturnCalculator):
        """Test with single equity point."""
        point = EquityPoint(datetime.now(UTC), Decimal("100000"))

        result = calculator.calculate_monthly_returns([point])

        assert result == []

    def test_single_month(self, calculator: ReturnCalculator):
        """Test with data in single month."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("100000")),
            EquityPoint(base + timedelta(days=15), Decimal("105000")),
            EquityPoint(base + timedelta(days=30), Decimal("110000")),
        ]

        result = calculator.calculate_monthly_returns(curve)

        assert len(result) == 1
        assert result[0].year == 2024
        assert result[0].month == 1
        assert result[0].month_label == "Jan 2024"
        assert result[0].return_pct == Decimal("10.0000")

    def test_multiple_months(self, calculator: ReturnCalculator):
        """Test with data across multiple months."""
        curve = [
            EquityPoint(datetime(2024, 1, 1, tzinfo=UTC), Decimal("100000")),
            EquityPoint(datetime(2024, 1, 31, tzinfo=UTC), Decimal("105000")),  # Jan +5%
            EquityPoint(datetime(2024, 2, 1, tzinfo=UTC), Decimal("105000")),
            EquityPoint(datetime(2024, 2, 28, tzinfo=UTC), Decimal("102000")),  # Feb -2.86%
            EquityPoint(datetime(2024, 3, 1, tzinfo=UTC), Decimal("102000")),
            EquityPoint(datetime(2024, 3, 31, tzinfo=UTC), Decimal("112000")),  # Mar +9.8%
        ]

        result = calculator.calculate_monthly_returns(curve)

        assert len(result) == 3
        assert result[0].month_label == "Jan 2024"
        assert result[0].return_pct == Decimal("5.0000")
        assert result[1].month_label == "Feb 2024"
        assert result[1].return_pct < Decimal("0")  # Negative
        assert result[2].month_label == "Mar 2024"

    def test_monthly_return_dataclass(self, calculator: ReturnCalculator):
        """Test MonthlyReturn dataclass fields."""
        curve = [
            EquityPoint(datetime(2024, 6, 1, tzinfo=UTC), Decimal("100000")),
            EquityPoint(datetime(2024, 6, 30, tzinfo=UTC), Decimal("108000")),
        ]

        result = calculator.calculate_monthly_returns(curve)

        assert len(result) == 1
        monthly = result[0]
        assert isinstance(monthly, MonthlyReturn)
        assert monthly.year == 2024
        assert monthly.month == 6
        assert monthly.month_label == "Jun 2024"
        assert monthly.start_value == Decimal("100000")
        assert monthly.end_value == Decimal("108000")
        assert monthly.return_pct == Decimal("8.0000")


class TestCalculateAnnualReturns:
    """Tests for calculate_annual_returns method (AC5)."""

    @pytest.fixture
    def calculator(self) -> ReturnCalculator:
        """Create ReturnCalculator instance."""
        return ReturnCalculator()

    def test_empty_equity_curve(self, calculator: ReturnCalculator):
        """Test with empty equity curve."""
        result = calculator.calculate_annual_returns([])

        assert result == []

    def test_single_point(self, calculator: ReturnCalculator):
        """Test with single equity point."""
        point = EquityPoint(datetime.now(UTC), Decimal("100000"))

        result = calculator.calculate_annual_returns([point])

        assert result == []

    def test_single_year(self, calculator: ReturnCalculator):
        """Test with data in single year."""
        curve = [
            EquityPoint(datetime(2024, 1, 1, tzinfo=UTC), Decimal("100000")),
            EquityPoint(datetime(2024, 6, 1, tzinfo=UTC), Decimal("110000")),
            EquityPoint(datetime(2024, 12, 31, tzinfo=UTC), Decimal("120000")),
        ]

        result = calculator.calculate_annual_returns(curve)

        assert len(result) == 1
        assert result[0].year == 2024
        assert result[0].return_pct == Decimal("20.0000")
        assert result[0].months_traded == 3  # Jan, Jun, Dec

    def test_multiple_years(self, calculator: ReturnCalculator):
        """Test with data across multiple years."""
        curve = [
            EquityPoint(datetime(2023, 1, 1, tzinfo=UTC), Decimal("100000")),
            EquityPoint(datetime(2023, 12, 31, tzinfo=UTC), Decimal("110000")),  # 2023: +10%
            EquityPoint(datetime(2024, 1, 1, tzinfo=UTC), Decimal("110000")),
            EquityPoint(datetime(2024, 12, 31, tzinfo=UTC), Decimal("132000")),  # 2024: +20%
        ]

        result = calculator.calculate_annual_returns(curve)

        assert len(result) == 2
        assert result[0].year == 2023
        assert result[0].return_pct == Decimal("10.0000")
        assert result[1].year == 2024
        assert result[1].return_pct == Decimal("20.0000")

    def test_annual_return_dataclass(self, calculator: ReturnCalculator):
        """Test AnnualReturn dataclass fields."""
        curve = [
            EquityPoint(datetime(2024, 1, 1, tzinfo=UTC), Decimal("100000")),
            EquityPoint(datetime(2024, 3, 1, tzinfo=UTC), Decimal("105000")),
            EquityPoint(datetime(2024, 6, 1, tzinfo=UTC), Decimal("110000")),
            EquityPoint(datetime(2024, 12, 31, tzinfo=UTC), Decimal("115000")),
        ]

        result = calculator.calculate_annual_returns(curve)

        assert len(result) == 1
        annual = result[0]
        assert isinstance(annual, AnnualReturn)
        assert annual.year == 2024
        assert annual.start_value == Decimal("100000")
        assert annual.end_value == Decimal("115000")
        assert annual.return_pct == Decimal("15.0000")
        assert annual.months_traded == 4  # Jan, Mar, Jun, Dec


class TestCalculatePeriodReturn:
    """Tests for calculate_period_return utility method."""

    @pytest.fixture
    def calculator(self) -> ReturnCalculator:
        """Create ReturnCalculator instance."""
        return ReturnCalculator()

    def test_positive_return(self, calculator: ReturnCalculator):
        """Test positive period return."""
        result = calculator.calculate_period_return(Decimal("100"), Decimal("115"))

        assert result == Decimal("15")

    def test_negative_return(self, calculator: ReturnCalculator):
        """Test negative period return."""
        result = calculator.calculate_period_return(Decimal("100"), Decimal("85"))

        assert result == Decimal("-15")

    def test_zero_return(self, calculator: ReturnCalculator):
        """Test zero return."""
        result = calculator.calculate_period_return(Decimal("100"), Decimal("100"))

        assert result == Decimal("0")

    def test_zero_start_value(self, calculator: ReturnCalculator):
        """Test with zero start value."""
        result = calculator.calculate_period_return(Decimal("0"), Decimal("100"))

        assert result == Decimal("0")


class TestCalculateCumulativeReturns:
    """Tests for calculate_cumulative_returns method."""

    @pytest.fixture
    def calculator(self) -> ReturnCalculator:
        """Create ReturnCalculator instance."""
        return ReturnCalculator()

    def test_empty_equity_curve(self, calculator: ReturnCalculator):
        """Test with empty equity curve."""
        result = calculator.calculate_cumulative_returns([])

        assert result == []

    def test_cumulative_progression(self, calculator: ReturnCalculator):
        """Test cumulative return progression."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("100000")),
            EquityPoint(base + timedelta(days=1), Decimal("105000")),  # +5%
            EquityPoint(base + timedelta(days=2), Decimal("110000")),  # +10%
            EquityPoint(base + timedelta(days=3), Decimal("100000")),  # 0%
        ]

        result = calculator.calculate_cumulative_returns(curve)

        assert len(result) == 4
        assert result[0][1] == Decimal("0.0000")  # Start at 0%
        assert result[1][1] == Decimal("5.0000")  # +5%
        assert result[2][1] == Decimal("10.0000")  # +10%
        assert result[3][1] == Decimal("0.0000")  # Back to 0%


class TestDecimalPrecision:
    """Tests for Decimal precision handling (AC6)."""

    @pytest.fixture
    def calculator(self) -> ReturnCalculator:
        """Create ReturnCalculator instance."""
        return ReturnCalculator()

    def test_high_precision_input(self, calculator: ReturnCalculator):
        """Test handling of high-precision Decimal inputs."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("100000.123456789")),
            EquityPoint(base + timedelta(days=365), Decimal("115000.987654321")),
        ]

        result = calculator.calculate_total_return(curve)

        # Should produce quantized result without crashing
        assert "." in str(result.value)

    def test_very_small_values(self, calculator: ReturnCalculator):
        """Test with very small equity values."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("0.0001")),
            EquityPoint(base + timedelta(days=365), Decimal("0.00012")),
        ]

        result = calculator.calculate_total_return(curve)

        assert result.value == Decimal("20.0000")

    def test_very_large_values(self, calculator: ReturnCalculator):
        """Test with very large equity values."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("1000000000")),  # 1 billion
            EquityPoint(base + timedelta(days=365), Decimal("1200000000")),
        ]

        result = calculator.calculate_total_return(curve)

        assert result.value == Decimal("20.0000")


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.fixture
    def calculator(self) -> ReturnCalculator:
        """Create ReturnCalculator instance."""
        return ReturnCalculator()

    def test_same_day_equity_points(self, calculator: ReturnCalculator):
        """Test with multiple equity points on same day."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("100000")),
            EquityPoint(base, Decimal("105000")),  # Same day
        ]

        result = calculator.calculate_cagr(curve)

        # Zero days = zero CAGR
        assert result.value == Decimal("0")

    def test_month_with_single_point(self, calculator: ReturnCalculator):
        """Test monthly returns skips months with single point."""
        curve = [
            EquityPoint(datetime(2024, 1, 15, tzinfo=UTC), Decimal("100000")),  # Single Jan point
            EquityPoint(datetime(2024, 2, 1, tzinfo=UTC), Decimal("105000")),
            EquityPoint(datetime(2024, 2, 28, tzinfo=UTC), Decimal("110000")),
        ]

        result = calculator.calculate_monthly_returns(curve)

        # January should be skipped (only 1 point)
        assert len(result) == 1
        assert result[0].month == 2

    def test_leap_year_handling(self, calculator: ReturnCalculator):
        """Test CAGR handles leap years correctly."""
        curve = [
            EquityPoint(datetime(2024, 1, 1, tzinfo=UTC), Decimal("100000")),  # 2024 is leap year
            EquityPoint(datetime(2025, 1, 1, tzinfo=UTC), Decimal("120000")),  # 366 days later
        ]

        result = calculator.calculate_cagr(curve)

        # Should be close to 20% (slightly more than 1 year)
        assert Decimal("0.19") < result.value < Decimal("0.21")
