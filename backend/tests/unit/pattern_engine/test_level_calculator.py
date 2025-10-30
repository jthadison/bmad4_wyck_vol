"""
Unit tests for Creek level calculation.

Tests volume-weighted averaging, strength scoring components, and validation
with synthetic test data.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.models.ohlcv import OHLCVBar
from src.models.pivot import Pivot, PivotType
from src.models.price_cluster import PriceCluster
from src.models.touch_detail import TouchDetail
from src.models.trading_range import TradingRange
from src.models.volume_analysis import VolumeAnalysis
from src.pattern_engine.level_calculator import (
    _assess_confidence,
    _calculate_weighted_price,
    _score_hold_duration,
    _score_rejection_wicks,
    _score_rejection_wicks_ice,
    _score_touch_count,
    _score_volume_trend,
    calculate_creek_level,
    calculate_ice_level,
)

# ============================================================================
# Test Fixtures and Helpers
# ============================================================================


def create_test_bar(
    symbol: str = "TEST",
    timeframe: str = "1d",
    open_price: Decimal = Decimal("100.00"),
    high: Decimal = Decimal("105.00"),
    low: Decimal = Decimal("95.00"),
    close: Decimal = Decimal("100.00"),
    volume: int = 1000000,
    timestamp: datetime = None,
    index: int = 0,
) -> OHLCVBar:
    """Create test OHLCV bar"""
    if timestamp is None:
        timestamp = datetime.now(UTC) + timedelta(days=index)

    return OHLCVBar(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        spread=high - low,
    )


def create_test_pivot(
    price: Decimal, index: int, symbol: str = "TEST", timeframe: str = "1d"
) -> Pivot:
    """Create test Pivot LOW object"""
    bar = create_test_bar(
        symbol=symbol,
        timeframe=timeframe,
        high=price + Decimal("5.00"),
        low=price,
        close=price + Decimal("3.50"),  # Upper half close (70% rejection wick)
        timestamp=datetime.now(UTC) + timedelta(days=index),
        index=index,
    )

    return Pivot(
        bar=bar, price=price, type=PivotType.LOW, strength=5, timestamp=bar.timestamp, index=index
    )


def create_test_pivot_high(
    price: Decimal, index: int, symbol: str = "TEST", timeframe: str = "1d"
) -> Pivot:
    """Create test Pivot HIGH object for Ice level testing"""
    bar = create_test_bar(
        symbol=symbol,
        timeframe=timeframe,
        high=price,
        low=price - Decimal("5.00"),
        close=price - Decimal("3.50"),  # Lower 30% close (70% upper wick rejection)
        timestamp=datetime.now(UTC) + timedelta(days=index),
        index=index,
    )

    return Pivot(
        bar=bar, price=price, type=PivotType.HIGH, strength=5, timestamp=bar.timestamp, index=index
    )


def create_touch_detail(
    index: int,
    price: Decimal,
    volume: int,
    volume_ratio: Decimal,
    rejection_wick: Decimal = Decimal("0.7"),
) -> TouchDetail:
    """Create TouchDetail for testing"""
    return TouchDetail(
        index=index,
        price=price,
        volume=volume,
        volume_ratio=volume_ratio,
        close_position=Decimal("0.7"),
        rejection_wick=rejection_wick,
        timestamp=datetime.now(UTC) + timedelta(days=index),
    )


def create_test_trading_range(
    support_pivots: list[Pivot], resistance_pivots: list[Pivot], quality_score: int = 80
) -> TradingRange:
    """Create test TradingRange with support and resistance clusters"""
    # Create support cluster
    support_prices = [p.price for p in support_pivots]
    support_avg = sum(support_prices) / len(support_prices)
    support_min = min(support_prices)
    support_max = max(support_prices)
    support_cluster = PriceCluster(
        pivots=support_pivots,
        average_price=support_avg,
        min_price=support_min,
        max_price=support_max,
        price_range=support_max - support_min,
        touch_count=len(support_pivots),
        cluster_type=PivotType.LOW,
        std_deviation=Decimal("0.50"),
        timestamp_range=(
            min(p.timestamp for p in support_pivots),
            max(p.timestamp for p in support_pivots),
        ),
    )

    # Create resistance cluster
    resistance_prices = [p.price for p in resistance_pivots]
    resistance_avg = sum(resistance_prices) / len(resistance_prices)
    resistance_min = min(resistance_prices)
    resistance_max = max(resistance_prices)
    resistance_cluster = PriceCluster(
        pivots=resistance_pivots,
        average_price=resistance_avg,
        min_price=resistance_min,
        max_price=resistance_max,
        price_range=resistance_max - resistance_min,
        touch_count=len(resistance_pivots),
        cluster_type=PivotType.HIGH,
        std_deviation=Decimal("0.50"),
        timestamp_range=(
            min(p.timestamp for p in resistance_pivots),
            max(p.timestamp for p in resistance_pivots),
        ),
    )

    # Calculate range metrics
    range_width = resistance_avg - support_avg
    range_width_pct = (range_width / support_avg).quantize(Decimal("0.0001"))

    # Get start/end indices
    all_pivots = support_pivots + resistance_pivots
    start_index = min(p.index for p in all_pivots)
    end_index = max(p.index for p in all_pivots)
    duration = end_index - start_index + 1

    trading_range = TradingRange(
        symbol="TEST",
        timeframe="1d",
        support_cluster=support_cluster,
        resistance_cluster=resistance_cluster,
        support=support_avg,
        resistance=resistance_avg,
        midpoint=((support_avg + resistance_avg) / 2).quantize(Decimal("0.00000001")),
        range_width=range_width,
        range_width_pct=range_width_pct,
        start_index=start_index,
        end_index=end_index,
        duration=duration,
        quality_score=quality_score,
    )

    return trading_range


# ============================================================================
# Task 17: Test Volume-Weighted Averaging (AC 8)
# ============================================================================


def test_creek_volume_weighted_average():
    """
    Test volume-weighted average with known volumes and prices.

    Scenario:
        Pivot 1: $100, volume 1M
        Pivot 2: $101, volume 2M
        Pivot 3: $102, volume 1M
        Expected: (100*1M + 101*2M + 102*1M) / 4M = $101.00
    """
    touches = [
        create_touch_detail(10, Decimal("100.00"), 1000000, Decimal("1.5")),
        create_touch_detail(18, Decimal("101.00"), 2000000, Decimal("1.0")),
        create_touch_detail(26, Decimal("102.00"), 1000000, Decimal("0.8")),
    ]

    weighted_price = _calculate_weighted_price(touches)

    # Expected: (100*1M + 101*2M + 102*1M) / 4M = 404M / 4M = 101.00
    assert weighted_price == Decimal("101.00"), f"Expected $101.00, got ${weighted_price}"


def test_creek_volume_weighted_average_equal_volumes():
    """Test weighted average with equal volumes (should equal simple average)"""
    touches = [
        create_touch_detail(10, Decimal("100.00"), 1000000, Decimal("1.0")),
        create_touch_detail(18, Decimal("101.00"), 1000000, Decimal("1.0")),
        create_touch_detail(26, Decimal("102.00"), 1000000, Decimal("1.0")),
    ]

    weighted_price = _calculate_weighted_price(touches)

    # Expected: (100 + 101 + 102) / 3 = 101.00
    assert weighted_price == Decimal("101.00"), f"Expected $101.00, got ${weighted_price}"


def test_creek_volume_weighted_average_high_volume_outlier():
    """Test weighted average with one high-volume outlier"""
    touches = [
        create_touch_detail(10, Decimal("100.00"), 1000000, Decimal("1.0")),
        create_touch_detail(18, Decimal("105.00"), 5000000, Decimal("2.0")),  # High volume
        create_touch_detail(26, Decimal("100.00"), 1000000, Decimal("0.8")),
    ]

    weighted_price = _calculate_weighted_price(touches)

    # Expected: (100*1M + 105*5M + 100*1M) / 7M = 725M / 7M = 103.57
    expected = Decimal("103.571428571428571428571428571")
    assert abs(weighted_price - expected) < Decimal(
        "0.01"
    ), f"Expected ~$103.57, got ${weighted_price}"


# ============================================================================
# Task 18: Test Strength Scoring Components (AC 5)
# ============================================================================


def test_score_touch_count():
    """Test touch count scoring: 5→40, 4→30, 3→20, 2→10"""
    # 5 touches → 40 pts
    touches_5 = [
        create_touch_detail(i * 8, Decimal("100.00"), 1000000, Decimal("1.0")) for i in range(5)
    ]
    assert _score_touch_count(touches_5) == 40

    # 4 touches → 30 pts
    touches_4 = [
        create_touch_detail(i * 8, Decimal("100.00"), 1000000, Decimal("1.0")) for i in range(4)
    ]
    assert _score_touch_count(touches_4) == 30

    # 3 touches → 20 pts
    touches_3 = [
        create_touch_detail(i * 8, Decimal("100.00"), 1000000, Decimal("1.0")) for i in range(3)
    ]
    assert _score_touch_count(touches_3) == 20

    # 2 touches → 10 pts (minimum)
    touches_2 = [
        create_touch_detail(i * 8, Decimal("100.00"), 1000000, Decimal("1.0")) for i in range(2)
    ]
    assert _score_touch_count(touches_2) == 10


def test_score_volume_trend_decreasing():
    """Test volume trend scoring: decreasing volume → 30 pts (accumulation)"""
    touches = [
        create_touch_detail(10, Decimal("100.00"), 2000000, Decimal("2.0")),
        create_touch_detail(18, Decimal("100.00"), 1500000, Decimal("1.5")),
        create_touch_detail(26, Decimal("100.00"), 1000000, Decimal("1.0")),
        create_touch_detail(34, Decimal("100.00"), 500000, Decimal("0.5")),
    ]

    score, trend = _score_volume_trend(touches)

    assert score == 30, f"Expected 30 pts for decreasing volume, got {score}"
    assert trend == "DECREASING", f"Expected DECREASING, got {trend}"


def test_score_volume_trend_flat():
    """Test volume trend scoring: flat volume → 15 pts (neutral)"""
    touches = [
        create_touch_detail(10, Decimal("100.00"), 1000000, Decimal("1.0")),
        create_touch_detail(18, Decimal("100.00"), 1100000, Decimal("1.1")),
        create_touch_detail(26, Decimal("100.00"), 900000, Decimal("0.9")),
        create_touch_detail(34, Decimal("100.00"), 1000000, Decimal("1.0")),
    ]

    score, trend = _score_volume_trend(touches)

    assert score == 15, f"Expected 15 pts for flat volume, got {score}"
    assert trend == "FLAT", f"Expected FLAT, got {trend}"


def test_score_volume_trend_increasing():
    """Test volume trend scoring: increasing volume → 0 pts (distribution)"""
    touches = [
        create_touch_detail(10, Decimal("100.00"), 500000, Decimal("0.5")),
        create_touch_detail(18, Decimal("100.00"), 1000000, Decimal("1.0")),
        create_touch_detail(26, Decimal("100.00"), 1500000, Decimal("1.5")),
        create_touch_detail(34, Decimal("100.00"), 2000000, Decimal("2.0")),
    ]

    score, trend = _score_volume_trend(touches)

    assert score == 0, f"Expected 0 pts for increasing volume, got {score}"
    assert trend == "INCREASING", f"Expected INCREASING, got {trend}"


def test_score_rejection_wicks():
    """Test rejection wick scoring: high→20, moderate→15, low→5"""
    # High rejection (avg 0.8) → 20 pts
    touches_high = [
        create_touch_detail(10, Decimal("100.00"), 1000000, Decimal("1.0"), Decimal("0.8")),
        create_touch_detail(18, Decimal("100.00"), 1000000, Decimal("1.0"), Decimal("0.8")),
        create_touch_detail(26, Decimal("100.00"), 1000000, Decimal("1.0"), Decimal("0.8")),
    ]
    assert _score_rejection_wicks(touches_high) == 20

    # Moderate rejection (avg 0.5) → 15 pts
    touches_mod = [
        create_touch_detail(10, Decimal("100.00"), 1000000, Decimal("1.0"), Decimal("0.5")),
        create_touch_detail(18, Decimal("100.00"), 1000000, Decimal("1.0"), Decimal("0.5")),
    ]
    assert _score_rejection_wicks(touches_mod) == 15

    # Low rejection (avg 0.2) → 5 pts
    touches_low = [
        create_touch_detail(10, Decimal("100.00"), 1000000, Decimal("1.0"), Decimal("0.2")),
        create_touch_detail(18, Decimal("100.00"), 1000000, Decimal("1.0"), Decimal("0.2")),
    ]
    assert _score_rejection_wicks(touches_low) == 5


def test_score_hold_duration():
    """Test hold duration scoring: 30→10, 20→8, 10→5, 5→2"""
    assert _score_hold_duration(30) == 10  # Very strong
    assert _score_hold_duration(20) == 8  # Strong
    assert _score_hold_duration(10) == 5  # Good
    assert _score_hold_duration(5) == 2  # Weak


# ============================================================================
# Task 19: Test Perfect Creek (100 score) (AC 5, 6)
# ============================================================================


def test_perfect_creek_100_score():
    """
    Test perfect creek scenario with 100 score.

    Scenario:
        - 5 touches (40 pts)
        - Decreasing volume: 2.0x → 1.5x → 1.0x → 0.8x → 0.5x (30 pts)
        - High rejection wicks: avg 0.8 (20 pts)
        - Long hold: 30 bars (10 pts)
        - Total: 100 pts
    """
    # Create 5 support pivots with decreasing volume
    support_pivots = [
        create_test_pivot(Decimal("100.00"), 10),
        create_test_pivot(Decimal("100.50"), 18),
        create_test_pivot(Decimal("100.20"), 26),
        create_test_pivot(Decimal("100.80"), 34),
        create_test_pivot(Decimal("100.30"), 40),  # 30 bars duration
    ]

    # Create resistance pivots (need 2 minimum) - using HIGH type
    resistance_bar_15 = create_test_bar(low=Decimal("105.00"), high=Decimal("110.00"), index=15)
    resistance_pivot_15 = Pivot(
        bar=resistance_bar_15,
        price=Decimal("110.00"),
        type=PivotType.HIGH,
        strength=5,
        timestamp=resistance_bar_15.timestamp,
        index=15,
    )

    resistance_bar_30 = create_test_bar(low=Decimal("105.50"), high=Decimal("110.50"), index=30)
    resistance_pivot_30 = Pivot(
        bar=resistance_bar_30,
        price=Decimal("110.50"),
        type=PivotType.HIGH,
        strength=5,
        timestamp=resistance_bar_30.timestamp,
        index=30,
    )

    resistance_pivots = [resistance_pivot_15, resistance_pivot_30]

    # Create trading range
    trading_range = create_test_trading_range(support_pivots, resistance_pivots, quality_score=80)

    # Create bars and volume analysis - must align with pivot indices
    max_index = max(p.index for p in support_pivots + resistance_pivots) + 1
    bars = []
    volume_analysis = []
    volume_ratios = [Decimal("2.0"), Decimal("1.5"), Decimal("1.0"), Decimal("0.8"), Decimal("0.5")]

    # Create a mapping of pivot index to volume ratio
    pivot_volume_map = {pivot.index: volume_ratios[i] for i, pivot in enumerate(support_pivots)}

    for idx in range(max_index):
        # Check if this index is a support pivot
        if idx in pivot_volume_map:
            # Find the pivot
            pivot = next(p for p in support_pivots if p.index == idx)
            bar = create_test_bar(
                high=pivot.price + Decimal("5.00"),
                low=pivot.price,
                close=pivot.price + Decimal("4.00"),  # 80% rejection wick
                volume=int(1000000 * float(pivot_volume_map[idx])),
                index=idx,
            )
            vol_ratio = pivot_volume_map[idx]
        else:
            # Filler bar
            bar = create_test_bar(index=idx)
            vol_ratio = Decimal("1.0")

        bars.append(bar)
        volume_analysis.append(
            VolumeAnalysis(
                bar=bar,
                volume_ratio=vol_ratio,
                spread_ratio=Decimal("1.0"),
                close_position=Decimal("0.8") if idx in pivot_volume_map else Decimal("0.5"),
                effort_result=None,
            )
        )

    # Calculate creek
    creek = calculate_creek_level(trading_range, bars, volume_analysis)

    # Verify strength score
    assert creek.strength_score == 100, f"Expected 100, got {creek.strength_score}"
    assert creek.strength_rating == "EXCELLENT"
    assert creek.volume_trend == "DECREASING"
    assert creek.confidence == "HIGH"
    assert creek.touch_count == 5


# ============================================================================
# Task 20: Test Minimum Strength Threshold (AC 6)
# ============================================================================


def test_weak_creek_below_minimum_strength():
    """
    Test weak creek scenario below minimum strength (< 60).

    Scenario:
        - 2 touches (10 pts)
        - Increasing volume (0 pts)
        - Weak rejection (5 pts)
        - Short hold: 5 bars (2 pts)
        - Total: 17 pts (below 60 threshold)
        - Should raise ValueError
    """
    # Create 2 support pivots with increasing volume (extended duration for min 10 bars)
    support_pivots = [
        create_test_pivot(Decimal("100.00"), 10),
        create_test_pivot(Decimal("100.50"), 22),  # 12 bars duration (meets minimum)
    ]

    # Create resistance pivots - using HIGH type
    resistance_bar_15 = create_test_bar(low=Decimal("105.00"), high=Decimal("110.00"), index=15)
    resistance_pivot_15 = Pivot(
        bar=resistance_bar_15,
        price=Decimal("110.00"),
        type=PivotType.HIGH,
        strength=5,
        timestamp=resistance_bar_15.timestamp,
        index=15,
    )

    resistance_bar_20 = create_test_bar(low=Decimal("105.50"), high=Decimal("110.50"), index=20)
    resistance_pivot_20 = Pivot(
        bar=resistance_bar_20,
        price=Decimal("110.50"),
        type=PivotType.HIGH,
        strength=5,
        timestamp=resistance_bar_20.timestamp,
        index=20,
    )

    resistance_pivots = [resistance_pivot_15, resistance_pivot_20]

    # Create trading range
    trading_range = create_test_trading_range(support_pivots, resistance_pivots, quality_score=80)

    # Create bars and volume analysis with increasing volume and weak rejection
    max_index = max(p.index for p in support_pivots + resistance_pivots) + 1
    bars = []
    volume_analysis = []

    # Create a mapping of pivot index to volume ratio
    pivot_volume_map = {
        pivot.index: Decimal(str(0.5 * (i + 1))) for i, pivot in enumerate(support_pivots)
    }

    for idx in range(max_index):
        # Check if this index is a support pivot
        if idx in pivot_volume_map:
            # Find the pivot
            pivot = next(p for p in support_pivots if p.index == idx)
            bar = create_test_bar(
                high=pivot.price + Decimal("5.00"),
                low=pivot.price,
                close=pivot.price + Decimal("1.00"),  # 20% rejection wick (weak)
                volume=int(500000 * (list(pivot_volume_map.keys()).index(idx) + 1)),
                index=idx,
            )
            vol_ratio = pivot_volume_map[idx]
            close_pos = Decimal("0.2")  # Weak close position
        else:
            # Filler bar
            bar = create_test_bar(index=idx)
            vol_ratio = Decimal("1.0")
            close_pos = Decimal("0.5")

        bars.append(bar)
        volume_analysis.append(
            VolumeAnalysis(
                bar=bar,
                volume_ratio=vol_ratio,
                spread_ratio=Decimal("1.0"),
                close_position=close_pos,
                effort_result=None,
            )
        )

    # Should raise ValueError for weak creek
    with pytest.raises(ValueError, match="strength.*below minimum"):
        calculate_creek_level(trading_range, bars, volume_analysis)


# ============================================================================
# Additional Tests
# ============================================================================


def test_assess_confidence():
    """Test confidence level assessment"""
    assert _assess_confidence(5) == "HIGH"
    assert _assess_confidence(4) == "MEDIUM"
    assert _assess_confidence(3) == "MEDIUM"
    assert _assess_confidence(2) == "LOW"


def test_creek_validation_low_quality_range():
    """Test that creek calculation requires quality_score >= 70"""
    support_pivots = [
        create_test_pivot(Decimal("100.00"), 10),
        create_test_pivot(Decimal("100.50"), 20),
    ]

    # Create resistance pivots - using HIGH type
    resistance_bar_15 = create_test_bar(low=Decimal("105.00"), high=Decimal("110.00"), index=15)
    resistance_pivot_15 = Pivot(
        bar=resistance_bar_15,
        price=Decimal("110.00"),
        type=PivotType.HIGH,
        strength=5,
        timestamp=resistance_bar_15.timestamp,
        index=15,
    )

    resistance_bar_25 = create_test_bar(low=Decimal("105.50"), high=Decimal("110.50"), index=25)
    resistance_pivot_25 = Pivot(
        bar=resistance_bar_25,
        price=Decimal("110.50"),
        type=PivotType.HIGH,
        strength=5,
        timestamp=resistance_bar_25.timestamp,
        index=25,
    )

    resistance_pivots = [resistance_pivot_15, resistance_pivot_25]

    # Create low-quality range (score 50)
    trading_range = create_test_trading_range(support_pivots, resistance_pivots, quality_score=50)

    bars = [create_test_bar(index=i) for i in range(30)]
    volume_analysis = [
        VolumeAnalysis(
            bar=bars[i],
            volume_ratio=Decimal("1.0"),
            spread_ratio=Decimal("1.0"),
            close_position=Decimal("0.5"),
            effort_result=None,
        )
        for i in range(30)
    ]

    # Should raise ValueError for low quality
    with pytest.raises(ValueError, match="quality score"):
        calculate_creek_level(trading_range, bars, volume_analysis)


def test_creek_validation_bars_volume_mismatch():
    """Test that bars and volume_analysis must match in length"""
    support_pivots = [
        create_test_pivot(Decimal("100.00"), 10),
        create_test_pivot(Decimal("100.50"), 20),
    ]

    # Create resistance pivots - using HIGH type
    resistance_bar_15 = create_test_bar(low=Decimal("105.00"), high=Decimal("110.00"), index=15)
    resistance_pivot_15 = Pivot(
        bar=resistance_bar_15,
        price=Decimal("110.00"),
        type=PivotType.HIGH,
        strength=5,
        timestamp=resistance_bar_15.timestamp,
        index=15,
    )

    resistance_bar_25 = create_test_bar(low=Decimal("105.50"), high=Decimal("110.50"), index=25)
    resistance_pivot_25 = Pivot(
        bar=resistance_bar_25,
        price=Decimal("110.50"),
        type=PivotType.HIGH,
        strength=5,
        timestamp=resistance_bar_25.timestamp,
        index=25,
    )

    resistance_pivots = [resistance_pivot_15, resistance_pivot_25]

    trading_range = create_test_trading_range(support_pivots, resistance_pivots, quality_score=80)

    bars = [create_test_bar(index=i) for i in range(30)]
    volume_analysis = [
        VolumeAnalysis(
            bar=bars[i],
            volume_ratio=Decimal("1.0"),
            spread_ratio=Decimal("1.0"),
            close_position=Decimal("0.5"),
            effort_result=None,
        )
        for i in range(20)
    ]  # Mismatch: 20 vs 30

    # Should raise ValueError for mismatch
    with pytest.raises(ValueError, match="length mismatch"):
        calculate_creek_level(trading_range, bars, volume_analysis)


# ============================================================================
# ICE LEVEL TESTS (Story 3.5)
# ============================================================================

# ============================================================================
# Task 19: Test Ice Volume-Weighted Averaging (AC 8)
# ============================================================================


def test_ice_volume_weighted_average():
    """
    Test ice volume-weighted average with known volumes and prices.

    Scenario (from Story 3.5 AC 8):
        Pivot 1: $200, volume 1M
        Pivot 2: $201, volume 2M
        Pivot 3: $202, volume 1M
        Expected: (200*1M + 201*2M + 202*1M) / 4M = $201.00
    """
    touches = [
        create_touch_detail(10, Decimal("200.00"), 1000000, Decimal("1.5")),
        create_touch_detail(18, Decimal("201.00"), 2000000, Decimal("1.0")),
        create_touch_detail(26, Decimal("202.00"), 1000000, Decimal("0.8")),
    ]

    weighted_price = _calculate_weighted_price(touches)

    # Expected: (200*1M + 201*2M + 202*1M) / 4M = 804M / 4M = 201.00
    assert weighted_price == Decimal("201.00"), f"Expected $201.00, got ${weighted_price}"


# ============================================================================
# Task 20: Test Ice Strength Scoring Components (AC 4, 5)
# ============================================================================


def test_score_rejection_wicks_ice_strong():
    """Test ice rejection wick scoring: high upper wick (avg 0.8) → 20 pts"""
    # Upper wick = (high - close) / (high - low)
    # High upper wick = close near low = strong downward rejection
    touches = [
        create_touch_detail(
            10, Decimal("200.00"), 1000000, Decimal("1.0"), rejection_wick=Decimal("0.8")
        ),
        create_touch_detail(
            18, Decimal("201.00"), 1000000, Decimal("1.0"), rejection_wick=Decimal("0.75")
        ),
        create_touch_detail(
            26, Decimal("202.00"), 1000000, Decimal("1.0"), rejection_wick=Decimal("0.85")
        ),
    ]

    score = _score_rejection_wicks_ice(touches)

    # Average = (0.8 + 0.75 + 0.85) / 3 = 0.8 → 20 pts
    assert score == 20, f"Expected 20 pts for strong ice rejection, got {score}"


def test_score_rejection_wicks_ice_moderate():
    """Test ice rejection wick scoring: moderate upper wick (avg 0.5) → 15 pts"""
    touches = [
        create_touch_detail(
            10, Decimal("200.00"), 1000000, Decimal("1.0"), rejection_wick=Decimal("0.5")
        ),
        create_touch_detail(
            18, Decimal("201.00"), 1000000, Decimal("1.0"), rejection_wick=Decimal("0.55")
        ),
        create_touch_detail(
            26, Decimal("202.00"), 1000000, Decimal("1.0"), rejection_wick=Decimal("0.45")
        ),
    ]

    score = _score_rejection_wicks_ice(touches)

    # Average = 0.5 → 15 pts
    assert score == 15, f"Expected 15 pts for moderate ice rejection, got {score}"


def test_score_rejection_wicks_ice_weak():
    """Test ice rejection wick scoring: low upper wick (avg 0.2) → 5 pts"""
    touches = [
        create_touch_detail(
            10, Decimal("200.00"), 1000000, Decimal("1.0"), rejection_wick=Decimal("0.2")
        ),
        create_touch_detail(
            18, Decimal("201.00"), 1000000, Decimal("1.0"), rejection_wick=Decimal("0.15")
        ),
        create_touch_detail(
            26, Decimal("202.00"), 1000000, Decimal("1.0"), rejection_wick=Decimal("0.25")
        ),
    ]

    score = _score_rejection_wicks_ice(touches)

    # Average = 0.2 → 5 pts
    assert score == 5, f"Expected 5 pts for weak ice rejection, got {score}"


# ============================================================================
# Task 21: Test Perfect Ice (100 score) (AC 4, 5)
# ============================================================================


def test_ice_perfect_score():
    """
    Test perfect ice scenario: 100 total score.

    Scenario:
        - 5 touches → 40 pts
        - Decreasing volume: 2.0x → 1.5x → 1.0x → 0.8x → 0.5x → 30 pts
        - High rejection wicks: avg 0.8 upper wick → 20 pts
        - Long hold: 30 bars → 10 pts
        Total: 100 pts
    """
    # Create 5 resistance pivots with decreasing volume (tight cluster within 1.5% tolerance)
    resistance_pivots = [
        create_test_pivot_high(Decimal("200.00"), 10),
        create_test_pivot_high(Decimal("200.20"), 18),
        create_test_pivot_high(Decimal("200.40"), 26),
        create_test_pivot_high(Decimal("200.30"), 34),
        create_test_pivot_high(Decimal("200.10"), 40),  # Last test at index 40 (30 bars duration)
    ]

    # Create support pivots (required for TradingRange) - need strong support to avoid creek failure
    support_pivots = [
        create_test_pivot(Decimal("190.00"), 12),
        create_test_pivot(Decimal("190.25"), 20),
        create_test_pivot(Decimal("190.10"), 28),
        create_test_pivot(Decimal("190.40"), 36),
    ]

    trading_range = create_test_trading_range(support_pivots, resistance_pivots, quality_score=90)

    # Create bars and volume analysis
    bars = []
    volume_analysis = []
    pivot_indices = {p.index for p in resistance_pivots}

    # Decreasing volume ratios for resistance touches
    pivot_volume_map = {
        10: Decimal("2.0"),
        18: Decimal("1.5"),
        26: Decimal("1.0"),
        34: Decimal("0.8"),
        40: Decimal("0.5"),
    }

    for idx in range(45):
        if idx in pivot_indices:
            pivot = next(p for p in resistance_pivots if p.index == idx)
            # Create bar with high upper wick (close near low)
            bar = create_test_bar(
                high=pivot.price,
                low=pivot.price - Decimal("5.00"),
                close=pivot.price - Decimal("4.00"),  # 80% upper wick
                volume=int(1000000 * float(pivot_volume_map[idx])),
                index=idx,
            )
            vol_ratio = pivot_volume_map[idx]
            close_pos = Decimal("0.2")  # Close near low
        else:
            # Filler bar
            bar = create_test_bar(index=idx)
            vol_ratio = Decimal("1.0")
            close_pos = Decimal("0.5")

        bars.append(bar)
        volume_analysis.append(
            VolumeAnalysis(
                bar=bar,
                volume_ratio=vol_ratio,
                spread_ratio=Decimal("1.0"),
                close_position=close_pos,
                effort_result=None,
            )
        )

    ice = calculate_ice_level(trading_range, bars, volume_analysis)

    assert ice.strength_score == 100, f"Expected perfect score 100, got {ice.strength_score}"
    assert ice.strength_rating == "EXCELLENT", f"Expected EXCELLENT, got {ice.strength_rating}"
    assert ice.touch_count == 5, f"Expected 5 touches, got {ice.touch_count}"
    assert ice.volume_trend == "DECREASING", f"Expected DECREASING, got {ice.volume_trend}"
    assert ice.confidence == "HIGH", f"Expected HIGH confidence, got {ice.confidence}"


# ============================================================================
# Task 22: Test Minimum Strength Threshold (AC 5)
# ============================================================================


def test_ice_minimum_strength_threshold():
    """
    Test weak ice scenario: below 60 strength threshold (should reject).

    Scenario:
        - 2 touches → 10 pts
        - Increasing volume → 0 pts
        - Weak rejection (avg 0.2) → 5 pts
        - Short hold: 5 bars → 2 pts
        Total: 17 pts (below 60 threshold)
    """
    # Create 2 resistance pivots with increasing volume (tight cluster within 1.5% tolerance)
    resistance_pivots = [
        create_test_pivot_high(Decimal("200.00"), 15),
        create_test_pivot_high(Decimal("200.20"), 25),  # 10 bars apart (minimum duration)
    ]

    # Create support pivots (required for TradingRange) - need strong support to avoid creek failure
    support_pivots = [
        create_test_pivot(Decimal("190.00"), 10),
        create_test_pivot(Decimal("190.25"), 18),
        create_test_pivot(Decimal("190.10"), 22),
        create_test_pivot(Decimal("190.40"), 30),
    ]

    trading_range = create_test_trading_range(support_pivots, resistance_pivots, quality_score=70)

    # Create bars and volume analysis
    bars = []
    volume_analysis = []
    pivot_indices = {p.index for p in resistance_pivots}

    # Increasing volume ratios for resistance touches
    pivot_volume_map = {15: Decimal("1.0"), 25: Decimal("2.0")}

    for idx in range(35):
        if idx in pivot_indices:
            pivot = next(p for p in resistance_pivots if p.index == idx)
            # Create bar with weak rejection (close near high)
            bar = create_test_bar(
                high=pivot.price,
                low=pivot.price - Decimal("5.00"),
                close=pivot.price - Decimal("1.00"),  # 20% upper wick (weak)
                volume=int(500000 * float(pivot_volume_map[idx])),
                index=idx,
            )
            vol_ratio = pivot_volume_map[idx]
            close_pos = Decimal("0.8")  # Close near high
        else:
            # Filler bar
            bar = create_test_bar(index=idx)
            vol_ratio = Decimal("1.0")
            close_pos = Decimal("0.5")

        bars.append(bar)
        volume_analysis.append(
            VolumeAnalysis(
                bar=bar,
                volume_ratio=vol_ratio,
                spread_ratio=Decimal("1.0"),
                close_position=close_pos,
                effort_result=None,
            )
        )

    # Should raise ValueError for weak ice
    with pytest.raises(ValueError, match="strength.*below minimum"):
        calculate_ice_level(trading_range, bars, volume_analysis)


# ============================================================================
# Task 24: Test Ice > Creek Validation (AC 7)
# ============================================================================


def test_ice_above_creek_valid():
    """
    Test valid range: Ice > Creek (resistance above support).

    This documents expected behavior - actual validation deferred to Story 3.8.
    """
    # Create support pivots (Creek will be ~$100) - need strong support to avoid creek failure
    support_pivots = [
        create_test_pivot(Decimal("100.00"), 10),
        create_test_pivot(Decimal("100.50"), 18),
        create_test_pivot(Decimal("100.25"), 26),
        create_test_pivot(Decimal("100.10"), 34),
    ]

    # Create resistance pivots (Ice will be ~$105, 5% above Creek) - tight cluster within 1.5% tolerance
    resistance_pivots = [
        create_test_pivot_high(Decimal("105.00"), 15),
        create_test_pivot_high(Decimal("105.30"), 23),
        create_test_pivot_high(Decimal("105.15"), 31),
        create_test_pivot_high(Decimal("105.40"), 37),
    ]

    trading_range = create_test_trading_range(support_pivots, resistance_pivots, quality_score=80)

    # Create bars and volume analysis
    bars = []
    volume_analysis = []

    for idx in range(40):
        bar = create_test_bar(index=idx)
        bars.append(bar)
        volume_analysis.append(
            VolumeAnalysis(
                bar=bar,
                volume_ratio=Decimal("1.0"),
                spread_ratio=Decimal("1.0"),
                close_position=Decimal("0.5"),
                effort_result=None,
            )
        )

    # Calculate both levels
    creek = calculate_creek_level(trading_range, bars, volume_analysis)
    ice = calculate_ice_level(trading_range, bars, volume_analysis)

    # Document expected behavior: Ice > Creek
    assert ice.price > creek.price, f"Ice ${ice.price} must be above Creek ${creek.price}"


# ============================================================================
# Task 25: Test Range Width Minimum (AC 10)
# ============================================================================


def test_ice_range_width_valid():
    """
    Test valid range width: >= 3% (per FR1).

    This documents expected behavior - actual validation deferred to Story 3.8.
    """
    # Create support pivots (Creek ~$100) - need strong support to avoid creek failure
    support_pivots = [
        create_test_pivot(Decimal("100.00"), 10),
        create_test_pivot(Decimal("100.50"), 18),
        create_test_pivot(Decimal("100.25"), 26),
        create_test_pivot(Decimal("100.10"), 34),
    ]

    # Create resistance pivots (Ice ~$103.50, 3.5% above Creek) - tight cluster within 1.5% tolerance
    resistance_pivots = [
        create_test_pivot_high(Decimal("103.50"), 15),
        create_test_pivot_high(Decimal("103.80"), 23),
        create_test_pivot_high(Decimal("103.65"), 31),
        create_test_pivot_high(Decimal("103.90"), 37),
    ]

    trading_range = create_test_trading_range(support_pivots, resistance_pivots, quality_score=80)

    # Create bars and volume analysis
    bars = []
    volume_analysis = []

    for idx in range(40):
        bar = create_test_bar(index=idx)
        bars.append(bar)
        volume_analysis.append(
            VolumeAnalysis(
                bar=bar,
                volume_ratio=Decimal("1.0"),
                spread_ratio=Decimal("1.0"),
                close_position=Decimal("0.5"),
                effort_result=None,
            )
        )

    # Calculate both levels
    creek = calculate_creek_level(trading_range, bars, volume_analysis)
    ice = calculate_ice_level(trading_range, bars, volume_analysis)

    # Document expected behavior: range width >= 3%
    range_width_pct = (ice.price - creek.price) / creek.price
    assert range_width_pct >= Decimal(
        "0.03"
    ), f"Range width {range_width_pct*100:.1f}% must be >= 3%"


# ============================================================================
# Test Ice Input Validation
# ============================================================================


def test_ice_validation_low_quality_range():
    """Test that ice calculation requires quality_score >= 70"""
    support_pivots = [
        create_test_pivot(Decimal("100.00"), 10),
        create_test_pivot(Decimal("100.50"), 20),
    ]

    resistance_pivots = [
        create_test_pivot_high(Decimal("110.00"), 15),
        create_test_pivot_high(Decimal("110.50"), 25),
    ]

    # Create low-quality range (score 50)
    trading_range = create_test_trading_range(support_pivots, resistance_pivots, quality_score=50)

    bars = [create_test_bar(index=i) for i in range(30)]
    volume_analysis = [
        VolumeAnalysis(
            bar=bars[i],
            volume_ratio=Decimal("1.0"),
            spread_ratio=Decimal("1.0"),
            close_position=Decimal("0.5"),
            effort_result=None,
        )
        for i in range(30)
    ]

    # Should raise ValueError for low quality
    with pytest.raises(ValueError, match="quality score"):
        calculate_ice_level(trading_range, bars, volume_analysis)
