"""
Unit Tests for SignalScorer - FR28 Priority Scoring (Story 9.3).

Tests the priority scoring algorithm including:
- Normalization functions (confidence, R-multiple, pattern priority)
- Weighted FR28 calculation
- AC 7: Spring 75% confidence beats SOS 85% confidence
- AC 8: LPS with 3.5R beats SOS with 2.8R
- Edge cases (clamping, validation, tie-breaking)

Author: Story 9.3 Unit Tests
"""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.signal import ConfidenceComponents, TargetLevels, TradeSignal, ValidationChain
from src.signal_prioritization.scorer import SignalScorer


def create_valid_signal(
    pattern_type: str,
    confidence: int,
    r_multiple: Decimal,
    entry_price: Decimal = Decimal("150.00"),
    stop_loss: Decimal = Decimal("148.00"),
) -> TradeSignal:
    """
    Helper to create valid TradeSignal with correct R-multiple calculation.

    Parameters:
    -----------
    pattern_type : str
        Pattern type (SPRING, LPS, SOS, UTAD)
    confidence : int
        Confidence score (70-95)
    r_multiple : Decimal
        Desired R-multiple (target will be calculated)
    entry_price : Decimal
        Entry price (default: 150.00)
    stop_loss : Decimal
        Stop loss price (default: 148.00, must be < entry)

    Returns:
    --------
    TradeSignal
        Valid signal with correct R-multiple calculation
    """
    # Calculate target from entry/stop/r_multiple
    # r_multiple = (target - entry) / (entry - stop)
    # target = entry + (r_multiple * (entry - stop))
    risk_per_share = entry_price - stop_loss
    target_price = entry_price + (r_multiple * risk_per_share)

    # Create confidence components that match overall confidence
    # Weighted average: pattern 50%, phase 30%, volume 20%
    pattern_conf = confidence
    phase_conf = confidence
    volume_conf = confidence

    return TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        pattern_type=pattern_type,  # type: ignore
        phase="C" if pattern_type == "SPRING" else "D",
        timeframe="1d",
        entry_price=entry_price,
        stop_loss=stop_loss,
        target_levels=TargetLevels(primary_target=target_price),
        position_size=Decimal("100"),
        position_size_unit="SHARES",
        risk_amount=Decimal("200.00"),
        notional_value=Decimal("15000.00"),
        r_multiple=r_multiple,
        confidence_score=confidence,
        confidence_components=ConfidenceComponents(
            pattern_confidence=pattern_conf,
            phase_confidence=phase_conf,
            volume_confidence=volume_conf,
            overall_confidence=confidence,
        ),
        validation_chain=ValidationChain(pattern_id=uuid4()),
        timestamp=datetime.now(),
    )


@pytest.fixture
def scorer():
    """SignalScorer with default normalization ranges."""
    return SignalScorer(
        min_confidence=70,
        max_confidence=95,
        min_r_multiple=Decimal("2.0"),
        max_r_multiple=Decimal("5.0"),
    )


# =============================================================================
# Test: Confidence Normalization
# =============================================================================


def test_normalize_confidence_min_value(scorer):
    """Test confidence=70 normalizes to 0.0 (minimum)."""
    normalized = scorer.normalize_confidence(70)
    assert normalized == Decimal("0.00")


def test_normalize_confidence_max_value(scorer):
    """Test confidence=95 normalizes to 1.0 (maximum)."""
    normalized = scorer.normalize_confidence(95)
    assert normalized == Decimal("1.00")


def test_normalize_confidence_mid_value(scorer):
    """Test confidence=85 normalizes to 0.60 (mid-range)."""
    normalized = scorer.normalize_confidence(85)
    # (85-70)/(95-70) = 15/25 = 0.60
    assert normalized == Decimal("0.60")


def test_normalize_confidence_below_min_clamped(scorer):
    """Test confidence below min (60) clamped to 0.0."""
    normalized = scorer.normalize_confidence(60)
    assert normalized == Decimal("0.00")


