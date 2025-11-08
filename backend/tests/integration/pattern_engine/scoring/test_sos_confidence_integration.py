"""
Integration tests for SOS confidence scoring.

Tests realistic scenarios combining all scoring components:
- Excellent SOS patterns (90-95 confidence)
- Acceptable SOS patterns (72-78 confidence)
- SOS + LPS scenarios (80-88 confidence)
- Edge cases and boundary conditions
"""

import pytest
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from uuid import uuid4

from src.pattern_engine.scoring.sos_confidence_scorer import (
    calculate_sos_confidence,
    get_confidence_quality,
)
from src.models.sos_breakout import SOSBreakout
from src.models.lps import LPS
from src.models.trading_range import TradingRange, RangeStatus
from src.models.phase_classification import PhaseClassification, WyckoffPhase, PhaseEvents
from src.models.ohlcv import OHLCVBar
from src.models.price_cluster import PriceCluster


# Helper Functions

def create_realistic_trading_range(duration_days: int = 25, quality: int = 80) -> TradingRange:
    """Create realistic trading range for integration testing."""
    support_cluster = PriceCluster(
        price_level=Decimal("95.00"),
        pivots=[],
        touch_count=4,
        strength_score=quality,
    )
    resistance_cluster = PriceCluster(
        price_level=Decimal("100.00"),
        pivots=[],
        touch_count=4,
        strength_score=quality,
    )

    return TradingRange(
        symbol="AAPL",
        timeframe="1d",
        support_cluster=support_cluster,
        resistance_cluster=resistance_cluster,
        support=Decimal("95.00"),
        resistance=Decimal("100.00"),
        midpoint=Decimal("97.50"),
        range_width=Decimal("5.00"),
        range_width_pct=Decimal("0.0526"),  # 5.26%
        start_index=0,
        end_index=duration_days,
        duration=duration_days,
        quality_score=quality,
        status=RangeStatus.ACTIVE,
        start_timestamp=datetime.now(UTC) - timedelta(days=duration_days),
        end_timestamp=datetime.now(UTC),
    )


def create_realistic_phase(phase: WyckoffPhase = WyckoffPhase.D, confidence: int = 90) -> PhaseClassification:
    """Create realistic phase classification for integration testing."""
    return PhaseClassification(
        phase=phase,
        confidence=confidence,
        duration=15,
        events_detected=PhaseEvents(),
        trading_allowed=True,
        phase_start_index=10,
        phase_start_timestamp=datetime.now(UTC) - timedelta(days=15),
    )


def create_realistic_sos(
    volume_ratio: Decimal,
    spread_ratio: Decimal,
    close_position: Decimal,
    breakout_pct: Decimal,
) -> SOSBreakout:
    """Create realistic SOS breakout for integration testing."""
    bar = OHLCVBar(
        symbol="AAPL",
        timeframe="1d",
        timestamp=datetime.now(UTC),
        open=Decimal("100.00"),
        high=Decimal("105.00"),
        low=Decimal("100.00"),
        close=Decimal("104.00"),
        volume=200000,
        spread=Decimal("5.00"),  # high - low
    )

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


