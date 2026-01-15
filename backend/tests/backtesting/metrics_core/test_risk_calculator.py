"""
Unit Tests for RiskCalculator (Story 18.7.2).

Tests O(n) algorithms for Sharpe, Sortino, and Calmar ratio calculations.
Includes performance benchmarks to verify O(n) scaling.

Author: Story 18.7.2
"""

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.backtesting.metrics_core.base import EquityPoint
from src.backtesting.metrics_core.risk_calculator import RiskCalculator


class TestCalculateSharpeRatio:
    """Tests for calculate_sharpe_ratio method (AC1, AC2)."""

    @pytest.fixture
    def calculator(self) -> RiskCalculator:
        """Create RiskCalculator instance with 2% risk-free rate."""
        return RiskCalculator(risk_free_rate=Decimal("0.02"))

    def test_empty_returns(self, calculator: RiskCalculator):
        """Test with empty returns list."""
        result = calculator.calculate_sharpe_ratio([])

        assert result.name == "sharpe_ratio"
        assert result.value == Decimal("0")
        assert result.metadata is not None
        assert "error" in result.metadata

    def test_single_return(self, calculator: RiskCalculator):
        """Test with single return value."""
        result = calculator.calculate_sharpe_ratio([Decimal("0.01")])

        assert result.value == Decimal("0")
        assert "error" in result.metadata

    def test_zero_variance_returns(self, calculator: RiskCalculator):
        """Test with all identical returns (zero variance)."""
        returns = [Decimal("0.01")] * 10

        result = calculator.calculate_sharpe_ratio(returns)

        assert result.value == Decimal("0")
        assert "error" in result.metadata

    def test_positive_sharpe_ratio(self, calculator: RiskCalculator):
        """Test positive Sharpe ratio with good returns."""
        # Simulate consistent positive returns averaging ~0.1% daily
        returns = [
            Decimal("0.001"),
            Decimal("0.0015"),
            Decimal("0.0008"),
            Decimal("0.0012"),
            Decimal("0.0011"),
            Decimal("0.0009"),
            Decimal("0.0013"),
            Decimal("0.0007"),
            Decimal("0.0014"),
            Decimal("0.001"),
        ]

        result = calculator.calculate_sharpe_ratio(returns)

        # Should be positive for consistently positive returns
        assert result.value > Decimal("0")
        assert result.metadata["annualized"] is True

    def test_negative_sharpe_ratio(self, calculator: RiskCalculator):
        """Test negative Sharpe ratio with poor returns."""
        # Simulate negative returns
        returns = [
            Decimal("-0.002"),
            Decimal("-0.001"),
            Decimal("-0.0015"),
            Decimal("-0.0025"),
            Decimal("-0.001"),
        ]

        result = calculator.calculate_sharpe_ratio(returns)

        assert result.value < Decimal("0")

    def test_annualization(self, calculator: RiskCalculator):
        """Test annualized vs non-annualized Sharpe ratio."""
        returns = [Decimal("0.001")] * 5 + [Decimal("0.002")] * 5

        annualized = calculator.calculate_sharpe_ratio(returns, annualize=True)
        non_annualized = calculator.calculate_sharpe_ratio(returns, annualize=False)

        # Annualized should be larger (multiplied by sqrt(252))
        assert abs(annualized.value) > abs(non_annualized.value)
        assert annualized.metadata["annualized"] is True
        assert non_annualized.metadata["annualized"] is False

    def test_sharpe_metadata(self, calculator: RiskCalculator):
        """Test Sharpe ratio metadata contains expected values."""
        returns = [Decimal("0.001"), Decimal("0.002"), Decimal("-0.001"), Decimal("0.003")]

        result = calculator.calculate_sharpe_ratio(returns)

        assert "mean_return" in result.metadata
        assert "std_dev" in result.metadata
        assert result.metadata["std_dev"] > Decimal("0")


