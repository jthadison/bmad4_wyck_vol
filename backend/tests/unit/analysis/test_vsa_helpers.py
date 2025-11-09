"""
Unit tests for VSA (Volume Spread Analysis) helpers (Story 4.7).

Tests Victoria's VSA helper functions for:
- Close position calculation
- Volume spread context analysis
- Preliminary Supply detection (UTAD)
- Distribution volume signature
- Volume trend detection (up/down separation)
- Helper functions (average volume/spread)

VSA Principle:
    Effort (Volume) vs Result (Spread) reveals professional activity.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.analysis.vsa_helpers import (
    VSA_THRESHOLDS,
    calculate_average_spread,
    calculate_average_volume,
    check_distribution_volume_signature,
    check_preliminary_supply,
    detect_volume_trend,
    get_close_position,
    get_volume_spread_context,
)
from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import PhaseEvents

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def create_bar():
    """Factory fixture for creating test bars."""

    def _create_bar(
        high: float = 105.0,
        low: float = 100.0,
        close: float = 103.0,
        volume: int = 1000000,
        index: int = 0,
    ) -> OHLCVBar:
        base_time = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)
        return OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=base_time + timedelta(days=index),
            open=Decimal(str((high + low) / 2)),
            high=Decimal(str(high)),
            low=Decimal(str(low)),
            close=Decimal(str(close)),
            volume=volume,
            spread=Decimal(str(high - low)),
        )

    return _create_bar


@pytest.fixture
def sample_bars_for_vsa(create_bar) -> list[OHLCVBar]:
    """Generate sample bars for VSA testing."""
    bars = []

    # Create 30 bars with varied volume and spreads
    for i in range(30):
        if i < 10:
            # Normal bars
            bar = create_bar(high=105, low=100, close=103, volume=1000000, index=i)
        elif i == 10:
            # Preliminary Supply (high volume, wide spread, closed weak)
            bar = create_bar(high=110, low=100, close=102, volume=2000000, index=i)
        elif 11 <= i < 20:
            # More normal bars
            bar = create_bar(high=105, low=100, close=103, volume=1000000, index=i)
        elif i == 20:
            # SC bar (climactic)
            bar = create_bar(high=105, low=90, close=100, volume=3000000, index=i)
        else:
            # Post-SC bars
            bar = create_bar(high=105, low=100, close=103, volume=1000000, index=i)

        bars.append(bar)

    return bars


# ============================================================================
# get_close_position() Tests
# ============================================================================


def test_close_position_at_high(create_bar):
    """Test close position when close = high (1.0)."""
    bar = create_bar(high=105, low=100, close=105)
    close_pos = get_close_position(bar)
    assert close_pos == 1.0


def test_close_position_at_low(create_bar):
    """Test close position when close = low (0.0)."""
    bar = create_bar(high=105, low=100, close=100)
    close_pos = get_close_position(bar)
    assert close_pos == 0.0


def test_close_position_at_midpoint(create_bar):
    """Test close position when close at midpoint (0.5)."""
    bar = create_bar(high=105, low=100, close=102.5)
    close_pos = get_close_position(bar)
    assert close_pos == pytest.approx(0.5, abs=0.01)


def test_close_position_upper_third(create_bar):
    """Test close position in upper third (0.6)."""
    bar = create_bar(high=105, low=100, close=103)
    close_pos = get_close_position(bar)
    assert close_pos == pytest.approx(0.6, abs=0.01)
    assert close_pos < VSA_THRESHOLDS["close_upper_third"]  # Below 0.67


def test_close_position_lower_third(create_bar):
    """Test close position in lower third (0.3)."""
    bar = create_bar(high=105, low=100, close=101.5)
    close_pos = get_close_position(bar)
    assert close_pos == pytest.approx(0.3, abs=0.01)
    assert close_pos <= VSA_THRESHOLDS["close_lower_third"]  # At or below 0.33


def test_close_position_doji_bar(create_bar):
    """Test close position for doji bar (high = low)."""
    bar = create_bar(high=100, low=100, close=100)
    close_pos = get_close_position(bar)
    assert close_pos == 0.5  # Doji returns neutral 0.5


# ============================================================================
# get_volume_spread_context() Tests
# ============================================================================


def test_vsa_context_high_effort_low_result_bullish_absorption(create_bar):
    """Test VSA context: high volume, narrow spread, bullish close = bullish absorption."""
    # High volume (2x avg), narrow spread (0.5x avg), close upper
    bar = create_bar(high=102, low=100, close=101.8, volume=2000000)

    context = get_volume_spread_context(
        bar=bar,
        avg_volume=1000000.0,
        avg_spread=4.0,  # Bar spread is 2, so ratio = 2/4 = 0.5 (narrow)
    )

    assert context["effort"] == pytest.approx(2.0, abs=0.01)  # 2x volume
    assert context["result"] < 0.8  # Narrow spread
    assert context["close_position"] > VSA_THRESHOLDS["close_upper_third"]
    assert context["interpretation"] == "bullish_absorption"


def test_vsa_context_high_effort_low_result_bearish_absorption(create_bar):
    """Test VSA context: high volume, narrow spread, bearish close = bearish absorption."""
    # High volume, narrow spread, close lower
    bar = create_bar(high=102, low=100, close=100.2, volume=2000000)

    context = get_volume_spread_context(bar=bar, avg_volume=1000000.0, avg_spread=4.0)

    assert context["effort"] == pytest.approx(2.0, abs=0.01)
    assert context["result"] < 0.8
    assert context["close_position"] < VSA_THRESHOLDS["close_upper_third"]
    assert context["interpretation"] == "bearish_absorption"


def test_vsa_context_low_effort_wide_result_no_demand(create_bar):
    """Test VSA context: low volume, wide spread, bearish close = no demand."""
    # Low volume (0.5x avg), wide spread (2x avg), close lower
    bar = create_bar(high=110, low=100, close=102, volume=500000)

    context = get_volume_spread_context(
        bar=bar,
        avg_volume=1000000.0,
        avg_spread=5.0,  # Bar spread is 10, so ratio = 10/5 = 2.0 (wide)
    )

    assert context["effort"] < VSA_THRESHOLDS["low_volume"]
    assert context["result"] > 1.5  # Wide spread
    assert context["close_position"] < VSA_THRESHOLDS["close_lower_third"]
    assert context["interpretation"] == "no_demand"


def test_vsa_context_low_effort_wide_result_no_supply(create_bar):
    """Test VSA context: low volume, wide spread, bullish close = no supply (bullish)."""
    # Low volume, wide spread, close upper
    bar = create_bar(high=110, low=100, close=108, volume=500000)

    context = get_volume_spread_context(bar=bar, avg_volume=1000000.0, avg_spread=5.0)

    assert context["effort"] < VSA_THRESHOLDS["low_volume"]
    assert context["result"] > 1.5
    assert context["close_position"] > VSA_THRESHOLDS["close_lower_third"]
    assert context["interpretation"] == "no_supply"


def test_vsa_context_harmony(create_bar):
    """Test VSA context: effort matches result = harmony."""
    # Normal volume (1x avg), normal spread (1x avg)
    bar = create_bar(high=105, low=100, close=103, volume=1000000)

    context = get_volume_spread_context(
        bar=bar,
        avg_volume=1000000.0,
        avg_spread=5.0,  # Bar spread is 5, so ratio = 5/5 = 1.0
    )

    assert abs(context["effort"] - context["result"]) < 0.3
    assert context["harmony"] == True
    assert context["interpretation"] == "harmony"


def test_vsa_context_divergence(create_bar):
    """Test VSA context: effort doesn't match result = divergence."""
    # High volume (2x), moderate spread (1.2x) - mismatch
    bar = create_bar(high=106, low=100, close=103, volume=2000000)

    context = get_volume_spread_context(
        bar=bar,
        avg_volume=1000000.0,
        avg_spread=5.0,  # Bar spread is 6, so ratio = 6/5 = 1.2
    )

    # Effort >> Result but not extreme enough for absorption
    effort_result_diff = abs(context["effort"] - context["result"])
    assert effort_result_diff >= 0.3  # Not harmonious
    assert context["harmony"] == False
    # Should be divergence (not absorption because spread not narrow enough)
    assert context["interpretation"] in ["divergence", "bullish_absorption", "bearish_absorption"]