def test_normalize_confidence_above_max_clamped(scorer):
    """Test confidence above max (100) clamped to 1.0."""
    normalized = scorer.normalize_confidence(100)
    assert normalized == Decimal("1.00")


# =============================================================================
# Test: R-Multiple Normalization
# =============================================================================


def test_normalize_r_multiple_min_value(scorer):
    """Test r=2.0 normalizes to 0.0 (minimum)."""
    normalized = scorer.normalize_r_multiple(Decimal("2.0"))
    assert normalized == Decimal("0.00")


def test_normalize_r_multiple_max_value(scorer):
    """Test r=5.0 normalizes to 1.0 (maximum)."""
    normalized = scorer.normalize_r_multiple(Decimal("5.0"))
    assert normalized == Decimal("1.00")


def test_normalize_r_multiple_mid_value(scorer):
    """Test r=3.5 normalizes to 0.50 (mid-range)."""
    normalized = scorer.normalize_r_multiple(Decimal("3.5"))
    # (3.5-2.0)/(5.0-2.0) = 1.5/3.0 = 0.50
    assert normalized == Decimal("0.50")


def test_normalize_r_multiple_below_min_clamped(scorer):
    """Test r below min (1.5) clamped to 0.0."""
    normalized = scorer.normalize_r_multiple(Decimal("1.5"))
    assert normalized == Decimal("0.00")


def test_normalize_r_multiple_above_max_clamped(scorer):
    """Test r above max (6.0) clamped to 1.0."""
    normalized = scorer.normalize_r_multiple(Decimal("6.0"))
    assert normalized == Decimal("1.00")


# =============================================================================
# Test: Pattern Priority Normalization (AC: 2, 3)
# =============================================================================


def test_normalize_pattern_priority_spring_highest(scorer):
    """Test SPRING (priority=1) normalizes to 1.0 (highest)."""
    normalized = scorer.normalize_pattern_priority("SPRING")
    # (4-1)/(4-1) = 3/3 = 1.0
    assert normalized == Decimal("1.00")


def test_normalize_pattern_priority_lps_second(scorer):
    """Test LPS (priority=2) normalizes to 0.67."""
    normalized = scorer.normalize_pattern_priority("LPS")
    # (4-2)/(4-1) = 2/3 = 0.67 (rounded)
    assert normalized == Decimal("0.67")


def test_normalize_pattern_priority_sos_third(scorer):
    """Test SOS (priority=3) normalizes to 0.33."""
    normalized = scorer.normalize_pattern_priority("SOS")
    # (4-3)/(4-1) = 1/3 = 0.33 (rounded)
    assert normalized == Decimal("0.33")


def test_normalize_pattern_priority_utad_lowest(scorer):
    """Test UTAD (priority=4) normalizes to 0.0 (lowest)."""
    normalized = scorer.normalize_pattern_priority("UTAD")
    # (4-4)/(4-1) = 0/3 = 0.0
    assert normalized == Decimal("0.00")


def test_normalize_pattern_priority_invalid_pattern_raises(scorer):
    """Test invalid pattern type raises ValueError."""
    with pytest.raises(ValueError, match="Invalid pattern_type"):
        scorer.normalize_pattern_priority("INVALID")


# =============================================================================
# Test: Weighted Priority Score Calculation (AC: 1, 4)
# =============================================================================


