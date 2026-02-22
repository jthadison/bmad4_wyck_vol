"""
Unit Tests for Selling Climax (SC) Pattern Detector (Story 25.9)

Test Coverage:
--------------
- AC1: SC detects valid selling climax
- AC2: SC rejects normal-volume bars (volume_ratio < 2.0)
- AC3: SC rejects bars with close in lower half
- AC9: Edge cases handled gracefully (zero-volume, doji, gaps)

Detector Implementation: backend/src/pattern_engine/_phase_detector_impl.py lines 105-176

Thresholds (verified from implementation):
- volume_ratio >= 2.0 (Filter 3, line 125)
- spread_ratio >= 1.5 (Filter 4, line 135)
- close_position >= 0.5 (Filter 5, line 155)
- current_bar.close < prior_bar.close (Filter 6, line 168)

Author: Story 25.9 Implementation
"""

from decimal import Decimal

import pytest

from src.models.volume_analysis import EffortResult, VolumeAnalysis
from src.pattern_engine._phase_detector_impl import detect_selling_climax
from tests.pattern_engine.detectors.conftest import create_test_bar


@pytest.fixture
def minimal_sc_bars(base_timestamp):
    """Minimal valid bar sequence for SC detection (2 bars: prior + SC candidate)."""
    return [
        create_test_bar(
            timestamp=base_timestamp,
            open_price=100.0,
            high=102.0,
            low=99.0,
            close=101.0,
            volume=1000,
        ),
        create_test_bar(
            timestamp=base_timestamp.replace(day=2),
            open_price=101.0,
            high=101.0,
            low=95.0,  # Sharp down move
            close=100.0,  # Close in upper half (100 vs 95-101 range)
            volume=2000,  # 2.0x volume
        ),
    ]


@pytest.fixture
def minimal_sc_volume_analysis(minimal_sc_bars):
    """Volume analysis for minimal_sc_bars fixture."""
    return [
        VolumeAnalysis(
            bar=minimal_sc_bars[0],
            volume_ratio=Decimal("1.0"),
            spread_ratio=Decimal("1.0"),
            effort_result=EffortResult.NORMAL,
            close_position=Decimal("0.67"),
        ),
        VolumeAnalysis(
            bar=minimal_sc_bars[1],
            volume_ratio=Decimal("2.0"),  # At threshold
            spread_ratio=Decimal("2.0"),  # Above threshold (1.5)
            effort_result=EffortResult.CLIMACTIC,
            close_position=Decimal("0.83"),  # In upper half
        ),
    ]


# =============================================================================
# POSITIVE DETECTION TESTS (AC1)
# =============================================================================


def test_sc_detects_valid_selling_climax(minimal_sc_bars, minimal_sc_volume_analysis):
    """AC1: SC detects valid selling climax with all filters passing."""
    sc = detect_selling_climax(minimal_sc_bars, minimal_sc_volume_analysis)

    assert sc is not None
    assert sc.bar["symbol"] == "TEST"
    assert Decimal(sc.bar["low"]) == Decimal("95.0")
    assert sc.volume_ratio == Decimal("2.0")


def test_sc_detects_ultra_high_volume_3x(minimal_sc_bars, minimal_sc_volume_analysis):
    """AC1: SC detects with ultra-high volume (3.0x average)."""
    minimal_sc_bars[1].volume = 3000
    minimal_sc_volume_analysis[1].volume_ratio = Decimal("3.0")

    sc = detect_selling_climax(minimal_sc_bars, minimal_sc_volume_analysis)

    assert sc is not None
    assert sc.volume_ratio == Decimal("3.0")


def test_sc_detects_wide_spread_2_5x(minimal_sc_bars, minimal_sc_volume_analysis):
    """AC1: SC detects with wide spread (2.5x average)."""
    minimal_sc_volume_analysis[1].spread_ratio = Decimal("2.5")

    sc = detect_selling_climax(minimal_sc_bars, minimal_sc_volume_analysis)

    assert sc is not None


def test_sc_detects_close_at_bar_midpoint(minimal_sc_bars, minimal_sc_volume_analysis):
    """AC1: SC detects when close exactly at bar midpoint (close_position=0.5)."""
    minimal_sc_volume_analysis[1].close_position = Decimal("0.5")

    sc = detect_selling_climax(minimal_sc_bars, minimal_sc_volume_analysis)

    assert sc is not None