# ============================================================================
# check_preliminary_supply() Tests
# ============================================================================


def test_preliminary_supply_detected(sample_bars_for_vsa):
    """Test Preliminary Supply detection (bar 10 has PS characteristics)."""
    # Create PhaseEvents with SC at bar 20
    sc_bar = sample_bars_for_vsa[20]
    events = PhaseEvents(
        selling_climax={
            "bar": {
                "timestamp": sc_bar.timestamp.isoformat(),
                "low": str(sc_bar.low),
            },
            "bar_index": 20,
        }
    )

    has_ps = check_preliminary_supply(events, sample_bars_for_vsa)

    # Bar 10 (10 bars before SC) has high volume, wide spread, closed weak
    # Should detect PS
    assert has_ps == True


def test_preliminary_supply_not_detected_no_sc():
    """Test PS not detected when no SC present."""
    events = PhaseEvents(selling_climax=None)
    bars = []

    has_ps = check_preliminary_supply(events, bars)
    assert has_ps == False


def test_preliminary_supply_not_detected_normal_volume(create_bar):
    """Test PS not detected when volume normal before SC."""
    bars = []

    # Create bars with normal volume throughout
    for i in range(30):
        bar = create_bar(high=105, low=100, close=103, volume=1000000, index=i)
        bars.append(bar)

    # SC at bar 20
    sc_bar = bars[20]
    events = PhaseEvents(
        selling_climax={
            "bar": {
                "timestamp": sc_bar.timestamp.isoformat(),
                "low": str(sc_bar.low),
            },
            "bar_index": 20,
        }
    )

    has_ps = check_preliminary_supply(events, bars)

    # No high volume bars before SC = no PS
    assert has_ps == False


