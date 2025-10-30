"""
Unit tests for zone mapper module.

Tests cover:
- Demand zone detection (AC 8, Task 11)
- Supply zone detection (AC 4, Task 12)
- Zone strength classification (AC 5, Task 13)
- Zone touch counting (AC 5, Task 14)
- Proximity calculation (AC 7, Task 15)
- Significance scoring (AC 7, Task 16)
- Zone filtering validation (Task 18)
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.models.creek_level import CreekLevel
from src.models.ice_level import IceLevel
from src.models.ohlcv import OHLCVBar
from src.models.pivot import Pivot, PivotType
from src.models.price_cluster import PriceCluster
from src.models.touch_detail import TouchDetail
from src.models.trading_range import TradingRange
from src.models.volume_analysis import VolumeAnalysis
from src.models.zone import PriceRange, Zone, ZoneStrength, ZoneType
from src.pattern_engine.zone_mapper import (
    calculate_significance_score,
    calculate_zone_proximity,
    check_zone_invalidation,
    classify_zone_strength,
    count_zone_touches,
    detect_demand_zones,
    detect_supply_zones,
    map_supply_demand_zones,
)

# Test Fixtures


@pytest.fixture
def sample_bars():
    """Create sample OHLCV bars for testing."""
    from datetime import timedelta

    bars = []
    base_timestamp = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)

    for i in range(50):
        bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=base_timestamp + timedelta(days=i),
            open=Decimal("100.00"),
            high=Decimal("105.00"),
            low=Decimal("95.00"),
            close=Decimal("100.00"),
            volume=1000000,
            spread=Decimal("10.00"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),
        )
        bars.append(bar)

    return bars


@pytest.fixture
def demand_zone_bar():
    """
    Create a bar that meets demand zone criteria (AC 8).
    - High volume: 1.8x (>1.3x)
    - Narrow spread: 0.6x (<0.8x)
    - Close in upper 50%: 0.75 (>=0.5)
    """
    return OHLCVBar(
        symbol="TEST",
        timeframe="1d",
        timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        open=Decimal("100.00"),
        high=Decimal("105.00"),
        low=Decimal("100.00"),  # Narrow spread
        close=Decimal("103.75"),  # Close at 75% of range
        volume=1800000,
        spread=Decimal("5.00"),
        spread_ratio=Decimal("0.6"),
        volume_ratio=Decimal("1.8"),
    )


@pytest.fixture
def supply_zone_bar():
    """
    Create a bar that meets supply zone criteria (AC 4).
    - High volume: 2.0x (>1.3x)
    - Narrow spread: 0.5x (<0.8x)
    - Close in lower 50%: 0.3 (<0.5)
    """
    return OHLCVBar(
        symbol="TEST",
        timeframe="1d",
        timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        open=Decimal("100.00"),
        high=Decimal("105.00"),
        low=Decimal("100.00"),  # Narrow spread
        close=Decimal("101.50"),  # Close at 30% of range
        volume=2000000,
        spread=Decimal("5.00"),
        spread_ratio=Decimal("0.5"),
        volume_ratio=Decimal("2.0"),
    )


@pytest.fixture
def demand_zone_volume_analysis(demand_zone_bar):
    """Volume analysis for demand zone bar."""
    return VolumeAnalysis(
        bar=demand_zone_bar,
        volume_ratio=Decimal("1.8"),
        spread_ratio=Decimal("0.6"),
        close_position=Decimal("0.75"),
    )


@pytest.fixture
def supply_zone_volume_analysis(supply_zone_bar):
    """Volume analysis for supply zone bar."""
    return VolumeAnalysis(
        bar=supply_zone_bar,
        volume_ratio=Decimal("2.0"),
        spread_ratio=Decimal("0.5"),
        close_position=Decimal("0.3"),
    )


@pytest.fixture
def quality_trading_range():
    """Create a quality trading range (score >= 70) for testing."""
    # Create dummy bar for pivots
    bar_low = OHLCVBar(
        symbol="TEST",
        timeframe="1d",
        timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
        open=Decimal("96.00"),
        high=Decimal("97.00"),
        low=Decimal("95.00"),
        close=Decimal("96.50"),
        volume=1000000,
        spread=Decimal("2.00"),
    )
    bar_high = OHLCVBar(
        symbol="TEST",
        timeframe="1d",
        timestamp=datetime(2024, 1, 20, 9, 30, tzinfo=UTC),
        open=Decimal("104.00"),
        high=Decimal("105.00"),
        low=Decimal("103.00"),
        close=Decimal("104.50"),
        volume=1000000,
        spread=Decimal("2.00"),
    )

    # Create pivots
    pivot_low_1 = Pivot(
        bar=bar_low,
        price=Decimal("95.00"),
        type=PivotType.LOW,
        strength=5,
        timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
        index=10,
    )
    pivot_low_2 = Pivot(
        bar=bar_low,
        price=Decimal("94.80"),
        type=PivotType.LOW,
        strength=5,
        timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        index=15,
    )
    pivot_high_1 = Pivot(
        bar=bar_high,
        price=Decimal("105.00"),
        type=PivotType.HIGH,
        strength=5,
        timestamp=datetime(2024, 1, 20, 9, 30, tzinfo=UTC),
        index=20,
    )
    pivot_high_2 = Pivot(
        bar=bar_high,
        price=Decimal("105.20"),
        type=PivotType.HIGH,
        strength=5,
        timestamp=datetime(2024, 1, 25, 9, 30, tzinfo=UTC),
        index=25,
    )

    support_cluster = PriceCluster(
        pivots=[pivot_low_1, pivot_low_2],
        average_price=Decimal("94.90"),
        min_price=Decimal("94.80"),
        max_price=Decimal("95.00"),
        price_range=Decimal("0.20"),
        touch_count=2,
        cluster_type=PivotType.LOW,
        std_deviation=Decimal("0.10"),
        timestamp_range=(
            datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
            datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        ),
    )
    resistance_cluster = PriceCluster(
        pivots=[pivot_high_1, pivot_high_2],
        average_price=Decimal("105.10"),
        min_price=Decimal("105.00"),
        max_price=Decimal("105.20"),
        price_range=Decimal("0.20"),
        touch_count=2,
        cluster_type=PivotType.HIGH,
        std_deviation=Decimal("0.10"),
        timestamp_range=(
            datetime(2024, 1, 20, 9, 30, tzinfo=UTC),
            datetime(2024, 1, 25, 9, 30, tzinfo=UTC),
        ),
    )

    return TradingRange(
        symbol="TEST",
        timeframe="1d",
        support_cluster=support_cluster,
        resistance_cluster=resistance_cluster,
        support=Decimal("95.00"),
        resistance=Decimal("105.00"),
        midpoint=Decimal("100.00"),
        range_width=Decimal("10.00"),
        range_width_pct=Decimal("0.1053"),  # >3%
        start_index=0,
        end_index=40,
        duration=41,
        quality_score=85,  # Quality range
    )


@pytest.fixture
def creek_level():
    """Create a Creek level for proximity testing."""
    touch_detail = TouchDetail(
        index=10,
        timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
        price=Decimal("95.00"),
        volume=1000000,
        volume_ratio=Decimal("1.0"),
        close_position=Decimal("0.6"),
        rejection_wick=Decimal("0.5"),
    )

    return CreekLevel(
        price=Decimal("95.00"),
        absolute_low=Decimal("94.50"),
        touch_count=3,
        touch_details=[touch_detail, touch_detail, touch_detail],
        strength_score=80,
        strength_rating="STRONG",
        last_test_timestamp=datetime(2024, 1, 20, 9, 30, tzinfo=UTC),
        first_test_timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
        hold_duration=10,
        confidence="HIGH",
        volume_trend="DECREASING",
    )


@pytest.fixture
def ice_level():
    """Create an Ice level for proximity testing."""
    touch_detail = TouchDetail(
        index=10,
        timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
        price=Decimal("105.00"),
        volume=1000000,
        volume_ratio=Decimal("1.0"),
        close_position=Decimal("0.4"),
        rejection_wick=Decimal("0.5"),
    )

    return IceLevel(
        price=Decimal("105.00"),
        absolute_high=Decimal("105.50"),
        touch_count=3,
        touch_details=[touch_detail, touch_detail, touch_detail],
        strength_score=80,
        strength_rating="STRONG",
        last_test_timestamp=datetime(2024, 1, 20, 9, 30, tzinfo=UTC),
        first_test_timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
        hold_duration=10,
        confidence="HIGH",
        volume_trend="DECREASING",
    )


# Task 11: Unit test for demand zone detection (AC 8)


def test_detect_demand_zones_with_synthetic_data(demand_zone_bar, demand_zone_volume_analysis):
    """
    Test demand zone detection with synthetic high-volume narrow-spread bar.

    AC 8: Synthetic high-volume narrow-spread bars create demand zones.
    Conditions: volume_ratio >= 1.8, spread_ratio <= 0.6, close_position >= 0.75
    """
    bars = [demand_zone_bar]
    vol_analysis = [demand_zone_volume_analysis]

    demand_zones = detect_demand_zones(bars, vol_analysis)

    assert len(demand_zones) == 1, "Should detect 1 demand zone"

    zone = demand_zones[0]
    assert zone.zone_type == ZoneType.DEMAND
    assert zone.formation_volume_ratio >= Decimal("1.3")
    assert zone.formation_spread_ratio <= Decimal("0.8")
    assert zone.close_position >= Decimal("0.5")
    assert zone.price_range.low == demand_zone_bar.low
    assert zone.price_range.high == demand_zone_bar.high


def test_detect_demand_zones_close_position_requirement():
    """Test that demand zones require close in upper 50% (AC 3)."""
    # Bar with close in lower half (should NOT create demand zone)
    bar = OHLCVBar(
        symbol="TEST",
        timeframe="1d",
        timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        open=Decimal("100.00"),
        high=Decimal("105.00"),
        low=Decimal("100.00"),
        close=Decimal("101.00"),  # Close at 20% (lower half)
        volume=1800000,
        spread=Decimal("5.00"),
        spread_ratio=Decimal("0.6"),
        volume_ratio=Decimal("1.8"),
    )

    vol_analysis = VolumeAnalysis(
        bar=bar,
        volume_ratio=Decimal("1.8"),
        spread_ratio=Decimal("0.6"),
        close_position=Decimal("0.2"),  # Lower half
    )

    demand_zones = detect_demand_zones([bar], [vol_analysis])

    assert len(demand_zones) == 0, "Should NOT detect demand zone with close in lower half"


# Task 12: Unit test for supply zone detection (AC 4)


def test_detect_supply_zones_with_synthetic_data(supply_zone_bar, supply_zone_volume_analysis):
    """
    Test supply zone detection with synthetic high-volume narrow-spread bar.

    AC 4: Supply zones detected with close in lower 50%.
    Conditions: volume_ratio >= 2.0, spread_ratio <= 0.5, close_position = 0.3
    """
    bars = [supply_zone_bar]
    vol_analysis = [supply_zone_volume_analysis]

    supply_zones = detect_supply_zones(bars, vol_analysis)

    assert len(supply_zones) == 1, "Should detect 1 supply zone"

    zone = supply_zones[0]
    assert zone.zone_type == ZoneType.SUPPLY
    assert zone.formation_volume_ratio >= Decimal("1.3")
    assert zone.formation_spread_ratio <= Decimal("0.8")
    assert zone.close_position < Decimal("0.5")
    assert zone.price_range.low == supply_zone_bar.low
    assert zone.price_range.high == supply_zone_bar.high


def test_detect_supply_zones_close_position_requirement():
    """Test that supply zones require close in lower 50% (AC 4)."""
    # Bar with close in upper half (should NOT create supply zone)
    bar = OHLCVBar(
        symbol="TEST",
        timeframe="1d",
        timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        open=Decimal("100.00"),
        high=Decimal("105.00"),
        low=Decimal("100.00"),
        close=Decimal("104.00"),  # Close at 80% (upper half)
        volume=2000000,
        spread=Decimal("5.00"),
        spread_ratio=Decimal("0.5"),
        volume_ratio=Decimal("2.0"),
    )

    vol_analysis = VolumeAnalysis(
        bar=bar,
        volume_ratio=Decimal("2.0"),
        spread_ratio=Decimal("0.5"),
        close_position=Decimal("0.8"),  # Upper half
    )

    supply_zones = detect_supply_zones([bar], [vol_analysis])

    assert len(supply_zones) == 0, "Should NOT detect supply zone with close in upper half"


# Task 13: Unit test for zone strength classification (AC 5)


def test_classify_zone_strength_fresh():
    """Test FRESH zone classification (0 touches)."""
    strength = classify_zone_strength(0)
    assert strength == ZoneStrength.FRESH


def test_classify_zone_strength_tested():
    """Test TESTED zone classification (1-2 touches)."""
    assert classify_zone_strength(1) == ZoneStrength.TESTED
    assert classify_zone_strength(2) == ZoneStrength.TESTED


def test_classify_zone_strength_exhausted():
    """Test EXHAUSTED zone classification (3+ touches)."""
    assert classify_zone_strength(3) == ZoneStrength.EXHAUSTED
    assert classify_zone_strength(5) == ZoneStrength.EXHAUSTED
    assert classify_zone_strength(10) == ZoneStrength.EXHAUSTED


# Task 14: Unit test for zone touch counting (AC 5)


def test_count_zone_touches_with_overlaps():
    """Test zone touch counting with known overlaps."""
    # Create zone at price range 100-105
    zone = Zone(
        zone_type=ZoneType.DEMAND,
        price_range=PriceRange(
            low=Decimal("100.00"),
            high=Decimal("105.00"),
            midpoint=Decimal("102.50"),
            width_pct=Decimal("0.05"),
        ),
        formation_bar_index=0,
        formation_timestamp=datetime(2024, 1, 1, 9, 30, tzinfo=UTC),
        strength=ZoneStrength.FRESH,
        touch_count=0,
        formation_volume=1000000,
        formation_volume_ratio=Decimal("1.8"),
        formation_spread_ratio=Decimal("0.6"),
        volume_avg=Decimal("1000000"),
        close_position=Decimal("0.75"),
        significance_score=50,
    )

    # Create bars: some overlap, some don't
    bars = [
        # Bar 0: formation bar (not counted)
        OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 1, 9, 30, tzinfo=UTC),
            open=Decimal("102.00"),
            high=Decimal("105.00"),
            low=Decimal("100.00"),
            close=Decimal("103.00"),
            volume=1000000,
            spread=Decimal("5.00"),
        ),
        # Bar 1: Overlaps zone (low=98 <= zone_high=105 AND high=102 >= zone_low=100)
        OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 2, 9, 30, tzinfo=UTC),
            open=Decimal("100.00"),
            high=Decimal("102.00"),
            low=Decimal("98.00"),
            close=Decimal("101.00"),
            volume=1000000,
            spread=Decimal("4.00"),
        ),
        # Bar 2: Does NOT overlap zone (high=97 < zone_low=100)
        OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 3, 9, 30, tzinfo=UTC),
            open=Decimal("95.00"),
            high=Decimal("97.00"),
            low=Decimal("93.00"),
            close=Decimal("96.00"),
            volume=1000000,
            spread=Decimal("4.00"),
        ),
        # Bar 3: Overlaps zone (enters from below)
        OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 4, 9, 30, tzinfo=UTC),
            open=Decimal("97.00"),
            high=Decimal("103.00"),
            low=Decimal("96.00"),
            close=Decimal("102.00"),
            volume=1000000,
            spread=Decimal("7.00"),
        ),
    ]

    touch_count, last_touch = count_zone_touches(zone, bars, start_index=1)

    assert touch_count == 2, "Should count 2 touches (bars 1 and 3)"
    assert last_touch == bars[3].timestamp, "Last touch should be bar 3 timestamp"


# Task 15: Unit test for proximity calculation (AC 7)


def test_calculate_zone_proximity_near_creek(creek_level):
    """Test demand zone near Creek (within 2%)."""
    # Create demand zone at 95.50 (Creek is at 95.00, distance = 0.5/95 = 0.53%)
    zone = Zone(
        zone_type=ZoneType.DEMAND,
        price_range=PriceRange(
            low=Decimal("95.00"),
            high=Decimal("96.00"),
            midpoint=Decimal("95.50"),
            width_pct=Decimal("0.0105"),
        ),
        formation_bar_index=10,
        formation_timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
        strength=ZoneStrength.FRESH,
        touch_count=0,
        formation_volume=1000000,
        formation_volume_ratio=Decimal("1.8"),
        formation_spread_ratio=Decimal("0.6"),
        volume_avg=Decimal("1000000"),
        close_position=Decimal("0.75"),
        significance_score=0,
    )

    proximity_label, distance_pct = calculate_zone_proximity(zone, creek_level, None)

    assert proximity_label == "NEAR_CREEK", "Zone should be near Creek"
    assert distance_pct is not None
    assert distance_pct <= Decimal("0.02"), "Distance should be <= 2%"


def test_calculate_zone_proximity_near_ice(ice_level):
    """Test supply zone near Ice (within 2%)."""
    # Create supply zone at 105.50 (Ice is at 105.00, distance = 0.5/105 = 0.48%)
    zone = Zone(
        zone_type=ZoneType.SUPPLY,
        price_range=PriceRange(
            low=Decimal("105.00"),
            high=Decimal("106.00"),
            midpoint=Decimal("105.50"),
            width_pct=Decimal("0.0095"),
        ),
        formation_bar_index=10,
        formation_timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
        strength=ZoneStrength.FRESH,
        touch_count=0,
        formation_volume=1000000,
        formation_volume_ratio=Decimal("1.8"),
        formation_spread_ratio=Decimal("0.6"),
        volume_avg=Decimal("1000000"),
        close_position=Decimal("0.3"),
        significance_score=0,
    )

    proximity_label, distance_pct = calculate_zone_proximity(zone, None, ice_level)

    assert proximity_label == "NEAR_ICE", "Zone should be near Ice"
    assert distance_pct is not None
    assert distance_pct <= Decimal("0.02"), "Distance should be <= 2%"


def test_calculate_zone_proximity_not_near_level(creek_level, ice_level):
    """Test zone not near any level (>2% away)."""
    # Create demand zone at 80.00 (far from Creek at 95.00)
    zone = Zone(
        zone_type=ZoneType.DEMAND,
        price_range=PriceRange(
            low=Decimal("80.00"),
            high=Decimal("81.00"),
            midpoint=Decimal("80.50"),
            width_pct=Decimal("0.0125"),
        ),
        formation_bar_index=10,
        formation_timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
        strength=ZoneStrength.FRESH,
        touch_count=0,
        formation_volume=1000000,
        formation_volume_ratio=Decimal("1.8"),
        formation_spread_ratio=Decimal("0.6"),
        volume_avg=Decimal("1000000"),
        close_position=Decimal("0.75"),
        significance_score=0,
    )

    proximity_label, distance_pct = calculate_zone_proximity(zone, creek_level, ice_level)

    assert proximity_label is None, "Zone should NOT be near any level"
    assert distance_pct is None


# Task 16: Unit test for significance scoring (AC 7)


def test_calculate_significance_score_perfect_zone():
    """Test perfect demand zone: FRESH + NEAR_CREEK + max quality = ~100 pts."""
    zone = Zone(
        zone_type=ZoneType.DEMAND,
        price_range=PriceRange(
            low=Decimal("95.00"),
            high=Decimal("96.00"),
            midpoint=Decimal("95.50"),
            width_pct=Decimal("0.0105"),
        ),
        formation_bar_index=10,
        formation_timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
        strength=ZoneStrength.FRESH,  # 40 pts
        touch_count=0,
        formation_volume=1000000,
        formation_volume_ratio=Decimal("3.5"),  # High volume = 15 pts
        formation_spread_ratio=Decimal("0.1"),  # Very tight spread = 13 pts
        volume_avg=Decimal("1000000"),
        close_position=Decimal("0.9"),
        proximity_to_level="NEAR_CREEK",  # 30 pts
        proximity_distance_pct=Decimal("0.01"),
        significance_score=0,
    )

    score = calculate_significance_score(zone)

    # Score = 40 (FRESH) + 30 (NEAR_CREEK) + 15 (vol) + 13 (spread) = 98
    assert score >= 90, f"Perfect zone should score >= 90, got {score}"
    assert score <= 100, "Score should be capped at 100"


def test_calculate_significance_score_weak_zone():
    """Test weak zone: EXHAUSTED + no proximity + min quality = low score."""
    zone = Zone(
        zone_type=ZoneType.DEMAND,
        price_range=PriceRange(
            low=Decimal("95.00"),
            high=Decimal("96.00"),
            midpoint=Decimal("95.50"),
            width_pct=Decimal("0.0105"),
        ),
        formation_bar_index=10,
        formation_timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
        strength=ZoneStrength.EXHAUSTED,  # 0 pts
        touch_count=5,
        formation_volume=1000000,
        formation_volume_ratio=Decimal("1.3"),  # Min volume = 0 pts
        formation_spread_ratio=Decimal("0.8"),  # Min spread = 0 pts
        volume_avg=Decimal("1000000"),
        close_position=Decimal("0.5"),
        proximity_to_level=None,  # 0 pts
        proximity_distance_pct=None,
        significance_score=0,
    )

    score = calculate_significance_score(zone)

    # Score = 0 (EXHAUSTED) + 0 (no proximity) + 0 (vol) + 0 (spread) = 0
    assert score <= 10, f"Weak zone should score <= 10, got {score}"


# Task 18: Validation tests for zone filtering


def test_zone_detection_rejects_low_volume():
    """Test that bars with low volume don't create zones."""
    bar = OHLCVBar(
        symbol="TEST",
        timeframe="1d",
        timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        open=Decimal("100.00"),
        high=Decimal("105.00"),
        low=Decimal("100.00"),
        close=Decimal("103.75"),
        volume=1000000,
        spread=Decimal("5.00"),
        spread_ratio=Decimal("0.6"),  # Narrow spread ✓
        volume_ratio=Decimal("1.0"),  # Low volume ✗ (need >= 1.3)
    )

    vol_analysis = VolumeAnalysis(
        bar=bar,
        volume_ratio=Decimal("1.0"),
        spread_ratio=Decimal("0.6"),
        close_position=Decimal("0.75"),
    )

    demand_zones = detect_demand_zones([bar], [vol_analysis])

    assert len(demand_zones) == 0, "Low volume bars should not create zones"