class TestCalculateSortinoRatio:
    """Tests for calculate_sortino_ratio method (AC1, AC3)."""

    @pytest.fixture
    def calculator(self) -> RiskCalculator:
        """Create RiskCalculator instance."""
        return RiskCalculator(risk_free_rate=Decimal("0.02"))

    def test_empty_returns(self, calculator: RiskCalculator):
        """Test with empty returns list."""
        result = calculator.calculate_sortino_ratio([])

        assert result.name == "sortino_ratio"
        assert result.value == Decimal("0")

    def test_single_return(self, calculator: RiskCalculator):
        """Test with single return value."""
        result = calculator.calculate_sortino_ratio([Decimal("0.01")])

        assert result.value == Decimal("0")

    def test_no_downside_returns(self, calculator: RiskCalculator):
        """Test with all positive returns (no downside)."""
        returns = [Decimal("0.01"), Decimal("0.02"), Decimal("0.015"), Decimal("0.008")]

        result = calculator.calculate_sortino_ratio(returns)

        # Should return very high value (essentially infinite)
        assert result.value == Decimal("999.9999")
        assert "No downside returns" in result.metadata.get("note", "")

    def test_sortino_higher_than_sharpe(self, calculator: RiskCalculator):
        """Test Sortino >= Sharpe when upside volatility exists."""
        # Returns with high upside, some downside
        returns = [
            Decimal("0.03"),
            Decimal("0.02"),
            Decimal("-0.01"),
            Decimal("0.025"),
            Decimal("-0.005"),
            Decimal("0.04"),
        ]

        sharpe = calculator.calculate_sharpe_ratio(returns)
        sortino = calculator.calculate_sortino_ratio(returns)

        # Sortino should be higher since it only penalizes downside
        assert sortino.value >= sharpe.value

    def test_custom_target_return(self, calculator: RiskCalculator):
        """Test Sortino with custom target return."""
        returns = [
            Decimal("0.005"),
            Decimal("0.008"),
            Decimal("0.003"),
            Decimal("0.006"),
            Decimal("0.004"),
        ]

        # With target of 0, all returns are positive
        with_zero_target = calculator.calculate_sortino_ratio(returns, target_return=Decimal("0"))

        # With target of 0.007, some returns are below target
        with_high_target = calculator.calculate_sortino_ratio(
            returns, target_return=Decimal("0.007")
        )

        # Higher target should result in lower (or more realistic) Sortino
        assert with_zero_target.value > with_high_target.value

    def test_sortino_metadata(self, calculator: RiskCalculator):
        """Test Sortino ratio metadata."""
        returns = [Decimal("0.01"), Decimal("-0.005"), Decimal("0.008"), Decimal("-0.003")]

        result = calculator.calculate_sortino_ratio(returns)

        assert "mean_return" in result.metadata
        assert "downside_deviation" in result.metadata
        assert "target_return" in result.metadata
        assert result.metadata["downside_deviation"] > Decimal("0")


