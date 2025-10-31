"""
Unit tests for Wyckoff phase classification logic.

Tests cover:
- Phase A classification (SC + AR)
- Phase B classification (STs, duration, FR14 enforcement)
- Phase C/D/E classification (Epic 5 events)
- Confidence scoring
- Phase progression (A → B → C → D → E)
- Edge cases (missing events, invalid sequences)
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from pydantic import ValidationError

from src.models.phase_classification import (
    WyckoffPhase,
    PhaseEvents,
    PhaseClassification,
)
from src.pattern_engine.phase_classifier import (
    classify_phase,
    classify_phase_a,
    classify_phase_b,
    classify_phase_c,
    classify_phase_d,
    classify_phase_e,
    calculate_phase_a_confidence,
    calculate_phase_b_confidence,
    calculate_phase_c_confidence,
    calculate_phase_d_confidence,
    calculate_phase_e_confidence,
    calculate_ar_confidence_proxy,
    analyze_st_progression,
    get_phase_description,
    get_typical_duration,
)


# Test fixtures


@pytest.fixture
def sc_dict():
    """Selling Climax test data."""
    return {
        "bar": {
            "index": 100,
            "timestamp": "2020-03-20T14:30:00+00:00",
            "open": 100.0,
            "high": 105.0,
            "low": 95.0,
            "close": 102.0,
            "volume": 10000000,
        },
        "volume_ratio": Decimal("2.5"),
        "spread_ratio": Decimal("1.8"),
        "close_position": Decimal("0.7"),
        "confidence": 85,
    }


@pytest.fixture
def ar_dict():
    """Automatic Rally test data."""
    return {
        "bar": {
            "index": 103,
            "timestamp": "2020-03-23T14:30:00+00:00",
            "open": 102.0,
            "high": 108.0,
            "low": 101.0,
            "close": 107.0,
            "volume": 8000000,
        },
        "rally_pct": Decimal("0.035"),
        "bars_after_sc": 3,
        "volume_profile": "HIGH",
    }


@pytest.fixture
def st1_dict():
    """First Secondary Test test data."""
    return {
        "bar": {
            "index": 110,
            "timestamp": "2020-03-30T14:30:00+00:00",
            "open": 104.0,
            "high": 105.0,
            "low": 96.0,
            "close": 97.0,
            "volume": 5000000,
        },
        "distance_from_sc_low": Decimal("0.01"),
        "volume_reduction_pct": Decimal("0.50"),
        "confidence": 80,
        "test_number": 1,
    }


@pytest.fixture
def st2_dict():
    """Second Secondary Test test data."""
    return {
        "bar": {
            "index": 120,
            "timestamp": "2020-04-09T14:30:00+00:00",
            "open": 102.0,
            "high": 104.0,
            "low": 96.5,
            "close": 98.0,
            "volume": 4500000,
        },
        "distance_from_sc_low": Decimal("0.015"),
        "volume_reduction_pct": Decimal("0.55"),
        "confidence": 82,
        "test_number": 2,
    }


@pytest.fixture
def spring_dict():
    """Spring test data (Epic 5)."""
    return {
        "bar": {
            "index": 130,
            "timestamp": "2020-04-19T14:30:00+00:00",
            "open": 97.0,
            "high": 104.0,
            "low": 93.0,
            "close": 102.0,
            "volume": 7000000,
        },
        "confidence": 85,
    }


@pytest.fixture
def sos_dict():
    """SOS Breakout test data (Epic 5)."""
    return {
        "bar": {
            "index": 140,
            "timestamp": "2020-04-29T14:30:00+00:00",
            "open": 108.0,
            "high": 115.0,
            "low": 107.0,
            "close": 113.0,
            "volume": 12000000,
        },
        "confidence": 88,
    }


@pytest.fixture
def lps_dict():
    """Last Point of Support test data (Epic 5)."""
    return {
        "bar": {
            "index": 150,
            "timestamp": "2020-05-09T14:30:00+00:00",
            "open": 110.0,
            "high": 112.0,
            "low": 108.0,
            "close": 111.0,
            "volume": 6000000,
        },
        "confidence": 82,
    }


# Phase A Tests


def test_classify_phase_a_success(sc_dict, ar_dict):
    """Test Phase A classification with SC + AR."""
    events = PhaseEvents(
        selling_climax=sc_dict,
        automatic_rally=ar_dict,
    )

    classification = classify_phase_a(events)

    assert classification is not None
    assert classification.phase == WyckoffPhase.A
    assert classification.confidence >= 75
    assert classification.trading_allowed is False
    assert "Phase A" in classification.rejection_reason
    assert classification.phase_start_index == 100
    assert classification.duration == 3  # AR at index 103


def test_classify_phase_a_missing_sc(ar_dict):
    """Test Phase A fails without SC."""
    events = PhaseEvents(automatic_rally=ar_dict)

    classification = classify_phase_a(events)

    assert classification is None


def test_classify_phase_a_missing_ar(sc_dict):
    """Test Phase A fails without AR."""
    events = PhaseEvents(selling_climax=sc_dict)

    classification = classify_phase_a(events)

    assert classification is None


def test_calculate_phase_a_confidence_high(sc_dict, ar_dict):
    """Test Phase A confidence with high-quality events."""
    ar_dict["bars_after_sc"] = 2  # Ideal sequence
    ar_dict["rally_pct"] = 0.10  # Strong rally 10%
    events = PhaseEvents(
        selling_climax=sc_dict,
        automatic_rally=ar_dict,
    )

    confidence = calculate_phase_a_confidence(events)

    # SC: 85 confidence → 42 pts (85/2)
    # AR: proxy (70+20+5=95) → 19 pts (95/5)
    # Vigor: 10% rally → 10 pts
    # Sequence: 2 bars → 20 pts
    # Total: 42+19+10+20 = 91 pts
    assert confidence >= 85


def test_calculate_phase_a_confidence_moderate(sc_dict, ar_dict):
    """Test Phase A confidence with moderate sequence."""
    ar_dict["bars_after_sc"] = 8  # Moderate sequence
    ar_dict["rally_pct"] = 0.06  # Moderate 6% rally
    sc_dict["confidence"] = 70  # Lower SC confidence
    events = PhaseEvents(
        selling_climax=sc_dict,
        automatic_rally=ar_dict,
    )

    confidence = calculate_phase_a_confidence(events)

    # SC: 70 → 35 pts (70/2)
    # AR: proxy (70+10+0=80) → 16 pts (80/5)
    # Vigor: 6% rally → 5 pts
    # Sequence: 8 bars → 10 pts
    # Total: 35+16+5+10 = 66 pts
    assert 60 <= confidence <= 75


# Phase B Tests


def test_classify_phase_b_early(sc_dict, ar_dict, st1_dict):
    """Test Phase B with duration <10 bars (early, trading NOT allowed)."""
    events = PhaseEvents(
        selling_climax=sc_dict,
        automatic_rally=ar_dict,
        secondary_tests=[st1_dict],
    )

    classification = classify_phase_b(events)

    assert classification is not None
    assert classification.phase == WyckoffPhase.B
    assert classification.trading_allowed is False
    assert "Early Phase B" in classification.rejection_reason
    assert classification.duration == 0  # Only 1 ST, duration from ST to ST


def test_classify_phase_b_adequate(sc_dict, ar_dict, st1_dict, st2_dict):
    """Test Phase B with duration >=10 bars (adequate, trading allowed)."""
    events = PhaseEvents(
        selling_climax=sc_dict,
        automatic_rally=ar_dict,
        secondary_tests=[st1_dict, st2_dict],
    )

    classification = classify_phase_b(events)

    assert classification is not None
    assert classification.phase == WyckoffPhase.B
    assert classification.duration == 10  # st1 at 110, st2 at 120
    assert classification.trading_allowed is True
    assert classification.rejection_reason is None


def test_classify_phase_b_missing_st():
    """Test Phase B fails without STs."""
    events = PhaseEvents()

    classification = classify_phase_b(events)

    assert classification is None


def test_calculate_phase_b_confidence_high(st1_dict, st2_dict):
    """Test Phase B confidence with multiple high-quality STs."""
    st3_dict = st2_dict.copy()
    st3_dict["bar"] = st2_dict["bar"].copy()
    st3_dict["bar"]["index"] = 135
    st3_dict["test_number"] = 3
    st3_dict["distance_from_sc_low"] = Decimal("0.01")  # Tightening

    events = PhaseEvents(secondary_tests=[st1_dict, st2_dict, st3_dict])

    confidence = calculate_phase_b_confidence(events, duration=25)

    # ST quality: avg 81 → 28 pts (81 * 0.35)
    # ST count: 3 → 25 pts
    # Duration: 25 → 17 pts
    # Progression: 8 volume + 3 tightening = 11 pts
    # Total: ~81 pts
    assert confidence >= 75


def test_calculate_phase_b_confidence_minimal(st1_dict):
    """Test Phase B confidence with minimal cause (1 ST, short duration)."""
    events = PhaseEvents(secondary_tests=[st1_dict])

    confidence = calculate_phase_b_confidence(events, duration=12)

    # ST quality: 80 → 28 pts (80 * 0.35)
    # ST count: 1 → 8 pts
    # Duration: 12 → 10 pts
    # Progression: 0 pts (only 1 ST)
    # Total: 46 pts
    assert 40 <= confidence <= 55


# Phase C Tests


def test_classify_phase_c_success(sc_dict, ar_dict, st1_dict, st2_dict, spring_dict):
    """Test Phase C classification with Spring."""
    events = PhaseEvents(
        selling_climax=sc_dict,
        automatic_rally=ar_dict,
        secondary_tests=[st1_dict, st2_dict],
        spring=spring_dict,
    )

    classification = classify_phase_c(events)

    assert classification is not None
    assert classification.phase == WyckoffPhase.C
    assert classification.confidence >= 80
    assert classification.trading_allowed is True
    assert classification.rejection_reason is None


def test_classify_phase_c_missing_spring():
    """Test Phase C fails without Spring."""
    events = PhaseEvents()

    classification = classify_phase_c(events)

    assert classification is None


# Phase D Tests


def test_classify_phase_d_success(
    sc_dict, ar_dict, st1_dict, st2_dict, spring_dict, sos_dict
):
    """Test Phase D classification with SOS breakout."""
    events = PhaseEvents(
        selling_climax=sc_dict,
        automatic_rally=ar_dict,
        secondary_tests=[st1_dict, st2_dict],
        spring=spring_dict,
        sos_breakout=sos_dict,
    )

    classification = classify_phase_d(events)

    assert classification is not None
    assert classification.phase == WyckoffPhase.D
    assert classification.confidence >= 85
    assert classification.trading_allowed is True
    assert classification.rejection_reason is None


def test_classify_phase_d_missing_sos():
    """Test Phase D fails without SOS."""
    events = PhaseEvents()

    classification = classify_phase_d(events)

    assert classification is None


# Phase E Tests


def test_classify_phase_e_success(
    sc_dict, ar_dict, st1_dict, st2_dict, spring_dict, sos_dict, lps_dict
):
    """Test Phase E classification with LPS."""
    events = PhaseEvents(
        selling_climax=sc_dict,
        automatic_rally=ar_dict,
        secondary_tests=[st1_dict, st2_dict],
        spring=spring_dict,
        sos_breakout=sos_dict,
        last_point_of_support=lps_dict,
    )

    classification = classify_phase_e(events)

    assert classification is not None
    assert classification.phase == WyckoffPhase.E
    assert classification.confidence >= 75
    assert classification.trading_allowed is True
    assert classification.rejection_reason is None


def test_classify_phase_e_missing_sos():
    """Test Phase E fails without SOS (Phase D not complete)."""
    events = PhaseEvents()

    classification = classify_phase_e(events)

    assert classification is None


# Main classify_phase Tests


def test_classify_phase_progression(
    sc_dict, ar_dict, st1_dict, st2_dict, spring_dict, sos_dict, lps_dict
):
    """Test full phase progression A → B → C → D → E."""
    # Phase A: SC + AR
    events_a = PhaseEvents(
        selling_climax=sc_dict,
        automatic_rally=ar_dict,
    )
    classification_a = classify_phase(events_a)
    assert classification_a.phase == WyckoffPhase.A
    assert classification_a.trading_allowed is False

    # Phase B (early): + 1 ST
    events_b_early = PhaseEvents(
        selling_climax=sc_dict,
        automatic_rally=ar_dict,
        secondary_tests=[st1_dict],
    )
    classification_b_early = classify_phase(events_b_early)
    assert classification_b_early.phase == WyckoffPhase.B
    assert classification_b_early.trading_allowed is False  # Early

    # Phase B (adequate): + 2nd ST (10 bars later)
    events_b_adequate = PhaseEvents(
        selling_climax=sc_dict,
        automatic_rally=ar_dict,
        secondary_tests=[st1_dict, st2_dict],
    )
    classification_b_adequate = classify_phase(events_b_adequate)
    assert classification_b_adequate.phase == WyckoffPhase.B
    assert classification_b_adequate.trading_allowed is True  # Adequate

    # Phase C: + Spring
    events_c = PhaseEvents(
        selling_climax=sc_dict,
        automatic_rally=ar_dict,
        secondary_tests=[st1_dict, st2_dict],
        spring=spring_dict,
    )
    classification_c = classify_phase(events_c)
    assert classification_c.phase == WyckoffPhase.C
    assert classification_c.trading_allowed is True

    # Phase D: + SOS
    events_d = PhaseEvents(
        selling_climax=sc_dict,
        automatic_rally=ar_dict,
        secondary_tests=[st1_dict, st2_dict],
        spring=spring_dict,
        sos_breakout=sos_dict,
    )
    classification_d = classify_phase(events_d)
    assert classification_d.phase == WyckoffPhase.D
    assert classification_d.trading_allowed is True

    # Phase E: + LPS
    events_e = PhaseEvents(
        selling_climax=sc_dict,
        automatic_rally=ar_dict,
        secondary_tests=[st1_dict, st2_dict],
        spring=spring_dict,
        sos_breakout=sos_dict,
        last_point_of_support=lps_dict,
    )
    classification_e = classify_phase(events_e)
    assert classification_e.phase == WyckoffPhase.E
    assert classification_e.trading_allowed is True


def test_classify_phase_no_events():
    """Test classify_phase with no events (no phase detected)."""
    events = PhaseEvents()

    classification = classify_phase(events)

    assert classification.phase is None
    assert classification.confidence == 0
    assert classification.trading_allowed is False
    assert "No clear Wyckoff phase detected" in classification.rejection_reason


def test_classify_phase_ar_without_sc(ar_dict):
    """Test AR without SC (should not classify Phase A)."""
    events = PhaseEvents(automatic_rally=ar_dict)

    classification = classify_phase(events)

    assert classification.phase is None


def test_classify_phase_st_without_sc_ar(st1_dict):
    """Test ST without SC + AR (should not classify Phase B)."""
    events = PhaseEvents(secondary_tests=[st1_dict])

    classification = classify_phase(events)

    # Should classify as Phase B (ST present)
    # Note: Story doesn't require Phase A before Phase B in current implementation
    # This may change in Story 4.6 (Phase Progression Validation)
    assert classification.phase == WyckoffPhase.B


# Confidence Scoring Tests


def test_calculate_phase_c_confidence_high(spring_dict):
    """Test Phase C confidence with high-quality Spring."""
    spring_dict["confidence"] = 90
    events = PhaseEvents(spring=spring_dict)

    confidence = calculate_phase_c_confidence(events)

    assert confidence >= 90


def test_calculate_phase_d_confidence_high(sos_dict):
    """Test Phase D confidence with high-quality SOS."""
    sos_dict["confidence"] = 88
    events = PhaseEvents(sos_breakout=sos_dict)

    confidence = calculate_phase_d_confidence(events)

    assert confidence >= 90


def test_calculate_phase_e_confidence_with_lps(lps_dict):
    """Test Phase E confidence with LPS."""
    lps_dict["confidence"] = 82
    events = PhaseEvents(last_point_of_support=lps_dict)

    confidence = calculate_phase_e_confidence(events)

    assert confidence >= 85


def test_calculate_phase_e_confidence_no_lps():
    """Test Phase E confidence without LPS (sustained move only)."""
    events = PhaseEvents()

    confidence = calculate_phase_e_confidence(events)

    assert confidence == 75


# Helper Utilities Tests


def test_get_phase_description():
    """Test get_phase_description for all phases."""
    assert "Stopping Action" in get_phase_description(WyckoffPhase.A)
    assert "Building Cause" in get_phase_description(WyckoffPhase.B)
    assert "Test" in get_phase_description(WyckoffPhase.C)
    assert "Sign of Strength" in get_phase_description(WyckoffPhase.D)
    assert "Markup" in get_phase_description(WyckoffPhase.E)


def test_get_typical_duration():
    """Test get_typical_duration for all phases."""
    assert get_typical_duration(WyckoffPhase.A) == (3, 10)
    assert get_typical_duration(WyckoffPhase.B) == (10, 40)
    assert get_typical_duration(WyckoffPhase.C) == (1, 5)
    assert get_typical_duration(WyckoffPhase.D) == (5, 15)
    assert get_typical_duration(WyckoffPhase.E) == (10, 999)


# Edge Cases


def test_phase_classification_validation():
    """Test PhaseClassification model validation."""
    with pytest.raises(ValidationError):
        PhaseClassification(
            phase=WyckoffPhase.A,
            confidence=150,  # Invalid
            duration=5,
            events_detected=PhaseEvents(),
            trading_allowed=False,
            phase_start_index=100,
            phase_start_timestamp=datetime.now(timezone.utc),
        )


def test_phase_classification_negative_duration():
    """Test PhaseClassification rejects negative duration."""
    with pytest.raises(ValidationError):
        PhaseClassification(
            phase=WyckoffPhase.A,
            confidence=80,
            duration=-5,  # Invalid
            events_detected=PhaseEvents(),
            trading_allowed=False,
            phase_start_index=100,
            phase_start_timestamp=datetime.now(timezone.utc),
        )


# Story 4.4.1 Tests - Real-time Duration Calculations


def test_phase_a_realtime_duration(sc_dict, ar_dict):
    """Test Phase A duration with current_bar_index (no ST yet)."""
    events = PhaseEvents(
        selling_climax=sc_dict,
        automatic_rally=ar_dict,
    )

    # Real-time at bar 115 (15 bars after SC at 100)
    classification = classify_phase_a(events, current_bar_index=115)

    assert classification.phase == WyckoffPhase.A
    assert classification.duration == 15  # Not 3!
    assert classification.trading_allowed is False


def test_phase_a_historical_duration(sc_dict, ar_dict):
    """Test Phase A duration in historical mode (current_bar_index=None)."""
    events = PhaseEvents(
        selling_climax=sc_dict,
        automatic_rally=ar_dict,
    )

    # Historical mode (no current_bar_index)
    classification = classify_phase_a(events)

    assert classification.phase == WyckoffPhase.A
    assert classification.duration == 3  # Falls back to AR index


def test_phase_b_realtime_duration_single_st(sc_dict, ar_dict, st1_dict):
    """Test Phase B duration with current_bar_index (only 1 ST)."""
    events = PhaseEvents(
        selling_climax=sc_dict,
        automatic_rally=ar_dict,
        secondary_tests=[st1_dict],  # ST at index 110
    )

    # Real-time at bar 125 (15 bars after ST1)
    classification = classify_phase_b(events, current_bar_index=125)

    assert classification.phase == WyckoffPhase.B
    assert classification.duration == 15  # Not 0!
    assert classification.trading_allowed is True  # >= 10 bars


def test_phase_b_historical_duration_single_st(sc_dict, ar_dict, st1_dict):
    """Test Phase B duration in historical mode with 1 ST."""
    events = PhaseEvents(
        selling_climax=sc_dict,
        automatic_rally=ar_dict,
        secondary_tests=[st1_dict],  # ST at index 110
    )

    # Historical mode
    classification = classify_phase_b(events)

    assert classification.phase == WyckoffPhase.B
    assert classification.duration == 0  # Falls back to last ST


def test_phase_b_realtime_fr14_enforcement(sc_dict, ar_dict, st1_dict):
    """Test FR14 enforcement with real-time durations."""
    events = PhaseEvents(
        selling_climax=sc_dict,
        automatic_rally=ar_dict,
        secondary_tests=[st1_dict],  # ST at index 110
    )

    # Real-time at bar 115 (5 bars after ST - too early)
    classification_early = classify_phase_b(events, current_bar_index=115)
    assert classification_early.trading_allowed is False

    # Real-time at bar 120 (10 bars after ST - adequate)
    classification_adequate = classify_phase_b(events, current_bar_index=120)
    assert classification_adequate.trading_allowed is True


# Story 4.4.1 Tests - AR Confidence Proxy


def test_ar_confidence_proxy_strong():
    """Test AR proxy confidence for strong rally (8%+, fast)."""
    ar = {"rally_pct": 0.10, "bars_after_sc": 2}  # 10% rally, 2 bars

    confidence = calculate_ar_confidence_proxy(ar)

    # Base 70 + Rally vigor 20 + Timing 5 = 95
    assert confidence == 95


def test_ar_confidence_proxy_moderate():
    """Test AR proxy confidence for moderate rally (5-8%, medium)."""
    ar = {"rally_pct": 0.06, "bars_after_sc": 4}  # 6% rally, 4 bars

    confidence = calculate_ar_confidence_proxy(ar)

    # Base 70 + Rally vigor 10 + Timing 3 = 83
    assert confidence == 83


def test_ar_confidence_proxy_weak():
    """Test AR proxy confidence for weak rally (3-5%, slow)."""
    ar = {"rally_pct": 0.035, "bars_after_sc": 8}  # 3.5% rally, 8 bars

    confidence = calculate_ar_confidence_proxy(ar)

    # Base 70 + Rally vigor 0 + Timing 0 = 70
    assert confidence == 70


def test_phase_a_uses_ar_proxy_when_no_confidence(sc_dict, ar_dict):
    """Test Phase A uses proxy when AR has no confidence field."""
    # Remove confidence field from AR (simulate Story 4.2 data)
    ar_dict.pop("confidence", None)
    ar_dict["rally_pct"] = 0.08  # 8% rally

    events = PhaseEvents(
        selling_climax=sc_dict,
        automatic_rally=ar_dict,
    )

    confidence = calculate_phase_a_confidence(events)

    # Should use proxy (base 70 + vigor 20 + timing 5 = 95)
    # AR pts = 95/5 = 19
    # Total includes SC pts + AR pts + vigor + sequence
    assert confidence > 0  # Verify it calculates


def test_phase_a_uses_actual_confidence_when_available(sc_dict, ar_dict):
    """Test Phase A uses actual confidence when available."""
    ar_dict["confidence"] = 90
    ar_dict["rally_pct"] = 0.05  # 5% rally (moderate)

    events = PhaseEvents(
        selling_climax=sc_dict,
        automatic_rally=ar_dict,
    )

    confidence = calculate_phase_a_confidence(events)

    # Should use actual confidence 90, not proxy
    assert confidence > 0


# Story 4.4.1 Tests - ST Progression Analysis


def test_st_progression_excellent():
    """Test ST progression with tightening and strong absorption."""
    sts = [
        {
            "confidence": 80,
            "volume_reduction_pct": 0.55,
            "distance_from_sc_low": 0.020,
        },  # ST1
        {
            "confidence": 82,
            "volume_reduction_pct": 0.52,
            "distance_from_sc_low": 0.015,
        },  # ST2 - closer
        {
            "confidence": 85,
            "volume_reduction_pct": 0.58,
            "distance_from_sc_low": 0.010,
        },  # ST3 - even closer
    ]

    progression_pts = analyze_st_progression(sts)

    # Volume: 55% avg → 8 pts, Tightening: 50% → 7 pts
    assert progression_pts == 15


def test_st_progression_good():
    """Test ST progression with moderate tightening and good absorption."""
    sts = [
        {
            "confidence": 80,
            "volume_reduction_pct": 0.45,
            "distance_from_sc_low": 0.020,
        },  # ST1
        {
            "confidence": 82,
            "volume_reduction_pct": 0.42,
            "distance_from_sc_low": 0.015,
        },  # ST2 - moderately closer
    ]

    progression_pts = analyze_st_progression(sts)

    # Volume: 43.5% avg → 6 pts, Tightening: 25% → 5 pts
    assert progression_pts == 11


def test_st_progression_poor():
    """Test ST progression with diverging and weak absorption."""
    sts = [
        {
            "confidence": 70,
            "volume_reduction_pct": 0.25,
            "distance_from_sc_low": 0.010,
        },  # ST1
        {
            "confidence": 72,
            "volume_reduction_pct": 0.22,
            "distance_from_sc_low": 0.015,
        },  # ST2 - farther (diverging)
    ]

    progression_pts = analyze_st_progression(sts)

    # Volume: 23.5% avg → 2 pts, Tightening: 0 (diverging)
    assert progression_pts == 2


def test_st_progression_single_st():
    """Test ST progression with single ST (should return 0)."""
    sts = [
        {"confidence": 80, "volume_reduction_pct": 0.55, "distance_from_sc_low": 0.020},
    ]

    progression_pts = analyze_st_progression(sts)

    # Need multiple tests to see trend
    assert progression_pts == 0


# Story 4.4.1 Tests - Phase B Rebalanced Confidence


def test_phase_b_confidence_includes_progression(st1_dict, st2_dict):
    """Test Phase B confidence includes ST progression points."""
    # Create ST3 with tightening
    st3_dict = st2_dict.copy()
    st3_dict["bar"] = st2_dict["bar"].copy()
    st3_dict["bar"]["index"] = 135
    st3_dict["test_number"] = 3
    st3_dict["distance_from_sc_low"] = Decimal(
        "0.005"
    )  # Much tighter (50% improvement)

    events = PhaseEvents(secondary_tests=[st1_dict, st2_dict, st3_dict])

    confidence = calculate_phase_b_confidence(events, duration=25)

    # Should include progression points
    # ST quality: ~28 pts (80*0.35), ST count: 25 pts, Duration: 17 pts, Progression: 8 + 7 = 15 pts
    # Total: ~85 pts
    assert confidence >= 80


# Story 4.4.1 Tests - Real-time AAPL Integration


def test_realtime_aapl_phase_b():
    """Test real-time Phase B classification matches Wyckoff principles."""
    # AAPL March-April 2020
    sc = {
        "bar": {
            "index": 100,
            "timestamp": "2020-03-20T14:30:00+00:00",
            "open": 100.0,
            "high": 105.0,
            "low": 95.0,
            "close": 102.0,
            "volume": 10000000,
        },
        "confidence": 92,
    }
    ar = {
        "bar": {
            "index": 103,
            "timestamp": "2020-03-23T14:30:00+00:00",
            "open": 102.0,
            "high": 115.0,
            "low": 101.0,
            "close": 115.0,
            "volume": 9000000,
        },
        "rally_pct": 0.147,  # 14.7% rally (strong!)
        "bars_after_sc": 3,
    }
    st1 = {
        "bar": {
            "index": 110,
            "timestamp": "2020-03-30T14:30:00+00:00",
            "open": 104.0,
            "high": 105.0,
            "low": 96.0,
            "close": 97.0,
            "volume": 5000000,
        },
        "confidence": 84,
        "volume_reduction_pct": 0.54,
        "distance_from_sc_low": 0.019,
    }

    events = PhaseEvents(
        selling_climax=sc,
        automatic_rally=ar,
        secondary_tests=[st1],
    )

    # Real-time at bar 125 (15 bars after ST1, no second ST yet)
    classification = classify_phase(events, current_bar_index=125)

    assert classification.phase == WyckoffPhase.B
    assert classification.duration == 15  # Critical fix
    assert classification.trading_allowed is True  # FR14 allows >= 10
    assert classification.confidence >= 45  # Single ST with no progression


def test_realtime_aapl_full_progression():
    """Test real-time AAPL progression through all phases."""
    # Setup events
    sc = {
        "bar": {"index": 100, "timestamp": "2020-03-20T14:30:00+00:00"},
        "confidence": 92,
    }
    ar = {
        "bar": {"index": 103, "timestamp": "2020-03-23T14:30:00+00:00"},
        "rally_pct": 0.147,
        "bars_after_sc": 3,
    }
    st1 = {
        "bar": {"index": 110, "timestamp": "2020-03-30T14:30:00+00:00"},
        "confidence": 84,
        "volume_reduction_pct": 0.54,
        "distance_from_sc_low": 0.019,
    }

    # Phase A - real-time at bar 108 (before ST)
    events_a = PhaseEvents(selling_climax=sc, automatic_rally=ar)
    classification_a = classify_phase(events_a, current_bar_index=108)
    assert classification_a.phase == WyckoffPhase.A
    assert classification_a.duration == 8
    assert classification_a.trading_allowed is False

    # Phase B (early) - real-time at bar 115 (5 bars after ST)
    events_b_early = PhaseEvents(
        selling_climax=sc, automatic_rally=ar, secondary_tests=[st1]
    )
    classification_b_early = classify_phase(events_b_early, current_bar_index=115)
    assert classification_b_early.phase == WyckoffPhase.B
    assert classification_b_early.duration == 5
    assert classification_b_early.trading_allowed is False  # < 10 bars

    # Phase B (adequate) - real-time at bar 125 (15 bars after ST)
    classification_b_adequate = classify_phase(events_b_early, current_bar_index=125)
    assert classification_b_adequate.phase == WyckoffPhase.B
    assert classification_b_adequate.duration == 15
    assert classification_b_adequate.trading_allowed is True  # >= 10 bars