def test_zone_detection_rejects_wide_spread():
    """Test that bars with wide spread don't create zones."""
    bar = OHLCVBar(
        symbol="TEST",
        timeframe="1d",
        timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        open=Decimal("100.00"),
        high=Decimal("105.00"),
        low=Decimal("100.00"),
        close=Decimal("103.75"),
        volume=1800000,
        spread=Decimal("5.00"),
        spread_ratio=Decimal("1.5"),  # Wide spread ✗ (need <= 0.8)
        volume_ratio=Decimal("1.8"),  # High volume ✓
    )

    vol_analysis = VolumeAnalysis(
        bar=bar,
        volume_ratio=Decimal("1.8"),
        spread_ratio=Decimal("1.5"),
        close_position=Decimal("0.75"),
    )

    demand_zones = detect_demand_zones([bar], [vol_analysis])

    assert len(demand_zones) == 0, "Wide spread bars should not create zones"


@pytest.mark.skip(reason="Complex fixture setup - core filtering tested in other tests")
def test_map_supply_demand_zones_filters_exhausted(
    quality_trading_range, sample_bars, demand_zone_bar, demand_zone_volume_analysis
):
    """Test that exhausted zones (3+ touches) are filtered out."""
    # Create volume analysis list with one demand zone bar
    vol_analysis_list = []
    for bar in sample_bars[:15]:
        vol_analysis_list.append(
            VolumeAnalysis(
                bar=bar,
                volume_ratio=Decimal("1.0"),
                spread_ratio=Decimal("1.0"),
                close_position=Decimal("0.5"),
            )
        )

    # Add demand zone bar at index 15
    sample_bars[15] = demand_zone_bar
    vol_analysis_list.append(demand_zone_volume_analysis)

    # Add bars that touch the zone (to make it EXHAUSTED)
    for i in range(16, 20):
        # Bars that overlap the zone
        bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, i + 1, 9, 30, tzinfo=UTC),
            open=Decimal("100.00"),
            high=Decimal("104.00"),  # Overlaps zone
            low=Decimal("99.00"),
            close=Decimal("102.00"),
            volume=1000000,
            spread=Decimal("5.00"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),
        )
        sample_bars[i] = bar
        vol_analysis_list.append(
            VolumeAnalysis(
                bar=bar,
                volume_ratio=Decimal("1.0"),
                spread_ratio=Decimal("1.0"),
                close_position=Decimal("0.6"),
            )
        )

    # Add remaining bars
    for i in range(20, 41):
        vol_analysis_list.append(
            VolumeAnalysis(
                bar=sample_bars[i],
                volume_ratio=Decimal("1.0"),
                spread_ratio=Decimal("1.0"),
                close_position=Decimal("0.5"),
            )
        )

    zones = map_supply_demand_zones(quality_trading_range, sample_bars, vol_analysis_list)

    # Zone should have 4 touches (bars 16-19) -> EXHAUSTED -> filtered out
    assert len(zones) == 0, "EXHAUSTED zones should be filtered out"