def test_sc_detects_strong_down_move(minimal_sc_bars, minimal_sc_volume_analysis):
    """AC1: SC detects strong down move (close well below prior close)."""
    minimal_sc_bars[1].close = Decimal("96.0")  # Stronger down move

    sc = detect_selling_climax(minimal_sc_bars, minimal_sc_volume_analysis)

    assert sc is not None


# =============================================================================
# NEGATIVE REJECTION TESTS (AC2, AC3)
# =============================================================================


def test_sc_rejects_volume_ratio_1_2_below_threshold(minimal_sc_bars, minimal_sc_volume_analysis):
    """AC2: SC rejects volume_ratio=1.2 (below 2.0 threshold)."""
    minimal_sc_bars[1].volume = 1200
    minimal_sc_volume_analysis[1].volume_ratio = Decimal("1.2")

    sc = detect_selling_climax(minimal_sc_bars, minimal_sc_volume_analysis)

    assert sc is None


def test_sc_rejects_close_in_lower_half(minimal_sc_bars, minimal_sc_volume_analysis):
    """AC3: SC rejects close in lower half of bar range (close_position < 0.5)."""
    minimal_sc_volume_analysis[1].close_position = Decimal("0.3")

    sc = detect_selling_climax(minimal_sc_bars, minimal_sc_volume_analysis)

    assert sc is None


def test_sc_rejects_spread_ratio_1_0_below_threshold(minimal_sc_bars, minimal_sc_volume_analysis):
    """SC rejects spread_ratio=1.0 (below 1.5 threshold)."""
    minimal_sc_volume_analysis[1].spread_ratio = Decimal("1.0")

    sc = detect_selling_climax(minimal_sc_bars, minimal_sc_volume_analysis)

    assert sc is None


def test_sc_rejects_upward_movement(minimal_sc_bars, minimal_sc_volume_analysis):
    """SC rejects upward movement (close >= prior close)."""
    minimal_sc_bars[1].close = Decimal("102.0")  # Above prior close (101.0)

    sc = detect_selling_climax(minimal_sc_bars, minimal_sc_volume_analysis)

    assert sc is None


def test_sc_rejects_volume_ratio_none(minimal_sc_bars, minimal_sc_volume_analysis):
    """SC rejects when volume_ratio is None (insufficient data)."""
    minimal_sc_volume_analysis[1].volume_ratio = None

    sc = detect_selling_climax(minimal_sc_bars, minimal_sc_volume_analysis)

    assert sc is None


def test_sc_rejects_spread_ratio_none(minimal_sc_bars, minimal_sc_volume_analysis):
    """SC rejects when spread_ratio is None (insufficient data)."""
    minimal_sc_volume_analysis[1].spread_ratio = None

    sc = detect_selling_climax(minimal_sc_bars, minimal_sc_volume_analysis)

    assert sc is None


def test_sc_skips_first_bar(base_timestamp):
    """SC skips first bar (i=0) - need prior close for validation."""
    bars = [
        create_test_bar(
            timestamp=base_timestamp,
            low=95.0,
            close=100.0,
            volume=2000,
        )
    ]

    volume_analysis = [
        VolumeAnalysis(
            bar=bars[0],
            volume_ratio=Decimal("2.0"),
            spread_ratio=Decimal("1.5"),
            effort_result=EffortResult.CLIMACTIC,
            close_position=Decimal("1.0"),
        )
    ]

    sc = detect_selling_climax(bars, volume_analysis)

    assert sc is None


def test_sc_rejects_not_climactic_effort(base_timestamp):
    """SC rejects bars where effort_result is not CLIMACTIC."""
    bars = [
        create_test_bar(timestamp=base_timestamp, volume=1000),
        create_test_bar(timestamp=base_timestamp.replace(day=2), low=95.0, volume=2000),
    ]

    volume_analysis = [
        VolumeAnalysis(
            bar=bars[0],
            volume_ratio=Decimal("1.0"),
            spread_ratio=Decimal("1.0"),
            effort_result=EffortResult.NORMAL,
            close_position=Decimal("0.5"),
        ),
        VolumeAnalysis(
            bar=bars[1],
            volume_ratio=Decimal("2.0"),
            spread_ratio=Decimal("1.5"),
            effort_result=EffortResult.NORMAL,  # NOT CLIMACTIC
            close_position=Decimal("0.8"),
        ),
    ]

    sc = detect_selling_climax(bars, volume_analysis)

    assert sc is None