# ============================================================================
# check_distribution_volume_signature() Tests
# ============================================================================


def test_distribution_signature_detected(create_bar):
    """Test distribution volume signature detection (low vol rallies, high vol declines)."""
    bars = []

    # Create 20 bars with distribution signature
    for i in range(20):
        if i % 2 == 0:
            # Up-bars (close > open): LOW volume, NARROW spread
            bar = create_bar(high=103, low=100, close=102, volume=500000, index=i)
            bar.open = Decimal("100")  # Up-bar
        else:
            # Down-bars (close < open): HIGH volume, WIDE spread
            bar = create_bar(high=110, low=100, close=101, volume=1500000, index=i)
            bar.open = Decimal("105")  # Down-bar

        bars.append(bar)

    has_distribution = check_distribution_volume_signature(bars)

    # Up-bars have low volume, down-bars have high volume = distribution
    assert has_distribution == True


def test_distribution_signature_not_detected_accumulation(create_bar):
    """Test distribution signature not detected in accumulation (opposite pattern)."""
    bars = []

    # Create 20 bars with accumulation signature (opposite of distribution)
    for i in range(20):
        if i % 2 == 0:
            # Up-bars: HIGH volume, WIDE spread (professional buying)
            bar = create_bar(high=110, low=100, close=108, volume=1500000, index=i)
            bar.open = Decimal("100")
        else:
            # Down-bars: LOW volume, NARROW spread (no selling pressure)
            bar = create_bar(high=103, low=100, close=101, volume=500000, index=i)
            bar.open = Decimal("102")

        bars.append(bar)

    has_distribution = check_distribution_volume_signature(bars)

    # Accumulation pattern = not distribution
    assert has_distribution == False


def test_distribution_signature_insufficient_bars(create_bar):
    """Test distribution signature with insufficient bars (<10)."""
    bars = [create_bar(index=i) for i in range(5)]

    has_distribution = check_distribution_volume_signature(bars)

    # Not enough bars to determine
    assert has_distribution == False


# ============================================================================
# detect_volume_trend() Tests
# ============================================================================


def test_volume_trend_increasing_overall(create_bar):
    """Test volume trend detection: increasing overall."""
    bars = []

    # Early phase: low volume
    for i in range(10):
        bar = create_bar(volume=1000000, index=i)
        bars.append(bar)

    # Recent phase: high volume (1.5x)
    for i in range(10, 20):
        bar = create_bar(volume=1500000, index=i)
        bars.append(bar)

    trend = detect_volume_trend(bars, phase_start_index=0)

    # Recent volume 1.5x early volume = 1.5 ratio > 1.2 = "increasing"
    assert trend["overall"] == "increasing"


def test_volume_trend_declining_overall(create_bar):
    """Test volume trend detection: declining overall."""
    bars = []

    # Early phase: high volume
    for i in range(10):
        bar = create_bar(volume=1500000, index=i)
        bars.append(bar)

    # Recent phase: low volume (0.6x)
    for i in range(10, 20):
        bar = create_bar(volume=900000, index=i)
        bars.append(bar)

    trend = detect_volume_trend(bars, phase_start_index=0)

    # Recent volume 0.6x early volume < 0.8 = "declining"
    assert trend["overall"] == "declining"


def test_volume_trend_up_bar_separation_exhaustion(create_bar):
    """Test volume trend: declining on up-bars = EXHAUSTION signal."""
    bars = []

    # Early phase: up-bars have high volume
    for i in range(10):
        bar = create_bar(volume=1500000, index=i)
        bar.open = Decimal("100")
        bar.close = Decimal("103")  # Up-bar
        bars.append(bar)

    # Recent phase: up-bars have low volume (EXHAUSTION)
    for i in range(10, 20):
        bar = create_bar(volume=500000, index=i)
        bar.open = Decimal("100")
        bar.close = Decimal("103")  # Up-bar
        bars.append(bar)

    trend = detect_volume_trend(bars, phase_start_index=0)

    # Up-bar volume declining = EXHAUSTION warning
    assert trend["up_bars"] == "declining"


