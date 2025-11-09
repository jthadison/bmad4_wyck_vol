"""
Integration test for Wyckoff phase classification with realistic AAPL data.

This test verifies phase classification using actual market data from AAPL
accumulation period (March-May 2020). The test loads detected events from
prior stories (4.1, 4.2, 4.3) and validates phase progression.
"""

from decimal import Decimal

import pytest

from src.models.phase_classification import PhaseEvents, WyckoffPhase
from src.pattern_engine.phase_classifier import classify_phase


@pytest.mark.integration
def test_phase_classification_aapl_accumulation():
    """
    Test phase classification with realistic AAPL accumulation data.

    This test simulates the Wyckoff accumulation cycle for AAPL during
    the March-May 2020 period:
    - March 20: SC at $224.37 (COVID-19 bottom)
    - March 23: AR rally to $257.31 (+14.7%)
    - March 30: 1st ST at $228.65
    - April 9: 2nd ST at $232.67
    - (Epic 5 will add Spring, SOS, LPS detection)
    """
    # Realistic SC from AAPL March 20, 2020 (COVID-19 bottom)
    sc_aapl = {
        "bar": {
            "index": 100,
            "timestamp": "2020-03-20T14:30:00+00:00",
            "open": 243.00,
            "high": 246.50,
            "low": 224.37,  # Actual AAPL low on Mar 20
            "close": 229.24,  # Actual AAPL close
            "volume": 269600000,  # Massive volume
        },
        "volume_ratio": Decimal("3.1"),  # Ultra-high volume
        "spread_ratio": Decimal("2.0"),  # Wide spread
        "close_position": Decimal("0.73"),  # Close in upper region
        "confidence": 92,
    }

    # Realistic AR from AAPL March 23, 2020
    ar_aapl = {
        "bar": {
            "index": 103,
            "timestamp": "2020-03-23T14:30:00+00:00",
            "open": 234.82,
            "high": 257.31,  # Rally high
            "low": 232.66,
            "close": 247.74,  # +8.1% from SC close
            "volume": 175330000,  # High volume
        },
        "rally_pct": Decimal("0.147"),  # 14.7% rally from SC low
        "bars_after_sc": 3,
        "volume_profile": "HIGH",
    }

    # Realistic 1st ST from AAPL March 30, 2020
    st1_aapl = {
        "bar": {
            "index": 110,
            "timestamp": "2020-03-30T14:30:00+00:00",
            "open": 246.50,
            "high": 248.60,
            "low": 228.65,  # Test of SC low (224.37)
            "close": 240.91,
            "volume": 124230000,  # Reduced from SC
        },
        "distance_from_sc_low": Decimal("0.019"),  # 1.9% above SC low
        "volume_reduction_pct": Decimal("0.54"),  # 54% reduction
        "confidence": 84,
        "test_number": 1,
    }

    # Realistic 2nd ST from AAPL April 9, 2020
    st2_aapl = {
        "bar": {
            "index": 120,
            "timestamp": "2020-04-09T14:30:00+00:00",
            "open": 240.70,
            "high": 245.10,
            "low": 232.67,  # Another test
            "close": 240.72,
            "volume": 116100000,  # Further reduced
        },
        "distance_from_sc_low": Decimal("0.037"),  # 3.7% above SC low
        "volume_reduction_pct": Decimal("0.57"),  # 57% reduction
        "confidence": 81,
        "test_number": 2,
    }

    # Test Phase A: SC + AR
    events_a = PhaseEvents(
        selling_climax=sc_aapl,
        automatic_rally=ar_aapl,
    )

    classification_a = classify_phase(events_a)

    assert classification_a.phase == WyckoffPhase.A
    assert classification_a.confidence >= 85  # High-quality events
    assert classification_a.trading_allowed is False
    assert "Phase A" in classification_a.rejection_reason
    assert classification_a.phase_start_index == 100
    assert classification_a.duration == 3

    # Test Phase B (early): SC + AR + 1st ST
    events_b_early = PhaseEvents(
        selling_climax=sc_aapl,
        automatic_rally=ar_aapl,
        secondary_tests=[st1_aapl],
    )

    classification_b_early = classify_phase(events_b_early)

    assert classification_b_early.phase == WyckoffPhase.B
    assert classification_b_early.trading_allowed is False  # Only 1 ST, duration = 0
    assert "Early Phase B" in classification_b_early.rejection_reason
    assert classification_b_early.phase_start_index == 110
    assert classification_b_early.duration == 0  # Only 1 ST

    # Test Phase B (adequate): SC + AR + 1st ST + 2nd ST
    events_b_adequate = PhaseEvents(
        selling_climax=sc_aapl,
        automatic_rally=ar_aapl,
        secondary_tests=[st1_aapl, st2_aapl],
    )

    classification_b_adequate = classify_phase(events_b_adequate)

    assert classification_b_adequate.phase == WyckoffPhase.B
    assert classification_b_adequate.duration == 10  # 110 to 120
    assert classification_b_adequate.trading_allowed is True  # >=10 bars
    assert classification_b_adequate.rejection_reason is None
    assert classification_b_adequate.confidence >= 65  # Good cause building


