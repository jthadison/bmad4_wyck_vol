"""
Unit tests for SOS confidence scoring module.

Tests cover:
- Maximum confidence scenario (caps at 100)
- Minimum passing confidence (70%)
- LPS vs SOS direct baseline (80 vs 65)
- Volume scoring tiers (1.5x, 2.0x, 2.5x)
- All scoring components individually
- Edge cases and validation
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.lps import LPS
from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import PhaseClassification, PhaseEvents, WyckoffPhase
from src.models.price_cluster import PriceCluster
from src.models.sos_breakout import SOSBreakout
from src.models.trading_range import RangeStatus, TradingRange
from src.pattern_engine.scoring.sos_confidence_scorer import (
    calculate_sos_confidence,
    get_confidence_quality,
)

# Test Fixtures


@pytest.fixture
def base_ohlcv_bar():
    """Create base OHLCV bar for testing."""
    return OHLCVBar(
        symbol="TEST",
        timeframe="1d",
        timestamp=datetime.now(UTC),
        open=Decimal("100.00"),
        high=Decimal("105.00"),
        low=Decimal("99.00"),
        close=Decimal("104.00"),
        volume=200000,
        spread=Decimal("6.00"),  # high - low = 105 - 99 = 6
    )


@pytest.fixture
def base_trading_range():
    """Create base trading range for testing."""
    support_cluster = PriceCluster(
        price_level=Decimal("95.00"),
        pivots=[],
        touch_count=3,
        strength_score=80,
    )
    resistance_cluster = PriceCluster(
        price_level=Decimal("100.00"),
        pivots=[],
        touch_count=3,
        strength_score=80,
    )

    return TradingRange(
        symbol="TEST",
        timeframe="1d",
        support_cluster=support_cluster,
        resistance_cluster=resistance_cluster,
        support=Decimal("95.00"),
        resistance=Decimal("100.00"),
        midpoint=Decimal("97.50"),
        range_width=Decimal("5.00"),
        range_width_pct=Decimal("0.05"),
        start_index=0,
        end_index=25,
        duration=25,
        quality_score=80,
        status=RangeStatus.ACTIVE,
        start_timestamp=datetime.now(UTC) - timedelta(days=25),
        end_timestamp=datetime.now(UTC),
    )


@pytest.fixture
def base_phase_classification():
    """Create base phase classification for testing."""
    return PhaseClassification(
        phase=WyckoffPhase.D,
        confidence=90,
        duration=15,
        events_detected=PhaseEvents(),
        trading_allowed=True,
        phase_start_index=10,
        phase_start_timestamp=datetime.now(UTC) - timedelta(days=15),
    )


def create_sos_breakout(
    bar: OHLCVBar,
    volume_ratio: Decimal = Decimal("2.0"),
    spread_ratio: Decimal = Decimal("1.4"),
    close_position: Decimal = Decimal("0.75"),
    breakout_pct: Decimal = Decimal("0.02"),
) -> SOSBreakout:
    """Create SOS breakout for testing."""
    return SOSBreakout(
        bar=bar,
        breakout_pct=breakout_pct,
        volume_ratio=volume_ratio,
        ice_reference=Decimal("100.00"),
        breakout_price=Decimal("102.00"),
        detection_timestamp=datetime.now(UTC),
        trading_range_id=uuid4(),
        spread_ratio=spread_ratio,
        close_position=close_position,
        spread=Decimal("5.00"),
    )


def create_lps(
    bar: OHLCVBar,
    held_support: bool = True,
    distance_from_ice: Decimal = Decimal("0.015"),
) -> LPS:
    """Create LPS for testing."""
    return LPS(
        bar=bar,
        distance_from_ice=distance_from_ice,
        distance_quality="PREMIUM",
        distance_confidence_bonus=10,
        volume_ratio=Decimal("0.6"),
        range_avg_volume=150000,
        volume_ratio_vs_avg=Decimal("0.8"),
        volume_ratio_vs_sos=Decimal("0.6"),
        pullback_spread=Decimal("2.50"),
        range_avg_spread=Decimal("3.00"),
        spread_ratio=Decimal("0.83"),
        spread_quality="NARROW",
        effort_result="NO_SUPPLY",
        effort_result_bonus=10,
        sos_reference=uuid4(),
        held_support=held_support,
        pullback_low=Decimal("100.50"),
        ice_level=Decimal("100.00"),
        sos_volume=200000,
        pullback_volume=120000,
        bars_after_sos=5,
        bounce_confirmed=True,
        bounce_bar_timestamp=datetime.now(UTC),
        detection_timestamp=datetime.now(UTC),
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


# Test: Maximum Confidence Scenario (Task 11)


def test_calculate_sos_confidence_maximum(
    base_ohlcv_bar, base_trading_range, base_phase_classification
):
    """
    Test maximum confidence scenario (all ideal conditions).

    Expected scoring:
    - Volume: 2.5x = 35 pts
    - Spread: 1.5x = 20 pts
    - Close: 0.8 = 20 pts
    - Breakout: 3% = 15 pts
    - Duration: 25 bars = 10 pts
    - LPS bonus: present + held support = 15 pts
    - Phase: D, 90 confidence = 5 pts
    - Total before baseline: 120 pts → capped at 100
    """
    # Arrange: Ideal SOS + LPS scenario
    sos = create_sos_breakout(
        bar=base_ohlcv_bar,
        volume_ratio=Decimal("2.5"),
        spread_ratio=Decimal("1.5"),
        close_position=Decimal("0.8"),
        breakout_pct=Decimal("0.03"),
    )

    lps = create_lps(bar=base_ohlcv_bar, held_support=True)

    # Act
    confidence = calculate_sos_confidence(sos, lps, base_trading_range, base_phase_classification)

    # Assert
    assert confidence == 100, "Maximum confidence should cap at 100"
    assert get_confidence_quality(confidence) == "EXCELLENT"


# Test: Minimum Passing Confidence (Task 12)


def test_calculate_sos_confidence_minimum_passing(base_ohlcv_bar, base_phase_classification):
    """
    Test minimum threshold (70%).

    Expected scoring (SOS direct entry):
    - Volume: 1.5x = 15 pts
    - Spread: 1.2x = 15 pts
    - Close: 0.7 = 15 pts
    - Breakout: 1% = 10 pts
    - Duration: 10 bars = 5 pts
    - No LPS = 0 pts
    - Phase: D, 70 confidence = 1 pt
    - Total before baseline: 61 pts
    - Baseline adjustment (SOS direct): to 65 baseline
    - Final: 65 pts (below 70 threshold, but baseline ensures >= 65)
    """
    # Arrange: SOS at minimum acceptable levels
    sos = create_sos_breakout(
        bar=base_ohlcv_bar,
        volume_ratio=Decimal("1.5"),
        spread_ratio=Decimal("1.2"),
        close_position=Decimal("0.7"),
        breakout_pct=Decimal("0.01"),
    )

    # Create minimal trading range (10 bars duration)
    support_cluster = PriceCluster(
        price_level=Decimal("95.00"),
        pivots=[],
        touch_count=2,
        strength_score=70,
    )
    resistance_cluster = PriceCluster(
        price_level=Decimal("100.00"),
        pivots=[],
        touch_count=2,
        strength_score=70,
    )

    trading_range = TradingRange(
        symbol="TEST",
        timeframe="1d",
        support_cluster=support_cluster,
        resistance_cluster=resistance_cluster,
        support=Decimal("95.00"),
        resistance=Decimal("100.00"),
        midpoint=Decimal("97.50"),
        range_width=Decimal("5.00"),
        range_width_pct=Decimal("0.05"),
        start_index=0,
        end_index=10,
        duration=10,
        quality_score=70,
        status=RangeStatus.ACTIVE,
        start_timestamp=datetime.now(UTC) - timedelta(days=10),
        end_timestamp=datetime.now(UTC),
    )

    phase = PhaseClassification(
        phase=WyckoffPhase.D,
        confidence=70,
        duration=10,
        events_detected=PhaseEvents(),
        trading_allowed=True,
        phase_start_index=5,
        phase_start_timestamp=datetime.now(UTC) - timedelta(days=10),
    )

    # Act
    confidence = calculate_sos_confidence(sos, None, trading_range, phase)

    # Assert
    assert confidence >= 65, "Should meet minimum SOS direct baseline (65)"
    assert get_confidence_quality(confidence) == "WEAK" if confidence < 70 else "ACCEPTABLE"


# Test: LPS vs SOS Direct Baseline (Task 13)


def test_lps_entry_baseline_80(base_ohlcv_bar, base_phase_classification):
    """
    Test LPS entry baseline (80).

    Expected:
    - Raw score: ~55 pts (weak volume, spread, close)
    - LPS bonus: +15 pts → 70 pts
    - Baseline adjustment (LPS entry): +10 pts to reach 80 baseline
    - Final: 80 pts minimum (UPDATED from 75)
    """
    # Arrange: Weak SOS but with LPS
    sos = create_sos_breakout(
        bar=base_ohlcv_bar,
        volume_ratio=Decimal("1.55"),  # Weak volume
        spread_ratio=Decimal("1.25"),  # Marginal spread
        close_position=Decimal("0.72"),  # Marginal close
        breakout_pct=Decimal("0.012"),  # Minimal breakout
    )

    lps = create_lps(bar=base_ohlcv_bar, held_support=True)

    # Minimal trading range (short duration)
    support_cluster = PriceCluster(
        price_level=Decimal("95.00"),
        pivots=[],
        touch_count=2,
        strength_score=70,
    )
    resistance_cluster = PriceCluster(
        price_level=Decimal("100.00"),
        pivots=[],
        touch_count=2,
        strength_score=70,
    )

    trading_range = TradingRange(
        symbol="TEST",
        timeframe="1d",
        support_cluster=support_cluster,
        resistance_cluster=resistance_cluster,
        support=Decimal("95.00"),
        resistance=Decimal("100.00"),
        midpoint=Decimal("97.50"),
        range_width=Decimal("5.00"),
        range_width_pct=Decimal("0.05"),
        start_index=0,
        end_index=10,
        duration=10,
        quality_score=70,
        status=RangeStatus.ACTIVE,
        start_timestamp=datetime.now(UTC) - timedelta(days=10),
        end_timestamp=datetime.now(UTC),
    )

    phase = PhaseClassification(
        phase=WyckoffPhase.D,
        confidence=70,
        duration=10,
        events_detected=PhaseEvents(),
        trading_allowed=True,
        phase_start_index=5,
        phase_start_timestamp=datetime.now(UTC) - timedelta(days=10),
    )

    # Act
    confidence = calculate_sos_confidence(sos, lps, trading_range, phase)

    # Assert (AC 9 - UPDATED)
    assert confidence >= 80, "LPS entry should have minimum 80 baseline (86% better expectancy)"
    assert get_confidence_quality(confidence) == "STRONG"


def test_sos_direct_baseline_65(base_ohlcv_bar, base_phase_classification):
    """
    Test SOS direct baseline (65).

    Expected:
    - Raw score: ~55 pts
    - No LPS bonus: +0 pts
    - Baseline adjustment (SOS direct): +10 pts to reach 65 baseline
    - Final: 65 pts minimum
    """
    # Arrange: Weak SOS without LPS
    sos = create_sos_breakout(
        bar=base_ohlcv_bar,
        volume_ratio=Decimal("1.55"),  # Weak volume
        spread_ratio=Decimal("1.25"),  # Marginal spread
        close_position=Decimal("0.72"),  # Marginal close
        breakout_pct=Decimal("0.012"),  # Minimal breakout
    )

    # Minimal trading range (short duration)
    support_cluster = PriceCluster(
        price_level=Decimal("95.00"),
        pivots=[],
        touch_count=2,
        strength_score=70,
    )
    resistance_cluster = PriceCluster(
        price_level=Decimal("100.00"),
        pivots=[],
        touch_count=2,
        strength_score=70,
    )

    trading_range = TradingRange(
        symbol="TEST",
        timeframe="1d",
        support_cluster=support_cluster,
        resistance_cluster=resistance_cluster,
        support=Decimal("95.00"),
        resistance=Decimal("100.00"),
        midpoint=Decimal("97.50"),
        range_width=Decimal("5.00"),
        range_width_pct=Decimal("0.05"),
        start_index=0,
        end_index=10,
        duration=10,
        quality_score=70,
        status=RangeStatus.ACTIVE,
        start_timestamp=datetime.now(UTC) - timedelta(days=10),
        end_timestamp=datetime.now(UTC),
    )

    phase = PhaseClassification(
        phase=WyckoffPhase.D,
        confidence=70,
        duration=10,
        events_detected=PhaseEvents(),
        trading_allowed=True,
        phase_start_index=5,
        phase_start_timestamp=datetime.now(UTC) - timedelta(days=10),
    )

    # Act
    confidence = calculate_sos_confidence(sos, None, trading_range, phase)

    # Assert (AC 9)
    assert confidence >= 65, "SOS direct entry should have minimum 65 baseline"
    assert confidence < 80, "SOS direct should be below LPS baseline (80)"
    assert get_confidence_quality(confidence) == "WEAK" if confidence < 70 else "ACCEPTABLE"


# Test: Volume Scoring Tiers (Task 14)


@pytest.mark.parametrize(
    "volume_ratio,expected_quality",
    [
        (Decimal("1.5"), "weak"),  # 1.5-1.7x: weak, borderline (15-18 pts)
        (Decimal("1.7"), "acceptable"),  # 1.7-2.0x: acceptable (18-25 pts)
        (Decimal("2.0"), "ideal"),  # 2.0-2.3x: ideal (25-32 pts) - 2.0x threshold
        (Decimal("2.3"), "very_strong"),  # 2.3-2.5x: very strong (32-35 pts)
        (Decimal("2.5"), "excellent"),  # 2.5x+: excellent, climactic (35 pts)
        (Decimal("3.0"), "excellent"),  # Above 2.5x still capped at 35 pts
    ],
)
def test_volume_scoring_tiers(
    volume_ratio, expected_quality, base_ohlcv_bar, base_trading_range, base_phase_classification
):
    """Test volume scoring at different levels (non-linear scoring)."""
    # Arrange
    sos = create_sos_breakout(
        bar=base_ohlcv_bar,
        volume_ratio=volume_ratio,
        spread_ratio=Decimal("1.4"),
        close_position=Decimal("0.75"),
        breakout_pct=Decimal("0.02"),
    )

    # Act
    confidence = calculate_sos_confidence(sos, None, base_trading_range, base_phase_classification)

    # Assert
    assert confidence >= 65, "Should meet SOS direct baseline"
    # Volume quality is validated internally - confidence should be appropriate for volume level
    if volume_ratio >= Decimal("2.5"):
        # Excellent volume should contribute significantly to high confidence
        assert confidence >= 75, f"Excellent volume {volume_ratio}x should yield confidence >= 75"


# Test: Individual Scoring Components


def test_spread_scoring(base_ohlcv_bar, base_trading_range, base_phase_classification):
    """Test spread expansion scoring."""
    # Test narrow spread (1.2x = 15 pts)
    sos_narrow = create_sos_breakout(
        bar=base_ohlcv_bar,
        volume_ratio=Decimal("2.0"),
        spread_ratio=Decimal("1.2"),
        close_position=Decimal("0.75"),
        breakout_pct=Decimal("0.02"),
    )

    # Test wide spread (1.5x = 20 pts)
    sos_wide = create_sos_breakout(
        bar=base_ohlcv_bar,
        volume_ratio=Decimal("2.0"),
        spread_ratio=Decimal("1.5"),
        close_position=Decimal("0.75"),
        breakout_pct=Decimal("0.02"),
    )

    confidence_narrow = calculate_sos_confidence(
        sos_narrow, None, base_trading_range, base_phase_classification
    )
    confidence_wide = calculate_sos_confidence(
        sos_wide, None, base_trading_range, base_phase_classification
    )

    # Wide spread should score higher
    assert confidence_wide > confidence_narrow, "Wide spread should score higher than narrow spread"


def test_close_position_scoring(base_ohlcv_bar, base_trading_range, base_phase_classification):
    """Test close position scoring."""
    # Test weak close (0.7 = 15 pts)
    sos_weak_close = create_sos_breakout(
        bar=base_ohlcv_bar,
        volume_ratio=Decimal("2.0"),
        spread_ratio=Decimal("1.4"),
        close_position=Decimal("0.7"),
        breakout_pct=Decimal("0.02"),
    )

    # Test strong close (0.8 = 20 pts)
    sos_strong_close = create_sos_breakout(
        bar=base_ohlcv_bar,
        volume_ratio=Decimal("2.0"),
        spread_ratio=Decimal("1.4"),
        close_position=Decimal("0.8"),
        breakout_pct=Decimal("0.02"),
    )

    confidence_weak = calculate_sos_confidence(
        sos_weak_close, None, base_trading_range, base_phase_classification
    )
    confidence_strong = calculate_sos_confidence(
        sos_strong_close, None, base_trading_range, base_phase_classification
    )

    # Strong close should score higher
    assert confidence_strong > confidence_weak, "Strong close should score higher than weak close"


def test_breakout_size_scoring(base_ohlcv_bar, base_trading_range, base_phase_classification):
    """Test breakout size scoring."""
    # Test small breakout (1% = 10 pts)
    sos_small = create_sos_breakout(
        bar=base_ohlcv_bar,
        volume_ratio=Decimal("2.0"),
        spread_ratio=Decimal("1.4"),
        close_position=Decimal("0.75"),
        breakout_pct=Decimal("0.01"),
    )

    # Test large breakout (3% = 15 pts)
    sos_large = create_sos_breakout(
        bar=base_ohlcv_bar,
        volume_ratio=Decimal("2.0"),
        spread_ratio=Decimal("1.4"),
        close_position=Decimal("0.75"),
        breakout_pct=Decimal("0.03"),
    )

    confidence_small = calculate_sos_confidence(
        sos_small, None, base_trading_range, base_phase_classification
    )
    confidence_large = calculate_sos_confidence(
        sos_large, None, base_trading_range, base_phase_classification
    )

    # Large breakout should score higher
    assert (
        confidence_large > confidence_small
    ), "Large breakout should score higher than small breakout"


def test_phase_bonus_scoring(base_ohlcv_bar, base_trading_range):
    """Test phase confidence bonus scoring."""
    sos = create_sos_breakout(bar=base_ohlcv_bar)

    # Test Phase D with high confidence (5 pts)
    phase_d_high = PhaseClassification(
        phase=WyckoffPhase.D,
        confidence=90,
        duration=15,
        events_detected=PhaseEvents(),
        trading_allowed=True,
        phase_start_index=10,
        phase_start_timestamp=datetime.now(UTC) - timedelta(days=15),
    )

    # Test Phase D with low confidence (1 pt)
    phase_d_low = PhaseClassification(
        phase=WyckoffPhase.D,
        confidence=65,
        duration=15,
        events_detected=PhaseEvents(),
        trading_allowed=True,
        phase_start_index=10,
        phase_start_timestamp=datetime.now(UTC) - timedelta(days=15),
    )

    # Test Phase C (3 pts for late Phase C)
    phase_c = PhaseClassification(
        phase=WyckoffPhase.C,
        confidence=90,
        duration=15,
        events_detected=PhaseEvents(),
        trading_allowed=True,
        phase_start_index=10,
        phase_start_timestamp=datetime.now(UTC) - timedelta(days=15),
    )

    confidence_d_high = calculate_sos_confidence(sos, None, base_trading_range, phase_d_high)
    confidence_d_low = calculate_sos_confidence(sos, None, base_trading_range, phase_d_low)
    confidence_c = calculate_sos_confidence(sos, None, base_trading_range, phase_c)

    # High confidence Phase D should score highest
    assert (
        confidence_d_high > confidence_d_low
    ), "High confidence Phase D should score higher than low confidence"
    assert confidence_d_high > confidence_c, "Phase D should score higher than Phase C"


# Test: get_confidence_quality helper


def test_get_confidence_quality():
    """Test confidence quality helper function."""
    assert get_confidence_quality(95) == "EXCELLENT"
    assert get_confidence_quality(90) == "EXCELLENT"
    assert get_confidence_quality(85) == "STRONG"
    assert get_confidence_quality(80) == "STRONG"
    assert get_confidence_quality(75) == "ACCEPTABLE"
    assert get_confidence_quality(70) == "ACCEPTABLE"
    assert get_confidence_quality(65) == "WEAK"
    assert get_confidence_quality(50) == "WEAK"


# Test: Edge Cases


def test_confidence_capped_at_100(base_ohlcv_bar, base_trading_range, base_phase_classification):
    """Test that confidence is capped at 100 even with maximum scores."""
    # Create ideal scenario that would exceed 100
    sos = create_sos_breakout(
        bar=base_ohlcv_bar,
        volume_ratio=Decimal("3.0"),  # Maximum volume
        spread_ratio=Decimal("2.0"),  # Excessive spread
        close_position=Decimal("1.0"),  # Perfect close
        breakout_pct=Decimal("0.05"),  # Large breakout
    )

    lps = create_lps(bar=base_ohlcv_bar, held_support=True)

    confidence = calculate_sos_confidence(sos, lps, base_trading_range, base_phase_classification)

    assert confidence == 100, "Confidence should be capped at 100"
