"""
Integration tests for SOS vs LPS entry preference logic (Story 6.4).

Tests realistic scenarios with full SOS → LPS → Entry preference workflow.
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


@pytest.fixture
def trading_range() -> TradingRange:
    """Create trading range with Ice at $100."""
    return create_simple_trading_range(Decimal("100.00"))


def test_sos_lps_entry_preference_full_flow(trading_range: TradingRange) -> None:
    """
    Integration test: Full SOS → LPS → Entry preference workflow.

    Scenario: Strong SOS at bar 25, LPS at bar 30 (5 bars after SOS).
    """
    # Step 1: SOS detected at bar 25
    sos_bar = OHLCVBar(
        symbol="AAPL",
        timeframe="1d",
        timestamp=datetime(2025, 1, 25, tzinfo=UTC),
        open=Decimal("100.00"),
        high=Decimal("103.00"),
        low=Decimal("99.50"),
        close=Decimal("102.00"),  # 2% above Ice
        volume=250000,
        spread=Decimal("3.50"),
        volume_ratio=Decimal("2.5"),  # Strong volume
        spread_ratio=Decimal("1.4"),
    )
    sos = SOSBreakout(
        bar=sos_bar,
        breakout_pct=Decimal("0.02"),
        volume_ratio=Decimal("2.5"),
        ice_reference=Decimal("100.00"),
        breakout_price=Decimal("102.00"),
        detection_timestamp=datetime(2025, 1, 25, tzinfo=UTC),
        trading_range_id=trading_range.id,
        spread_ratio=Decimal("1.4"),
        close_position=Decimal("0.75"),
        spread=Decimal("3.50"),
    )

    # Step 2: Bars 26-29 - wait for LPS (no LPS yet)
    for bars_after in range(1, 5):
        preference = determine_entry_preference(
            sos=sos,
            lps=None,  # No LPS yet
            range=trading_range,
            bars_after_sos=bars_after,
            sos_confidence=85,
        )
        # Should wait for LPS
        assert preference.entry_type == EntryType.NO_ENTRY
        assert "monitoring for pullback" in preference.user_notification.lower()
        assert preference.wait_period_complete is False

    # Step 3: LPS detected at bar 30 (5 bars after SOS)
    lps_bar = OHLCVBar(
        symbol="AAPL",
        timeframe="1d",
        timestamp=datetime(2025, 1, 30, tzinfo=UTC),
        open=Decimal("101.00"),
        high=Decimal("101.50"),
        low=Decimal("100.50"),  # 0.5% above Ice
        close=Decimal("101.00"),
        volume=120000,
        spread=Decimal("1.00"),
        volume_ratio=Decimal("0.8"),
        spread_ratio=Decimal("0.6"),
    )
    lps = LPS(
        bar=lps_bar,
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
        sos_reference=sos.id,
        held_support=True,
        pullback_low=Decimal("100.50"),
        ice_level=Decimal("100.00"),
        sos_volume=250000,
        pullback_volume=120000,
        bars_after_sos=5,
        bounce_confirmed=True,
        bounce_bar_timestamp=datetime(2025, 1, 31, tzinfo=UTC),
        detection_timestamp=datetime(2025, 1, 30, tzinfo=UTC),
        trading_range_id=trading_range.id,
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

    # Step 4: Entry preference with LPS present
    preference_with_lps = determine_entry_preference(
        sos=sos,
        lps=lps,  # LPS formed
        range=trading_range,
        bars_after_sos=5,
        sos_confidence=85,
    )

    # Verify LPS entry selected
    assert preference_with_lps.entry_type == EntryType.LPS_ENTRY
    assert preference_with_lps.stop_distance_pct == Decimal("3.0")
    assert "lps entry" in preference_with_lps.user_notification.lower()
    assert preference_with_lps.wait_period_complete is True
    assert preference_with_lps.lps_pattern is not None
    assert preference_with_lps.get_r_multiple_advantage() == "EXCELLENT"


def test_sos_no_lps_direct_entry(trading_range: TradingRange) -> None:
    """
    Strong SOS, no LPS forms, direct entry after 10 bars.

    Scenario: SOS at bar 25, no pullback, bars continue higher.
    """
    # SOS detected
    sos_bar = OHLCVBar(
        symbol="AAPL",
        timeframe="1d",
        timestamp=datetime(2025, 1, 25, tzinfo=UTC),
        open=Decimal("100.00"),
        high=Decimal("103.00"),
        low=Decimal("99.50"),
        close=Decimal("102.00"),
        volume=250000,
        spread=Decimal("3.50"),
        volume_ratio=Decimal("2.5"),
        spread_ratio=Decimal("1.4"),
    )
    sos = SOSBreakout(
        bar=sos_bar,
        breakout_pct=Decimal("0.02"),
        volume_ratio=Decimal("2.5"),  # Very strong
        ice_reference=Decimal("100.00"),
        breakout_price=Decimal("102.00"),
        detection_timestamp=datetime(2025, 1, 25, tzinfo=UTC),
        trading_range_id=trading_range.id,
        spread_ratio=Decimal("1.4"),
        close_position=Decimal("0.75"),
        spread=Decimal("3.50"),
    )

    # Bars 1-10: Wait for LPS
    for bars_after in range(1, 11):
        pref = determine_entry_preference(
            sos=sos,
            lps=None,
            range=trading_range,
            bars_after_sos=bars_after,
            sos_confidence=90,
        )
        assert pref.entry_type == EntryType.NO_ENTRY, f"Bar {bars_after}: waiting"
        assert pref.wait_period_complete is False

    # Bar 11: Wait complete, no LPS, SOS strong enough
    pref_11 = determine_entry_preference(
        sos=sos, lps=None, range=trading_range, bars_after_sos=11, sos_confidence=90
    )
    assert pref_11.entry_type == EntryType.SOS_DIRECT_ENTRY
    assert pref_11.stop_distance_pct == Decimal("5.0")
    assert "No LPS after 10 bars" in pref_11.preference_reason
    assert pref_11.wait_period_complete is True
    assert pref_11.get_r_multiple_advantage() == "GOOD"


def test_sos_no_lps_weak_sos_no_entry(trading_range: TradingRange) -> None:
    """
    Weak SOS, no LPS forms, no direct entry.

    Scenario: SOS at bar 25 (weak: 1.8x volume, 75% confidence), no pullback.
    """
    # Weak SOS
    sos_bar = OHLCVBar(
        symbol="AAPL",
        timeframe="1d",
        timestamp=datetime(2025, 1, 25, tzinfo=UTC),
        open=Decimal("100.00"),
        high=Decimal("102.50"),
        low=Decimal("99.50"),
        close=Decimal("102.00"),
        volume=180000,
        spread=Decimal("3.00"),
        volume_ratio=Decimal("1.8"),  # < 2.0x (weak)
        spread_ratio=Decimal("1.3"),
    )
    sos = SOSBreakout(
        bar=sos_bar,
        breakout_pct=Decimal("0.02"),
        volume_ratio=Decimal("1.8"),  # Doesn't meet direct entry threshold
        ice_reference=Decimal("100.00"),
        breakout_price=Decimal("102.00"),
        detection_timestamp=datetime(2025, 1, 25, tzinfo=UTC),
        trading_range_id=trading_range.id,
        spread_ratio=Decimal("1.3"),
        close_position=Decimal("0.65"),
        spread=Decimal("3.00"),
    )

    # Bars 1-10: Wait for LPS
    for bars_after in range(1, 11):
        pref = determine_entry_preference(
            sos=sos,
            lps=None,
            range=trading_range,
            bars_after_sos=bars_after,
            sos_confidence=75,  # < 80 (weak)
        )
        assert pref.entry_type == EntryType.NO_ENTRY
        assert pref.wait_period_complete is False

    # Bar 11: Wait complete, no LPS, SOS NOT strong enough
    pref_11 = determine_entry_preference(
        sos=sos, lps=None, range=trading_range, bars_after_sos=11, sos_confidence=75
    )
    assert pref_11.entry_type == EntryType.NO_ENTRY
    assert "not strong enough" in pref_11.preference_reason.lower()
    assert pref_11.wait_period_complete is True
    assert "confidence" in pref_11.preference_reason.lower()
    assert "volume" in pref_11.preference_reason.lower()


def test_realistic_multiple_attempts_scenario(trading_range: TradingRange) -> None:
    """
    Realistic scenario: Multiple bars tracked, LPS forms at bar 7.

    Timeline:
    - Bar 25: SOS detected (2.3x volume, 88% confidence)
    - Bars 26-31 (bars_after_sos 1-6): NO_ENTRY (waiting for LPS)
    - Bar 32 (bars_after_sos 7): LPS detected → LPS_ENTRY
    """
    # SOS detected
    sos_bar = OHLCVBar(
        symbol="AAPL",
        timeframe="1d",
        timestamp=datetime(2025, 1, 25, tzinfo=UTC),
        open=Decimal("100.00"),
        high=Decimal("103.00"),
        low=Decimal("99.50"),
        close=Decimal("102.30"),
        volume=230000,
        spread=Decimal("3.50"),
        volume_ratio=Decimal("2.3"),
        spread_ratio=Decimal("1.4"),
    )
    sos = SOSBreakout(
        bar=sos_bar,
        breakout_pct=Decimal("0.023"),  # 2.3% above Ice
        volume_ratio=Decimal("2.3"),
        ice_reference=Decimal("100.00"),
        breakout_price=Decimal("102.30"),
        detection_timestamp=datetime(2025, 1, 25, tzinfo=UTC),
        trading_range_id=trading_range.id,
        spread_ratio=Decimal("1.4"),
        close_position=Decimal("0.77"),
        spread=Decimal("3.50"),
    )

    # Bars 26-31: Wait for LPS (bars 1-6)
    for bars_after in range(1, 7):
        pref = determine_entry_preference(
            sos=sos, lps=None, range=trading_range, bars_after_sos=bars_after, sos_confidence=88
        )
        assert pref.entry_type == EntryType.NO_ENTRY
        assert "monitoring" in pref.preference_reason.lower()
        assert pref.wait_period_complete is False

    # Bar 32: LPS detected (bar 7)
    lps_bar = OHLCVBar(
        symbol="AAPL",
        timeframe="1d",
        timestamp=datetime(2025, 2, 1, tzinfo=UTC),
        open=Decimal("101.50"),
        high=Decimal("102.00"),
        low=Decimal("100.80"),  # 0.8% above Ice
        close=Decimal("101.20"),
        volume=115000,
        spread=Decimal("1.20"),
        volume_ratio=Decimal("0.77"),
        spread_ratio=Decimal("0.65"),
    )
    lps = LPS(
        bar=lps_bar,
        distance_from_ice=Decimal("0.008"),  # 0.8% above Ice
        distance_quality="PREMIUM",
        distance_confidence_bonus=10,
        volume_ratio=Decimal("0.50"),
        range_avg_volume=150000,
        volume_ratio_vs_avg=Decimal("0.77"),
        volume_ratio_vs_sos=Decimal("0.50"),
        pullback_spread=Decimal("1.20"),
        range_avg_spread=Decimal("2.50"),
        spread_ratio=Decimal("0.48"),
        spread_quality="NARROW",
        effort_result="NO_SUPPLY",
        effort_result_bonus=10,
        sos_reference=sos.id,
        held_support=True,
        pullback_low=Decimal("100.80"),
        ice_level=Decimal("100.00"),
        sos_volume=230000,
        pullback_volume=115000,
        bars_after_sos=7,
        bounce_confirmed=True,
        bounce_bar_timestamp=datetime(2025, 2, 2, tzinfo=UTC),
        detection_timestamp=datetime(2025, 2, 1, tzinfo=UTC),
        trading_range_id=trading_range.id,
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

    # Entry preference with LPS at bar 7
    pref_lps = determine_entry_preference(
        sos=sos, lps=lps, range=trading_range, bars_after_sos=7, sos_confidence=88
    )

    assert pref_lps.entry_type == EntryType.LPS_ENTRY
    assert pref_lps.stop_distance_pct == Decimal("3.0")
    assert pref_lps.stop_loss == Decimal("97.00")
    assert "tighter stop" in pref_lps.preference_reason.lower()
    assert pref_lps.get_r_multiple_advantage() == "EXCELLENT"


def test_edge_case_lps_at_exactly_bar_10(trading_range: TradingRange) -> None:
    """
    Edge case: LPS forms at exactly bar 10 (last possible bar).
    """
    # SOS
    sos_bar = OHLCVBar(
        symbol="AAPL",
        timeframe="1d",
        timestamp=datetime(2025, 1, 25, tzinfo=UTC),
        open=Decimal("100.00"),
        high=Decimal("103.00"),
        low=Decimal("99.50"),
        close=Decimal("102.00"),
        volume=250000,
        spread=Decimal("3.50"),
        volume_ratio=Decimal("2.5"),
        spread_ratio=Decimal("1.4"),
    )
    sos = SOSBreakout(
        bar=sos_bar,
        breakout_pct=Decimal("0.02"),
        volume_ratio=Decimal("2.5"),
        ice_reference=Decimal("100.00"),
        breakout_price=Decimal("102.00"),
        detection_timestamp=datetime(2025, 1, 25, tzinfo=UTC),
        trading_range_id=trading_range.id,
        spread_ratio=Decimal("1.4"),
        close_position=Decimal("0.75"),
        spread=Decimal("3.50"),
    )

    # Bar 10: Still waiting (NO_ENTRY)
    pref_10_no_lps = determine_entry_preference(
        sos=sos, lps=None, range=trading_range, bars_after_sos=10, sos_confidence=90
    )
    assert pref_10_no_lps.entry_type == EntryType.NO_ENTRY
    assert pref_10_no_lps.wait_period_complete is False

    # LPS detected at bar 10 (exactly at boundary)
    lps_bar = OHLCVBar(
        symbol="AAPL",
        timeframe="1d",
        timestamp=datetime(2025, 2, 4, tzinfo=UTC),
        open=Decimal("101.00"),
        high=Decimal("101.50"),
        low=Decimal("100.50"),
        close=Decimal("101.00"),
        volume=120000,
        spread=Decimal("1.00"),
        volume_ratio=Decimal("0.8"),
        spread_ratio=Decimal("0.6"),
    )
    lps = LPS(
        bar=lps_bar,
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
        sos_reference=sos.id,
        held_support=True,
        pullback_low=Decimal("100.50"),
        ice_level=Decimal("100.00"),
        sos_volume=250000,
        pullback_volume=120000,
        bars_after_sos=10,  # Exactly at boundary
        bounce_confirmed=True,
        bounce_bar_timestamp=datetime(2025, 2, 5, tzinfo=UTC),
        detection_timestamp=datetime(2025, 2, 4, tzinfo=UTC),
        trading_range_id=trading_range.id,
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

    pref_10_with_lps = determine_entry_preference(
        sos=sos, lps=lps, range=trading_range, bars_after_sos=10, sos_confidence=90
    )
    # LPS formed, so LPS entry (even at boundary)
    assert pref_10_with_lps.entry_type == EntryType.LPS_ENTRY
    assert pref_10_with_lps.stop_distance_pct == Decimal("3.0")