def test_calculate_priority_score_weighted_spring_example(scorer):
    """
    Test weighted calculation for Spring example (AC: 1, 4).

    Signal: confidence=80, r_multiple=3.0, pattern=SPRING
    Expected:
    - confidence_norm: (80-70)/(95-70) = 10/25 = 0.40
    - r_norm: (3.0-2.0)/(5.0-2.0) = 1.0/3.0 = 0.33
    - pattern_norm (Spring): 1.0
    - weighted: (0.40*0.40) + (0.33*0.30) + (1.0*0.30) = 0.16 + 0.10 + 0.30 = 0.56
    - scaled: 0.56 * 100 = 56.0
    """
    signal = create_valid_signal(pattern_type="SPRING", confidence=80, r_multiple=Decimal("3.0"))

    priority_score = scorer.calculate_priority_score(signal)

    # Verify components
    assert priority_score.components.confidence_score == 80
    assert priority_score.components.confidence_normalized == Decimal("0.40")
    assert priority_score.components.r_multiple == Decimal("3.0")
    assert priority_score.components.r_normalized == Decimal("0.33")
    assert priority_score.components.pattern_type == "SPRING"
    assert priority_score.components.pattern_priority == 1
    assert priority_score.components.pattern_normalized == Decimal("1.00")

    # Verify final score
    # (0.40*0.40) + (0.33*0.30) + (1.0*0.30) = 0.16 + 0.099 + 0.30 = 0.559 ≈ 55.90
    assert priority_score.priority_score >= Decimal("55.0")
    assert priority_score.priority_score <= Decimal("56.0")


# =============================================================================
# AC 7: Spring 75% Confidence Beats SOS 85% Confidence
# =============================================================================


def test_spring_75_confidence_beats_sos_85_confidence(scorer):
    """
    Test AC 7: Spring 75% confidence scores higher than SOS 85% confidence.

    Spring Signal:
    - confidence=75: (75-70)/(95-70) = 5/25 = 0.20
    - r_multiple=3.5: (3.5-2.0)/(5.0-2.0) = 1.5/3.0 = 0.50
    - pattern=SPRING: 1.0
    - score = (0.20*0.40) + (0.50*0.30) + (1.0*0.30) = 0.08 + 0.15 + 0.30 = 0.53 = 53.0

    SOS Signal:
    - confidence=85: (85-70)/(95-70) = 15/25 = 0.60
    - r_multiple=3.5: 0.50 (same)
    - pattern=SOS: 0.33
    - score = (0.60*0.40) + (0.50*0.30) + (0.33*0.30) = 0.24 + 0.15 + 0.10 = 0.49 = 49.0

    Expected: spring_score (53.0) > sos_score (49.0)
    Pattern priority (30% weight) outweighs 10-point confidence difference.
    """
    # Spring signal: 75% confidence
    spring_signal = create_valid_signal(
        pattern_type="SPRING",
        confidence=75,
        r_multiple=Decimal("3.5"),
    )

    # SOS signal: 85% confidence
    sos_signal = create_valid_signal(
        pattern_type="SOS",
        confidence=85,
        r_multiple=Decimal("3.5"),
    )

    spring_score = scorer.calculate_priority_score(spring_signal)
    sos_score = scorer.calculate_priority_score(sos_signal)

    # AC 7: Spring should score higher despite lower confidence
    assert spring_score.priority_score > sos_score.priority_score

    # Verify approximate scores
    assert spring_score.priority_score >= Decimal("52.0")
    assert spring_score.priority_score <= Decimal("54.0")
    assert sos_score.priority_score >= Decimal("48.0")
    assert sos_score.priority_score <= Decimal("50.0")


# =============================================================================
# AC 8: LPS with 3.5R Beats SOS with 2.8R
# =============================================================================


