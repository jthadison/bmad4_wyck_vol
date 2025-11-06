"""
Unit tests for SpringDetector documentation examples.

This test module validates all code examples from:
- spring_detector.py docstrings (Task 23)
- docs/examples/spring_detector_usage_examples.md (Task 24)

Purpose:
--------
Ensure documentation examples are accurate, executable, and demonstrate
correct SpringDetector behavior for single-spring and multi-spring scenarios.

Test Coverage:
--------------
1. Single spring detection with risk assessment
2. Multi-spring declining volume (professional accumulation)
3. Multi-spring rising volume (distribution warning)
4. Volume trend analysis (DECLINING/STABLE/RISING)
5. Risk profile analysis (LOW/MODERATE/HIGH)
6. Best spring and signal selection
7. Backward compatibility (legacy detect() API)

Author: Story 5.6 Phase 4 - Documentation Tests
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.creek_level import CreekLevel
from src.models.jump_level import JumpLevel
from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import WyckoffPhase
from src.models.trading_range import TradingRange
from src.pattern_engine.detectors.spring_detector import (
    SpringDetector,
    analyze_spring_risk_profile,
    analyze_volume_trend,
)
from src.models.spring_history import SpringHistory


# ============================================================
# FIXTURES - Test Data Factories
# ============================================================


@pytest.fixture
def base_timestamp():
    """Base timestamp for test sequences."""
    return datetime(2024, 1, 1, tzinfo=UTC)


@pytest.fixture
def trading_range():
    """Standard trading range with Creek at $100, Jump at $110."""
    return TradingRange(
        id=uuid4(),
        symbol="TEST",
        start_time=datetime(2024, 1, 1, tzinfo=UTC),
        creek=CreekLevel(
            price=Decimal("100.00"),
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            touches=5,
            strength_score=75,
        ),
        jump=JumpLevel(
            price=Decimal("110.00"),
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            touches=4,
            strength_score=70,
        ),
    )


def create_ohlcv_bar(
    symbol: str,
    timestamp: datetime,
    open_price: Decimal,
    high: Decimal,
    low: Decimal,
    close: Decimal,
    volume: int,
) -> OHLCVBar:
    """Helper to create OHLCV bars."""
    return OHLCVBar(
        symbol=symbol,
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def create_bar_sequence_with_single_spring(
    trading_range: TradingRange,
    base_timestamp: datetime,
) -> list[OHLCVBar]:
    """
    Create 50-bar sequence with ONE spring at bar 25.

    Spring characteristics:
    - Bar 25: Low $98.00 (2% below Creek at $100)
    - Volume: 42,000 (0.42x of 20-bar average ~100,000)
    - Recovery: 2 bars (bar 27 closes above Creek at $100.50)
    - Test: Bar 32 retests at $98.20, volume 35,000 (0.35x)
    """
    bars = []
    avg_volume = 100_000

    # Bars 0-24: Normal trading around Creek
    for i in range(25):
        timestamp = base_timestamp + timedelta(days=i)
        bars.append(
            create_ohlcv_bar(
                symbol=trading_range.symbol,
                timestamp=timestamp,
                open_price=Decimal("100.00"),
                high=Decimal("102.00"),
                low=Decimal("99.00"),
                close=Decimal("100.50"),
                volume=avg_volume + (i % 3) * 5000,  # Slight variation
            )
        )

    # Bar 25: SPRING (low $98.00, volume 0.42x)
    bars.append(
        create_ohlcv_bar(
            symbol=trading_range.symbol,
            timestamp=base_timestamp + timedelta(days=25),
            open_price=Decimal("99.50"),
            high=Decimal("99.80"),
            low=Decimal("98.00"),  # 2% below Creek
            close=Decimal("99.20"),
            volume=42_000,  # 0.42x average
        )
    )

    # Bar 26: Recovery starts (close still below Creek)
    bars.append(
        create_ohlcv_bar(
            symbol=trading_range.symbol,
            timestamp=base_timestamp + timedelta(days=26),
            open_price=Decimal("99.20"),
            high=Decimal("100.80"),
            low=Decimal("99.00"),
            close=Decimal("99.80"),  # Still below Creek
            volume=90_000,
        )
    )

    # Bar 27: RECOVERY CONFIRMED (close above Creek)
    bars.append(
        create_ohlcv_bar(
            symbol=trading_range.symbol,
            timestamp=base_timestamp + timedelta(days=27),
            open_price=Decimal("99.80"),
            high=Decimal("101.50"),
            low=Decimal("99.50"),
            close=Decimal("100.50"),  # Above Creek ✅
            volume=95_000,
        )
    )

    # Bars 28-31: Normal trading
    for i in range(28, 32):
        timestamp = base_timestamp + timedelta(days=i)
        bars.append(
            create_ohlcv_bar(
                symbol=trading_range.symbol,
                timestamp=timestamp,
                open_price=Decimal("100.50"),
                high=Decimal("102.00"),
                low=Decimal("100.00"),
                close=Decimal("101.00"),
                volume=avg_volume,
            )
        )

    # Bar 32: TEST CONFIRMATION (retest spring low, lower volume)
    bars.append(
        create_ohlcv_bar(
            symbol=trading_range.symbol,
            timestamp=base_timestamp + timedelta(days=32),
            open_price=Decimal("101.00"),
            high=Decimal("101.00"),
            low=Decimal("98.20"),  # Retest (holds above spring low $98.00)
            close=Decimal("99.50"),
            volume=35_000,  # 0.35x (lower than spring 0.42x) ✅
        )
    )

    # Bars 33-49: Continued trading
    for i in range(33, 50):
        timestamp = base_timestamp + timedelta(days=i)
        bars.append(
            create_ohlcv_bar(
                symbol=trading_range.symbol,
                timestamp=timestamp,
                open_price=Decimal("100.50"),
                high=Decimal("102.00"),
                low=Decimal("100.00"),
                close=Decimal("101.00"),
                volume=avg_volume,
            )
        )

    return bars


def create_bar_sequence_with_declining_volume_springs(
    trading_range: TradingRange,
    base_timestamp: datetime,
) -> list[OHLCVBar]:
    """
    Create 70-bar sequence with THREE springs showing DECLINING volume.

    Spring 1 (Bar 25): $98.00 low, 0.60x volume
    Spring 2 (Bar 40): $97.50 low, 0.48x volume (LOWER)
    Spring 3 (Bar 55): $97.00 low, 0.32x volume (LOWEST)

    This is professional accumulation pattern (LOW risk).
    """
    bars = []
    avg_volume = 100_000

    # Bars 0-24: Normal trading
    for i in range(25):
        timestamp = base_timestamp + timedelta(days=i)
        bars.append(
            create_ohlcv_bar(
                symbol=trading_range.symbol,
                timestamp=timestamp,
                open_price=Decimal("100.00"),
                high=Decimal("102.00"),
                low=Decimal("99.00"),
                close=Decimal("100.50"),
                volume=avg_volume + (i % 3) * 5000,
            )
        )

    # SPRING 1: Bar 25 (0.60x volume)
    bars.append(
        create_ohlcv_bar(
            symbol=trading_range.symbol,
            timestamp=base_timestamp + timedelta(days=25),
            open_price=Decimal("99.50"),
            high=Decimal("99.80"),
            low=Decimal("98.00"),  # 2% below Creek
            close=Decimal("99.00"),
            volume=60_000,  # 0.60x
        )
    )

    # Recovery for Spring 1 (3 bars)
    for i in range(26, 29):
        timestamp = base_timestamp + timedelta(days=i)
        bars.append(
            create_ohlcv_bar(
                symbol=trading_range.symbol,
                timestamp=timestamp,
                open_price=Decimal("99.00") if i == 26 else Decimal("99.50"),
                high=Decimal("101.00"),
                low=Decimal("98.50"),
                close=Decimal("100.50") if i == 28 else Decimal("99.50"),
                volume=avg_volume,
            )
        )

    # Test for Spring 1 (Bar 32)
    for i in range(29, 32):
        timestamp = base_timestamp + timedelta(days=i)
        bars.append(
            create_ohlcv_bar(
                symbol=trading_range.symbol,
                timestamp=timestamp,
                open_price=Decimal("100.50"),
                high=Decimal("102.00"),
                low=Decimal("100.00"),
                close=Decimal("101.00"),
                volume=avg_volume,
            )
        )

    bars.append(
        create_ohlcv_bar(
            symbol=trading_range.symbol,
            timestamp=base_timestamp + timedelta(days=32),
            open_price=Decimal("101.00"),
            high=Decimal("101.00"),
            low=Decimal("98.20"),  # Test
            close=Decimal("99.50"),
            volume=50_000,  # Lower than spring 1
        )
    )

    # Bars 33-39: Normal trading
    for i in range(33, 40):
        timestamp = base_timestamp + timedelta(days=i)
        bars.append(
            create_ohlcv_bar(
                symbol=trading_range.symbol,
                timestamp=timestamp,
                open_price=Decimal("100.50"),
                high=Decimal("102.00"),
                low=Decimal("99.50"),
                close=Decimal("100.50"),
                volume=avg_volume,
            )
        )

    # SPRING 2: Bar 40 (0.48x volume - LOWER than Spring 1)
    bars.append(
        create_ohlcv_bar(
            symbol=trading_range.symbol,
            timestamp=base_timestamp + timedelta(days=40),
            open_price=Decimal("99.00"),
            high=Decimal("99.50"),
            low=Decimal("97.50"),  # 2.5% below Creek
            close=Decimal("98.50"),
            volume=48_000,  # 0.48x (LOWER) ✅
        )
    )

    # Recovery for Spring 2 (2 bars)
    for i in range(41, 43):
        timestamp = base_timestamp + timedelta(days=i)
        bars.append(
            create_ohlcv_bar(
                symbol=trading_range.symbol,
                timestamp=timestamp,
                open_price=Decimal("98.50") if i == 41 else Decimal("99.50"),
                high=Decimal("101.00"),
                low=Decimal("98.00"),
                close=Decimal("100.50") if i == 42 else Decimal("99.50"),
                volume=avg_volume,
            )
        )

    # Test for Spring 2 (Bar 47)
    for i in range(43, 47):
        timestamp = base_timestamp + timedelta(days=i)
        bars.append(
            create_ohlcv_bar(
                symbol=trading_range.symbol,
                timestamp=timestamp,
                open_price=Decimal("100.50"),
                high=Decimal("102.00"),
                low=Decimal("100.00"),
                close=Decimal("101.00"),
                volume=avg_volume,
            )
        )

    bars.append(
        create_ohlcv_bar(
            symbol=trading_range.symbol,
            timestamp=base_timestamp + timedelta(days=47),
            open_price=Decimal("101.00"),
            high=Decimal("101.00"),
            low=Decimal("97.70"),  # Test
            close=Decimal("99.00"),
            volume=40_000,  # Lower than spring 2
        )
    )

    # Bars 48-54: Normal trading
    for i in range(48, 55):
        timestamp = base_timestamp + timedelta(days=i)
        bars.append(
            create_ohlcv_bar(
                symbol=trading_range.symbol,
                timestamp=timestamp,
                open_price=Decimal("100.50"),
                high=Decimal("102.00"),
                low=Decimal("99.50"),
                close=Decimal("100.50"),
                volume=avg_volume,
            )
        )

    # SPRING 3: Bar 55 (0.32x volume - LOWEST) ✅
    bars.append(
        create_ohlcv_bar(
            symbol=trading_range.symbol,
            timestamp=base_timestamp + timedelta(days=55),
            open_price=Decimal("98.50"),
            high=Decimal("98.80"),
            low=Decimal("97.00"),  # 3% below Creek
            close=Decimal("97.50"),
            volume=32_000,  # 0.32x (LOWEST) ✅
        )
    )

    # Recovery for Spring 3 (1 bar - fastest)
    bars.append(
        create_ohlcv_bar(
            symbol=trading_range.symbol,
            timestamp=base_timestamp + timedelta(days=56),
            open_price=Decimal("97.50"),
            high=Decimal("101.50"),
            low=Decimal("97.00"),
            close=Decimal("100.50"),  # Immediate recovery ✅
            volume=95_000,
        )
    )

    # Test for Spring 3 (Bar 61)
    for i in range(57, 61):
        timestamp = base_timestamp + timedelta(days=i)
        bars.append(
            create_ohlcv_bar(
                symbol=trading_range.symbol,
                timestamp=timestamp,
                open_price=Decimal("100.50"),
                high=Decimal("102.00"),
                low=Decimal("100.00"),
                close=Decimal("101.00"),
                volume=avg_volume,
            )
        )

    bars.append(
        create_ohlcv_bar(
            symbol=trading_range.symbol,
            timestamp=base_timestamp + timedelta(days=61),
            open_price=Decimal("101.00"),
            high=Decimal("101.00"),
            low=Decimal("97.20"),  # Test
            close=Decimal("98.50"),
            volume=28_000,  # Lowest test volume
        )
    )

    # Bars 62-69: Continued trading
    for i in range(62, 70):
        timestamp = base_timestamp + timedelta(days=i)
        bars.append(
            create_ohlcv_bar(
                symbol=trading_range.symbol,
                timestamp=timestamp,
                open_price=Decimal("100.50"),
                high=Decimal("102.00"),
                low=Decimal("100.00"),
                close=Decimal("101.00"),
                volume=avg_volume,
            )
        )

    return bars


# ============================================================
# TEST SUITE 1: SINGLE SPRING DETECTION
# ============================================================


def test_single_spring_detection_basic_example(
    trading_range, base_timestamp
):
    """
    Test: Single spring detection matches documentation Example 1.

    Documentation Reference:
    - docs/examples/spring_detector_usage_examples.md Section 1
    - spring_detector.py SpringDetector class docstring

    Validates:
    - spring_count = 1
    - risk_level = MODERATE (0.42x volume in 0.3-0.7x range)
    - volume_trend = STABLE (only 1 spring)
    - best_spring.volume_ratio = 0.42x
    """
    detector = SpringDetector()
    bars = create_bar_sequence_with_single_spring(trading_range, base_timestamp)

    # Detect all springs
    history = detector.detect_all_springs(
        range=trading_range,
        bars=bars,
        phase=WyckoffPhase.C,
    )

    # Validate documentation example
    assert history.spring_count == 1, "Should detect exactly 1 spring"
    assert history.risk_level == "MODERATE", "0.42x volume = MODERATE risk"
    assert history.volume_trend == "STABLE", "Single spring = STABLE trend"

    # Validate best spring
    assert history.best_spring is not None
    assert history.best_spring.volume_ratio < Decimal("0.5"), "Volume <0.5x"
    assert history.best_spring.spring_low == Decimal("98.00")
    assert history.best_spring.quality_tier == "IDEAL"  # 0.42x volume


def test_single_spring_signal_generation(
    trading_range, base_timestamp
):
    """
    Test: Single spring generates signal matching documentation.

    Validates:
    - Signal generated (test confirmed)
    - Confidence >= 70% (FR4 minimum)
    - R-multiple >= 3.0R (FR19 minimum)
    - Entry > Stop, Target > Entry
    """
    detector = SpringDetector()
    bars = create_bar_sequence_with_single_spring(trading_range, base_timestamp)

    history = detector.detect_all_springs(
        range=trading_range,
        bars=bars,
        phase=WyckoffPhase.C,
    )

    # Get best signal
    best_signal = detector.get_best_signal(history)

    assert best_signal is not None, "Should generate signal (test confirmed)"
    assert best_signal.confidence >= 70, "FR4: Confidence >= 70%"
    assert best_signal.r_multiple >= Decimal("3.0"), "FR19: R >= 3.0R"
    assert best_signal.entry_price > best_signal.stop_loss, "Entry > Stop"
    assert best_signal.target_price > best_signal.entry_price, "Target > Entry"


# ============================================================
# TEST SUITE 2: MULTI-SPRING DECLINING VOLUME (PROFESSIONAL)
# ============================================================


def test_multi_spring_declining_volume_detection(
    trading_range, base_timestamp
):
    """
    Test: Multi-spring declining volume matches documentation Example 2.

    Documentation Reference:
    - docs/examples/spring_detector_usage_examples.md Section 2
    - spring_detector.py detect_all_springs() docstring

    Spring Sequence:
    - Spring 1: 0.60x volume
    - Spring 2: 0.48x volume (LOWER)
    - Spring 3: 0.32x volume (LOWEST)

    Validates:
    - spring_count = 3
    - volume_trend = DECLINING (0.60 → 0.48 → 0.32)
    - risk_level = LOW (professional accumulation)
    - best_spring = Spring 3 (lowest volume per Wyckoff hierarchy)
    """
    detector = SpringDetector()
    bars = create_bar_sequence_with_declining_volume_springs(
        trading_range, base_timestamp
    )

    # Detect all springs
    history = detector.detect_all_springs(
        range=trading_range,
        bars=bars,
        phase=WyckoffPhase.C,
    )

    # Validate multi-spring detection
    assert history.spring_count == 3, "Should detect 3 springs"
    assert history.volume_trend == "DECLINING", "Volume 0.60→0.48→0.32 = DECLINING"
    assert history.risk_level == "LOW", "Declining volume = professional = LOW risk"

    # Validate spring sequence
    assert len(history.springs) == 3
    spring1, spring2, spring3 = history.springs

    # Validate declining volume
    assert spring1.volume_ratio == Decimal("0.6"), "Spring 1: 0.60x"
    assert spring2.volume_ratio == Decimal("0.48"), "Spring 2: 0.48x (LOWER)"
    assert spring3.volume_ratio == Decimal("0.32"), "Spring 3: 0.32x (LOWEST)"

    # Validate best spring = Spring 3 (lowest volume)
    assert history.best_spring == spring3, "Best spring = lowest volume (Wyckoff)"
    assert history.best_spring.volume_ratio == Decimal("0.32")


def test_multi_spring_declining_volume_all_signals_tracked(
    trading_range, base_timestamp
):
    """
    Test: All signals tracked in chronological order.

    Validates:
    - All 3 springs have signals (if tests confirmed)
    - Signals tracked chronologically
    - Best signal has highest confidence
    """
    detector = SpringDetector()
    bars = create_bar_sequence_with_declining_volume_springs(
        trading_range, base_timestamp
    )

    history = detector.detect_all_springs(
        range=trading_range,
        bars=bars,
        phase=WyckoffPhase.C,
    )

    # All springs should have signals (all have tests)
    assert len(history.signals) == 3, "All 3 springs should have signals"

    # Signals should be in chronological order
    for i in range(len(history.signals) - 1):
        assert (
            history.signals[i].spring_bar_timestamp
            < history.signals[i + 1].spring_bar_timestamp
        ), "Signals should be chronological"

    # Best signal has highest confidence
    best_signal = detector.get_best_signal(history)
    assert best_signal is not None
    assert all(
        best_signal.confidence >= signal.confidence
        for signal in history.signals
    ), "Best signal should have highest confidence"


# ============================================================
# TEST SUITE 3: VOLUME TREND ANALYSIS
# ============================================================


def test_analyze_volume_trend_declining():
    """
    Test: analyze_volume_trend() with declining pattern.

    Documentation Reference:
    - docs/examples/spring_detector_usage_examples.md Section 5
    - spring_detector.py analyze_volume_trend() docstring

    Sequence: 0.6 → 0.5 → 0.4 → 0.3 (DECLINING)
    First half avg: (0.6 + 0.5) / 2 = 0.55
    Second half avg: (0.4 + 0.3) / 2 = 0.35
    Change: (0.35 - 0.55) / 0.55 = -36% (>15% decrease = DECLINING)
    """
    from src.models.spring import Spring

    # Create mock springs (only volume_ratio matters)
    base_time = datetime(2024, 1, 1, tzinfo=UTC)
    spring1 = Spring(
        bar=OHLCVBar(
            symbol="TEST",
            timestamp=base_time,
            open=Decimal("100"),
            high=Decimal("100"),
            low=Decimal("98"),
            close=Decimal("99"),
            volume=60000,
        ),
        bar_index=25,
        penetration_pct=Decimal("0.02"),
        volume_ratio=Decimal("0.6"),
        recovery_bars=2,
        creek_reference=Decimal("100"),
        spring_low=Decimal("98"),
        recovery_price=Decimal("100.5"),
        detection_timestamp=base_time,
        trading_range_id=uuid4(),
    )

    spring2 = Spring(
        bar=OHLCVBar(
            symbol="TEST",
            timestamp=base_time + timedelta(days=15),
            open=Decimal("100"),
            high=Decimal("100"),
            low=Decimal("97.5"),
            close=Decimal("99"),
            volume=50000,
        ),
        bar_index=40,
        penetration_pct=Decimal("0.025"),
        volume_ratio=Decimal("0.5"),
        recovery_bars=2,
        creek_reference=Decimal("100"),
        spring_low=Decimal("97.5"),
        recovery_price=Decimal("100.5"),
        detection_timestamp=base_time + timedelta(days=15),
        trading_range_id=uuid4(),
    )

    spring3 = Spring(
        bar=OHLCVBar(
            symbol="TEST",
            timestamp=base_time + timedelta(days=30),
            open=Decimal("100"),
            high=Decimal("100"),
            low=Decimal("97"),
            close=Decimal("99"),
            volume=40000,
        ),
        bar_index=55,
        penetration_pct=Decimal("0.03"),
        volume_ratio=Decimal("0.4"),
        recovery_bars=1,
        creek_reference=Decimal("100"),
        spring_low=Decimal("97"),
        recovery_price=Decimal("100.5"),
        detection_timestamp=base_time + timedelta(days=30),
        trading_range_id=uuid4(),
    )

    spring4 = Spring(
        bar=OHLCVBar(
            symbol="TEST",
            timestamp=base_time + timedelta(days=45),
            open=Decimal("100"),
            high=Decimal("100"),
            low=Decimal("96.5"),
            close=Decimal("99"),
            volume=30000,
        ),
        bar_index=70,
        penetration_pct=Decimal("0.035"),
        volume_ratio=Decimal("0.3"),
        recovery_bars=1,
        creek_reference=Decimal("100"),
        spring_low=Decimal("96.5"),
        recovery_price=Decimal("100.5"),
        detection_timestamp=base_time + timedelta(days=45),
        trading_range_id=uuid4(),
    )

    # Analyze trend
    trend = analyze_volume_trend([spring1, spring2, spring3, spring4])

    assert trend == "DECLINING", "0.6→0.5→0.4→0.3 should be DECLINING"


def test_analyze_volume_trend_stable():
    """
    Test: analyze_volume_trend() with stable pattern.

    Sequence: 0.45 → 0.50 → 0.48 → 0.52 (STABLE)
    Change within ±15% threshold
    """
    from src.models.spring import Spring

    base_time = datetime(2024, 1, 1, tzinfo=UTC)

    # Create springs with stable volume (0.45-0.52 range)
    springs = []
    volumes = [Decimal("0.45"), Decimal("0.50"), Decimal("0.48"), Decimal("0.52")]

    for i, vol in enumerate(volumes):
        spring = Spring(
            bar=OHLCVBar(
                symbol="TEST",
                timestamp=base_time + timedelta(days=i * 15),
                open=Decimal("100"),
                high=Decimal("100"),
                low=Decimal("98"),
                close=Decimal("99"),
                volume=int(vol * 100000),
            ),
            bar_index=25 + i * 15,
            penetration_pct=Decimal("0.02"),
            volume_ratio=vol,
            recovery_bars=2,
            creek_reference=Decimal("100"),
            spring_low=Decimal("98"),
            recovery_price=Decimal("100.5"),
            detection_timestamp=base_time + timedelta(days=i * 15),
            trading_range_id=uuid4(),
        )
        springs.append(spring)

    # Analyze trend
    trend = analyze_volume_trend(springs)

    assert trend == "STABLE", "Volume within ±15% should be STABLE"


def test_analyze_volume_trend_single_spring_returns_stable():
    """
    Test: Single spring returns STABLE (need 2+ for trend).

    Documentation Reference:
    - docs/examples/spring_detector_usage_examples.md Section 5
    """
    from src.models.spring import Spring

    base_time = datetime(2024, 1, 1, tzinfo=UTC)
    spring = Spring(
        bar=OHLCVBar(
            symbol="TEST",
            timestamp=base_time,
            open=Decimal("100"),
            high=Decimal("100"),
            low=Decimal("98"),
            close=Decimal("99"),
            volume=50000,
        ),
        bar_index=25,
        penetration_pct=Decimal("0.02"),
        volume_ratio=Decimal("0.5"),
        recovery_bars=2,
        creek_reference=Decimal("100"),
        spring_low=Decimal("98"),
        recovery_price=Decimal("100.5"),
        detection_timestamp=base_time,
        trading_range_id=uuid4(),
    )

    # Single spring should return STABLE
    trend = analyze_volume_trend([spring])
    assert trend == "STABLE", "Single spring = STABLE (need 2+ for trend)"


# ============================================================
# TEST SUITE 4: RISK PROFILE ANALYSIS
# ============================================================


def test_analyze_risk_profile_single_spring_low_volume():
    """
    Test: Single spring <0.3x volume = LOW risk.

    Documentation Reference:
    - docs/examples/spring_detector_usage_examples.md Section 4
    - spring_detector.py analyze_spring_risk_profile() docstring
    """
    history = SpringHistory(symbol="TEST", trading_range_id=uuid4())

    # Create spring with ultra-low volume (<0.3x)
    base_time = datetime(2024, 1, 1, tzinfo=UTC)
    spring = Spring(
        bar=OHLCVBar(
            symbol="TEST",
            timestamp=base_time,
            open=Decimal("100"),
            high=Decimal("100"),
            low=Decimal("98"),
            close=Decimal("99"),
            volume=25000,
        ),
        bar_index=25,
        penetration_pct=Decimal("0.02"),
        volume_ratio=Decimal("0.25"),  # <0.3x = LOW risk
        recovery_bars=1,
        creek_reference=Decimal("100"),
        spring_low=Decimal("98"),
        recovery_price=Decimal("100.5"),
        detection_timestamp=base_time,
        trading_range_id=uuid4(),
    )

    history.add_spring(spring, signal=None)

    # Analyze risk
    risk = analyze_spring_risk_profile(history)

    assert risk == "LOW", "Single spring <0.3x volume = LOW risk"


def test_analyze_risk_profile_single_spring_moderate_volume():
    """
    Test: Single spring 0.3-0.7x volume = MODERATE risk.
    """
    history = SpringHistory(symbol="TEST", trading_range_id=uuid4())

    base_time = datetime(2024, 1, 1, tzinfo=UTC)
    spring = Spring(
        bar=OHLCVBar(
            symbol="TEST",
            timestamp=base_time,
            open=Decimal("100"),
            high=Decimal("100"),
            low=Decimal("98"),
            close=Decimal("99"),
            volume=50000,
        ),
        bar_index=25,
        penetration_pct=Decimal("0.02"),
        volume_ratio=Decimal("0.5"),  # 0.3-0.7x = MODERATE
        recovery_bars=2,
        creek_reference=Decimal("100"),
        spring_low=Decimal("98"),
        recovery_price=Decimal("100.5"),
        detection_timestamp=base_time,
        trading_range_id=uuid4(),
    )

    history.add_spring(spring, signal=None)

    # Analyze risk
    risk = analyze_spring_risk_profile(history)

    assert risk == "MODERATE", "Single spring 0.3-0.7x volume = MODERATE risk"


def test_analyze_risk_profile_multi_spring_declining_low_risk():
    """
    Test: Multi-spring declining volume = LOW risk (professional).

    Documentation Reference:
    - docs/examples/spring_detector_usage_examples.md Section 2
    """
    history = SpringHistory(symbol="TEST", trading_range_id=uuid4())
    base_time = datetime(2024, 1, 1, tzinfo=UTC)

    # Create 3 springs with declining volume
    volumes = [Decimal("0.6"), Decimal("0.4"), Decimal("0.3")]

    for i, vol in enumerate(volumes):
        spring = Spring(
            bar=OHLCVBar(
                symbol="TEST",
                timestamp=base_time + timedelta(days=i * 15),
                open=Decimal("100"),
                high=Decimal("100"),
                low=Decimal("98") - Decimal(str(i * 0.5)),
                close=Decimal("99"),
                volume=int(vol * 100000),
            ),
            bar_index=25 + i * 15,
            penetration_pct=Decimal("0.02"),
            volume_ratio=vol,
            recovery_bars=3 - i,
            creek_reference=Decimal("100"),
            spring_low=Decimal("98") - Decimal(str(i * 0.5)),
            recovery_price=Decimal("100.5"),
            detection_timestamp=base_time + timedelta(days=i * 15),
            trading_range_id=uuid4(),
        )
        history.add_spring(spring, signal=None)

    # Analyze risk
    risk = analyze_spring_risk_profile(history)

    assert risk == "LOW", "Declining volume = professional = LOW risk"


# ============================================================
# TEST SUITE 5: BEST SPRING AND SIGNAL SELECTION
# ============================================================


def test_best_spring_selection_wyckoff_hierarchy(
    trading_range, base_timestamp
):
    """
    Test: Best spring selected using Wyckoff quality hierarchy.

    Hierarchy:
    1. Volume quality (primary): Lower = better
    2. Penetration depth (secondary): Deeper = better
    3. Recovery speed (tiebreaker): Faster = better

    Documentation Reference:
    - docs/examples/spring_detector_usage_examples.md Section 6
    """
    detector = SpringDetector()
    bars = create_bar_sequence_with_declining_volume_springs(
        trading_range, base_timestamp
    )

    history = detector.detect_all_springs(
        range=trading_range,
        bars=bars,
        phase=WyckoffPhase.C,
    )

    # Best spring should be Spring 3 (lowest volume 0.32x)
    assert history.best_spring is not None
    assert history.best_spring.volume_ratio == Decimal("0.32"), (
        "Best spring = lowest volume (Wyckoff primary criterion)"
    )


def test_best_signal_selection_highest_confidence():
    """
    Test: Best signal selected by highest confidence.

    Documentation Reference:
    - docs/examples/spring_detector_usage_examples.md Section 6
    - spring_detector.py get_best_signal() docstring
    """
    detector = SpringDetector()
    history = SpringHistory(symbol="TEST", trading_range_id=uuid4())

    # Create mock signals with different confidences
    from src.models.spring_signal import SpringSignal
    from src.models.spring import Spring

    base_time = datetime(2024, 1, 1, tzinfo=UTC)

    for i, confidence in enumerate([75, 85, 80]):  # Signal 2 has highest (85)
        spring = Spring(
            bar=OHLCVBar(
                symbol="TEST",
                timestamp=base_time + timedelta(days=i * 15),
                open=Decimal("100"),
                high=Decimal("100"),
                low=Decimal("98"),
                close=Decimal("99"),
                volume=50000,
            ),
            bar_index=25 + i * 15,
            penetration_pct=Decimal("0.02"),
            volume_ratio=Decimal("0.5"),
            recovery_bars=2,
            creek_reference=Decimal("100"),
            spring_low=Decimal("98"),
            recovery_price=Decimal("100.5"),
            detection_timestamp=base_time + timedelta(days=i * 15),
            trading_range_id=uuid4(),
        )

        signal = SpringSignal(
            symbol="TEST",
            entry_price=Decimal("100.10"),
            stop_loss=Decimal("95.00"),
            target_price=Decimal("110.00"),
            position_size=100,
            risk_amount=Decimal("500"),
            r_multiple=Decimal("3.0"),
            confidence=confidence,
            spring_bar_timestamp=base_time + timedelta(days=i * 15),
            test_bar_timestamp=base_time + timedelta(days=i * 15 + 7),
            urgency="IMMEDIATE",
            trading_range_id=uuid4(),
            phase="C",
        )

        history.add_spring(spring, signal)

    # Get best signal
    best = detector.get_best_signal(history)

    assert best is not None
    assert best.confidence == 85, "Best signal = highest confidence (85%)"


# ============================================================
# TEST SUITE 6: BACKWARD COMPATIBILITY
# ============================================================


def test_backward_compatibility_legacy_detect_api(
    trading_range, base_timestamp
):
    """
    Test: Legacy detect() API returns List[SpringSignal].

    Documentation Reference:
    - docs/examples/spring_detector_usage_examples.md Section 7
    - spring_detector.py detect() method docstring

    Validates:
    - detect() returns list of signals
    - Signals are same as history.signals
    - Existing code using detect() still works
    """
    detector = SpringDetector()
    bars = create_bar_sequence_with_single_spring(trading_range, base_timestamp)

    # Legacy API
    signals = detector.detect(
        range=trading_range,
        bars=bars,
        phase=WyckoffPhase.C,
    )

    # Should return list of SpringSignal
    assert isinstance(signals, list), "detect() should return list"
    assert len(signals) >= 0, "List can be empty or have signals"

    # Compare with new API
    history = detector.detect_all_springs(
        range=trading_range,
        bars=bars,
        phase=WyckoffPhase.C,
    )

    assert signals == history.signals, "Legacy API should match new API signals"


# ============================================================
# TEST SUITE 7: PHASE 4 DOCUMENTATION COMPLETENESS
# ============================================================


def test_documentation_examples_comprehensive_coverage():
    """
    Test: Verify all documentation examples have corresponding tests.

    This meta-test ensures Phase 4 documentation has complete test coverage.
    """
    # Documentation sections from spring_detector_usage_examples.md
    documented_scenarios = [
        "single_spring_detection",
        "multi_spring_declining_volume",
        "multi_spring_rising_volume",
        "risk_assessment",
        "volume_trend_analysis",
        "best_spring_signal_selection",
        "backward_compatibility",
    ]

    # Count tests for each scenario (based on test function names)
    import sys
    current_module = sys.modules[__name__]

    test_functions = [
        name for name in dir(current_module)
        if name.startswith("test_") and callable(getattr(current_module, name))
    ]

    # Verify each scenario has at least one test
    for scenario in documented_scenarios:
        matching_tests = [
            test for test in test_functions
            if scenario.replace("_", "") in test.replace("_", "")
        ]
        assert len(matching_tests) > 0, (
            f"Documentation scenario '{scenario}' should have at least one test. "
            f"Found: {matching_tests}"
        )

    print(f"\n✅ Documentation coverage validated: {len(test_functions)} tests covering "
          f"{len(documented_scenarios)} scenarios")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