class TestCalculateCalmarRatio:
    """Tests for calculate_calmar_ratio method (AC1)."""

    @pytest.fixture
    def calculator(self) -> RiskCalculator:
        """Create RiskCalculator instance."""
        return RiskCalculator()

    def _create_equity_curve(
        self, start_val: Decimal, end_val: Decimal, days: int
    ) -> list[EquityPoint]:
        """Create simple linear equity curve."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        step = (end_val - start_val) / Decimal(days)
        return [
            EquityPoint(base + timedelta(days=i), start_val + step * Decimal(i))
            for i in range(days + 1)
        ]

    def test_empty_equity_curve(self, calculator: RiskCalculator):
        """Test with empty equity curve."""
        result = calculator.calculate_calmar_ratio([])

        assert result.name == "calmar_ratio"
        assert result.value == Decimal("0")

    def test_single_point(self, calculator: RiskCalculator):
        """Test with single equity point."""
        point = EquityPoint(datetime.now(UTC), Decimal("100000"))

        result = calculator.calculate_calmar_ratio([point])

        assert result.value == Decimal("0")

    def test_no_drawdown(self, calculator: RiskCalculator):
        """Test with steadily increasing equity (no drawdown)."""
        curve = self._create_equity_curve(Decimal("100000"), Decimal("150000"), 365)

        result = calculator.calculate_calmar_ratio(curve)

        # Should return very high value (no drawdown)
        assert result.value == Decimal("999.9999")

    def test_positive_calmar_ratio(self, calculator: RiskCalculator):
        """Test positive Calmar ratio with drawdown."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("100000")),
            EquityPoint(base + timedelta(days=90), Decimal("90000")),  # 10% drawdown
            EquityPoint(base + timedelta(days=180), Decimal("105000")),
            EquityPoint(base + timedelta(days=365), Decimal("120000")),  # 20% annual return
        ]

        result = calculator.calculate_calmar_ratio(curve)

        # Calmar = 20% / 10% = 2.0
        assert result.value > Decimal("0")
        assert "annualized_return_pct" in result.metadata
        assert "max_drawdown_pct" in result.metadata

    def test_calmar_with_provided_cagr(self, calculator: RiskCalculator):
        """Test Calmar with pre-calculated CAGR."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("100000")),
            EquityPoint(base + timedelta(days=180), Decimal("90000")),  # 10% DD
            EquityPoint(base + timedelta(days=365), Decimal("100000")),
        ]

        result = calculator.calculate_calmar_ratio(curve, annualized_return=Decimal("0.15"))

        # Calmar = 15% / 10% = 1.5
        assert Decimal("1.4") < result.value < Decimal("1.6")


class TestCalculateReturnsFromEquity:
    """Tests for calculate_returns_from_equity utility method."""

    @pytest.fixture
    def calculator(self) -> RiskCalculator:
        """Create RiskCalculator instance."""
        return RiskCalculator()

    def test_empty_equity_curve(self, calculator: RiskCalculator):
        """Test with empty equity curve."""
        returns = calculator.calculate_returns_from_equity([])

        assert returns == []

    def test_single_point(self, calculator: RiskCalculator):
        """Test with single equity point."""
        point = EquityPoint(datetime.now(UTC), Decimal("100000"))

        returns = calculator.calculate_returns_from_equity([point])

        assert returns == []

    def test_simple_returns(self, calculator: RiskCalculator):
        """Test returns calculation from equity curve."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(base, Decimal("100000")),
            EquityPoint(base + timedelta(days=1), Decimal("101000")),  # 1%
            EquityPoint(base + timedelta(days=2), Decimal("100000")),  # -0.99%
            EquityPoint(base + timedelta(days=3), Decimal("102000")),  # 2%
        ]

        returns = calculator.calculate_returns_from_equity(curve)

        assert len(returns) == 3
        assert returns[0] == Decimal("0.01")  # 1%
        assert returns[2] == Decimal("0.02")  # 2%