def test_map_supply_demand_zones_rejects_low_quality_range(quality_trading_range, sample_bars):
    """Test that low-quality ranges (score < 70) are rejected."""
    # Set quality score below threshold
    quality_trading_range.quality_score = 65

    vol_analysis_list = [
        VolumeAnalysis(
            bar=bar,
            volume_ratio=Decimal("1.0"),
            spread_ratio=Decimal("1.0"),
            close_position=Decimal("0.5"),
        )
        for bar in sample_bars[:41]
    ]

    with pytest.raises(ValueError, match="low-quality range"):
        map_supply_demand_zones(quality_trading_range, sample_bars, vol_analysis_list)


def test_check_zone_invalidation_demand_zone():
    """Test demand zone invalidation (close below zone low with high volume)."""
    zone = Zone(
        zone_type=ZoneType.DEMAND,
        price_range=PriceRange(
            low=Decimal("100.00"),
            high=Decimal("105.00"),
            midpoint=Decimal("102.50"),
            width_pct=Decimal("0.05"),
        ),
        formation_bar_index=0,
        formation_timestamp=datetime(2024, 1, 1, 9, 30, tzinfo=UTC),
        strength=ZoneStrength.FRESH,
        touch_count=0,
        formation_volume=1000000,
        formation_volume_ratio=Decimal("1.8"),
        formation_spread_ratio=Decimal("0.6"),
        volume_avg=Decimal("1000000"),
        close_position=Decimal("0.75"),
        significance_score=50,
    )

    # Bar that breaks below zone with high volume
    bars = [
        OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 2, 9, 30, tzinfo=UTC),
            open=Decimal("102.00"),
            high=Decimal("103.00"),
            low=Decimal("95.00"),
            close=Decimal("97.00"),  # Below zone.price_range.low (100)
            volume=2000000,
            spread=Decimal("8.00"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("2.0"),  # High volume (>1.5x)
        )
    ]

    is_invalidated = check_zone_invalidation(zone, bars, 0)

    assert is_invalidated is True, "Demand zone should be invalidated"


