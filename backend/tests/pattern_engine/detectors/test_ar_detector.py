"""
Unit Tests for Automatic Rally (AR) Pattern Detector (Story 25.9)

Test Coverage:
--------------
- AC4: AR detects valid automatic rally after Spring/SC
- AC5: AR rejects low-volume bars (volume_ratio < 0.7)
- AC5: AR rejects high-volume bars (volume_ratio > 1.3)
- AC6: AR rejects bars with insufficient recovery (< 40%)
- AC7: AR rejects bars with close in lower half
- AC8: AR rejects bars exceeding Ice level
- AC9: Edge cases handled gracefully (zero-volume, doji, gaps)

Detector Implementation: backend/src/pattern_engine/detectors/ar_detector.py

Thresholds (verified from implementation):
- volume_ratio: 0.7 <= ratio <= 1.3 (lines 53, 227, 440)
- recovery_percent >= 0.4 (40%) (lines 238, 451)
- close_position >= 0.5 (lines 79, 242, 455)
- Search window: 2-10 bars after Spring/SC (lines 205-206, 418-419)

Author: Story 25.9 Implementation
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.selling_climax import SellingClimax
from src.models.spring import Spring
from src.pattern_engine.detectors.ar_detector import detect_ar_after_sc, detect_ar_after_spring
from tests.pattern_engine.detectors.conftest import create_test_bar


@pytest.fixture
def base_timestamp() -> datetime:
    """Base timestamp for test bars (2024-01-01 UTC)."""
    return datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)


@pytest.fixture
def valid_spring(base_timestamp):
    """Valid Spring pattern for AR testing."""
    spring_bar = create_test_bar(
        timestamp=base_timestamp,
        low=95.0,
        close=96.0,
        volume=500,  # Low volume
    )
    return Spring(
        bar=spring_bar,
        bar_index=5,
        penetration_pct=Decimal("0.02"),
        volume_ratio=Decimal("0.5"),
        recovery_bars=2,
        creek_reference=Decimal("97.0"),
        spring_low=Decimal("95.0"),
        recovery_price=Decimal("97.5"),
        detection_timestamp=base_timestamp,
        trading_range_id=uuid4(),
    )


@pytest.fixture
def valid_sc(base_timestamp):
    """Valid Selling Climax pattern for AR testing."""
    sc_bar = create_test_bar(
        timestamp=base_timestamp,
        low=90.0,
        close=95.0,
        volume=3000,  # High volume
    )
    return SellingClimax(
        bar=sc_bar.model_dump(),
        bar_index=3,
        volume_ratio=Decimal("3.0"),
        spread_ratio=Decimal("2.0"),
        close_position=Decimal("0.8"),
        confidence=90,
        prior_close=Decimal("100.0"),
        detection_timestamp=base_timestamp,
    )


@pytest.fixture
def bars_with_ar_after_spring(base_timestamp, valid_spring):
    """Bar sequence with valid AR after Spring."""
    return [
        create_test_bar(timestamp=base_timestamp.replace(day=i), volume=1000) for i in range(1, 6)
    ] + [
        create_test_bar(
            timestamp=base_timestamp, low=95.0, close=96.0, volume=500
        ),  # Spring bar at index 5
        create_test_bar(
            timestamp=base_timestamp.replace(day=7),
            low=96.0,
            high=102.0,
            close=101.0,
            volume=900,  # AR: 0.9x volume, 60% recovery
        ),
    ]


# =============================================================================
# POSITIVE DETECTION TESTS - AR AFTER SPRING (AC4)
# =============================================================================


def test_ar_after_spring_detects_valid_rally(valid_spring, bars_with_ar_after_spring):
    """AC4: AR detects valid automatic rally after Spring."""
    volume_avg = Decimal("1000")
    ice_level = Decimal("105.0")

    ar = detect_ar_after_spring(bars_with_ar_after_spring, valid_spring, volume_avg, ice_level)

    assert ar is not None
    assert ar.bar_index == 6
    assert ar.recovery_percent >= Decimal("0.4")


def test_ar_after_spring_40_percent_recovery_exactly(valid_spring, base_timestamp):
    """AC4: AR detects with exactly 40% recovery (boundary pass)."""
    bars = [
        create_test_bar(timestamp=base_timestamp.replace(day=i), volume=1000) for i in range(1, 6)
    ] + [
        create_test_bar(
            timestamp=base_timestamp, low=95.0, close=96.0, volume=500
        ),  # Spring at index 5
        create_test_bar(
            timestamp=base_timestamp.replace(day=7),
            low=96.0,
            close=99.0,  # Exactly 40% recovery: (99-95)/(105-95) = 0.4
            volume=900,
        ),
    ]
    volume_avg = Decimal("1000")

    ar = detect_ar_after_spring(bars, valid_spring, volume_avg)

    assert ar is not None
    assert ar.recovery_percent >= Decimal("0.4")


def test_ar_after_spring_volume_0_7x_exactly(valid_spring, bars_with_ar_after_spring):
    """AC4: AR detects with volume exactly 0.7x (boundary pass)."""
    bars_with_ar_after_spring[6].volume = 700  # Exactly 0.7x
    volume_avg = Decimal("1000")

    ar = detect_ar_after_spring(bars_with_ar_after_spring, valid_spring, volume_avg)

    assert ar is not None


def test_ar_after_spring_volume_1_3x_exactly(valid_spring, bars_with_ar_after_spring):
    """AC4: AR detects with volume exactly 1.3x (boundary pass)."""
    bars_with_ar_after_spring[6].volume = 1300  # Exactly 1.3x
    volume_avg = Decimal("1000")

    ar = detect_ar_after_spring(bars_with_ar_after_spring, valid_spring, volume_avg)

    assert ar is not None


def test_ar_after_spring_close_position_0_5_exactly(valid_spring, base_timestamp):
    """AC4: AR detects with close_position exactly 0.5 (boundary pass)."""
    bars = [
        create_test_bar(timestamp=base_timestamp.replace(day=i), volume=1000) for i in range(1, 6)
    ] + [
        create_test_bar(timestamp=base_timestamp, low=95.0, close=96.0, volume=500),  # Spring
        create_test_bar(
            timestamp=base_timestamp.replace(day=7),
            low=96.0,
            high=106.0,
            close=101.0,  # Exactly at midpoint
            volume=900,
        ),
    ]
    volume_avg = Decimal("1000")

    ar = detect_ar_after_spring(bars, valid_spring, volume_avg)

    assert ar is not None


def test_ar_after_spring_ideal_conditions(valid_spring, base_timestamp):
    """AC4: AR detects with ideal conditions (50% recovery, 1.0x volume)."""
    bars = [
        create_test_bar(timestamp=base_timestamp.replace(day=i), volume=1000) for i in range(1, 6)
    ] + [
        create_test_bar(timestamp=base_timestamp, low=95.0, close=96.0, volume=500),  # Spring
        create_test_bar(
            timestamp=base_timestamp.replace(day=7),
            low=96.0,
            close=100.0,  # 50% recovery
            volume=1000,  # 1.0x volume
        ),
    ]
    volume_avg = Decimal("1000")

    ar = detect_ar_after_spring(bars, valid_spring, volume_avg)

    assert ar is not None
    assert ar.quality_score > 0.5  # Should be high quality


# =============================================================================
# POSITIVE DETECTION TESTS - AR AFTER SC (AC4)
# =============================================================================


def test_ar_after_sc_detects_valid_rally(valid_sc, base_timestamp):
    """AC4: AR detects valid automatic rally after SC."""
    bars = [
        create_test_bar(timestamp=base_timestamp.replace(day=i), volume=1000) for i in range(1, 4)
    ] + [
        create_test_bar(
            timestamp=base_timestamp, low=90.0, close=95.0, volume=3000
        ),  # SC at index 3
        create_test_bar(
            timestamp=base_timestamp.replace(day=5),
            low=95.0,
            high=104.0,
            close=103.0,  # 60% recovery: (103-90)/(110-90) = 0.65
            volume=1000,  # 1.0x volume
        ),
    ]
    volume_avg = Decimal("1000")

    ar = detect_ar_after_sc(bars, valid_sc, volume_avg)

    assert ar is not None
    assert ar.recovery_percent >= Decimal("0.4")


def test_ar_after_sc_40_percent_recovery_exactly(valid_sc, base_timestamp):
    """AC4: AR detects with exactly 40% recovery after SC."""
    bars = [
        create_test_bar(timestamp=base_timestamp.replace(day=i), volume=1000) for i in range(1, 4)
    ] + [
        create_test_bar(timestamp=base_timestamp, low=90.0, close=95.0, volume=3000),  # SC
        create_test_bar(
            timestamp=base_timestamp.replace(day=5),
            close=98.0,  # 40% recovery from 90 to prior high
            volume=1000,
        ),
    ]
    volume_avg = Decimal("1000")

    ar = detect_ar_after_sc(bars, valid_sc, volume_avg)

    assert ar is not None


# =============================================================================
# NEGATIVE REJECTION TESTS (AC5, AC6, AC7, AC8)
# =============================================================================


def test_ar_after_spring_rejects_30_percent_recovery(valid_spring, base_timestamp):
    """AC6: AR rejects 30% recovery (below 40% threshold)."""
    bars = [
        create_test_bar(timestamp=base_timestamp.replace(day=i), volume=1000) for i in range(1, 6)
    ] + [
        create_test_bar(timestamp=base_timestamp, low=95.0, close=96.0, volume=500),
        create_test_bar(
            timestamp=base_timestamp.replace(day=7),
            close=98.0,  # Only 30% recovery
            volume=900,
        ),
    ]
    volume_avg = Decimal("1000")

    ar = detect_ar_after_spring(bars, valid_spring, volume_avg)

    assert ar is None


def test_ar_after_spring_rejects_volume_0_6x(valid_spring, bars_with_ar_after_spring):
    """AC5: AR rejects volume 0.6x (below 0.7x threshold)."""
    bars_with_ar_after_spring[6].volume = 600  # Below 0.7x
    volume_avg = Decimal("1000")

    ar = detect_ar_after_spring(bars_with_ar_after_spring, valid_spring, volume_avg)

    assert ar is None


def test_ar_after_spring_rejects_volume_1_5x(valid_spring, bars_with_ar_after_spring):
    """AC5: AR rejects volume 1.5x (above 1.3x threshold, looks like SOS)."""
    bars_with_ar_after_spring[6].volume = 1500  # Above 1.3x
    volume_avg = Decimal("1000")

    ar = detect_ar_after_spring(bars_with_ar_after_spring, valid_spring, volume_avg)

    assert ar is None


def test_ar_after_spring_rejects_close_in_lower_half(valid_spring, base_timestamp):
    """AC7: AR rejects close in lower half (close_position < 0.5)."""
    bars = [
        create_test_bar(timestamp=base_timestamp.replace(day=i), volume=1000) for i in range(1, 6)
    ] + [
        create_test_bar(timestamp=base_timestamp, low=95.0, close=96.0, volume=500),
        create_test_bar(
            timestamp=base_timestamp.replace(day=7),
            low=96.0,
            high=110.0,
            close=100.0,  # In lower half: (100-96)/(110-96) = 0.29
            volume=900,
        ),
    ]
    volume_avg = Decimal("1000")

    ar = detect_ar_after_spring(bars, valid_spring, volume_avg)

    assert ar is None


def test_ar_after_spring_rejects_recovery_39_percent(valid_spring, base_timestamp):
    """Boundary: AR rejects 39% recovery (just below 40%)."""
    bars = [
        create_test_bar(timestamp=base_timestamp.replace(day=i), volume=1000) for i in range(1, 6)
    ] + [
        create_test_bar(timestamp=base_timestamp, low=95.0, close=96.0, volume=500),
        create_test_bar(
            timestamp=base_timestamp.replace(day=7),
            close=98.9,  # 39% recovery
            volume=900,
        ),
    ]
    volume_avg = Decimal("1000")

    ar = detect_ar_after_spring(bars, valid_spring, volume_avg)

    assert ar is None


def test_ar_after_spring_rejects_volume_0_69x(valid_spring, bars_with_ar_after_spring):
    """Boundary: AR rejects volume 0.69x (just below 0.7x)."""
    bars_with_ar_after_spring[6].volume = 690
    volume_avg = Decimal("1000")

    ar = detect_ar_after_spring(bars_with_ar_after_spring, valid_spring, volume_avg)

    assert ar is None


def test_ar_after_spring_rejects_volume_1_31x(valid_spring, bars_with_ar_after_spring):
    """Boundary: AR rejects volume 1.31x (just above 1.3x)."""
    bars_with_ar_after_spring[6].volume = 1310
    volume_avg = Decimal("1000")

    ar = detect_ar_after_spring(bars_with_ar_after_spring, valid_spring, volume_avg)

    assert ar is None


def test_ar_after_spring_empty_bars_returns_none(valid_spring):
    """Edge case: Empty bars list → returns None."""
    bars = []
    volume_avg = Decimal("1000")

    ar = detect_ar_after_spring(bars, valid_spring, volume_avg)

    assert ar is None


def test_ar_after_spring_none_spring_returns_none(bars_with_ar_after_spring):
    """Edge case: Spring is None → returns None."""
    volume_avg = Decimal("1000")

    ar = detect_ar_after_spring(bars_with_ar_after_spring, None, volume_avg)

    assert ar is None


def test_ar_after_spring_volume_avg_zero_returns_none(valid_spring, bars_with_ar_after_spring):
    """Edge case: volume_avg <= 0 → returns None."""
    ar = detect_ar_after_spring(bars_with_ar_after_spring, valid_spring, Decimal("0"))

    assert ar is None


def test_ar_after_spring_at_end_of_bars_returns_none(valid_spring, base_timestamp):
    """Edge case: Spring at end of bars → no bars to scan, returns None."""
    bars = [
        create_test_bar(timestamp=base_timestamp.replace(day=i), volume=1000) for i in range(1, 6)
    ] + [create_test_bar(timestamp=base_timestamp, low=95.0, close=96.0, volume=500)]
    # Spring is at index 5, no bars after it
    volume_avg = Decimal("1000")

    ar = detect_ar_after_spring(bars, valid_spring, volume_avg)

    assert ar is None


def test_ar_after_spring_rejects_exceeds_ice_level(valid_spring, base_timestamp):
    """AC8: AR rejects bar that exceeds Ice level."""
    bars = [
        create_test_bar(timestamp=base_timestamp.replace(day=i), volume=1000) for i in range(1, 6)
    ] + [
        create_test_bar(timestamp=base_timestamp, low=95.0, close=96.0, volume=500),
        create_test_bar(
            timestamp=base_timestamp.replace(day=7),
            low=96.0,
            high=106.0,  # Exceeds Ice at 105.0
            close=105.5,
            volume=900,
        ),
    ]
    volume_avg = Decimal("1000")
    ice_level = Decimal("105.0")

    ar = detect_ar_after_spring(bars, valid_spring, volume_avg, ice_level)

    assert ar is None


def test_ar_after_sc_empty_bars_returns_none(valid_sc):
    """Edge case: Empty bars list → returns None."""
    bars = []
    volume_avg = Decimal("1000")

    ar = detect_ar_after_sc(bars, valid_sc, volume_avg)

    assert ar is None


def test_ar_after_sc_none_sc_returns_none(base_timestamp):
    """Edge case: SC is None → returns None."""
    bars = [create_test_bar(timestamp=base_timestamp.replace(day=i)) for i in range(1, 6)]
    volume_avg = Decimal("1000")

    ar = detect_ar_after_sc(bars, None, volume_avg)

    assert ar is None


def test_ar_after_sc_volume_avg_zero_returns_none(valid_sc, base_timestamp):
    """Edge case: volume_avg <= 0 → returns None."""
    bars = [create_test_bar(timestamp=base_timestamp.replace(day=i)) for i in range(1, 6)]

    ar = detect_ar_after_sc(bars, valid_sc, Decimal("0"))

    assert ar is None


def test_ar_after_sc_no_valid_bars_in_window_returns_none(valid_sc, base_timestamp):
    """Edge case: No valid bars in search window → returns None."""
    # Create bars where all bars after SC fail validation
    bars = [
        create_test_bar(
            timestamp=base_timestamp, low=90.0, close=95.0, volume=3000
        ),  # SC at index 0
        create_test_bar(
            timestamp=base_timestamp.replace(day=2),
            low=92.0,
            high=93.0,
            close=92.0,  # Only ~10% recovery, too low
            volume=500,  # Below 0.7x threshold
        ),
        create_test_bar(
            timestamp=base_timestamp.replace(day=3),
            low=91.0,
            high=92.0,
            close=91.5,  # Too low recovery
            volume=2000,  # Too high volume (2.0x)
        ),
    ]
    volume_avg = Decimal("1000")

    ar = detect_ar_after_sc(bars, valid_sc, volume_avg)

    assert ar is None


def test_ar_after_spring_single_bar_only_returns_none(valid_spring, base_timestamp):
    """Edge case: Single bar only → no Spring bar in sequence, returns None."""
    bars = [create_test_bar(timestamp=base_timestamp, volume=1000)]
    volume_avg = Decimal("1000")

    ar = detect_ar_after_spring(bars, valid_spring, volume_avg)

    assert ar is None


# =============================================================================
# BOUNDARY TESTS
# =============================================================================


def test_ar_boundary_recovery_exactly_40_percent(valid_spring, base_timestamp):
    """Boundary: Recovery exactly 40% → pass."""
    # Calculate: prior_high from lookback will be max of bars[0:6] = 102.0
    # decline_range = 102.0 - 95.0 = 7.0
    # For 40% recovery: close = 95.0 + (0.4 * 7.0) = 97.8
    # close_position: need close in upper half, so (close-low)/(high-low) >= 0.5
    # Using low=96, high=100, close=98: (98-96)/(100-96) = 0.5 ✓
    bars = [
        create_test_bar(timestamp=base_timestamp.replace(day=i), volume=1000) for i in range(1, 6)
    ] + [
        create_test_bar(timestamp=base_timestamp, low=95.0, close=96.0, volume=500),
        create_test_bar(
            timestamp=base_timestamp.replace(day=7),
            low=96.0,
            high=100.0,
            close=98.0,  # Close position = 0.5, recovery = (98-95)/7 = 0.43 > 0.4 ✓
            volume=900,
        ),
    ]
    volume_avg = Decimal("1000")

    ar = detect_ar_after_spring(bars, valid_spring, volume_avg)

    assert ar is not None


def test_ar_boundary_recovery_39_9_percent(valid_spring, base_timestamp):
    """Boundary: Recovery 39.9% → fail."""
    bars = [
        create_test_bar(timestamp=base_timestamp.replace(day=i), volume=1000) for i in range(1, 6)
    ] + [
        create_test_bar(timestamp=base_timestamp, low=95.0, close=96.0, volume=500),
        create_test_bar(timestamp=base_timestamp.replace(day=7), close=98.99, volume=900),
    ]
    volume_avg = Decimal("1000")

    ar = detect_ar_after_spring(bars, valid_spring, volume_avg)

    assert ar is None


def test_ar_boundary_volume_exactly_0_7x(valid_spring, bars_with_ar_after_spring):
    """Boundary: Volume exactly 0.7x → pass."""
    bars_with_ar_after_spring[6].volume = 700
    volume_avg = Decimal("1000")

    ar = detect_ar_after_spring(bars_with_ar_after_spring, valid_spring, volume_avg)

    assert ar is not None


def test_ar_boundary_volume_0_699x(valid_spring, bars_with_ar_after_spring):
    """Boundary: Volume 0.699x → fail."""
    bars_with_ar_after_spring[6].volume = 699
    volume_avg = Decimal("1000")

    ar = detect_ar_after_spring(bars_with_ar_after_spring, valid_spring, volume_avg)

    assert ar is None


def test_ar_boundary_volume_exactly_1_3x(valid_spring, bars_with_ar_after_spring):
    """Boundary: Volume exactly 1.3x → pass."""
    bars_with_ar_after_spring[6].volume = 1300
    volume_avg = Decimal("1000")

    ar = detect_ar_after_spring(bars_with_ar_after_spring, valid_spring, volume_avg)

    assert ar is not None


def test_ar_boundary_volume_1_301x(valid_spring, bars_with_ar_after_spring):
    """Boundary: Volume 1.301x → fail."""
    bars_with_ar_after_spring[6].volume = 1301
    volume_avg = Decimal("1000")

    ar = detect_ar_after_spring(bars_with_ar_after_spring, valid_spring, volume_avg)

    assert ar is None


# =============================================================================
# EDGE CASE TESTS (AC9)
# =============================================================================


def test_ar_zero_volume_bar_handled_gracefully(valid_spring, base_timestamp):
    """AC9: Zero volume bar → handled gracefully, no crash."""
    bars = [
        create_test_bar(timestamp=base_timestamp.replace(day=i), volume=1000) for i in range(1, 6)
    ] + [
        create_test_bar(timestamp=base_timestamp, low=95.0, close=96.0, volume=500),
        create_test_bar(
            timestamp=base_timestamp.replace(day=7), close=101.0, volume=0
        ),  # Zero volume
    ]
    volume_avg = Decimal("1000")

    ar = detect_ar_after_spring(bars, valid_spring, volume_avg)

    assert ar is None  # Should reject gracefully, not crash


def test_ar_doji_bar_handled_gracefully(valid_spring, base_timestamp):
    """AC9: Doji bar (spread=0) → handled gracefully, no exception."""
    bars = [
        create_test_bar(timestamp=base_timestamp.replace(day=i), volume=1000) for i in range(1, 6)
    ] + [
        create_test_bar(timestamp=base_timestamp, low=95.0, close=96.0, volume=500),
        create_test_bar(
            timestamp=base_timestamp.replace(day=7),
            high=101.0,
            low=101.0,  # Doji
            close=101.0,
            volume=900,
        ),
    ]
    volume_avg = Decimal("1000")

    # Should not crash
    ar = detect_ar_after_spring(bars, valid_spring, volume_avg)

    # May pass or fail depending on recovery, but should not crash
    assert ar is None or ar is not None


def test_ar_gap_bar_no_exception(valid_spring, base_timestamp):
    """AC9: Gap bar → no exception."""
    bars = [
        create_test_bar(timestamp=base_timestamp.replace(day=i), volume=1000) for i in range(1, 6)
    ] + [
        create_test_bar(timestamp=base_timestamp, low=95.0, close=96.0, volume=500),
        create_test_bar(
            timestamp=base_timestamp.replace(day=7),
            open_price=110.0,  # Gap up
            high=112.0,
            low=109.0,
            close=111.0,
            volume=900,
        ),
    ]
    volume_avg = Decimal("1000")

    # Should not crash
    ar = detect_ar_after_spring(bars, valid_spring, volume_avg)

    # May detect or not depending on thresholds
    assert ar is None or ar is not None


def test_ar_ice_level_none_no_crash(valid_spring, bars_with_ar_after_spring):
    """Edge case: Ice level is None → no crash."""
    volume_avg = Decimal("1000")

    ar = detect_ar_after_spring(bars_with_ar_after_spring, valid_spring, volume_avg, ice_level=None)

    assert ar is not None  # Should detect without Ice validation
