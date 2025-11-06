"""
Integration tests for SpringDetector multi-spring detection (Story 5.6.1).

This test suite validates the multi-spring iteration functionality of SpringDetector,
ensuring that all springs in a trading range are detected, tracked, and analyzed correctly.

Test Coverage:
--------------
- Task 17: Multi-spring accumulation cycle (AC 5)
- Realistic AAPL-style scenario with 3 springs showing declining volume
- Volume trend analysis (DECLINING/STABLE/RISING)
- Risk assessment (LOW/MODERATE/HIGH)
- Best spring selection using Wyckoff hierarchy (lowest volume = best)

Integration Points:
-------------------
- Story 5.1: detect_spring() for pattern detection
- Story 5.3: detect_test_confirmation() for test validation
- Story 5.4: calculate_spring_confidence() for confidence scoring
- Story 5.5: generate_spring_signal() for signal generation
- Task 2A: VolumeCache for O(1) volume lookups
- Task 25: analyze_spring_risk_profile() and analyze_volume_trend()

Author: Story 5.6.1 - SpringDetector Multi-Spring Iteration
"""

import pytest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from src.models.ohlcv import OHLCVBar
from src.models.pivot import Pivot, PivotType
from src.models.price_cluster import PriceCluster
from src.models.creek_level import CreekLevel
from src.models.touch_detail import TouchDetail
from src.models.trading_range import TradingRange, RangeStatus
from src.models.phase_classification import WyckoffPhase
from src.pattern_engine.detectors.spring_detector import SpringDetector


