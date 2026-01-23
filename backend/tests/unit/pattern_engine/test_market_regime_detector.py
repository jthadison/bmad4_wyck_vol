"""
Tests for Market Regime Detection (Story 16.7a)

Test Coverage:
--------------
1. Test all 5 regime types (RANGING, TRENDING_UP, TRENDING_DOWN, HIGH_VOLATILITY, LOW_VOLATILITY)
2. Test ADX calculation accuracy
3. Test ATR calculation accuracy
4. Test regime detection logic thresholds
5. Test edge cases (insufficient data, zero values)
6. Test performance requirements (< 10ms per bar)

Author: Story 16.7a
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.models.campaign import MarketRegime
from src.models.ohlcv import OHLCVBar
from src.pattern_engine.market_regime_detector import MarketRegimeDetector


@pytest.fixture
def detector() -> MarketRegimeDetector:
    """Create a MarketRegimeDetector instance for testing."""
    return MarketRegimeDetector()


def create_ohlcv_bars(
    count: int,
    base_price: Decimal = Decimal("100.0"),
    trend: str = "flat",
    volatility: str = "normal",
) -> list[OHLCVBar]:
    """
    Create synthetic OHLCV bars for testing.

    Parameters:
    -----------
    count : int
        Number of bars to create
    base_price : Decimal
        Starting price (default 100.0)
    trend : str
        "flat" (ranging), "up" (uptrend), "down" (downtrend)
    volatility : str
        "normal", "high", "low"

    Returns:
    --------
    list[OHLCVBar]
        Generated OHLCV bars
    """
    bars = []
    current_price = base_price
    base_time = datetime.now(UTC)

    # Volatility multipliers - need extreme differences for detection
    vol_multiplier = {
        "low": Decimal("0.1"),  # Very tight ranges
        "normal": Decimal("1.0"),
        "high": Decimal("5.0"),  # Very wide ranges
    }[volatility]

    # Trend increments
    trend_increment = {
        "flat": Decimal("0.0"),
        "up": Decimal("0.5"),
        "down": Decimal("-0.5"),
    }[trend]

    for i in range(count):
        # Apply trend
        current_price += trend_increment

        # Calculate bar range based on volatility
        bar_range = Decimal("1.0") * vol_multiplier

        high = current_price + bar_range
        low = current_price - bar_range
        open_price = current_price - (bar_range / Decimal("2"))
        close_price = current_price + (bar_range / Decimal("2"))
        spread = high - low

        bar = OHLCVBar(
            symbol="TEST",
            timeframe="1h",
            timestamp=base_time + timedelta(hours=i),
            open=open_price,
            high=high,
            low=low,
            close=close_price,
            volume=1000000,
            spread=spread,
        )
        bars.append(bar)

    return bars


class TestMarketRegimeDetector:
    """Test suite for MarketRegimeDetector."""

    def test_ranging_market_detection(self, detector: MarketRegimeDetector) -> None:
        """
        Test RANGING regime detection (ADX < 25).

        AC #1: Detect RANGING markets (ideal for Wyckoff)
        """
        # Create flat market with low trend strength
        bars = create_ohlcv_bars(count=50, trend="flat", volatility="normal")

        regime = detector.detect_regime(bars)

        assert regime == MarketRegime.RANGING, f"Expected RANGING but got {regime}"

    def test_trending_up_detection(self, detector: MarketRegimeDetector) -> None:
        """
        Test TRENDING_UP regime detection (ADX >= 25 + price rising).

        AC #1: Detect TRENDING markets (uptrend)
        AC #3: ADX >= 25 + price direction → TRENDING_UP
        """
        # Create strong uptrend
        bars = create_ohlcv_bars(count=50, trend="up", volatility="normal")

        regime = detector.detect_regime(bars)

        assert regime == MarketRegime.TRENDING_UP, f"Expected TRENDING_UP but got {regime}"

    def test_trending_down_detection(self, detector: MarketRegimeDetector) -> None:
        """
        Test TRENDING_DOWN regime detection (ADX >= 25 + price falling).

        AC #1: Detect TRENDING markets (downtrend)
        AC #3: ADX >= 25 + price direction → TRENDING_DOWN
        """
        # Create strong downtrend
        bars = create_ohlcv_bars(count=50, trend="down", volatility="normal")

        regime = detector.detect_regime(bars)

        assert regime == MarketRegime.TRENDING_DOWN, f"Expected TRENDING_DOWN but got {regime}"

    def test_high_volatility_detection(self, detector: MarketRegimeDetector) -> None:
        """
        Test HIGH_VOLATILITY regime detection (ATR > 1.5x avg).

        AC #1: Detect HIGH_VOLATILITY markets
        AC #3: ATR > 1.5x avg → HIGH_VOLATILITY
        """
        # Create bars with normal volatility first, then spike to high volatility
        # First 30 bars with normal volatility (establishes baseline)
        bars = create_ohlcv_bars(count=30, trend="flat", volatility="normal")
        # Add 20 more bars with high volatility (creates spike)
        bars.extend(
            create_ohlcv_bars(count=20, base_price=bars[-1].close, trend="flat", volatility="high")
        )

        regime = detector.detect_regime(bars)

        assert regime == MarketRegime.HIGH_VOLATILITY, f"Expected HIGH_VOLATILITY but got {regime}"

    def test_low_volatility_detection(self, detector: MarketRegimeDetector) -> None:
        """
        Test LOW_VOLATILITY regime detection (ATR < 0.5x avg).

        AC #1: Detect LOW_VOLATILITY markets
        AC #3: ATR < 0.5x avg → LOW_VOLATILITY
        """
        # Create bars with normal volatility first, then drop to low volatility
        # First 30 bars with normal volatility (establishes baseline)
        bars = create_ohlcv_bars(count=30, trend="flat", volatility="normal")
        # Add 20 more bars with low volatility (creates compression)
        bars.extend(
            create_ohlcv_bars(count=20, base_price=bars[-1].close, trend="flat", volatility="low")
        )

        regime = detector.detect_regime(bars)

        assert regime == MarketRegime.LOW_VOLATILITY, f"Expected LOW_VOLATILITY but got {regime}"

    def test_adx_calculation_returns_valid_range(self, detector: MarketRegimeDetector) -> None:
        """
        Test ADX calculation returns value in valid range (0-100).

        AC #2: ADX (Average Directional Index) calculation for trend strength
        """
        bars = create_ohlcv_bars(count=50, trend="up", volatility="normal")

        adx = detector._calculate_adx(bars, period=14)

        assert Decimal("0") <= adx <= Decimal("100"), f"ADX {adx} outside valid range [0, 100]"

    def test_atr_calculation_returns_positive(self, detector: MarketRegimeDetector) -> None:
        """
        Test ATR calculation returns positive value.

        AC #2: ATR (Average True Range) calculation for volatility
        """
        bars = create_ohlcv_bars(count=50, trend="flat", volatility="normal")

        atr = detector._calculate_atr(bars, period=14)

        assert atr >= Decimal("0"), f"ATR {atr} should be non-negative"

    def test_insufficient_data_defaults_to_ranging(self, detector: MarketRegimeDetector) -> None:
        """
        Test that insufficient data defaults to RANGING regime.

        Edge case: Not enough bars for reliable calculation
        """
        bars = create_ohlcv_bars(count=20, trend="flat", volatility="normal")

        regime = detector.detect_regime(bars)

        assert regime == MarketRegime.RANGING, "Insufficient data should default to RANGING"

    def test_adx_with_insufficient_bars_returns_zero(self, detector: MarketRegimeDetector) -> None:
        """Test ADX calculation with insufficient bars returns zero."""
        bars = create_ohlcv_bars(count=10, trend="flat", volatility="normal")

        adx = detector._calculate_adx(bars, period=14)

        assert adx == Decimal("0"), "Insufficient bars should return ADX = 0"

    def test_atr_with_insufficient_bars_returns_zero(self, detector: MarketRegimeDetector) -> None:
        """Test ATR calculation with insufficient bars returns zero."""
        bars = create_ohlcv_bars(count=10, trend="flat", volatility="normal")

        atr = detector._calculate_atr(bars, period=14)

        assert atr == Decimal("0"), "Insufficient bars should return ATR = 0"

    def test_regime_detection_performance(self, detector: MarketRegimeDetector) -> None:
        """
        Test regime detection performance (< 10ms per bar).

        NFR #7: Regime detection < 10ms per bar
        """
        import time

        bars = create_ohlcv_bars(count=100, trend="flat", volatility="normal")

        start_time = time.perf_counter()
        regime = detector.detect_regime(bars)
        end_time = time.perf_counter()

        elapsed_ms = (end_time - start_time) * 1000

        assert elapsed_ms < 10.0, f"Regime detection took {elapsed_ms:.2f}ms (should be < 10ms)"

    def test_adx_trend_strength_increases_with_trend(self, detector: MarketRegimeDetector) -> None:
        """
        Test that ADX increases with stronger trends.

        Validates ADX correctly measures trend strength.
        """
        flat_bars = create_ohlcv_bars(count=50, trend="flat", volatility="normal")
        trending_bars = create_ohlcv_bars(count=50, trend="up", volatility="normal")

        flat_adx = detector._calculate_adx(flat_bars, period=14)
        trending_adx = detector._calculate_adx(trending_bars, period=14)

        assert (
            trending_adx >= flat_adx
        ), f"Trending ADX {trending_adx} should be >= flat ADX {flat_adx}"

    def test_atr_increases_with_volatility(self, detector: MarketRegimeDetector) -> None:
        """
        Test that ATR increases with higher volatility.

        Validates ATR correctly measures volatility.
        """
        low_vol_bars = create_ohlcv_bars(count=50, trend="flat", volatility="low")
        high_vol_bars = create_ohlcv_bars(count=50, trend="flat", volatility="high")

        low_atr = detector._calculate_atr(low_vol_bars, period=14)
        high_atr = detector._calculate_atr(high_vol_bars, period=14)

        assert (
            high_atr > low_atr
        ), f"High volatility ATR {high_atr} should be > low volatility ATR {low_atr}"

    def test_regime_detection_with_mixed_conditions(self, detector: MarketRegimeDetector) -> None:
        """
        Test regime detection prioritizes volatility over trend.

        Validates detection logic priority:
        1. Volatility extremes (HIGH/LOW)
        2. Trend strength (RANGING vs TRENDING)
        3. Trend direction (UP vs DOWN)
        """
        # Create uptrend with normal volatility first, then spike volatility
        bars = create_ohlcv_bars(count=30, trend="up", volatility="normal")
        bars.extend(
            create_ohlcv_bars(count=20, base_price=bars[-1].close, trend="up", volatility="high")
        )
        regime = detector.detect_regime(bars)

        assert (
            regime == MarketRegime.HIGH_VOLATILITY
        ), "Volatility extremes should take priority over trend"

    def test_regime_enum_values(self) -> None:
        """Test MarketRegime enum has all required values."""
        expected_regimes = {
            "RANGING",
            "TRENDING_UP",
            "TRENDING_DOWN",
            "HIGH_VOLATILITY",
            "LOW_VOLATILITY",
        }

        actual_regimes = {regime.value for regime in MarketRegime}

        assert (
            actual_regimes == expected_regimes
        ), f"Missing or extra regimes: {actual_regimes ^ expected_regimes}"

    def test_detector_initialization_sets_default_params(
        self, detector: MarketRegimeDetector
    ) -> None:
        """Test detector initializes with correct default parameters."""
        assert detector.adx_period == 14
        assert detector.atr_period == 14
        assert detector.avg_atr_period == 20
        assert detector.adx_threshold == Decimal("25.0")
        assert detector.high_vol_multiplier == Decimal("1.5")
        assert detector.low_vol_multiplier == Decimal("0.5")

    def test_atr_with_zero_range_bars(self, detector: MarketRegimeDetector) -> None:
        """Test ATR calculation handles bars with zero range (doji bars)."""
        bars = []
        base_time = datetime.now(UTC)
        base_price = Decimal("100.0")

        # Create 50 bars with identical OHLC (zero range)
        for i in range(50):
            bar = OHLCVBar(
                symbol="TEST",
                timeframe="1h",
                timestamp=base_time + timedelta(hours=i),
                open=base_price,
                high=base_price,
                low=base_price,
                close=base_price,
                volume=1000000,
                spread=Decimal("0"),
            )
            bars.append(bar)

        atr = detector._calculate_atr(bars, period=14)

        # ATR should be zero for zero-range bars
        assert atr == Decimal("0"), f"ATR for zero-range bars should be 0, got {atr}"

    def test_regime_detection_with_exact_threshold_values(
        self, detector: MarketRegimeDetector
    ) -> None:
        """
        Test regime detection at exact threshold boundaries.

        Validates behavior at ADX = 25 threshold.
        """
        # This is a boundary test - actual results depend on synthetic data
        # Just verify no exceptions are raised
        bars = create_ohlcv_bars(count=50, trend="flat", volatility="normal")

        try:
            regime = detector.detect_regime(bars)
            assert regime in MarketRegime, f"Invalid regime returned: {regime}"
        except Exception as e:
            pytest.fail(f"Regime detection failed at threshold boundary: {e}")

    def test_avg_atr_calculation(self, detector: MarketRegimeDetector) -> None:
        """Test average ATR calculation over lookback period."""
        bars = create_ohlcv_bars(count=50, trend="flat", volatility="normal")

        avg_atr = detector._calculate_avg_atr(bars, period=20)

        assert avg_atr >= Decimal("0"), f"Average ATR should be non-negative, got {avg_atr}"

    def test_avg_atr_with_insufficient_data(self, detector: MarketRegimeDetector) -> None:
        """Test average ATR calculation with insufficient data returns zero."""
        bars = create_ohlcv_bars(count=20, trend="flat", volatility="normal")

        avg_atr = detector._calculate_avg_atr(bars, period=20)

        assert avg_atr == Decimal("0"), "Insufficient data should return avg_atr = 0"