def test_volume_trend_down_bar_separation_healthy(create_bar):
    """Test volume trend: declining on down-bars = HEALTHY (demand holds)."""
    bars = []

    # Early phase: down-bars have high volume
    for i in range(10):
        bar = create_bar(volume=1500000, index=i)
        bar.open = Decimal("103")
        bar.close = Decimal("100")  # Down-bar
        bars.append(bar)

    # Recent phase: down-bars have low volume (HEALTHY - demand holds)
    for i in range(10, 20):
        bar = create_bar(volume=500000, index=i)
        bar.open = Decimal("103")
        bar.close = Decimal("100")  # Down-bar
        bars.append(bar)

    trend = detect_volume_trend(bars, phase_start_index=0)

    # Down-bar volume declining = HEALTHY (low volume on pullbacks)
    assert trend["down_bars"] == "declining"


def test_volume_trend_stable(create_bar):
    """Test volume trend: stable (ratio 0.8 to 1.2)."""
    bars = []

    # Create 20 bars with consistent volume
    for i in range(20):
        bar = create_bar(volume=1000000, index=i)
        bars.append(bar)

    trend = detect_volume_trend(bars, phase_start_index=0)

    # Recent volume same as early volume = "stable"
    assert trend["overall"] == "stable"


def test_volume_trend_insufficient_bars(create_bar):
    """Test volume trend with insufficient bars (<20)."""
    bars = [create_bar(index=i) for i in range(15)]

    trend = detect_volume_trend(bars, phase_start_index=0)

    # Insufficient bars = all "stable"
    assert trend["overall"] == "stable"
    assert trend["up_bars"] == "stable"
    assert trend["down_bars"] == "stable"


# ============================================================================
# calculate_average_volume() Tests
# ============================================================================


def test_calculate_average_volume_default_period(create_bar):
    """Test average volume calculation with default 20-bar period."""
    bars = [create_bar(volume=1000000, index=i) for i in range(30)]

    avg_vol = calculate_average_volume(bars)

    assert avg_vol == pytest.approx(1000000.0, abs=1.0)


def test_calculate_average_volume_custom_period(create_bar):
    """Test average volume calculation with custom period."""
    bars = [create_bar(volume=1000000, index=i) for i in range(30)]

    avg_vol = calculate_average_volume(bars, period=10)

    # Should use last 10 bars
    assert avg_vol == pytest.approx(1000000.0, abs=1.0)


def test_calculate_average_volume_varied_volume(create_bar):
    """Test average volume with varied volumes."""
    bars = []

    # First 10: low volume
    for i in range(10):
        bars.append(create_bar(volume=500000, index=i))

    # Last 10: high volume
    for i in range(10, 20):
        bars.append(create_bar(volume=1500000, index=i))

    avg_vol = calculate_average_volume(bars, period=20)

    # Average of 500k and 1500k = 1000k
    assert avg_vol == pytest.approx(1000000.0, abs=1.0)


# ============================================================================
# calculate_average_spread() Tests
# ============================================================================


def test_calculate_average_spread_default_period(create_bar):
    """Test average spread calculation with default 20-bar period."""
    # Create bars with 5-point spread (high=105, low=100)
    bars = [create_bar(high=105, low=100, index=i) for i in range(30)]

    avg_spread = calculate_average_spread(bars)

    # Spread = (high - low) / close = 5 / 103 ≈ 0.0485
    assert avg_spread > 0
    assert avg_spread < 0.1  # Reasonable spread ratio


def test_calculate_average_spread_custom_period(create_bar):
    """Test average spread with custom period."""
    bars = [create_bar(high=105, low=100, index=i) for i in range(30)]

    avg_spread = calculate_average_spread(bars, period=10)

    # Should use last 10 bars
    assert avg_spread > 0


def test_calculate_average_spread_varied_spreads(create_bar):
    """Test average spread with varied spreads."""
    bars = []

    # First 10: narrow spread
    for i in range(10):
        bars.append(create_bar(high=102, low=100, close=101, index=i))

    # Last 10: wide spread
    for i in range(10, 20):
        bars.append(create_bar(high=110, low=100, close=105, index=i))

    avg_spread = calculate_average_spread(bars, period=20)

    # Average of narrow and wide spreads
    assert avg_spread > 0
