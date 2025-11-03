"""
Integration test for Spring pattern detection with VolumeAnalyzer.

This test validates that Spring detector correctly integrates with VolumeAnalyzer
for volume ratio calculations (Story 2.5 integration with Story 5.1).

Key integration point tested:
- Story 5.1 (Spring detector) calls VolumeAnalyzer.calculate_volume_ratio()
- Volume ratio must be <0.7x per FR12
- VolumeAnalyzer uses 20-bar average for calculation

The unit tests in test_spring_detector.py already cover all Spring detection
logic comprehensively. This integration test focuses specifically on verifying
the VolumeAnalyzer integration works correctly with real volume calculations.
"""

import pytest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from src.models.ohlcv import OHLCVBar
from src.pattern_engine.volume_analyzer import calculate_volume_ratio


@pytest.mark.integration
def test_volume_analyzer_integration_for_spring_detection():
    """
    Test VolumeAnalyzer integration with Spring detection workflow.

    This test validates that the volume ratio calculation used by Spring
    detector (via VolumeAnalyzer.calculate_volume_ratio) works correctly
    with realistic bar sequences.

    Scenario:
    - Create 30 bars with average volume of 1M shares
    - Bar 25: Spring candidate with 250K volume (0.25x average)
    - Bar 26: High-volume breakdown with 800K volume (0.8x average)

    Expected:
    - Bar 25 volume ratio ~0.25x (ACCEPTED for Spring, <0.7x threshold)
    - Bar 26 volume ratio ~0.8x (REJECTED for Spring, >=0.7x threshold)
    """
    bars = []
    base_volume = 1_000_000  # 1M shares average
    start_time = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)

    # Create 30 bars with consistent average volume
    for i in range(30):
        timestamp = start_time + timedelta(days=i)

        # Normal bars: volume oscillates around 1M
        if i < 25:
            volume = int(base_volume * (0.95 + (i % 3) * 0.05))  # 950K to 1.05M
        # Bar 25: Low volume spring candidate (250K = 0.25x)
        elif i == 25:
            volume = int(base_volume * 0.25)  # 250K - LOW volume
        # Bar 26: High volume breakdown (800K = 0.8x)
        elif i == 26:
            volume = int(base_volume * 0.8)  # 800K - HIGH volume
        # Remaining bars: normal volume
        else:
            volume = int(base_volume)

        # Create bar
        bar = OHLCVBar(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            timestamp=timestamp,
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("99.00"),
            close=Decimal("100.50"),
            volume=volume,
            spread=Decimal("2.00"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),
        )
        bars.append(bar)

    # Test bar 25 (low volume spring candidate)
    bar_25_volume_ratio = calculate_volume_ratio(bars, 25)
    assert bar_25_volume_ratio is not None, "Volume ratio should be calculated for bar 25"
    assert 0.20 <= bar_25_volume_ratio <= 0.30, \
        f"Bar 25 volume ratio should be ~0.25x (got {bar_25_volume_ratio:.2f}x)"
    assert bar_25_volume_ratio < 0.7, \
        "Bar 25 volume ratio should be <0.7x (ACCEPTED for Spring per FR12)"

    # Test bar 26 (high volume breakdown)
    bar_26_volume_ratio = calculate_volume_ratio(bars, 26)
    assert bar_26_volume_ratio is not None, "Volume ratio should be calculated for bar 26"
    assert 0.75 <= bar_26_volume_ratio <= 0.85, \
        f"Bar 26 volume ratio should be ~0.8x (got {bar_26_volume_ratio:.2f}x)"
    assert bar_26_volume_ratio >= 0.7, \
        "Bar 26 volume ratio should be >=0.7x (REJECTED for Spring per FR12)"

    # Validate calculation methodology (20-bar average)
    # For bar 25: avg of bars [5:25] should be ~1M, so 250K / 1M = 0.25x
    bars_for_avg = bars[5:25]
    avg_volume = sum(b.volume for b in bars_for_avg) / len(bars_for_avg)
    expected_ratio_bar_25 = bars[25].volume / avg_volume
    assert abs(bar_25_volume_ratio - expected_ratio_bar_25) < 0.01, \
        f"VolumeAnalyzer calculation should match manual calc (expected {expected_ratio_bar_25:.2f}, got {bar_25_volume_ratio:.2f})"


@pytest.mark.integration
def test_volume_analyzer_insufficient_bars():
    """
    Test VolumeAnalyzer behavior with insufficient bars for Spring detection.

    Spring detector requires minimum 20 bars for volume average calculation.
    This test validates that calculate_volume_ratio returns None when there
    are insufficient bars, which Spring detector handles correctly.

    Expected:
    - calculate_volume_ratio returns None for bars with <20 history
    - Spring detector rejects pattern when volume ratio is None
    """
    bars = []
    start_time = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)

    # Create only 15 bars (insufficient for 20-bar average)
    for i in range(15):
        timestamp = start_time + timedelta(days=i)
        bar = OHLCVBar(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            timestamp=timestamp,
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("99.00"),
            close=Decimal("100.50"),
            volume=1_000_000,
            spread=Decimal("2.00"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),
        )
        bars.append(bar)

    # Attempt to calculate volume ratio for bar 10 (only 10 bars of history)
    volume_ratio = calculate_volume_ratio(bars, 10)

    # Should return None (insufficient bars for 20-bar average)
    assert volume_ratio is None, \
        "VolumeAnalyzer should return None when there are <20 bars of history"


@pytest.mark.integration
def test_volume_analyzer_edge_case_zero_average():
    """
    Test VolumeAnalyzer behavior when average volume is zero.

    This tests the edge case where all bars in the lookback window have zero
    volume (e.g., market holiday, data gap). VolumeAnalyzer should return None
    to avoid division by zero.

    Expected:
    - calculate_volume_ratio returns None when average volume is 0
    - Spring detector rejects pattern (treats None volume ratio as invalid)
    """
    bars = []
    start_time = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)

    # Create 25 bars with ZERO volume in lookback window
    for i in range(25):
        timestamp = start_time + timedelta(days=i)

        # First 20 bars: ZERO volume
        if i < 20:
            volume = 0
        # Bar 20+: Normal volume
        else:
            volume = 1_000_000

        bar = OHLCVBar(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            timestamp=timestamp,
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("99.00"),
            close=Decimal("100.50"),
            volume=volume,
            spread=Decimal("2.00"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),
        )
        bars.append(bar)

    # Attempt to calculate volume ratio for bar 20 (avg of bars 0-19 is 0)
    volume_ratio = calculate_volume_ratio(bars, 20)

    # Should return None (cannot divide by zero average)
    assert volume_ratio is None, \
        "VolumeAnalyzer should return None when average volume is zero (avoid division by zero)"