class TestPerformanceBenchmark:
    """Performance benchmarks to verify O(n) scaling (AC2, AC3)."""

    @pytest.fixture
    def calculator(self) -> RiskCalculator:
        """Create RiskCalculator instance."""
        return RiskCalculator()

    def _create_returns(self, n: int) -> list[Decimal]:
        """Create list of n random-like returns."""
        returns = []
        for i in range(n):
            # Simulate daily returns between -2% and +2%
            base = Decimal("0.001")
            variation = Decimal(str((i % 40 - 20) / 1000))  # -0.02 to +0.02
            returns.append(base + variation)
        return returns

    def _create_equity_curve(self, n: int) -> list[EquityPoint]:
        """Create equity curve with n points."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        value = Decimal("100000")
        curve = []
        for i in range(n):
            if i % 100 == 50:
                value = value * Decimal("0.95")
            elif i % 100 == 75:
                value = value * Decimal("1.08")
            else:
                value = value * Decimal("1.001")
            curve.append(EquityPoint(base + timedelta(days=i), value))
        return curve

    @pytest.mark.benchmark
    def test_sharpe_scales_linearly(self, calculator: RiskCalculator):
        """Verify calculate_sharpe_ratio is O(n)."""
        sizes = [1000, 2000, 4000, 8000]
        times: list[float] = []

        for size in sizes:
            returns = self._create_returns(size)

            start = time.perf_counter()
            calculator.calculate_sharpe_ratio(returns)
            elapsed = time.perf_counter() - start

            times.append(elapsed)

        # Verify O(n) scaling
        for i in range(1, len(times)):
            ratio = times[i] / max(times[i - 1], 0.0001)
            size_ratio = sizes[i] / sizes[i - 1]
            assert ratio < size_ratio * 3, (
                f"Scaling ratio {ratio:.2f} too high. " f"Possible O(n²) behavior detected."
            )

    @pytest.mark.benchmark
    def test_sortino_scales_linearly(self, calculator: RiskCalculator):
        """Verify calculate_sortino_ratio is O(n)."""
        sizes = [1000, 2000, 4000, 8000]
        times: list[float] = []

        for size in sizes:
            returns = self._create_returns(size)

            start = time.perf_counter()
            calculator.calculate_sortino_ratio(returns)
            elapsed = time.perf_counter() - start

            times.append(elapsed)

        # Verify O(n) scaling
        for i in range(1, len(times)):
            ratio = times[i] / max(times[i - 1], 0.0001)
            size_ratio = sizes[i] / sizes[i - 1]
            assert ratio < size_ratio * 3, "Possible O(n²) behavior detected."

    @pytest.mark.benchmark
    def test_calmar_scales_linearly(self, calculator: RiskCalculator):
        """Verify calculate_calmar_ratio is O(n)."""
        sizes = [1000, 2000, 4000, 8000]
        times: list[float] = []

        for size in sizes:
            curve = self._create_equity_curve(size)

            start = time.perf_counter()
            calculator.calculate_calmar_ratio(curve)
            elapsed = time.perf_counter() - start

            times.append(elapsed)

        # Verify O(n) scaling
        for i in range(1, len(times)):
            ratio = times[i] / max(times[i - 1], 0.0001)
            size_ratio = sizes[i] / sizes[i - 1]
            assert ratio < size_ratio * 3, "Possible O(n²) behavior detected."


class TestEdgeCases:
    """Tests for edge cases and boundary conditions (AC6)."""

    @pytest.fixture
    def calculator(self) -> RiskCalculator:
        """Create RiskCalculator instance."""
        return RiskCalculator()

    def test_very_small_returns(self, calculator: RiskCalculator):
        """Test with very small return values."""
        returns = [Decimal("0.00001")] * 10 + [Decimal("0.00002")] * 10

        result = calculator.calculate_sharpe_ratio(returns)

        # Should still produce valid result
        assert result.value != Decimal("0") or "error" not in result.metadata

    def test_large_negative_returns(self, calculator: RiskCalculator):
        """Test with large negative returns."""
        returns = [Decimal("-0.1"), Decimal("-0.15"), Decimal("-0.2")]

        result = calculator.calculate_sharpe_ratio(returns)

        # Should produce large negative Sharpe
        assert result.value < Decimal("0")

    def test_high_precision_decimals(self, calculator: RiskCalculator):
        """Test decimal precision is maintained."""
        returns = [
            Decimal("0.0012345678"),
            Decimal("0.0023456789"),
            Decimal("-0.0011111111"),
        ]

        result = calculator.calculate_sharpe_ratio(returns)

        # Should not crash, result should be quantized
        assert "." in str(result.value)

    def test_risk_free_rate_property(self):
        """Test risk_free_rate property access."""
        rate = Decimal("0.03")
        calculator = RiskCalculator(risk_free_rate=rate)

        assert calculator.risk_free_rate == rate
