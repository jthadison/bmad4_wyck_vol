"""
Unit tests for SOS vs LPS entry preference logic (Story 6.4).

Tests all 10 acceptance criteria:
1. Entry preference hierarchy: LPS (best) > SOS direct (acceptable)
2. LPS advantages: tighter stop (3% vs 5%), better R-multiple, confirmation
3. SOS direct entry requirements: confidence 80+, volume 2.0x+
4. Wait period: after SOS, wait 10 bars for potential LPS
5. If LPS forms: signal LPS entry (overrides SOS direct)
6. If no LPS after 10 bars: signal SOS direct if strong enough
7. Signal annotation: entry type (LPS_ENTRY vs SOS_DIRECT_ENTRY)
8. Unit test: LPS detected → SOS direct entry suppressed
9. Integration test: strong SOS without pullback generates direct entry
10. User notification: "LPS entry preferred - monitoring for pullback"
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.entry_preference import EntryType
from src.models.ice_level import IceLevel
from src.models.lps import LPS
from src.models.ohlcv import OHLCVBar
from src.models.pivot import Pivot, PivotType
from src.models.price_cluster import PriceCluster
from src.models.sos_breakout import SOSBreakout
from src.models.touch_detail import TouchDetail
from src.models.trading_range import RangeStatus, TradingRange
from src.pattern_engine.entry_preference import determine_entry_preference


# Test Helper Functions
def create_simple_trading_range(ice_price: Decimal = Decimal("100.00")) -> TradingRange:
    """
    Create simple trading range with Ice level (adapted from LPS detector tests).

    Args:
        ice_price: Ice level price (default: $100)

    Returns:
        TradingRange instance with Ice level for entry preference testing
    """
    support = ice_price * Decimal("0.90")
    resistance = ice_price
    midpoint = (support + resistance) / 2
    range_width = resistance - support
    range_width_pct = ((range_width / support) * Decimal("100")).quantize(Decimal("0.0001"))

    base_timestamp = datetime(2025, 1, 1, tzinfo=UTC)

    # Create minimal clusters (LPS detector pattern)
    support_pivots = []
    for i, idx in enumerate([10, 20]):
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=base_timestamp,
            open=support,
            high=support + Decimal("2.00"),
            low=support,
            close=support + Decimal("1.00"),
            volume=150000,
            spread=Decimal("2.00"),
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
        average_price=support,
        min_price=support,
        max_price=support + Decimal("0.50"),
        price_range=Decimal("0.50"),
        touch_count=2,
        cluster_type=PivotType.LOW,
        std_deviation=Decimal("0.25"),
        timestamp_range=(support_pivots[0].timestamp, support_pivots[-1].timestamp),
    )

    resistance_pivots = []
    for i, idx in enumerate([15, 25]):
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=base_timestamp,
            open=resistance - Decimal("1.00"),
            high=resistance,
            low=resistance - Decimal("2.00"),
            close=resistance - Decimal("0.50"),
            volume=150000,
            spread=Decimal("2.00"),
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
        average_price=resistance,
        min_price=resistance - Decimal("0.50"),
        max_price=resistance,
        price_range=Decimal("0.50"),
        touch_count=2,
        cluster_type=PivotType.HIGH,
        std_deviation=Decimal("0.25"),
        timestamp_range=(resistance_pivots[0].timestamp, resistance_pivots[-1].timestamp),
    )

    # Create Ice level
    ice = IceLevel(
        price=ice_price,
        absolute_high=ice_price + Decimal("1.00"),
        touch_count=2,
        touch_details=[
            TouchDetail(
                index=i,
                price=ice_price,
                volume=150000,
                volume_ratio=Decimal("1.0"),
                close_position=Decimal("0.3"),
                rejection_wick=Decimal("0.5"),
                timestamp=base_timestamp,
            )
            for i in [0, 1]
        ],
        strength_score=75,
        strength_rating="STRONG",
        last_test_timestamp=base_timestamp,
        first_test_timestamp=base_timestamp,
        hold_duration=10,
        confidence="HIGH",
        volume_trend="DECREASING",
    )

    return TradingRange(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        support_cluster=support_cluster,
        resistance_cluster=resistance_cluster,
        support=support,
        resistance=resistance,
        midpoint=midpoint,
        range_width=range_width,
        range_width_pct=range_width_pct,
        start_index=0,
        end_index=30,
        duration=31,
        quality_score=75,
        ice=ice,
        status=RangeStatus.ACTIVE,
        start_timestamp=base_timestamp,
        end_timestamp=base_timestamp,
    )


# Test Fixtures
@pytest.fixture
def trading_range() -> TradingRange:
    """Create trading range with Ice at $100."""
    return create_simple_trading_range(Decimal("100.00"))


@pytest.fixture
def sos_breakout_strong() -> SOSBreakout:
    """Create strong SOS breakout (2.5x volume, qualifies for direct entry)."""
    bar = OHLCVBar(
        symbol="AAPL",
        timeframe="1d",
        timestamp=datetime(2025, 1, 25, tzinfo=UTC),
        open=Decimal("100.00"),
        high=Decimal("103.00"),
        low=Decimal("99.50"),
        close=Decimal("102.00"),  # 2% above Ice
        volume=250000,
        spread=Decimal("3.50"),
        volume_ratio=Decimal("2.5"),  # 2.5x volume (strong)
        spread_ratio=Decimal("1.4"),
    )
    return SOSBreakout(
        bar=bar,
        breakout_pct=Decimal("0.02"),  # 2% above Ice
        volume_ratio=Decimal("2.5"),  # Very strong volume
        ice_reference=Decimal("100.00"),
        breakout_price=Decimal("102.00"),
        detection_timestamp=datetime(2025, 1, 25, tzinfo=UTC),
        trading_range_id=uuid4(),
        spread_ratio=Decimal("1.4"),  # Wide spread (conviction)
        close_position=Decimal("0.75"),  # Strong close
        spread=Decimal("3.50"),
    )


@pytest.fixture
def sos_breakout_weak() -> SOSBreakout:
    """Create weak SOS breakout (1.8x volume, doesn't qualify for direct entry)."""
    bar = OHLCVBar(
        symbol="AAPL",
        timeframe="1d",
        timestamp=datetime(2025, 1, 25, tzinfo=UTC),
        open=Decimal("100.00"),
        high=Decimal("102.50"),
        low=Decimal("99.50"),
        close=Decimal("102.00"),
        volume=180000,
        spread=Decimal("3.00"),
        volume_ratio=Decimal("1.8"),  # 1.8x volume (marginal)
        spread_ratio=Decimal("1.3"),
    )
    return SOSBreakout(
        bar=bar,
        breakout_pct=Decimal("0.02"),
        volume_ratio=Decimal("1.8"),  # < 2.0x (doesn't meet direct entry threshold)
        ice_reference=Decimal("100.00"),
        breakout_price=Decimal("102.00"),
        detection_timestamp=datetime(2025, 1, 25, tzinfo=UTC),
        trading_range_id=uuid4(),
        spread_ratio=Decimal("1.3"),
        close_position=Decimal("0.65"),
        spread=Decimal("3.00"),
    )


@pytest.fixture
def lps_pattern(sos_breakout_strong: SOSBreakout) -> LPS:
    """Create LPS pattern (pullback to Ice 5 bars after SOS)."""
    pullback_bar = OHLCVBar(
        symbol="AAPL",
        timeframe="1d",
        timestamp=datetime(2025, 1, 30, tzinfo=UTC),
        open=Decimal("101.00"),
        high=Decimal("101.50"),
        low=Decimal("100.50"),  # 0.5% above Ice
        close=Decimal("101.00"),
        volume=120000,
        spread=Decimal("1.00"),
        volume_ratio=Decimal("0.8"),  # Low volume (healthy pullback)
        spread_ratio=Decimal("0.6"),
    )
    return LPS(
        bar=pullback_bar,
        distance_from_ice=Decimal("0.005"),  # 0.5% above Ice
        distance_quality="PREMIUM",
        distance_confidence_bonus=10,
        volume_ratio=Decimal("0.48"),  # Context: 48% of SOS volume
        range_avg_volume=150000,
        volume_ratio_vs_avg=Decimal("0.80"),  # 80% of range avg (GOOD)
        volume_ratio_vs_sos=Decimal("0.48"),  # 48% of SOS (reduced)
        pullback_spread=Decimal("1.00"),
        range_avg_spread=Decimal("2.50"),
        spread_ratio=Decimal("0.40"),  # Narrow spread
        spread_quality="NARROW",
        effort_result="NO_SUPPLY",
        effort_result_bonus=10,
        sos_reference=sos_breakout_strong.id,
        held_support=True,
        pullback_low=Decimal("100.50"),
        ice_level=Decimal("100.00"),
        sos_volume=250000,
        pullback_volume=120000,
        bars_after_sos=5,  # 5 bars after SOS
        bounce_confirmed=True,
        bounce_bar_timestamp=datetime(2025, 1, 31, tzinfo=UTC),
        detection_timestamp=datetime(2025, 1, 30, tzinfo=UTC),
        trading_range_id=uuid4(),
        is_double_bottom=False,
        second_test_timestamp=None,
        atr_14=Decimal("2.50"),
        stop_distance=Decimal("3.00"),
        stop_distance_pct=Decimal("3.0"),
        stop_price=Decimal("97.00"),
        volume_trend="DECLINING",
        volume_trend_quality="EXCELLENT",
        volume_trend_bonus=5,
    )


# AC 5, 8: LPS entry preferred over SOS direct
def test_lps_entry_preferred_over_sos_direct(
    sos_breakout_strong: SOSBreakout,
    lps_pattern: LPS,
    trading_range: TradingRange,
) -> None:
    """AC 5, 8: LPS entry overrides SOS direct entry."""
    # Arrange
    sos_confidence = 90  # High confidence (qualifies for direct)

    # Act
    preference = determine_entry_preference(
        sos=sos_breakout_strong,
        lps=lps_pattern,  # LPS present
        range=trading_range,
        bars_after_sos=5,
        sos_confidence=sos_confidence,
    )

    # Assert (AC 5, 8)
    assert preference.entry_type == EntryType.LPS_ENTRY, "LPS entry should be preferred"
    assert preference.lps_pattern is not None, "LPS pattern should be included"
    assert preference.stop_distance_pct == Decimal("3.0"), "LPS stop: 3% below Ice"
    assert preference.stop_loss == Decimal("97.00"), "Stop at Ice - 3%"

    # AC 2: Verify LPS advantages
    assert "tighter stop" in preference.preference_reason.lower()
    assert "better" in preference.preference_reason.lower() and (
        "r-multiple" in preference.preference_reason.lower()
        or "risk" in preference.preference_reason.lower()
    )

    # Even though SOS qualifies for direct entry, LPS overrides
    assert preference.sos_confidence == 90
    assert sos_breakout_strong.volume_ratio >= Decimal("2.0")  # SOS strong enough


# AC 4, 10: Wait period monitoring
def test_wait_period_monitoring(
    sos_breakout_strong: SOSBreakout,
    trading_range: TradingRange,
) -> None:
    """AC 4, 10: Wait up to 10 bars for LPS before SOS direct."""
    # Test at bar 3 (within wait period)
    preference = determine_entry_preference(
        sos=sos_breakout_strong,
        lps=None,  # No LPS yet
        range=trading_range,
        bars_after_sos=3,  # 3 bars after SOS
        sos_confidence=90,
    )

    # Assert (AC 4)
    assert preference.entry_type == EntryType.NO_ENTRY, "Should wait for LPS"
    assert preference.wait_period_complete is False, "Wait period not complete"
    assert preference.bars_after_sos == 3

    # AC 10: User notification
    assert "LPS entry preferred" in preference.user_notification
    assert "monitoring for pullback" in preference.user_notification.lower()
    assert (
        "7 more bars" in preference.user_notification
        or "waiting" in preference.user_notification.lower()
    )


# AC 4: Wait period boundary (bar 10 vs 11)
def test_wait_period_boundary(
    sos_breakout_strong: SOSBreakout,
    trading_range: TradingRange,
) -> None:
    """Wait period ends at bar 10."""
    # Bar 10: still waiting
    pref_10 = determine_entry_preference(
        sos=sos_breakout_strong,
        lps=None,
        range=trading_range,
        bars_after_sos=10,
        sos_confidence=90,
    )
    assert pref_10.entry_type == EntryType.NO_ENTRY, "Bar 10: still waiting"
    assert pref_10.wait_period_complete is False

    # Bar 11: wait complete, evaluate SOS direct
    pref_11 = determine_entry_preference(
        sos=sos_breakout_strong,
        lps=None,
        range=trading_range,
        bars_after_sos=11,
        sos_confidence=90,
    )
    assert pref_11.entry_type == EntryType.SOS_DIRECT_ENTRY, "Bar 11: SOS direct if strong"
    assert pref_11.wait_period_complete is True


# AC 6, 9: Strong SOS qualifies for direct entry
def test_strong_sos_direct_entry(
    sos_breakout_strong: SOSBreakout,
    trading_range: TradingRange,
) -> None:
    """AC 6, 9: Strong SOS without pullback generates direct entry."""
    # Arrange: Strong SOS (confidence 90%, volume 2.5x)

    # Act: No LPS, wait period complete (11 bars)
    preference = determine_entry_preference(
        sos=sos_breakout_strong,
        lps=None,  # No LPS
        range=trading_range,
        bars_after_sos=11,  # Wait period complete
        sos_confidence=90,  # >= 80 (AC 3)
    )

    # Assert (AC 6, 9)
    assert preference.entry_type == EntryType.SOS_DIRECT_ENTRY
    assert preference.lps_pattern is None, "No LPS present"
    assert preference.stop_distance_pct == Decimal("5.0"), "SOS stop: 5% below Ice"
    assert preference.stop_loss == Decimal("95.00"), "Stop at Ice - 5%"
    assert preference.entry_price == Decimal("102.00"), "Entry at SOS breakout price"
    assert preference.wait_period_complete is True

    # Verify direct entry requirements met (AC 3)
    assert preference.sos_confidence >= 80
    assert sos_breakout_strong.volume_ratio >= Decimal("2.0")


# AC 3: Confidence threshold (79% vs 80%)
def test_sos_confidence_threshold(
    sos_breakout_strong: SOSBreakout,
    trading_range: TradingRange,
) -> None:
    """AC 3: Confidence >= 80 required for SOS direct."""
    # 79% confidence: NO ENTRY
    pref_79 = determine_entry_preference(
        sos=sos_breakout_strong,
        lps=None,
        range=trading_range,
        bars_after_sos=11,
        sos_confidence=79,
    )
    assert pref_79.entry_type == EntryType.NO_ENTRY, "79% confidence < 80% threshold"
    assert "confidence" in pref_79.preference_reason.lower()

    # 80% confidence: SOS DIRECT
    pref_80 = determine_entry_preference(
        sos=sos_breakout_strong,
        lps=None,
        range=trading_range,
        bars_after_sos=11,
        sos_confidence=80,
    )
    assert pref_80.entry_type == EntryType.SOS_DIRECT_ENTRY, "80% confidence >= 80% threshold"


# AC 3: Volume threshold (1.9x vs 2.0x)
def test_sos_volume_threshold() -> None:
    """AC 3: Volume >= 2.0x required for SOS direct."""
    trading_range = create_simple_trading_range()

    # 1.9x volume: NO ENTRY
    bar_19 = OHLCVBar(
        symbol="AAPL",
        timeframe="1d",
        timestamp=datetime(2025, 1, 25, tzinfo=UTC),
        open=Decimal("100.00"),
        high=Decimal("102.50"),
        low=Decimal("99.50"),
        close=Decimal("102.00"),
        volume=190000,
        spread=Decimal("3.00"),
        volume_ratio=Decimal("1.9"),
        spread_ratio=Decimal("1.3"),
    )
    sos_19 = SOSBreakout(
        bar=bar_19,
        breakout_pct=Decimal("0.02"),
        volume_ratio=Decimal("1.9"),  # < 2.0x
        ice_reference=Decimal("100.00"),
        breakout_price=Decimal("102.00"),
        detection_timestamp=datetime(2025, 1, 25, tzinfo=UTC),
        trading_range_id=uuid4(),
        spread_ratio=Decimal("1.3"),
        close_position=Decimal("0.65"),
        spread=Decimal("3.00"),
    )
    pref_19 = determine_entry_preference(
        sos=sos_19, lps=None, range=trading_range, bars_after_sos=11, sos_confidence=90
    )
    assert pref_19.entry_type == EntryType.NO_ENTRY, "1.9x volume < 2.0x threshold"
    assert "volume" in pref_19.preference_reason.lower()

    # 2.0x volume: SOS DIRECT
    bar_20 = OHLCVBar(
        symbol="AAPL",
        timeframe="1d",
        timestamp=datetime(2025, 1, 25, tzinfo=UTC),
        open=Decimal("100.00"),
        high=Decimal("103.00"),
        low=Decimal("99.50"),
        close=Decimal("102.00"),
        volume=200000,
        spread=Decimal("3.50"),
        volume_ratio=Decimal("2.0"),
        spread_ratio=Decimal("1.4"),
    )
    sos_20 = SOSBreakout(
        bar=bar_20,
        breakout_pct=Decimal("0.02"),
        volume_ratio=Decimal("2.0"),  # >= 2.0x
        ice_reference=Decimal("100.00"),
        breakout_price=Decimal("102.00"),
        detection_timestamp=datetime(2025, 1, 25, tzinfo=UTC),
        trading_range_id=uuid4(),
        spread_ratio=Decimal("1.4"),
        close_position=Decimal("0.75"),
        spread=Decimal("3.50"),
    )
    pref_20 = determine_entry_preference(
        sos=sos_20, lps=None, range=trading_range, bars_after_sos=11, sos_confidence=90
    )
    assert pref_20.entry_type == EntryType.SOS_DIRECT_ENTRY, "2.0x volume >= 2.0x threshold"


# AC 2: LPS vs SOS stop distances
def test_lps_vs_sos_stop_distance(
    sos_breakout_strong: SOSBreakout,
    lps_pattern: LPS,
    trading_range: TradingRange,
) -> None:
    """AC 2: LPS 3% stop vs SOS 5% stop."""
    # LPS Entry: 3% stop
    pref_lps = determine_entry_preference(
        sos=sos_breakout_strong,
        lps=lps_pattern,
        range=trading_range,
        bars_after_sos=5,
        sos_confidence=90,
    )
    assert pref_lps.entry_type == EntryType.LPS_ENTRY
    assert pref_lps.stop_distance_pct == Decimal("3.0"), "LPS: 3% stop"
    assert pref_lps.stop_loss == Decimal("97.00"), "Stop at Ice ($100) - 3%"

    # SOS Direct Entry: 5% stop
    pref_sos = determine_entry_preference(
        sos=sos_breakout_strong,
        lps=None,
        range=trading_range,
        bars_after_sos=11,
        sos_confidence=90,
    )
    assert pref_sos.entry_type == EntryType.SOS_DIRECT_ENTRY
    assert pref_sos.stop_distance_pct == Decimal("5.0"), "SOS: 5% stop"
    assert pref_sos.stop_loss == Decimal("95.00"), "Stop at Ice ($100) - 5%"

    # AC 2: LPS has tighter stop (better R-multiple)
    lps_stop_distance = pref_lps.stop_distance_pct
    sos_stop_distance = pref_sos.stop_distance_pct
    assert lps_stop_distance < sos_stop_distance, "LPS stop (3%) < SOS stop (5%)"

    # Verify R-multiple advantage
    assert pref_lps.get_r_multiple_advantage() == "EXCELLENT"
    assert pref_sos.get_r_multiple_advantage() == "GOOD"


# AC 7: Entry type annotation
def test_entry_type_annotation(
    sos_breakout_strong: SOSBreakout,
    lps_pattern: LPS,
    trading_range: TradingRange,
) -> None:
    """AC 7: Signal annotation indicates entry type."""
    # LPS Entry
    pref_lps = determine_entry_preference(
        sos=sos_breakout_strong,
        lps=lps_pattern,
        range=trading_range,
        bars_after_sos=5,
        sos_confidence=90,
    )
    assert pref_lps.entry_type == EntryType.LPS_ENTRY, "AC 7: LPS_ENTRY annotation"
    assert pref_lps.entry_type.value == "LPS_ENTRY"

    # SOS Direct Entry
    pref_sos = determine_entry_preference(
        sos=sos_breakout_strong,
        lps=None,
        range=trading_range,
        bars_after_sos=11,
        sos_confidence=90,
    )
    assert pref_sos.entry_type == EntryType.SOS_DIRECT_ENTRY, "AC 7: SOS_DIRECT_ENTRY annotation"
    assert pref_sos.entry_type.value == "SOS_DIRECT_ENTRY"

    # No Entry
    pref_none = determine_entry_preference(
        sos=sos_breakout_strong,
        lps=None,
        range=trading_range,
        bars_after_sos=5,
        sos_confidence=90,
    )
    assert pref_none.entry_type == EntryType.NO_ENTRY, "AC 7: NO_ENTRY annotation"


# Edge case: Missing confidence
def test_missing_confidence_no_direct_entry(
    sos_breakout_strong: SOSBreakout,
    trading_range: TradingRange,
) -> None:
    """No SOS confidence provided → no direct entry."""
    preference = determine_entry_preference(
        sos=sos_breakout_strong,
        lps=None,
        range=trading_range,
        bars_after_sos=11,
        sos_confidence=None,  # Missing confidence
    )

    assert preference.entry_type == EntryType.NO_ENTRY
    assert "confidence" in preference.preference_reason.lower()


# Edge case: LPS at bar 10 boundary
def test_lps_at_bar_10_boundary(
    sos_breakout_strong: SOSBreakout,
    trading_range: TradingRange,
) -> None:
    """LPS formed at bar 10 (boundary case)."""
    # Create LPS at exactly bar 10
    pullback_bar = OHLCVBar(
        symbol="AAPL",
        timeframe="1d",
        timestamp=datetime(2025, 2, 5, tzinfo=UTC),
        open=Decimal("101.00"),
        high=Decimal("101.50"),
        low=Decimal("100.50"),
        close=Decimal("101.00"),
        volume=120000,
        spread=Decimal("1.00"),
        volume_ratio=Decimal("0.8"),
        spread_ratio=Decimal("0.6"),
    )
    lps_at_10 = LPS(
        bar=pullback_bar,
        distance_from_ice=Decimal("0.005"),
        distance_quality="PREMIUM",
        distance_confidence_bonus=10,
        volume_ratio=Decimal("0.48"),
        range_avg_volume=150000,
        volume_ratio_vs_avg=Decimal("0.80"),
        volume_ratio_vs_sos=Decimal("0.48"),
        pullback_spread=Decimal("1.00"),
        range_avg_spread=Decimal("2.50"),
        spread_ratio=Decimal("0.40"),
        spread_quality="NARROW",
        effort_result="NO_SUPPLY",
        effort_result_bonus=10,
        sos_reference=sos_breakout_strong.id,
        held_support=True,
        pullback_low=Decimal("100.50"),
        ice_level=Decimal("100.00"),
        sos_volume=250000,
        pullback_volume=120000,
        bars_after_sos=10,  # Exactly at boundary
        bounce_confirmed=True,
        bounce_bar_timestamp=datetime(2025, 2, 6, tzinfo=UTC),
        detection_timestamp=datetime(2025, 2, 5, tzinfo=UTC),
        trading_range_id=uuid4(),
        is_double_bottom=False,
        second_test_timestamp=None,
        atr_14=Decimal("2.50"),
        stop_distance=Decimal("3.00"),
        stop_distance_pct=Decimal("3.0"),
        stop_price=Decimal("97.00"),
        volume_trend="DECLINING",
        volume_trend_quality="EXCELLENT",
        volume_trend_bonus=5,
    )

    preference = determine_entry_preference(
        sos=sos_breakout_strong,
        lps=lps_at_10,
        range=trading_range,
        bars_after_sos=10,
        sos_confidence=90,
    )

    # LPS formed, so LPS entry (even at boundary)
    assert preference.entry_type == EntryType.LPS_ENTRY
    assert preference.stop_distance_pct == Decimal("3.0")


# AC 1: Entry hierarchy validation
def test_entry_hierarchy(
    sos_breakout_strong: SOSBreakout,
    lps_pattern: LPS,
    trading_range: TradingRange,
) -> None:
    """AC 1: Entry preference hierarchy: LPS > SOS direct > No entry."""
    # Best: LPS Entry
    pref_lps = determine_entry_preference(
        sos=sos_breakout_strong,
        lps=lps_pattern,
        range=trading_range,
        bars_after_sos=5,
        sos_confidence=90,
    )
    assert pref_lps.entry_type == EntryType.LPS_ENTRY, "Best: LPS entry"
    assert pref_lps.get_r_multiple_advantage() == "EXCELLENT"

    # Acceptable: SOS Direct (no LPS, strong SOS)
    pref_sos = determine_entry_preference(
        sos=sos_breakout_strong,
        lps=None,
        range=trading_range,
        bars_after_sos=11,
        sos_confidence=90,
    )
    assert pref_sos.entry_type == EntryType.SOS_DIRECT_ENTRY, "Acceptable: SOS direct"
    assert pref_sos.get_r_multiple_advantage() == "GOOD"

    # Wait: No entry yet (within wait period)
    pref_wait = determine_entry_preference(
        sos=sos_breakout_strong,
        lps=None,
        range=trading_range,
        bars_after_sos=5,
        sos_confidence=90,
    )
    assert pref_wait.entry_type == EntryType.NO_ENTRY, "Wait: monitoring for LPS"
    assert pref_wait.wait_period_complete is False


# Multiple wait period bars test
@pytest.mark.parametrize("bars_after", [1, 3, 5, 7, 10])
def test_wait_period_progression(
    sos_breakout_strong: SOSBreakout,
    trading_range: TradingRange,
    bars_after: int,
) -> None:
    """Test wait period at multiple bars (1-10)."""
    preference = determine_entry_preference(
        sos=sos_breakout_strong,
        lps=None,
        range=trading_range,
        bars_after_sos=bars_after,
        sos_confidence=90,
    )

    # All bars 1-10 should wait for LPS
    assert preference.entry_type == EntryType.NO_ENTRY
    assert preference.wait_period_complete is False
    assert "monitoring" in preference.preference_reason.lower()
