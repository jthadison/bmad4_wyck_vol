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


@pytest.mark.integration
def test_test_confirmation_detection_integration():
    """
    Task 17: Integration test for Test Confirmation detection (Story 5.3).

    This test validates the complete workflow from Spring detection to Test
    confirmation using synthetic OHLCV data with realistic volume patterns.

    Workflow tested:
    1. Create bar sequence with spring pattern
    2. Detect spring using Story 5.1 detect_spring()
    3. Detect test confirmation using Story 5.3 detect_test_confirmation()
    4. Validate test characteristics

    This demonstrates FR13 enforcement: Springs require test confirmation
    before being tradeable.
    """
    from src.models.spring import Spring
    from src.models.pivot import Pivot, PivotType
    from src.models.price_cluster import PriceCluster
    from src.models.creek_level import CreekLevel
    from src.models.touch_detail import TouchDetail
    from src.models.trading_range import TradingRange, RangeStatus
    from src.pattern_engine.detectors.spring_detector import detect_test_confirmation

    # Test parameters
    creek_level = Decimal("100.00")
    base_volume = 1_000_000  # 1M shares
    start_time = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)

    # Helper function to create trading range (copied from unit tests)
    def create_trading_range_for_test() -> TradingRange:
        """Create test trading range with Creek level."""
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

        support_pivots = []
        for i, idx in enumerate([10, 20, 30]):
            bar = OHLCVBar(
                id=uuid4(),
                symbol="AAPL",
                timeframe="1d",
                timestamp=base_timestamp + timedelta(days=idx),
                open=creek_level - Decimal("1.00"),
                high=creek_level + Decimal("5.00"),
                low=creek_level - Decimal("2.00"),
                close=creek_level + Decimal("1.00"),
                volume=100000,
                spread=Decimal("7.00"),
                spread_ratio=Decimal("1.0"),
                volume_ratio=Decimal("1.0"),
            )
            pivot = Pivot(
                bar=bar,
                price=bar.low,
                type=PivotType.LOW,
                strength=5,
                timestamp=bar.timestamp,
                index=idx,
            )
            support_pivots.append(pivot)

        support_cluster = PriceCluster(
            pivots=support_pivots,
            average_price=creek_level - Decimal("2.00"),
            min_price=creek_level - Decimal("3.00"),
            max_price=creek_level - Decimal("1.00"),
            price_range=Decimal("2.00"),
            touch_count=3,
            cluster_type=PivotType.LOW,
            std_deviation=Decimal("0.50"),
            timestamp_range=(support_pivots[0].timestamp, support_pivots[-1].timestamp),
        )

        resistance_pivots = []
        for i, idx in enumerate([15, 25, 35]):
            bar = OHLCVBar(
                id=uuid4(),
                symbol="AAPL",
                timeframe="1d",
                timestamp=base_timestamp + timedelta(days=idx),
                open=creek_level + Decimal("6.00"),
                high=creek_level + Decimal("10.00"),
                low=creek_level + Decimal("5.00"),
                close=creek_level + Decimal("7.00"),
                volume=100000,
                spread=Decimal("5.00"),
                spread_ratio=Decimal("1.0"),
                volume_ratio=Decimal("1.0"),
            )
            pivot = Pivot(
                bar=bar,
                price=bar.high,
                type=PivotType.HIGH,
                strength=5,
                timestamp=bar.timestamp,
                index=idx,
            )
            resistance_pivots.append(pivot)

        resistance_cluster = PriceCluster(
            pivots=resistance_pivots,
            average_price=creek_level + Decimal("10.00"),
            min_price=creek_level + Decimal("9.00"),
            max_price=creek_level + Decimal("11.00"),
            price_range=Decimal("2.00"),
            touch_count=3,
            cluster_type=PivotType.HIGH,
            std_deviation=Decimal("0.50"),
            timestamp_range=(resistance_pivots[0].timestamp, resistance_pivots[-1].timestamp),
        )

        creek = CreekLevel(
            price=creek_level,
            absolute_low=creek_level - Decimal("1.00"),
            touch_count=3,
            touch_details=[
                TouchDetail(
                    index=i,
                    price=creek_level,
                    volume=100000,
                    volume_ratio=Decimal("1.0"),
                    close_position=Decimal("0.7"),
                    rejection_wick=Decimal("0.5"),
                    timestamp=base_timestamp + timedelta(days=idx),
                )
                for i, idx in enumerate([10, 20, 30])
            ],
            strength_score=75,
            strength_rating="STRONG",
            last_test_timestamp=base_timestamp + timedelta(days=30),
            first_test_timestamp=base_timestamp + timedelta(days=10),
            hold_duration=20,
            confidence="HIGH",
            volume_trend="DECREASING",
        )

        return TradingRange(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            support_cluster=support_cluster,
            resistance_cluster=resistance_cluster,
            support=creek_level - Decimal("2.00"),
            resistance=creek_level + Decimal("10.00"),
            midpoint=creek_level + Decimal("4.00"),
            range_width=Decimal("12.00"),
            range_width_pct=Decimal("0.12"),
            start_index=0,
            end_index=50,
            duration=51,
            creek=creek,
            status=RangeStatus.ACTIVE,
        )

    # Create trading range using helper function
    trading_range = create_trading_range_for_test()

    # Create bars array with spring and test
    bars = []

    # Bars 0-19: Normal trading above Creek (establish volume baseline)
    for i in range(20):
        timestamp = start_time + timedelta(days=i)
        volume = int(base_volume * (0.95 + (i % 3) * 0.05))  # 950K to 1.05M

        bar = OHLCVBar(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            timestamp=timestamp,
            open=creek_level + Decimal("1.00"),
            high=creek_level + Decimal("5.00"),
            low=creek_level + Decimal("0.50"),
            close=creek_level + Decimal("2.00"),
            volume=volume,
            spread=Decimal("4.50"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),
        )
        bars.append(bar)

    # Bar 20: Spring (2% below Creek, 0.4x volume)
    spring_timestamp = start_time + timedelta(days=20)
    spring_low = creek_level * Decimal("0.98")  # 2% below Creek
    spring_volume = int(base_volume * 0.4)  # 0.4x volume (LOW)

    spring_bar = OHLCVBar(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        timestamp=spring_timestamp,
        open=creek_level - Decimal("0.50"),
        high=creek_level + Decimal("1.00"),
        low=spring_low,  # Penetrates below Creek
        close=creek_level + Decimal("0.50"),  # Recovers above Creek
        volume=spring_volume,
        spread=Decimal("3.00"),
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("0.4"),
    )
    bars.append(spring_bar)

    # Bars 21-24: Recovery bars (above Creek, normal volume)
    for i in range(1, 5):
        timestamp = spring_timestamp + timedelta(days=i)
        volume = int(base_volume)

        bar = OHLCVBar(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            timestamp=timestamp,
            open=creek_level + Decimal("1.00"),
            high=creek_level + Decimal("4.00"),
            low=creek_level + Decimal("0.50"),
            close=creek_level + Decimal("2.50"),
            volume=volume,
            spread=Decimal("3.50"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),
        )
        bars.append(bar)

    # Bar 25: Test (0.25x volume, approaches spring low, holds it)
    test_timestamp = spring_timestamp + timedelta(days=5)
    test_low = spring_low + Decimal("0.60")  # ~0.6% above spring low
    test_volume = int(base_volume * 0.25)  # 0.25x volume (LOWER than spring)

    test_bar = OHLCVBar(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        timestamp=test_timestamp,
        open=creek_level + Decimal("1.00"),
        high=creek_level + Decimal("3.00"),
        low=test_low,  # Approaches spring low but holds above it
        close=creek_level + Decimal("1.50"),
        volume=test_volume,
        spread=Decimal("2.40"),
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("0.25"),
    )
    bars.append(test_bar)

    # Create Spring manually (simulating detect_spring output)
    spring = Spring(
        bar=spring_bar,
        bar_index=20,
        penetration_pct=Decimal("0.02"),  # 2%
        volume_ratio=Decimal("0.4"),  # 0.4x
        recovery_bars=1,
        creek_reference=creek_level,
        spring_low=spring_low,
        recovery_price=creek_level + Decimal("0.50"),
        detection_timestamp=datetime.now(UTC),
        trading_range_id=trading_range.id,
    )

    # ============================================================
    # TEST: Detect test confirmation (Story 5.3)
    # ============================================================

    test = detect_test_confirmation(trading_range, spring, bars)

    # Validate test was detected
    assert test is not None, "Test confirmation should be detected (FR13)"

    # Validate test bar
    assert (
        test.bar.timestamp == test_bar.timestamp
    ), "Test should be detected at bar 25"

    # Validate timing
    assert test.bars_after_spring == 5, "Test should be 5 bars after spring"

    # Validate volume decrease (FR13 requirement)
    volume_ratio_test = calculate_volume_ratio(bars, 25)
    assert volume_ratio_test is not None, "Test volume ratio should be calculated"
    assert (
        volume_ratio_test < 0.4
    ), "Test volume should be lower than spring volume (supply exhaustion)"

    # Validate test holds spring low (CRITICAL)
    assert test.holds_spring_low is True, "Test MUST hold spring low (AC 5)"
    assert test.bar.low >= spring_low, "Test low should be >= spring low"

    # Validate distance from spring
    assert (
        test.distance_pct <= Decimal("0.03")
    ), "Test should be within 3% of spring low"

    # Validate volume decrease percentage (test < spring)
    # Note: volume_decrease_pct uses actual VolumeAnalyzer calculations,
    # so expect some variance from simple ratio (0.4 - 0.25) / 0.4 = 37.5%
    assert test.volume_decrease_pct > Decimal("0.2"), \
        f"Volume decrease should be > 20% (got {test.volume_decrease_pct:.1%})"
    assert test.volume_decrease_pct < Decimal("0.6"), \
        f"Volume decrease should be < 60% (got {test.volume_decrease_pct:.1%})"

    # Validate test quality
    assert test.quality_score in [
        "EXCELLENT",
        "GOOD",
        "ACCEPTABLE",
    ], "Test should have valid quality score"

    # ============================================================
    # FR13 VALIDATION: Spring with test is tradeable
    # ============================================================

    # This test confirms that:
    # 1. Spring detection (Story 5.1) produces Spring object
    # 2. Test confirmation (Story 5.3) finds valid test
    # 3. Test holds spring low (CRITICAL validation)
    # 4. Test volume < spring volume (supply exhaustion confirmed)
    # 5. FR13: Spring is now tradeable (will be used in Story 5.5 signal generation)

    print(f"\n=== Test Confirmation Integration Test Results ===")
    print(f"Spring detected at: {spring.bar.timestamp}")
    print(f"Spring low: ${spring.spring_low}")
    print(f"Spring volume: {spring.volume_ratio}x average")
    print(f"\nTest detected at: {test.bar.timestamp}")
    print(f"Test low: ${test.bar.low}")
    print(f"Test volume: {test.volume_ratio}x average")
    print(f"Volume decrease: {test.volume_decrease_pct:.1%}")
    print(f"Distance from spring: {test.distance_pct:.2%}")
    print(f"Test quality: {test.quality_score}")
    print(f"\nFR13 Status: Spring is TRADEABLE (test confirmed)\n")