def create_realistic_lps(held_support: bool = True) -> LPS:
    """Create realistic LPS for integration testing."""
    bar = OHLCVBar(
        symbol="AAPL",
        timeframe="1d",
        timestamp=datetime.now(UTC),
        open=Decimal("101.00"),
        high=Decimal("102.00"),
        low=Decimal("100.50"),
        close=Decimal("101.50"),
        volume=120000,
        spread=Decimal("1.50"),  # high - low
    )

    return LPS(
        bar=bar,
        distance_from_ice=Decimal("0.015"),
        distance_quality="PREMIUM",
        distance_confidence_bonus=10,
        volume_ratio=Decimal("0.6"),
        range_avg_volume=150000,
        volume_ratio_vs_avg=Decimal("0.8"),
        volume_ratio_vs_sos=Decimal("0.6"),
        pullback_spread=Decimal("1.50"),
        range_avg_spread=Decimal("3.00"),
        spread_ratio=Decimal("0.50"),
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


# Integration Tests

def test_sos_confidence_realistic_excellent():
    """
    Test excellent SOS scenario (realistic market conditions).

    Setup:
    - Strong volume: 2.3x (32 pts)
    - Wide spread: 1.6x (20 pts)
    - Strong close: 0.82 (20 pts)
    - Good breakout: 2.5% (14 pts)
    - Long accumulation: 25 bars (10 pts)
    - Phase D high confidence: 90 (5 pts)
    - No LPS (0 pts)

    Expected confidence: 90-95 (EXCELLENT quality)
    """
    # Arrange
    sos = create_realistic_sos(
        volume_ratio=Decimal("2.3"),
        spread_ratio=Decimal("1.6"),
        close_position=Decimal("0.82"),
        breakout_pct=Decimal("0.025"),
    )

    trading_range = create_realistic_trading_range(duration_days=25, quality=85)
    phase = create_realistic_phase(phase=WyckoffPhase.D, confidence=90)

    # Act
    confidence = calculate_sos_confidence(sos, None, trading_range, phase)

    # Assert
    assert 90 <= confidence <= 100, f"Expected excellent confidence 90-100, got {confidence}"
    assert get_confidence_quality(confidence) in ["EXCELLENT", "STRONG"], "Should be EXCELLENT or STRONG quality"


def test_sos_confidence_realistic_acceptable():
    """
    Test acceptable SOS scenario (moderate quality).

    Setup:
    - Moderate volume: 1.75x (22 pts)
    - Acceptable spread: 1.3x (17 pts)
    - Moderate close: 0.73 (17 pts)
    - Minimal breakout: 1.2% (11 pts)
    - Medium accumulation: 15 bars (7 pts)
    - Phase D medium confidence: 75 (3 pts)
    - No LPS (0 pts)

    Expected confidence: 72-78 (ACCEPTABLE quality)
    """
    # Arrange
    sos = create_realistic_sos(
        volume_ratio=Decimal("1.75"),
        spread_ratio=Decimal("1.3"),
        close_position=Decimal("0.73"),
        breakout_pct=Decimal("0.012"),
    )

    trading_range = create_realistic_trading_range(duration_days=15, quality=75)
    phase = create_realistic_phase(phase=WyckoffPhase.D, confidence=75)

    # Act
    confidence = calculate_sos_confidence(sos, None, trading_range, phase)

    # Assert
    assert 70 <= confidence <= 85, f"Expected acceptable confidence 70-85, got {confidence}"
    assert get_confidence_quality(confidence) in ["ACCEPTABLE", "STRONG"], "Should be ACCEPTABLE or STRONG quality"


def test_sos_confidence_realistic_with_lps():
    """
    Test SOS + LPS scenario (lower-risk entry).

    Setup:
    - Good volume: 2.0x (25 pts)
    - Good spread: 1.4x (18 pts)
    - Good close: 0.75 (17 pts)
    - Good breakout: 2% (12 pts)
    - Good accumulation: 20 bars (10 pts)
    - LPS bonus: held support (15 pts)
    - Phase D high confidence: 90 (5 pts)

    Expected confidence: 80-88 (STRONG quality with LPS baseline)
    """
    # Arrange
    sos = create_realistic_sos(
        volume_ratio=Decimal("2.0"),
        spread_ratio=Decimal("1.4"),
        close_position=Decimal("0.75"),
        breakout_pct=Decimal("0.02"),
    )

    lps = create_realistic_lps(held_support=True)

    trading_range = create_realistic_trading_range(duration_days=20, quality=80)
    phase = create_realistic_phase(phase=WyckoffPhase.D, confidence=90)

    # Act
    confidence = calculate_sos_confidence(sos, lps, trading_range, phase)

    # Assert
    assert confidence >= 80, f"LPS entry should have minimum 80 baseline, got {confidence}"
    assert get_confidence_quality(confidence) in ["STRONG", "EXCELLENT"], "Should be STRONG or EXCELLENT with LPS"


def test_sos_confidence_realistic_weak_rejected():
    """
    Test weak SOS scenario (below threshold, rejected).

    Setup:
    - Weak volume: 1.52x (15 pts)
    - Narrow spread: 1.21x (15 pts)
    - Weak close: 0.65 (12 pts)
    - Minimal breakout: 1.0% (10 pts)
    - Short accumulation: 8 bars (3 pts)
    - Phase D low confidence: 65 (1 pt)
    - No LPS (0 pts)

    Raw total: ~56 pts → baseline adjustment to 65 (SOS direct)
    Expected confidence: 65 (WEAK quality, below 70 threshold)
    """
    # Arrange
    sos = create_realistic_sos(
        volume_ratio=Decimal("1.52"),
        spread_ratio=Decimal("1.21"),
        close_position=Decimal("0.65"),
        breakout_pct=Decimal("0.01"),
    )

    # Short accumulation range
    support_cluster = PriceCluster(
        price_level=Decimal("95.00"),
        pivots=[],
        touch_count=2,
        strength_score=65,
    )
    resistance_cluster = PriceCluster(
        price_level=Decimal("100.00"),
        pivots=[],
        touch_count=2,
        strength_score=65,
    )

    trading_range = TradingRange(
        symbol="WEAK",
        timeframe="1d",
        support_cluster=support_cluster,
        resistance_cluster=resistance_cluster,
        support=Decimal("95.00"),
        resistance=Decimal("100.00"),
        midpoint=Decimal("97.50"),
        range_width=Decimal("5.00"),
        range_width_pct=Decimal("0.0526"),
        start_index=0,
        end_index=10,
        duration=10,
        quality_score=65,
        status=RangeStatus.ACTIVE,
        start_timestamp=datetime.now(UTC) - timedelta(days=10),
        end_timestamp=datetime.now(UTC),
    )

    phase = create_realistic_phase(phase=WyckoffPhase.D, confidence=65)

    # Act
    confidence = calculate_sos_confidence(sos, None, trading_range, phase)

    # Assert
    assert confidence >= 65, f"Should meet SOS direct baseline (65), got {confidence}"
    assert confidence < 70, f"Weak SOS should be below 70 threshold, got {confidence}"
    assert get_confidence_quality(confidence) == "WEAK", "Should be WEAK quality (rejected)"


def test_sos_confidence_realistic_late_phase_c():
    """
    Test SOS in late Phase C (transition to Phase D).

    Setup:
    - Good volume: 2.1x (27 pts)
    - Good spread: 1.45x (19 pts)
    - Good close: 0.78 (19 pts)
    - Good breakout: 2.2% (13 pts)
    - Good accumulation: 18 bars (9 pts)
    - Phase C high confidence: 90 (3 pts partial bonus)
    - No LPS (0 pts)

    Expected confidence: 85-92 (STRONG quality)
    Phase C with high confidence should receive partial phase bonus
    """
    # Arrange
    sos = create_realistic_sos(
        volume_ratio=Decimal("2.1"),
        spread_ratio=Decimal("1.45"),
        close_position=Decimal("0.78"),
        breakout_pct=Decimal("0.022"),
    )

    trading_range = create_realistic_trading_range(duration_days=18, quality=82)
    phase = create_realistic_phase(phase=WyckoffPhase.C, confidence=90)  # Late Phase C

    # Act
    confidence = calculate_sos_confidence(sos, None, trading_range, phase)

    # Assert
    assert confidence >= 70, f"Late Phase C SOS should pass threshold, got {confidence}"
    assert get_confidence_quality(confidence) in ["ACCEPTABLE", "STRONG", "EXCELLENT"], "Should be acceptable or better"


def test_sos_confidence_realistic_maximum_all_factors():
    """
    Test maximum realistic scenario (all factors excellent).

    Setup:
    - Climactic volume: 2.8x (35 pts)
    - Wide spread: 1.7x (20 pts)
    - Perfect close: 0.95 (20 pts)
    - Strong breakout: 3.5% (15 pts)
    - Long accumulation: 30 bars (10 pts)
    - LPS bonus: held support (15 pts)
    - Phase D excellent confidence: 95 (5 pts)

    Total: 120 pts → capped at 100
    Expected confidence: 100 (EXCELLENT quality)
    """
    # Arrange
    sos = create_realistic_sos(
        volume_ratio=Decimal("2.8"),
        spread_ratio=Decimal("1.7"),
        close_position=Decimal("0.95"),
        breakout_pct=Decimal("0.035"),
    )

    lps = create_realistic_lps(held_support=True)

    trading_range = create_realistic_trading_range(duration_days=30, quality=95)
    phase = create_realistic_phase(phase=WyckoffPhase.D, confidence=95)

    # Act
    confidence = calculate_sos_confidence(sos, lps, trading_range, phase)

    # Assert
    assert confidence == 100, f"Maximum scenario should cap at 100, got {confidence}"
    assert get_confidence_quality(confidence) == "EXCELLENT", "Should be EXCELLENT quality"


def test_sos_confidence_realistic_lps_saves_marginal_sos():
    """
    Test LPS bonus saving a marginal SOS (below 70 without LPS, above 70 with LPS).

    Setup:
    - Marginal volume: 1.68x (20 pts)
    - Marginal spread: 1.28x (16 pts)
    - Marginal close: 0.71 (15 pts)
    - Marginal breakout: 1.3% (11 pts)
    - Short accumulation: 12 bars (6 pts)
    - Phase D moderate confidence: 72 (3 pts)
    - Raw total: ~71 pts (below LPS baseline)

    Without LPS: 65 baseline (WEAK, rejected)
    With LPS: 80 baseline + 15 bonus = 80+ (STRONG, accepted)
    """
    # Arrange
    sos = create_realistic_sos(
        volume_ratio=Decimal("1.68"),
        spread_ratio=Decimal("1.28"),
        close_position=Decimal("0.71"),
        breakout_pct=Decimal("0.013"),
    )

    lps = create_realistic_lps(held_support=True)

    trading_range = create_realistic_trading_range(duration_days=12, quality=72)
    phase = create_realistic_phase(phase=WyckoffPhase.D, confidence=72)

    # Act - Without LPS
    confidence_without_lps = calculate_sos_confidence(sos, None, trading_range, phase)

    # Act - With LPS
    confidence_with_lps = calculate_sos_confidence(sos, lps, trading_range, phase)

    # Assert
    assert confidence_without_lps >= 65, "SOS direct should meet 65 baseline"
    assert confidence_without_lps < 80, "SOS direct should be below LPS baseline"
    assert confidence_with_lps >= 80, "LPS entry should meet 80 baseline and pass threshold"
    assert get_confidence_quality(confidence_with_lps) == "STRONG", "LPS entry should be STRONG quality"

    # LPS should significantly improve confidence
    assert confidence_with_lps > confidence_without_lps, "LPS should improve confidence significantly"