def create_aapl_accumulation_range(creek_level: Decimal) -> TradingRange:
    """
    Create realistic AAPL-style trading range for multi-spring testing.

    Args:
        creek_level: Support level (Creek) for the trading range

    Returns:
        TradingRange with Creek level and support/resistance clusters
    """
    base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

    # Create support pivots (3 touches at Creek level)
    support_pivots = []
    for i, idx in enumerate([10, 25, 40]):
        bar = OHLCVBar(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            timestamp=base_timestamp + timedelta(days=idx),
            open=creek_level - Decimal("1.00"),
            high=creek_level + Decimal("5.00"),
            low=creek_level - Decimal("2.00"),
            close=creek_level + Decimal("1.00"),
            volume=1_000_000,
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

    # Create resistance pivots (3 touches at resistance)
    resistance_pivots = []
    for i, idx in enumerate([15, 30, 45]):
        bar = OHLCVBar(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            timestamp=base_timestamp + timedelta(days=idx),
            open=creek_level + Decimal("15.00"),
            high=creek_level + Decimal("20.00"),
            low=creek_level + Decimal("14.00"),
            close=creek_level + Decimal("16.00"),
            volume=1_000_000,
            spread=Decimal("6.00"),
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
        average_price=creek_level + Decimal("20.00"),
        min_price=creek_level + Decimal("19.00"),
        max_price=creek_level + Decimal("21.00"),
        price_range=Decimal("2.00"),
        touch_count=3,
        cluster_type=PivotType.HIGH,
        std_deviation=Decimal("0.50"),
        timestamp_range=(resistance_pivots[0].timestamp, resistance_pivots[-1].timestamp),
    )

    # Create Creek level with strong support characteristics
    creek = CreekLevel(
        price=creek_level,
        absolute_low=creek_level - Decimal("1.00"),
        touch_count=3,
        touch_details=[
            TouchDetail(
                index=i,
                price=creek_level,
                volume=1_000_000,
                volume_ratio=Decimal("1.0"),
                close_position=Decimal("0.7"),
                rejection_wick=Decimal("0.5"),
                timestamp=base_timestamp + timedelta(days=idx),
            )
            for i, idx in enumerate([10, 25, 40])
        ],
        strength_score=80,  # Excellent support
        strength_rating="STRONG",
        last_test_timestamp=base_timestamp + timedelta(days=40),
        first_test_timestamp=base_timestamp + timedelta(days=10),
        hold_duration=30,
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
        resistance=creek_level + Decimal("20.00"),
        midpoint=creek_level + Decimal("9.00"),
        range_width=Decimal("22.00"),
        range_width_pct=Decimal("0.22"),
        start_index=0,
        end_index=70,
        duration=71,
        creek=creek,
        status=RangeStatus.ACTIVE,
    )


def create_three_spring_scenario(
    creek_level: Decimal,
    base_volume: int = 1_000_000
) -> list[OHLCVBar]:
    """
    Create realistic 3-spring accumulation scenario with declining volume.

    Wyckoff Pattern:
    ----------------
    Professional accumulation shows DECLINING volume through successive springs.
    This indicates supply exhaustion as fewer sellers remain with each test.

    Spring Sequence:
    ----------------
    - Spring 1 (Bar 25): 0.6x volume, 2.0% penetration, 3-bar recovery
    - Spring 2 (Bar 45): 0.5x volume, 2.5% penetration, 2-bar recovery
    - Spring 3 (Bar 65): 0.4x volume, 3.0% penetration, 1-bar recovery

    Expected Results:
    -----------------
    - history.spring_count == 3
    - history.volume_trend == "DECLINING" (0.6 → 0.5 → 0.4)
    - history.risk_level == "LOW" (declining volume = professional)
    - history.best_spring has volume_ratio == 0.4 (Spring 3, lowest volume)

    Args:
        creek_level: Support level for springs to penetrate below
        base_volume: Average volume for baseline calculation

    Returns:
        List[OHLCVBar] with 70 bars including 3 springs with tests
    """
    bars = []
    start_time = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)

    # Bars 0-24: Establish volume baseline (oscillate around base_volume)
    for i in range(25):
        timestamp = start_time + timedelta(days=i)
        volume = int(base_volume * (0.95 + (i % 3) * 0.05))  # 950K to 1.05M

        bar = OHLCVBar(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            timestamp=timestamp,
            open=creek_level + Decimal("2.00"),
            high=creek_level + Decimal("6.00"),
            low=creek_level + Decimal("1.00"),
            close=creek_level + Decimal("3.50"),
            volume=volume,
            spread=Decimal("5.00"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),
        )
        bars.append(bar)

    # ============================================================
    # SPRING 1: Bar 25 (0.6x volume, 2% penetration, 3-bar recovery)
    # ============================================================

    # Bar 25: Spring 1
    spring1_low = creek_level * Decimal("0.98")  # 2% below Creek
    spring1_bar = OHLCVBar(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        timestamp=start_time + timedelta(days=25),
        open=creek_level,
        high=creek_level + Decimal("2.00"),
        low=spring1_low,  # Penetrates 2% below Creek
        close=creek_level + Decimal("0.50"),
        volume=int(base_volume * 0.6),  # 0.6x volume
        spread=Decimal("2.50"),
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("0.6"),
    )
    bars.append(spring1_bar)

    # Bars 26-27: Recovery in progress
    for i in range(1, 3):
        timestamp = start_time + timedelta(days=25 + i)
        bar = OHLCVBar(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            timestamp=timestamp,
            open=creek_level + Decimal("0.50"),
            high=creek_level + Decimal("3.00"),
            low=creek_level - Decimal("0.50"),
            close=creek_level + Decimal("1.50"),
            volume=int(base_volume),
            spread=Decimal("3.50"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),
        )
        bars.append(bar)

    # Bar 28: Spring 1 recovery complete (3rd bar closes above Creek)
    bar = OHLCVBar(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        timestamp=start_time + timedelta(days=28),
        open=creek_level + Decimal("1.00"),
        high=creek_level + Decimal("4.00"),
        low=creek_level + Decimal("0.50"),
        close=creek_level + Decimal("3.00"),  # Recovery confirmed
        volume=int(base_volume),
        spread=Decimal("3.50"),
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("1.0"),
    )
    bars.append(bar)

    # Bars 29-33: Normal trading + Spring 1 test
    for i in range(29, 34):
        timestamp = start_time + timedelta(days=i)

        # Bar 33: Spring 1 test (lower volume)
        if i == 33:
            volume = int(base_volume * 0.5)  # Test with lower volume than spring
            low = spring1_low + Decimal("0.50")  # Approaches spring low
        else:
            volume = int(base_volume)
            low = creek_level + Decimal("0.50")

        bar = OHLCVBar(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            timestamp=timestamp,
            open=creek_level + Decimal("2.00"),
            high=creek_level + Decimal("5.00"),
            low=low,
            close=creek_level + Decimal("3.00"),
            volume=volume,
            spread=Decimal("4.50"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0") if i != 33 else Decimal("0.5"),
        )
        bars.append(bar)

    # ============================================================
    # SPRING 2: Bar 45 (0.5x volume, 2.5% penetration, 2-bar recovery)
    # ============================================================

    # Bars 34-44: Normal trading
    for i in range(34, 45):
        timestamp = start_time + timedelta(days=i)
        volume = int(base_volume * (0.95 + (i % 3) * 0.05))

        bar = OHLCVBar(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            timestamp=timestamp,
            open=creek_level + Decimal("2.00"),
            high=creek_level + Decimal("6.00"),
            low=creek_level + Decimal("1.00"),
            close=creek_level + Decimal("3.50"),
            volume=volume,
            spread=Decimal("5.00"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),
        )
        bars.append(bar)

    # Bar 45: Spring 2
    spring2_low = creek_level * Decimal("0.975")  # 2.5% below Creek
    spring2_bar = OHLCVBar(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        timestamp=start_time + timedelta(days=45),
        open=creek_level,
        high=creek_level + Decimal("2.00"),
        low=spring2_low,  # Penetrates 2.5% below Creek
        close=creek_level + Decimal("0.50"),
        volume=int(base_volume * 0.5),  # 0.5x volume (lower than Spring 1)
        spread=Decimal("2.50"),
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("0.5"),
    )
    bars.append(spring2_bar)

    # Bar 46: Spring 2 recovery in progress
    bar = OHLCVBar(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        timestamp=start_time + timedelta(days=46),
        open=creek_level + Decimal("0.50"),
        high=creek_level + Decimal("3.00"),
        low=creek_level - Decimal("0.50"),
        close=creek_level + Decimal("1.50"),
        volume=int(base_volume),
        spread=Decimal("3.50"),
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("1.0"),
    )
    bars.append(bar)

    # Bar 47: Spring 2 recovery complete (2nd bar closes above Creek)
    bar = OHLCVBar(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        timestamp=start_time + timedelta(days=47),
        open=creek_level + Decimal("1.00"),
        high=creek_level + Decimal("4.00"),
        low=creek_level + Decimal("0.50"),
        close=creek_level + Decimal("3.00"),  # Recovery confirmed
        volume=int(base_volume),
        spread=Decimal("3.50"),
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("1.0"),
    )
    bars.append(bar)

    # Bars 48-53: Normal trading + Spring 2 test
    for i in range(48, 54):
        timestamp = start_time + timedelta(days=i)

        # Bar 53: Spring 2 test (lower volume)
        if i == 53:
            volume = int(base_volume * 0.4)  # Test with lower volume than spring
            low = spring2_low + Decimal("0.50")  # Approaches spring low
        else:
            volume = int(base_volume)
            low = creek_level + Decimal("0.50")

        bar = OHLCVBar(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            timestamp=timestamp,
            open=creek_level + Decimal("2.00"),
            high=creek_level + Decimal("5.00"),
            low=low,
            close=creek_level + Decimal("3.00"),
            volume=volume,
            spread=Decimal("4.50"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0") if i != 53 else Decimal("0.4"),
        )
        bars.append(bar)

    # ============================================================
    # SPRING 3: Bar 65 (0.4x volume, 3% penetration, 1-bar recovery)
    # ============================================================

    # Bars 54-64: Normal trading
    for i in range(54, 65):
        timestamp = start_time + timedelta(days=i)
        volume = int(base_volume * (0.95 + (i % 3) * 0.05))

        bar = OHLCVBar(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            timestamp=timestamp,
            open=creek_level + Decimal("2.00"),
            high=creek_level + Decimal("6.00"),
            low=creek_level + Decimal("1.00"),
            close=creek_level + Decimal("3.50"),
            volume=volume,
            spread=Decimal("5.00"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),
        )
        bars.append(bar)

    # Bar 65: Spring 3 (BEST - lowest volume, fastest recovery)
    spring3_low = creek_level * Decimal("0.97")  # 3% below Creek
    spring3_bar = OHLCVBar(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        timestamp=start_time + timedelta(days=65),
        open=creek_level,
        high=creek_level + Decimal("2.00"),
        low=spring3_low,  # Penetrates 3% below Creek
        close=creek_level + Decimal("1.50"),  # Recovers in same bar!
        volume=int(base_volume * 0.4),  # 0.4x volume (LOWEST - best quality)
        spread=Decimal("3.50"),
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("0.4"),
    )
    bars.append(spring3_bar)

    # Bars 66-70: Normal trading + Spring 3 test
    for i in range(66, 71):
        timestamp = start_time + timedelta(days=i)

        # Bar 70: Spring 3 test (lower volume)
        if i == 70:
            volume = int(base_volume * 0.3)  # Test with lower volume than spring
            low = spring3_low + Decimal("0.50")  # Approaches spring low
        else:
            volume = int(base_volume)
            low = creek_level + Decimal("0.50")

        bar = OHLCVBar(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            timestamp=timestamp,
            open=creek_level + Decimal("2.00"),
            high=creek_level + Decimal("5.00"),
            low=low,
            close=creek_level + Decimal("3.00"),
            volume=volume,
            spread=Decimal("4.50"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0") if i != 70 else Decimal("0.3"),
        )
        bars.append(bar)

    return bars


@pytest.mark.integration
def test_three_spring_accumulation_cycle():
    """
    Task 17 / AC 5: Multi-spring accumulation cycle integration test.

    Purpose:
    --------
    Validates that SpringDetector correctly detects ALL springs in a trading range,
    tracks them chronologically, analyzes volume trends, and selects the best spring
    using Wyckoff quality hierarchy (lowest volume = best).

    Scenario:
    ---------
    AAPL 45-day accumulation with 3 springs showing DECLINING volume:
    - Spring 1 (Day 25): 0.6x volume, 2% penetration, 3-bar recovery
    - Spring 2 (Day 45): 0.5x volume, 2.5% penetration, 2-bar recovery
    - Spring 3 (Day 65): 0.4x volume, 3% penetration, 1-bar recovery (BEST)

    Expected:
    ---------
    - history.spring_count == 3 (all springs detected)
    - history.volume_trend == "DECLINING" (0.6 → 0.5 → 0.4)
    - history.risk_level == "LOW" (declining = professional accumulation)
    - history.best_spring.volume_ratio == 0.4 (Spring 3, lowest volume)
    - All springs ordered chronologically
    - At least 1 signal generated (springs with test confirmation)

    Wyckoff Context:
    ----------------
    > "Professional accumulation is characterized by DECLINING volume through
    > successive springs. Each spring tests lower with less selling pressure,
    > proving supply exhaustion. The final spring (lowest volume) is the best
    > entry signal as it shows maximum supply exhaustion."
    """
    # Setup
    creek_level = Decimal("100.00")
    trading_range = create_aapl_accumulation_range(creek_level)
    bars = create_three_spring_scenario(creek_level, base_volume=1_000_000)
    detector = SpringDetector()

    # Execute
    history = detector.detect_all_springs(
        range=trading_range,
        bars=bars,
        phase=WyckoffPhase.C
    )

    # ============================================================
    # VALIDATION: Spring Count (AC 1)
    # ============================================================
    assert history.spring_count == 3, \
        f"Should detect 3 springs (got {history.spring_count})"

    # ============================================================
    # VALIDATION: Volume Trend Analysis (AC 4)
    # ============================================================
    assert history.volume_trend == "DECLINING", \
        f"Volume trend should be DECLINING (got {history.volume_trend})"

    # ============================================================
    # VALIDATION: Risk Assessment (AC 4)
    # ============================================================
    assert history.risk_level == "LOW", \
        f"Risk level should be LOW for declining volume (got {history.risk_level})"

    # ============================================================
    # VALIDATION: Best Spring Selection (AC 4)
    # ============================================================
    assert history.best_spring is not None, "Best spring should be selected"
    assert history.best_spring.volume_ratio == Decimal("0.4"), \
        f"Best spring should have lowest volume 0.4x (got {history.best_spring.volume_ratio}x)"

    # ============================================================
    # VALIDATION: Chronological Ordering (AC 1)
    # ============================================================
    assert len(history.springs) == 3, "History should contain 3 springs"

    # Verify chronological order
    for i in range(len(history.springs) - 1):
        assert history.springs[i].bar.timestamp < history.springs[i + 1].bar.timestamp, \
            f"Springs should be in chronological order (spring {i} >= spring {i+1})"

    # ============================================================
    # VALIDATION: Volume Progression (AC 5)
    # ============================================================
    # Verify declining volume: Spring 1 (0.6x) → Spring 2 (0.5x) → Spring 3 (0.4x)
    volumes = [s.volume_ratio for s in history.springs]
    assert volumes[0] >= Decimal("0.55") and volumes[0] <= Decimal("0.65"), \
        f"Spring 1 volume should be ~0.6x (got {volumes[0]}x)"
    assert volumes[1] >= Decimal("0.45") and volumes[1] <= Decimal("0.55"), \
        f"Spring 2 volume should be ~0.5x (got {volumes[1]}x)"
    assert volumes[2] >= Decimal("0.35") and volumes[2] <= Decimal("0.45"), \
        f"Spring 3 volume should be ~0.4x (got {volumes[2]}x)"

    # Verify DECLINING pattern
    assert volumes[0] > volumes[1] > volumes[2], \
        "Volume should decline through springs (professional accumulation)"

    # ============================================================
    # VALIDATION: Signal Generation (AC 1)
    # ============================================================
    # At least one spring should generate a signal (has test confirmation)
    assert len(history.signals) >= 1, \
        f"At least 1 signal should be generated (got {len(history.signals)})"

    # ============================================================
    # VALIDATION: Best Signal Selection (AC 4)
    # ============================================================
    if len(history.signals) > 0:
        best_signal = detector.get_best_signal(history)
        assert best_signal is not None, "Best signal should be selected"
        assert best_signal.confidence >= 70, \
            f"Best signal should meet 70% confidence threshold (got {best_signal.confidence}%)"

    # ============================================================
    # SUCCESS: Log results for verification
    # ============================================================
    print("\n=== Three-Spring Accumulation Cycle Test Results ===")
    print(f"Spring count: {history.spring_count}")
    print(f"Volume trend: {history.volume_trend}")
    print(f"Risk level: {history.risk_level}")
    print(f"\nSpring Details:")
    for i, spring in enumerate(history.springs, 1):
        print(f"  Spring {i}: {spring.volume_ratio}x volume, "
              f"{spring.penetration_pct:.1%} penetration, "
              f"{spring.recovery_bars} bars recovery")
    print(f"\nBest Spring: Volume {history.best_spring.volume_ratio}x "
          f"(Spring {history.springs.index(history.best_spring) + 1})")
    print(f"Signals generated: {len(history.signals)}")
    if history.best_signal:
        print(f"Best signal: {history.best_signal.confidence}% confidence, "
              f"{history.best_signal.r_multiple}R\n")


@pytest.mark.integration
def test_multi_spring_no_springs_detected():
    """
    Task 20 / Edge Case: No springs in range (empty history).

    Purpose:
    --------
    Validates SpringDetector returns empty history when no springs detected.

    Expected:
    ---------
    - history.spring_count == 0
    - history.volume_trend == "STABLE" (default for no springs)
    - history.risk_level == "MODERATE" (default for no springs)
    - history.best_spring == None
    - history.signals == [] (empty list)
    """
    creek_level = Decimal("100.00")
    trading_range = create_aapl_accumulation_range(creek_level)

    # Create bars with NO springs (price stays above Creek)
    bars = []
    start_time = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)
    base_volume = 1_000_000

    for i in range(30):
        timestamp = start_time + timedelta(days=i)
        volume = int(base_volume * (0.95 + (i % 3) * 0.05))

        bar = OHLCVBar(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            timestamp=timestamp,
            open=creek_level + Decimal("2.00"),
            high=creek_level + Decimal("6.00"),
            low=creek_level + Decimal("1.00"),  # Never penetrates Creek
            close=creek_level + Decimal("3.50"),
            volume=volume,
            spread=Decimal("5.00"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),
        )
        bars.append(bar)

    detector = SpringDetector()

    # Execute
    history = detector.detect_all_springs(
        range=trading_range,
        bars=bars,
        phase=WyckoffPhase.C
    )

    # Validate
    assert history.spring_count == 0, "Should detect 0 springs"
    assert history.volume_trend == "STABLE", "Default volume trend for no springs"
    assert history.risk_level == "MODERATE", "Default risk level for no springs"
    assert history.best_spring is None, "No best spring when no springs"
    assert len(history.signals) == 0, "No signals when no springs"

    print("\n=== No Springs Detected Test Results ===")
    print(f"Spring count: {history.spring_count}")
    print(f"Volume trend: {history.volume_trend}")
    print(f"Risk level: {history.risk_level}")
    print("Status: No springs detected (price never penetrated Creek)\n")


@pytest.mark.integration
def test_multi_spring_single_spring_no_test():
    """
    Task 20 / Edge Case: Single spring without test confirmation.

    Purpose:
    --------
    Validates SpringDetector handles springs without test confirmation.
    Per FR13, springs without tests should be added to history but NOT generate signals.

    Expected:
    ---------
    - history.spring_count == 1
    - history.signals == [] (empty - no test confirmation)
    - history.best_spring exists
    - history.risk_level based on single spring volume
    """
    creek_level = Decimal("100.00")
    trading_range = create_aapl_accumulation_range(creek_level)

    # Create bars with ONE spring (no test bars)
    bars = []
    start_time = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)
    base_volume = 1_000_000

    # Bars 0-24: Baseline
    for i in range(25):
        timestamp = start_time + timedelta(days=i)
        volume = int(base_volume * (0.95 + (i % 3) * 0.05))

        bar = OHLCVBar(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            timestamp=timestamp,
            open=creek_level + Decimal("2.00"),
            high=creek_level + Decimal("6.00"),
            low=creek_level + Decimal("1.00"),
            close=creek_level + Decimal("3.50"),
            volume=volume,
            spread=Decimal("5.00"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),
        )
        bars.append(bar)

    # Bar 25: Spring (0.4x volume, 2% penetration)
    spring_low = creek_level * Decimal("0.98")
    spring_bar = OHLCVBar(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        timestamp=start_time + timedelta(days=25),
        open=creek_level,
        high=creek_level + Decimal("2.00"),
        low=spring_low,
        close=creek_level + Decimal("1.50"),  # Recovers in 1 bar
        volume=int(base_volume * 0.4),
        spread=Decimal("3.50"),
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("0.4"),
    )
    bars.append(spring_bar)

    # Bars 26-30: Normal trading (NO TEST - price stays above spring low)
    for i in range(26, 31):
        timestamp = start_time + timedelta(days=i)
        volume = int(base_volume)

        bar = OHLCVBar(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            timestamp=timestamp,
            open=creek_level + Decimal("2.00"),
            high=creek_level + Decimal("6.00"),
            low=creek_level + Decimal("1.50"),  # Never approaches spring low
            close=creek_level + Decimal("3.50"),
            volume=volume,
            spread=Decimal("5.00"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),
        )
        bars.append(bar)

    detector = SpringDetector()

    # Execute
    history = detector.detect_all_springs(
        range=trading_range,
        bars=bars,
        phase=WyckoffPhase.C
    )

    # Validate
    assert history.spring_count == 1, "Should detect 1 spring"
    assert len(history.signals) == 0, \
        "No signals should be generated without test confirmation (FR13)"
    assert history.best_spring is not None, "Best spring should exist"
    assert history.best_spring.volume_ratio == Decimal("0.4"), \
        "Best spring should have 0.4x volume"

    # Risk level based on single spring volume (0.4x = MODERATE range)
    assert history.risk_level in ["LOW", "MODERATE"], \
        "Risk level should be LOW or MODERATE for 0.4x volume"

    print("\n=== Single Spring No Test Test Results ===")
    print(f"Spring count: {history.spring_count}")
    print(f"Signals generated: {len(history.signals)} (expected 0 - no test)")
    print(f"Best spring volume: {history.best_spring.volume_ratio}x")
    print(f"Risk level: {history.risk_level}")
    print("Status: Spring detected but NOT tradeable (FR13: no test confirmation)\n")


@pytest.mark.integration
def test_spring_invalidation_by_breakdown():
    """
    Task 19 / AC 7: Spring invalidation test (range breakdown after spring).

    Purpose:
    --------
    Validates that SpringDetector correctly handles range invalidation when
    price breaks down >5% below Creek after spring recovery.

    Expected Behavior:
    ------------------
    1. Detect first spring successfully
    2. Price breaks down >5% below Creek in next 10 bars after recovery
    3. range.status marked as BREAKOUT
    4. No additional springs detected after invalidation
    5. Invalidation event logged with context

    Wyckoff Context:
    ----------------
    > "If price breaks down significantly below Creek after a Spring, this
    > invalidates the accumulation campaign. The Spring 'failed' and the range
    > is no longer valid for long entries."
    """
    creek_level = Decimal("100.00")
    trading_range = create_aapl_accumulation_range(creek_level)

    # Create bars with spring + breakdown scenario
    bars = []
    start_time = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)
    base_volume = 1_000_000

    # Bars 0-24: Baseline
    for i in range(25):
        timestamp = start_time + timedelta(days=i)
        volume = int(base_volume * (0.95 + (i % 3) * 0.05))

        bar = OHLCVBar(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            timestamp=timestamp,
            open=creek_level + Decimal("2.00"),
            high=creek_level + Decimal("6.00"),
            low=creek_level + Decimal("1.00"),
            close=creek_level + Decimal("3.50"),
            volume=volume,
            spread=Decimal("5.00"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),
        )
        bars.append(bar)

    # Bar 25: Spring (0.4x volume, 2% penetration)
    spring_low = creek_level * Decimal("0.98")
    spring_bar = OHLCVBar(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        timestamp=start_time + timedelta(days=25),
        open=creek_level,
        high=creek_level + Decimal("2.00"),
        low=spring_low,
        close=creek_level + Decimal("1.50"),  # Recovers in 1 bar
        volume=int(base_volume * 0.4),
        spread=Decimal("3.50"),
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("0.4"),
    )
    bars.append(spring_bar)

    # Bars 26-29: Normal trading after spring
    for i in range(26, 30):
        timestamp = start_time + timedelta(days=i)
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

    # Bar 30: BREAKDOWN >5% below Creek (invalidates spring)
    breakdown_price = creek_level * Decimal("0.94")  # 6% below Creek
    breakdown_bar = OHLCVBar(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        timestamp=start_time + timedelta(days=30),
        open=creek_level,
        high=creek_level + Decimal("1.00"),
        low=breakdown_price,  # Breaks down significantly
        close=breakdown_price + Decimal("0.50"),
        volume=int(base_volume * 1.5),  # High volume breakdown
        spread=Decimal("6.50"),
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("1.5"),
    )
    bars.append(breakdown_bar)

    # Bars 31-40: Continued breakdown (should NOT detect new springs)
    for i in range(31, 41):
        timestamp = start_time + timedelta(days=i)
        volume = int(base_volume)

        bar = OHLCVBar(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            timestamp=timestamp,
            open=breakdown_price + Decimal("1.00"),
            high=breakdown_price + Decimal("3.00"),
            low=breakdown_price - Decimal("1.00"),
            close=breakdown_price + Decimal("1.50"),
            volume=volume,
            spread=Decimal("4.00"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),
        )
        bars.append(bar)

    detector = SpringDetector()

    # Execute
    history = detector.detect_all_springs(
        range=trading_range,
        bars=bars,
        phase=WyckoffPhase.C
    )

    # ============================================================
    # VALIDATION: Spring Invalidation (AC 7)
    # ============================================================

    # Check range status
    assert trading_range.status == RangeStatus.BREAKOUT, \
        f"Range should be marked as BREAKOUT after breakdown (got {trading_range.status})"

    # Should NOT detect additional springs after invalidation
    assert history.spring_count <= 1, \
        f"Should detect at most 1 spring before invalidation (got {history.spring_count})"

    print("\n=== Spring Invalidation Test Results (Task 19 / AC 7) ===")
    print(f"Springs detected: {history.spring_count}")
    print(f"Range status: {trading_range.status}")
    print(f"Breakdown bar: Day 30 (6% below Creek)")
    print(f"Status: ✅ Range invalidated, no additional springs detected\n")