def test_sc_rejects_high_volume_but_low_spread(minimal_sc_bars, minimal_sc_volume_analysis):
    """SC rejects high volume but insufficient spread."""
    minimal_sc_bars[1].volume = 3000
    minimal_sc_volume_analysis[1].volume_ratio = Decimal("3.0")  # OK
    minimal_sc_volume_analysis[1].spread_ratio = Decimal("1.0")  # REJECT

    sc = detect_selling_climax(minimal_sc_bars, minimal_sc_volume_analysis)

    assert sc is None


def test_sc_rejects_wide_spread_but_low_volume(minimal_sc_bars, minimal_sc_volume_analysis):
    """SC rejects wide spread but insufficient volume."""
    minimal_sc_bars[1].volume = 1500
    minimal_sc_volume_analysis[1].volume_ratio = Decimal("1.5")  # REJECT
    minimal_sc_volume_analysis[1].spread_ratio = Decimal("2.0")  # OK

    sc = detect_selling_climax(minimal_sc_bars, minimal_sc_volume_analysis)

    assert sc is None


# =============================================================================
# BOUNDARY TESTS
# =============================================================================


def test_sc_boundary_volume_ratio_exactly_2_0(minimal_sc_bars, minimal_sc_volume_analysis):
    """Boundary: volume_ratio exactly 2.0 (inclusive threshold) → pass."""
    minimal_sc_volume_analysis[1].volume_ratio = Decimal("2.0")

    sc = detect_selling_climax(minimal_sc_bars, minimal_sc_volume_analysis)

    assert sc is not None


def test_sc_boundary_volume_ratio_1_99(minimal_sc_bars, minimal_sc_volume_analysis):
    """Boundary: volume_ratio 1.99 (just below threshold) → fail."""
    minimal_sc_volume_analysis[1].volume_ratio = Decimal("1.99")

    sc = detect_selling_climax(minimal_sc_bars, minimal_sc_volume_analysis)

    assert sc is None


def test_sc_boundary_spread_ratio_exactly_1_5(minimal_sc_bars, minimal_sc_volume_analysis):
    """Boundary: spread_ratio exactly 1.5 (inclusive threshold) → pass."""
    minimal_sc_volume_analysis[1].spread_ratio = Decimal("1.5")

    sc = detect_selling_climax(minimal_sc_bars, minimal_sc_volume_analysis)

    assert sc is not None


def test_sc_boundary_spread_ratio_1_49(minimal_sc_bars, minimal_sc_volume_analysis):
    """Boundary: spread_ratio 1.49 (just below threshold) → fail."""
    minimal_sc_volume_analysis[1].spread_ratio = Decimal("1.49")

    sc = detect_selling_climax(minimal_sc_bars, minimal_sc_volume_analysis)

    assert sc is None


def test_sc_boundary_close_position_exactly_0_5(minimal_sc_bars, minimal_sc_volume_analysis):
    """Boundary: close_position exactly 0.5 (inclusive threshold) → pass."""
    minimal_sc_volume_analysis[1].close_position = Decimal("0.5")

    sc = detect_selling_climax(minimal_sc_bars, minimal_sc_volume_analysis)

    assert sc is not None


def test_sc_boundary_close_position_0_49(minimal_sc_bars, minimal_sc_volume_analysis):
    """Boundary: close_position 0.49 (just below threshold) → fail."""
    minimal_sc_volume_analysis[1].close_position = Decimal("0.49")

    sc = detect_selling_climax(minimal_sc_bars, minimal_sc_volume_analysis)

    assert sc is None


def test_sc_boundary_close_exactly_at_prior_close(base_timestamp):
    """Boundary: close exactly at prior close (no down move) → fail."""
    bars = [
        create_test_bar(timestamp=base_timestamp, close=100.0, volume=1000),
        create_test_bar(
            timestamp=base_timestamp.replace(day=2), low=95.0, close=100.0, volume=2000
        ),
    ]

    volume_analysis = [
        VolumeAnalysis(
            bar=bars[0],
            volume_ratio=Decimal("1.0"),
            spread_ratio=Decimal("1.0"),
            effort_result=EffortResult.NORMAL,
            close_position=Decimal("0.5"),
        ),
        VolumeAnalysis(
            bar=bars[1],
            volume_ratio=Decimal("2.0"),
            spread_ratio=Decimal("1.5"),
            effort_result=EffortResult.CLIMACTIC,
            close_position=Decimal("0.83"),
        ),
    ]

    sc = detect_selling_climax(bars, volume_analysis)

    assert sc is None  # close >= prior_close