def test_lps_3_5r_beats_sos_2_8r(scorer):
    """
    Test AC 8: LPS with 3.5R scores higher than SOS with 2.8R.

    LPS Signal:
    - confidence=80: 0.40
    - r_multiple=3.5: (3.5-2.0)/(5.0-2.0) = 0.50
    - pattern=LPS: 0.67
    - score = (0.40*0.40) + (0.50*0.30) + (0.67*0.30) = 0.16 + 0.15 + 0.20 = 0.51 = 51.0

    SOS Signal:
    - confidence=80: 0.40 (same)
    - r_multiple=2.8: (2.8-2.0)/(5.0-2.0) = 0.8/3.0 = 0.27
    - pattern=SOS: 0.33
    - score = (0.40*0.40) + (0.27*0.30) + (0.33*0.30) = 0.16 + 0.08 + 0.10 = 0.34 = 34.0

    Expected: lps_score (51.0) > sos_score (34.0)
    Higher R-multiple (30%) + better pattern priority (30%) significantly beat SOS.
    """
    # LPS signal: 3.5R
    lps_signal = create_valid_signal(
        pattern_type="LPS",
        confidence=80,
        r_multiple=Decimal("3.5"),
    )

    # SOS signal: 2.8R
    sos_signal = create_valid_signal(
        pattern_type="SOS",
        confidence=80,
        r_multiple=Decimal("2.8"),
    )

    lps_score = scorer.calculate_priority_score(lps_signal)
    sos_score = scorer.calculate_priority_score(sos_signal)

    # AC 8: LPS should score significantly higher
    assert lps_score.priority_score > sos_score.priority_score

    # Verify approximate scores
    assert lps_score.priority_score >= Decimal("50.0")
    assert lps_score.priority_score <= Decimal("52.0")
    assert sos_score.priority_score >= Decimal("33.0")
    assert sos_score.priority_score <= Decimal("35.0")


# =============================================================================
# Test: Validation and Error Handling
# =============================================================================


def test_normalize_pattern_priority_invalid_raises(scorer):
    """Test invalid pattern type raises ValueError in normalization."""
    with pytest.raises(ValueError, match="Invalid pattern_type"):
        scorer.normalize_pattern_priority("INVALID")


# =============================================================================
# Test: Tie-Breaking with PriorityScore.__lt__ (AC: 5)
# =============================================================================


def test_priority_score_comparison_higher_score_wins():
    """Test PriorityScore comparison: higher score wins."""
    from src.models.priority import PriorityComponents, PriorityScore

    score_a = PriorityScore(
        signal_id=uuid4(),
        priority_score=Decimal("75.0"),
        components=PriorityComponents(
            confidence_score=80,
            confidence_normalized=Decimal("0.40"),
            r_multiple=Decimal("3.5"),
            r_normalized=Decimal("0.50"),
            pattern_type="SPRING",
            pattern_priority=1,
            pattern_normalized=Decimal("1.00"),
        ),
    )

    score_b = PriorityScore(
        signal_id=uuid4(),
        priority_score=Decimal("65.0"),
        components=PriorityComponents(
            confidence_score=85,
            confidence_normalized=Decimal("0.60"),
            r_multiple=Decimal("3.0"),
            r_normalized=Decimal("0.33"),
            pattern_type="SOS",
            pattern_priority=3,
            pattern_normalized=Decimal("0.33"),
        ),
    )

    # score_a (75.0) > score_b (65.0), so score_a < score_b in heap ordering
    assert score_a < score_b


def test_priority_score_tie_breaking_uses_pattern_priority():
    """Test AC 5: Equal scores use pattern_priority for tie-breaking."""
    from src.models.priority import PriorityComponents, PriorityScore

    # Both have same score (50.0)
    spring_score = PriorityScore(
        signal_id=uuid4(),
        priority_score=Decimal("50.0"),
        components=PriorityComponents(
            confidence_score=75,
            confidence_normalized=Decimal("0.20"),
            r_multiple=Decimal("3.0"),
            r_normalized=Decimal("0.33"),
            pattern_type="SPRING",
            pattern_priority=1,  # Higher priority (lower number)
            pattern_normalized=Decimal("1.00"),
        ),
    )

    sos_score = PriorityScore(
        signal_id=uuid4(),
        priority_score=Decimal("50.0"),
        components=PriorityComponents(
            confidence_score=85,
            confidence_normalized=Decimal("0.60"),
            r_multiple=Decimal("2.5"),
            r_normalized=Decimal("0.17"),
            pattern_type="SOS",
            pattern_priority=3,  # Lower priority (higher number)
            pattern_normalized=Decimal("0.33"),
        ),
    )

    # Equal scores, but Spring (priority=1) beats SOS (priority=3)
    assert spring_score < sos_score  # Spring wins in heap ordering