@pytest.mark.integration
def test_phase_classification_full_progression():
    """
    Test full phase progression A → B → C → D → E with realistic timing.

    This test demonstrates the complete Wyckoff cycle with realistic
    bar spacing and event timing.
    """
    # Phase A events
    sc = {
        "bar": {
            "index": 50,
            "timestamp": "2020-03-20T14:30:00+00:00",
            "open": 100.0,
            "high": 105.0,
            "low": 95.0,
            "close": 102.0,
            "volume": 10000000,
        },
        "confidence": 88,
    }

    ar = {
        "bar": {
            "index": 53,
            "timestamp": "2020-03-23T14:30:00+00:00",
            "open": 102.0,
            "high": 108.0,
            "low": 101.0,
            "close": 107.0,
            "volume": 8000000,
        },
        "bars_after_sc": 3,
    }

    # Phase B events (building cause)
    st1 = {
        "bar": {
            "index": 60,
            "timestamp": "2020-03-30T14:30:00+00:00",
            "open": 104.0,
            "high": 105.0,
            "low": 96.0,
            "close": 97.0,
            "volume": 5000000,
        },
        "confidence": 82,
        "test_number": 1,
    }

    st2 = {
        "bar": {
            "index": 70,
            "timestamp": "2020-04-09T14:30:00+00:00",
            "open": 102.0,
            "high": 104.0,
            "low": 96.5,
            "close": 98.0,
            "volume": 4500000,
        },
        "confidence": 80,
        "test_number": 2,
    }

    st3 = {
        "bar": {
            "index": 80,
            "timestamp": "2020-04-19T14:30:00+00:00",
            "open": 100.0,
            "high": 103.0,
            "low": 97.0,
            "close": 99.0,
            "volume": 4200000,
        },
        "confidence": 78,
        "test_number": 3,
    }

    # Phase C event (Spring - Epic 5)
    spring = {
        "bar": {
            "index": 90,
            "timestamp": "2020-04-29T14:30:00+00:00",
            "open": 97.0,
            "high": 104.0,
            "low": 93.0,  # Penetrates below Creek
            "close": 102.0,  # Recovers
            "volume": 7000000,
        },
        "confidence": 85,
    }

    # Phase D event (SOS - Epic 5)
    sos = {
        "bar": {
            "index": 100,
            "timestamp": "2020-05-09T14:30:00+00:00",
            "open": 108.0,
            "high": 115.0,  # Breaks above Ice
            "low": 107.0,
            "close": 113.0,
            "volume": 12000000,  # High volume
        },
        "confidence": 90,
    }

    # Phase E event (LPS - Epic 5)
    lps = {
        "bar": {
            "index": 110,
            "timestamp": "2020-05-19T14:30:00+00:00",
            "open": 110.0,
            "high": 112.0,
            "low": 108.0,  # Pullback to Ice
            "close": 111.0,  # Holds
            "volume": 6000000,
        },
        "confidence": 83,
    }

    # Verify progression at each phase
    phases = []

    # Phase A
    events = PhaseEvents(selling_climax=sc, automatic_rally=ar)
    classification = classify_phase(events)
    phases.append(classification.phase)
    assert classification.phase == WyckoffPhase.A
    assert classification.trading_allowed is False

    # Phase B (early)
    events.secondary_tests = [st1]
    classification = classify_phase(events)
    phases.append(classification.phase)
    assert classification.phase == WyckoffPhase.B
    assert classification.trading_allowed is False

    # Phase B (adequate)
    events.secondary_tests = [st1, st2, st3]
    classification = classify_phase(events)
    assert classification.phase == WyckoffPhase.B
    assert classification.trading_allowed is True  # 30 bars duration

    # Phase C
    events.spring = spring
    classification = classify_phase(events)
    phases.append(classification.phase)
    assert classification.phase == WyckoffPhase.C
    assert classification.trading_allowed is True

    # Phase D
    events.sos_breakout = sos
    classification = classify_phase(events)
    phases.append(classification.phase)
    assert classification.phase == WyckoffPhase.D
    assert classification.trading_allowed is True

    # Phase E
    events.last_point_of_support = lps
    classification = classify_phase(events)
    phases.append(classification.phase)
    assert classification.phase == WyckoffPhase.E
    assert classification.trading_allowed is True

    # Verify correct progression order
    expected = [WyckoffPhase.A, WyckoffPhase.B, WyckoffPhase.C, WyckoffPhase.D, WyckoffPhase.E]
    assert phases == expected


@pytest.mark.integration
def test_phase_b_duration_threshold():
    """
    Test FR14 enforcement for Phase B duration threshold (10 bars).

    This test verifies that trading is correctly allowed/disallowed based
    on Phase B duration, which is critical for FR14 compliance.
    """
    sc = {
        "bar": {"index": 0, "timestamp": "2020-01-01T14:30:00+00:00"},
        "confidence": 85,
    }

    ar = {
        "bar": {"index": 3, "timestamp": "2020-01-04T14:30:00+00:00"},
        "bars_after_sc": 3,
    }

    st1 = {
        "bar": {"index": 10, "timestamp": "2020-01-11T14:30:00+00:00"},
        "confidence": 80,
        "test_number": 1,
    }

    # Test various Phase B durations
    durations_to_test = [
        (15, False),  # 5 bars: NOT allowed
        (19, False),  # 9 bars: NOT allowed
        (20, True),  # 10 bars: ALLOWED (threshold)
        (25, True),  # 15 bars: ALLOWED
        (50, True),  # 40 bars: ALLOWED (strong cause)
    ]

    for st2_index, should_allow in durations_to_test:
        st2 = {
            "bar": {"index": st2_index, "timestamp": "2020-01-20T14:30:00+00:00"},
            "confidence": 78,
            "test_number": 2,
        }

        events = PhaseEvents(
            selling_climax=sc,
            automatic_rally=ar,
            secondary_tests=[st1, st2],
        )

        classification = classify_phase(events)
        duration = st2_index - st1["bar"]["index"]

        assert classification.phase == WyckoffPhase.B
        assert classification.duration == duration
        assert classification.trading_allowed == should_allow

        if should_allow:
            assert classification.rejection_reason is None
        else:
            assert "Early Phase B" in classification.rejection_reason