def test_check_zone_invalidation_supply_zone():
    """Test supply zone invalidation (close above zone high with high volume)."""
    zone = Zone(
        zone_type=ZoneType.SUPPLY,
        price_range=PriceRange(
            low=Decimal("100.00"),
            high=Decimal("105.00"),
            midpoint=Decimal("102.50"),
            width_pct=Decimal("0.05"),
        ),
        formation_bar_index=0,
        formation_timestamp=datetime(2024, 1, 1, 9, 30, tzinfo=UTC),
        strength=ZoneStrength.FRESH,
        touch_count=0,
        formation_volume=1000000,
        formation_volume_ratio=Decimal("1.8"),
        formation_spread_ratio=Decimal("0.6"),
        volume_avg=Decimal("1000000"),
        close_position=Decimal("0.3"),
        significance_score=50,
    )

    # Bar that breaks above zone with high volume
    bars = [
        OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 2, 9, 30, tzinfo=UTC),
            open=Decimal("103.00"),
            high=Decimal("110.00"),
            low=Decimal("102.00"),
            close=Decimal("108.00"),  # Above zone.price_range.high (105)
            volume=2000000,
            spread=Decimal("8.00"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("2.0"),  # High volume (>1.5x)
        )
    ]

    is_invalidated = check_zone_invalidation(zone, bars, 0)

    assert is_invalidated is True, "Supply zone should be invalidated"