def test_sc_boundary_close_just_below_prior_close(base_timestamp):
    """Boundary: close just below prior close (minimal down move) → pass."""
    bars = [
        create_test_bar(timestamp=base_timestamp, close=100.0, volume=1000),
        create_test_bar(
            timestamp=base_timestamp.replace(day=2), low=95.0, close=99.99, volume=2000
        ),
    ]

    volume_analysis = [
        VolumeAnalysis(
            bar=bars[0],
            volume_ratio=Decimal("1.0"),
            spread_ratio=Decimal("1.0"),
            effort_result=EffortResult.NORMAL,
            close_position=Decimal("0.5"),
        ),
        VolumeAnalysis(
            bar=bars[1],
            volume_ratio=Decimal("2.0"),
            spread_ratio=Decimal("1.5"),
            effort_result=EffortResult.CLIMACTIC,
            close_position=Decimal("0.83"),
        ),
    ]

    sc = detect_selling_climax(bars, volume_analysis)

    assert sc is not None


# =============================================================================
# EDGE CASE TESTS (AC9)
# =============================================================================


def test_sc_zero_volume_bar_returns_none(base_timestamp):
    """AC9: Zero-volume bar → volume_ratio fails threshold, returns None."""
    bars = [
        create_test_bar(timestamp=base_timestamp, volume=1000),
        create_test_bar(timestamp=base_timestamp.replace(day=2), low=95.0, volume=0),
    ]

    volume_analysis = [
        VolumeAnalysis(
            bar=bars[0],
            volume_ratio=Decimal("1.0"),
            spread_ratio=Decimal("1.0"),
            effort_result=EffortResult.NORMAL,
            close_position=Decimal("0.5"),
        ),
        VolumeAnalysis(
            bar=bars[1],
            volume_ratio=Decimal("0"),  # Zero volume
            spread_ratio=Decimal("1.5"),
            effort_result=EffortResult.CLIMACTIC,
            close_position=Decimal("0.83"),
        ),
    ]

    sc = detect_selling_climax(bars, volume_analysis)

    assert sc is None


def test_sc_doji_bar_spread_ratio_zero(base_timestamp):
    """AC9: Doji bar (spread=0) → spread_ratio=0, fails threshold, returns None."""
    bars = [
        create_test_bar(timestamp=base_timestamp, volume=1000),
        create_test_bar(
            timestamp=base_timestamp.replace(day=2),
            high=100.0,
            low=100.0,  # Doji
            close=99.0,
            volume=2000,
        ),
    ]

    volume_analysis = [
        VolumeAnalysis(
            bar=bars[0],
            volume_ratio=Decimal("1.0"),
            spread_ratio=Decimal("1.0"),
            effort_result=EffortResult.NORMAL,
            close_position=Decimal("0.5"),
        ),
        VolumeAnalysis(
            bar=bars[1],
            volume_ratio=Decimal("2.0"),
            spread_ratio=Decimal("0"),  # Doji
            effort_result=EffortResult.CLIMACTIC,
            close_position=None,
        ),
    ]

    sc = detect_selling_climax(bars, volume_analysis)

    assert sc is None


def test_sc_gap_bar_processed_normally(base_timestamp):
    """AC9: Gap bar (open far from prior close) → processed normally, no exception."""
    bars = [
        create_test_bar(timestamp=base_timestamp, close=100.0, volume=1000),
        create_test_bar(
            timestamp=base_timestamp.replace(day=2),
            open_price=90.0,  # Gap down
            high=95.0,
            low=85.0,
            close=93.0,
            volume=2000,
        ),
    ]

    volume_analysis = [
        VolumeAnalysis(
            bar=bars[0],
            volume_ratio=Decimal("1.0"),
            spread_ratio=Decimal("1.0"),
            effort_result=EffortResult.NORMAL,
            close_position=Decimal("0.5"),
        ),
        VolumeAnalysis(
            bar=bars[1],
            volume_ratio=Decimal("2.0"),
            spread_ratio=Decimal("1.5"),
            effort_result=EffortResult.CLIMACTIC,
            close_position=Decimal("0.8"),
        ),
    ]

    sc = detect_selling_climax(bars, volume_analysis)

    assert sc is not None  # Gap is irrelevant to SC logic


