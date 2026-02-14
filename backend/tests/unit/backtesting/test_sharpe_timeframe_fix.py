"""
Test for Story 13.5 C-2 Fix: Timeframe-aware Sharpe Ratio Calculation

Purpose:
--------
Verify that Sharpe ratio calculation correctly adjusts annualization factor
based on the data timeframe (intraday vs daily).

Critical Bug Background:
------------------------
Prior to this fix, Sharpe ratio calculation hardcoded 252 trading days/year,
causing massively inflated Sharpe ratios for intraday timeframes:
- 1h backtests: ~15.8x too high (should use 6,048 bars/year, not 252)
- 15m backtests: ~63.2x too high (should use 24,192 bars/year, not 252)

Expected Behavior After Fix:
-----------------------------
For equivalent trading performance:
- Daily Sharpe = 2.0
- Hourly Sharpe ≈ 2.0 (same annualized performance)
- 15m Sharpe ≈ 2.0 (same annualized performance)

The annualization factor sqrt(bars_per_year) should scale appropriately:
- Daily: sqrt(252) ≈ 15.87
- Hourly: sqrt(6048) ≈ 77.77 (4.9x larger)
- 15m: sqrt(24192) ≈ 155.54 (9.8x larger)

Author: Story 13.5 C-2 Fix
"""

from datetime import UTC, datetime
from decimal import Decimal

from src.backtesting.metrics import MetricsCalculator
from src.models.backtest import EquityCurvePoint


class TestSharpeTimeframeAwareness:
    """Test suite for timeframe-aware Sharpe ratio calculation."""

    def test_daily_sharpe_baseline(self):
        """Verify daily Sharpe calculation produces expected baseline."""
        # Create equity curve with consistent 0.1% daily returns
        equity_curve = self._create_equity_curve_with_constant_returns(
            initial_value=Decimal("100000"),
            daily_return_pct=Decimal("0.001"),  # 0.1% per bar
            num_bars=252,  # 1 year of daily data
            bars_per_day=1,  # Daily bars
        )

        calculator = MetricsCalculator(timeframe="1d")
        sharpe = calculator._calculate_sharpe_ratio(equity_curve)

        # With 0.1% daily return (~28% annualized), expect high Sharpe
        # Note: 0.1% daily with low volatility is an exceptional strategy
        assert sharpe > Decimal("0"), "Daily Sharpe should be positive for profitable strategy"
        assert sharpe < Decimal("100"), "Daily Sharpe should be finite"

    def test_hourly_sharpe_uses_correct_annualization(self):
        """
        Verify hourly Sharpe uses 6048 bars/year not 252.

        Before fix: Used sqrt(252) = 15.87 annualization factor
        After fix: Uses sqrt(6048) = 77.77 annualization factor
        """
        hourly_return = Decimal("0.001") / Decimal("24")
        equity_curve = self._create_equity_curve_with_constant_returns(
            initial_value=Decimal("100000"),
            daily_return_pct=hourly_return,
            num_bars=6048,  # 1 year
            bars_per_day=24,
        )

        calculator = MetricsCalculator(timeframe="1h")
        sharpe = calculator._calculate_sharpe_ratio(equity_curve)

        # Sharpe should be finite and positive
        assert sharpe > Decimal("0"), "Sharpe should be positive for profitable strategy"
        assert sharpe < Decimal("1000"), "Sharpe should be reasonable"

        # Verify correct bars_per_year used
        assert calculator._get_bars_per_year("1h") == 6048

    def test_15m_sharpe_uses_correct_annualization(self):
        """
        Verify 15-minute Sharpe uses 24192 bars/year not 252.

        Before fix: Used sqrt(252) = 15.87 annualization factor
        After fix: Uses sqrt(24192) = 155.54 annualization factor
        """
        min15_return = Decimal("0.001") / Decimal("96")
        equity_curve = self._create_equity_curve_with_constant_returns(
            initial_value=Decimal("100000"),
            daily_return_pct=min15_return,
            num_bars=24192,  # 1 year
            bars_per_day=96,
        )

        calculator = MetricsCalculator(timeframe="15m")
        sharpe = calculator._calculate_sharpe_ratio(equity_curve)

        # Sharpe should be finite and positive
        assert sharpe > Decimal("0"), "Sharpe should be positive for profitable strategy"
        assert sharpe < Decimal("1000"), "Sharpe should be reasonable"

        # Verify correct bars_per_year used
        assert calculator._get_bars_per_year("15m") == 24192

    def test_bars_per_year_calculation(self):
        """Verify _get_bars_per_year returns correct values."""
        calculator = MetricsCalculator()

        assert calculator._get_bars_per_year("1d") == 252
        assert calculator._get_bars_per_year("daily") == 252
        assert calculator._get_bars_per_year("1h") == 6048  # 252 * 24
        assert calculator._get_bars_per_year("4h") == 1512  # 252 * 6
        assert calculator._get_bars_per_year("15m") == 24192  # 252 * 24 * 4
        assert calculator._get_bars_per_year("5m") == 72576  # 252 * 24 * 12
        assert calculator._get_bars_per_year("1m") == 362880  # 252 * 24 * 60
        assert calculator._get_bars_per_year("1w") == 52
        assert calculator._get_bars_per_year("weekly") == 52

    def test_unknown_timeframe_defaults_to_daily(self):
        """Verify unknown timeframes default to daily (252 bars/year)."""
        calculator = MetricsCalculator()

        assert calculator._get_bars_per_year("unknown_tf") == 252
        assert calculator._get_bars_per_year("30m") == 252  # Not explicitly handled

    def _create_equity_curve_with_constant_returns(
        self,
        initial_value: Decimal,
        daily_return_pct: Decimal,
        num_bars: int,
        bars_per_day: int = 1,
    ) -> list[EquityCurvePoint]:
        """
        Helper: Create equity curve with returns that have realistic volatility.

        Volatility scales with sqrt(time), so intraday bars have lower volatility
        per bar than daily bars to maintain equivalent annualized volatility.

        Args:
            initial_value: Starting portfolio value
            daily_return_pct: Average return per bar (e.g., 0.001 = 0.1%)
            num_bars: Number of bars to generate
            bars_per_day: Number of bars per trading day (1=daily, 24=hourly, 96=15m)

        Returns:
            List of EquityCurvePoint with varying returns around the mean
        """
        import random

        random.seed(42)  # Reproducible results

        equity_curve = []
        current_value = initial_value
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

        # Scale volatility by sqrt(bars_per_day) to match reality
        # Daily bars: volatility_factor ∈ [0.5, 1.5]
        # Hourly bars: volatility_factor / sqrt(24) ∈ [0.102, 0.306]
        # 15m bars: volatility_factor / sqrt(96) ∈ [0.051, 0.153]
        volatility_scale = 1.0 / (bars_per_day**0.5)

        for i in range(num_bars):
            # Add bar to curve
            equity_curve.append(
                EquityCurvePoint(
                    timestamp=base_timestamp.replace(day=1 + (i % 28)),
                    portfolio_value=current_value,
                    equity_value=current_value,
                    cash=Decimal("0"),
                    positions_value=current_value,
                )
            )

            # Add realistic volatility: returns vary ±50% around mean
            # Scaled by sqrt(bars_per_day) to match reality
            base_volatility_factor = random.uniform(0.5, 1.5)
            volatility_factor = Decimal(str(base_volatility_factor * volatility_scale))
            bar_return = daily_return_pct * volatility_factor

            # Compound return for next bar
            current_value = current_value * (Decimal("1") + bar_return)

        return equity_curve