def test_sc_huge_volume_spike_10x(base_timestamp):
    """Edge case: Huge volume spike (10x average) → should pass."""
    bars = [
        create_test_bar(timestamp=base_timestamp, close=100.0, volume=1000),
        create_test_bar(
            timestamp=base_timestamp.replace(day=2), low=90.0, close=97.0, volume=10000
        ),
    ]

    volume_analysis = [
        VolumeAnalysis(
            bar=bars[0],
            volume_ratio=Decimal("1.0"),
            spread_ratio=Decimal("1.0"),
            effort_result=EffortResult.NORMAL,
            close_position=Decimal("0.5"),
        ),
        VolumeAnalysis(
            bar=bars[1],
            volume_ratio=Decimal("10.0"),
            spread_ratio=Decimal("2.0"),
            effort_result=EffortResult.CLIMACTIC,
            close_position=Decimal("0.8"),
        ),
    ]

    sc = detect_selling_climax(bars, volume_analysis)

    assert sc is not None
    assert sc.volume_ratio == Decimal("10.0")


def test_sc_all_bars_have_volume_ratio_none(base_timestamp):
    """Edge case: All bars have volume_ratio=None → returns None."""
    bars = [
        create_test_bar(timestamp=base_timestamp, volume=1000),
        create_test_bar(timestamp=base_timestamp.replace(day=2), low=95.0, volume=2000),
    ]

    volume_analysis = [
        VolumeAnalysis(
            bar=bars[0],
            volume_ratio=None,
            spread_ratio=None,
            effort_result=EffortResult.NORMAL,
            close_position=None,
        ),
        VolumeAnalysis(
            bar=bars[1],
            volume_ratio=None,
            spread_ratio=None,
            effort_result=EffortResult.CLIMACTIC,
            close_position=None,
        ),
    ]

    sc = detect_selling_climax(bars, volume_analysis)

    assert sc is None


def test_sc_multi_bar_sequence_detects_last_bar(base_timestamp):
    """SC detects selling climax on last bar of 5-bar sequence."""
    bars = [
        create_test_bar(timestamp=base_timestamp, volume=1000),
        create_test_bar(timestamp=base_timestamp.replace(day=2), volume=1100),
        create_test_bar(timestamp=base_timestamp.replace(day=3), volume=900),
        create_test_bar(timestamp=base_timestamp.replace(day=4), volume=1050),
        create_test_bar(timestamp=base_timestamp.replace(day=5), low=90.0, close=96.0, volume=2500),
    ]

    volume_analysis = [
        VolumeAnalysis(
            bar=bars[0],
            volume_ratio=Decimal("1.0"),
            spread_ratio=Decimal("1.0"),
            effort_result=EffortResult.NORMAL,
            close_position=Decimal("0.5"),
        ),
        VolumeAnalysis(
            bar=bars[1],
            volume_ratio=Decimal("1.1"),
            spread_ratio=Decimal("1.0"),
            effort_result=EffortResult.NORMAL,
            close_position=Decimal("0.5"),
        ),
        VolumeAnalysis(
            bar=bars[2],
            volume_ratio=Decimal("0.9"),
            spread_ratio=Decimal("1.0"),
            effort_result=EffortResult.NORMAL,
            close_position=Decimal("0.5"),
        ),
        VolumeAnalysis(
            bar=bars[3],
            volume_ratio=Decimal("1.05"),
            spread_ratio=Decimal("1.0"),
            effort_result=EffortResult.NORMAL,
            close_position=Decimal("0.5"),
        ),
        VolumeAnalysis(
            bar=bars[4],
            volume_ratio=Decimal("2.5"),
            spread_ratio=Decimal("1.8"),
            effort_result=EffortResult.CLIMACTIC,
            close_position=Decimal("0.6"),
        ),
    ]

    sc = detect_selling_climax(bars, volume_analysis)

    assert sc is not None
    assert Decimal(sc.bar["low"]) == Decimal("90.0")


def test_sc_returns_correct_sc_low_price(minimal_sc_bars, minimal_sc_volume_analysis):
    """SC event contains correct SC low price field."""
    sc = detect_selling_climax(minimal_sc_bars, minimal_sc_volume_analysis)

    assert sc is not None
    assert Decimal(sc.bar["low"]) == Decimal("95.0")
    assert sc.bar["symbol"] == "TEST"


def test_sc_empty_bars_raises_valueerror():
    """Edge case: Empty bars list → raises ValueError."""
    bars = []
    volume_analysis = []

    with pytest.raises(ValueError, match="Bars list cannot be empty"):
        detect_selling_climax(bars, volume_analysis)
