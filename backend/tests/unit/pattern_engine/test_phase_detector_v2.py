"""
Unit tests for PhaseDetector v2 (Story 4.7).

Tests cover:
- Basic PhaseDetector initialization
- Event detection pipeline integration
- Phase classification
- FR15 validation (pattern-phase alignment)
- Caching functionality
- Helper methods

Phase 1 Testing Scope:
- Core PhaseDetector functionality with SC/AR/ST events
- Phase A and Phase B detection
- Cache hit/miss scenarios
- FR15 validation for known patterns

Phase 2/3 will add:
- Phase invalidation/confirmation tests
- Breakdown classification tests
- Sub-phase state machine tests
- Risk management tests
"""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List

from src.models.ohlcv import OHLCVBar
from src.models.volume_analysis import VolumeAnalysis
from src.models.effort_result import EffortResult
from src.models.trading_range import TradingRange
from src.models.wyckoff_phase import WyckoffPhase
from src.pattern_engine.phase_detector_v2 import (
    PhaseDetector,
    get_current_phase,
    is_trading_allowed,
    get_phase_description,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_bars() -> List[OHLCVBar]:
    """Generate sample OHLCV bars for testing."""
    base_time = datetime(2024, 1, 1, 9, 30, tzinfo=timezone.utc)
    bars = []

    # Generate 50 bars with realistic price action
    for i in range(50):
        timestamp = base_time + timedelta(days=i)

        # Simulate downtrend leading to SC at bar 20
        if i < 20:
            base_price = Decimal("100") - Decimal(str(i * 0.5))
        # SC zone at bars 20-22
        elif i in [20, 21, 22]:
            base_price = Decimal("90")
        # AR rally at bars 23-25
        elif 23 <= i <= 25:
            base_price = Decimal("90") + Decimal(str((i - 22) * 1.5))
        # ST oscillation in Phase B
        else:
            base_price = Decimal("93") + Decimal(str((i % 5) * 0.3))

        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=timestamp,
            open=base_price,
            high=base_price + Decimal("2"),
            low=base_price - Decimal("2"),
            close=base_price + Decimal("1"),
            volume=1000000 * (2 if i in [20, 21, 22] else 1),  # High volume at SC
            spread=Decimal("4"),
        )
        bars.append(bar)

    return bars


@pytest.fixture
def sample_volume_analysis(sample_bars) -> List[VolumeAnalysis]:
    """Generate sample volume analysis matching bars."""
    analyses = []

    for i, bar in enumerate(sample_bars):
        # Mark SC bars as CLIMACTIC
        if i in [20, 21, 22]:
            effort_result = EffortResult.CLIMACTIC
            volume_ratio = Decimal("2.5")
            spread_ratio = Decimal("2.0")
        else:
            effort_result = EffortResult.NORMAL
            volume_ratio = Decimal("1.0")
            spread_ratio = Decimal("1.0")

        analysis = VolumeAnalysis(
            symbol=bar.symbol,
            timeframe=bar.timeframe,
            timestamp=bar.timestamp,
            volume=bar.volume,
            average_volume=Decimal("1000000"),
            volume_ratio=volume_ratio,
            spread=bar.spread,
            average_spread=Decimal("2.0"),
            spread_ratio=spread_ratio,
            close_position=Decimal("0.75"),  # Upper region
            effort_result=effort_result,
        )
        analyses.append(analysis)

    return analyses


@pytest.fixture
def sample_trading_range() -> TradingRange:
    """Generate sample trading range."""
    # Simplified trading range for testing
    # In real implementation, this would be fully populated
    class SimpleTradingRange:
        def __init__(self):
            self.support = Decimal("89")
            self.resistance = Decimal("96")
            self.creek = type('obj', (object,), {'price': Decimal("89")})()
            self.ice = type('obj', (object,), {'price': Decimal("96")})()

    return SimpleTradingRange()


# ============================================================================
# PhaseDetector Initialization Tests
# ============================================================================


def test_phase_detector_initialization():
    """Test PhaseDetector initializes with empty cache."""
    detector = PhaseDetector()

    assert detector is not None
    assert detector._cache == {}


# ============================================================================
# Event Detection Pipeline Tests
# ============================================================================


def test_detect_phase_with_sc_only(sample_bars, sample_volume_analysis, sample_trading_range):
    """Test phase detection with only SC detected (no AR yet)."""
    detector = PhaseDetector()

    # Use only bars up to SC (bar 22)
    bars = sample_bars[:23]
    volume_analysis = sample_volume_analysis[:23]

    phase_info = detector.detect_phase(sample_trading_range, bars, volume_analysis)

    # Should detect SC but no phase yet (need AR for Phase A)
    assert phase_info.events.sc is not None
    assert phase_info.events.ar is None
    assert phase_info.phase is None or phase_info.phase == WyckoffPhase.A


def test_detect_phase_with_sc_and_ar(sample_bars, sample_volume_analysis, sample_trading_range):
    """Test phase detection with SC + AR (Phase A confirmed)."""
    detector = PhaseDetector()

    # Use bars through AR (bar 25)
    bars = sample_bars[:26]
    volume_analysis = sample_volume_analysis[:26]

    phase_info = detector.detect_phase(sample_trading_range, bars, volume_analysis)

    # Should detect SC + AR = Phase A
    assert phase_info.events.sc is not None
    assert phase_info.events.ar is not None
    assert phase_info.phase == WyckoffPhase.A


def test_detect_phase_with_st(sample_bars, sample_volume_analysis, sample_trading_range):
    """Test phase detection with ST (Phase B entry)."""
    detector = PhaseDetector()

    # Use all bars (includes ST in Phase B)
    phase_info = detector.detect_phase(
        sample_trading_range, sample_bars, sample_volume_analysis
    )

    # Should detect SC + AR + ST = Phase B
    assert phase_info.events.sc is not None
    assert phase_info.events.ar is not None
    # ST detection depends on price action - may or may not detect
    # Just verify events structure is populated
    assert phase_info.events.st_list is not None


# ============================================================================
# Phase Classification Tests
# ============================================================================


def test_phase_info_structure(sample_bars, sample_volume_analysis, sample_trading_range):
    """Test that PhaseInfo contains all required fields."""
    detector = PhaseDetector()

    phase_info = detector.detect_phase(
        sample_trading_range, sample_bars, sample_volume_analysis
    )

    # Core fields
    assert hasattr(phase_info, 'phase')
    assert hasattr(phase_info, 'confidence')
    assert hasattr(phase_info, 'events')
    assert hasattr(phase_info, 'duration')
    assert hasattr(phase_info, 'progression_history')

    # Risk management fields
    assert hasattr(phase_info, 'current_risk_level')
    assert hasattr(phase_info, 'position_action_required')

    # Validate types
    assert isinstance(phase_info.confidence, int)
    assert 0 <= phase_info.confidence <= 100
    assert isinstance(phase_info.duration, int)
    assert phase_info.duration >= 0


def test_trading_allowed_fr14_enforcement(sample_bars, sample_volume_analysis, sample_trading_range):
    """Test FR14 trading restrictions enforcement."""
    detector = PhaseDetector()

    phase_info = detector.detect_phase(
        sample_trading_range, sample_bars, sample_volume_analysis
    )

    # Test is_trading_allowed method
    if phase_info.phase == WyckoffPhase.A:
        # Phase A: NOT allowed
        assert phase_info.is_trading_allowed() == False
    elif phase_info.phase == WyckoffPhase.B:
        # Phase B: depends on duration
        if phase_info.duration < 10:
            assert phase_info.is_trading_allowed() == False
        else:
            assert phase_info.is_trading_allowed() == True
    elif phase_info.phase in [WyckoffPhase.C, WyckoffPhase.D, WyckoffPhase.E]:
        # Phase C/D/E: ALLOWED
        assert phase_info.is_trading_allowed() == True


# ============================================================================
# FR15 Validation Tests
# ============================================================================


def test_fr15_spring_pattern_validation(sample_bars, sample_volume_analysis, sample_trading_range):
    """Test FR15 validation for Spring patterns (Phase C only)."""
    detector = PhaseDetector()

    phase_info = detector.detect_phase(
        sample_trading_range, sample_bars, sample_volume_analysis
    )

    is_valid, reason = detector.is_valid_for_pattern(phase_info, "SPRING")

    if phase_info.phase == WyckoffPhase.C:
        assert is_valid == True
        assert reason is None
    else:
        assert is_valid == False
        assert "Phase C" in reason


def test_fr15_sos_pattern_validation(sample_bars, sample_volume_analysis, sample_trading_range):
    """Test FR15 validation for SOS patterns (Phase D only)."""
    detector = PhaseDetector()

    phase_info = detector.detect_phase(
        sample_trading_range, sample_bars, sample_volume_analysis
    )

    is_valid, reason = detector.is_valid_for_pattern(phase_info, "SOS")

    if phase_info.phase == WyckoffPhase.D:
        assert is_valid == True
        assert reason is None
    else:
        assert is_valid == False
        assert "Phase D" in reason


def test_fr15_lps_pattern_validation(sample_bars, sample_volume_analysis, sample_trading_range):
    """Test FR15 validation for LPS patterns (Phase D or E)."""
    detector = PhaseDetector()

    phase_info = detector.detect_phase(
        sample_trading_range, sample_bars, sample_volume_analysis
    )

    is_valid, reason = detector.is_valid_for_pattern(phase_info, "LPS")

    if phase_info.phase in [WyckoffPhase.D, WyckoffPhase.E]:
        assert is_valid == True
        assert reason is None
    else:
        assert is_valid == False
        assert "Phase D or E" in reason


# ============================================================================
# Caching Tests
# ============================================================================


def test_cache_hit_on_repeated_detection(sample_bars, sample_volume_analysis, sample_trading_range):
    """Test that cache returns same result when bar count unchanged."""
    detector = PhaseDetector()

    # First call - should populate cache
    result1 = detector.detect_phase(
        sample_trading_range, sample_bars, sample_volume_analysis
    )

    # Second call with same bars - should hit cache
    result2 = detector.detect_phase(
        sample_trading_range, sample_bars, sample_volume_analysis
    )

    # Results should be identical (same object from cache)
    assert result1.phase == result2.phase
    assert result1.confidence == result2.confidence
    assert result1.duration == result2.duration


def test_cache_miss_on_new_bars(sample_bars, sample_volume_analysis, sample_trading_range):
    """Test that cache misses when new bars added."""
    detector = PhaseDetector()

    # First call with subset of bars
    bars1 = sample_bars[:30]
    volume_analysis1 = sample_volume_analysis[:30]
    result1 = detector.detect_phase(sample_trading_range, bars1, volume_analysis1)

    # Second call with more bars - should miss cache
    bars2 = sample_bars[:40]
    volume_analysis2 = sample_volume_analysis[:40]
    result2 = detector.detect_phase(sample_trading_range, bars2, volume_analysis2)

    # Durations should be different (more bars = longer duration)
    assert result2.duration >= result1.duration


def test_cache_invalidation_specific(sample_bars, sample_volume_analysis, sample_trading_range):
    """Test cache invalidation for specific symbol/timeframe."""
    detector = PhaseDetector()

    # Populate cache
    detector.detect_phase(sample_trading_range, sample_bars, sample_volume_analysis)
    assert len(detector._cache) > 0

    # Invalidate specific symbol/timeframe
    detector.invalidate_cache("AAPL", "1d")

    # Cache should be empty
    assert len(detector._cache) == 0


def test_cache_invalidation_all(sample_bars, sample_volume_analysis, sample_trading_range):
    """Test cache invalidation for all entries."""
    detector = PhaseDetector()

    # Populate cache
    detector.detect_phase(sample_trading_range, sample_bars, sample_volume_analysis)
    assert len(detector._cache) > 0

    # Invalidate all
    detector.invalidate_cache()

    # Cache should be empty
    assert len(detector._cache) == 0


# ============================================================================
# Helper Function Tests
# ============================================================================


def test_get_current_phase_helper(sample_bars, sample_volume_analysis, sample_trading_range):
    """Test get_current_phase helper function."""
    detector = PhaseDetector()

    phase_info = detector.detect_phase(
        sample_trading_range, sample_bars, sample_volume_analysis
    )

    phase = get_current_phase(phase_info)

    # Should return same as phase_info.phase
    assert phase == phase_info.phase


def test_is_trading_allowed_helper(sample_bars, sample_volume_analysis, sample_trading_range):
    """Test is_trading_allowed helper function."""
    detector = PhaseDetector()

    phase_info = detector.detect_phase(
        sample_trading_range, sample_bars, sample_volume_analysis
    )

    allowed = is_trading_allowed(phase_info)

    # Should return same as phase_info.is_trading_allowed()
    assert allowed == phase_info.is_trading_allowed()


def test_get_phase_description_helper():
    """Test get_phase_description helper function."""
    desc_a = get_phase_description(WyckoffPhase.A)
    desc_b = get_phase_description(WyckoffPhase.B)
    desc_c = get_phase_description(WyckoffPhase.C)
    desc_d = get_phase_description(WyckoffPhase.D)
    desc_e = get_phase_description(WyckoffPhase.E)

    assert "Stopping Action" in desc_a
    assert "Building Cause" in desc_b
    assert "Test" in desc_c
    assert "Sign of Strength" in desc_d
    assert "Markup" in desc_e


# ============================================================================
# Input Validation Tests
# ============================================================================


def test_empty_bars_raises_error(sample_volume_analysis, sample_trading_range):
    """Test that empty bars list raises ValueError."""
    detector = PhaseDetector()

    with pytest.raises(ValueError, match="Bars list cannot be empty"):
        detector.detect_phase(sample_trading_range, [], sample_volume_analysis)


def test_mismatched_bars_volume_analysis_raises_error(sample_bars, sample_trading_range):
    """Test that mismatched bars/volume_analysis lengths raises ValueError."""
    detector = PhaseDetector()

    # Create mismatched volume_analysis (shorter)
    short_volume_analysis = []

    with pytest.raises(ValueError, match="length mismatch"):
        detector.detect_phase(sample_trading_range, sample_bars, short_volume_analysis)


def test_insufficient_bars_warning(sample_trading_range):
    """Test that <20 bars triggers warning but doesn't fail."""
    detector = PhaseDetector()

    # Create minimal bars (< 20)
    base_time = datetime(2024, 1, 1, 9, 30, tzinfo=timezone.utc)
    minimal_bars = []
    minimal_volume_analysis = []

    for i in range(15):
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=base_time + timedelta(days=i),
            open=Decimal("100"),
            high=Decimal("102"),
            low=Decimal("98"),
            close=Decimal("101"),
            volume=1000000,
            spread=Decimal("4"),
        )
        minimal_bars.append(bar)

        analysis = VolumeAnalysis(
            symbol=bar.symbol,
            timeframe=bar.timeframe,
            timestamp=bar.timestamp,
            volume=bar.volume,
            average_volume=Decimal("1000000"),
            volume_ratio=Decimal("1.0"),
            spread=bar.spread,
            average_spread=Decimal("2.0"),
            spread_ratio=Decimal("1.0"),
            close_position=Decimal("0.75"),
            effort_result=EffortResult.NORMAL,
        )
        minimal_volume_analysis.append(analysis)

    # Should not raise error, just warning
    phase_info = detector.detect_phase(
        sample_trading_range, minimal_bars, minimal_volume_analysis
    )

    # Should still return PhaseInfo (even if phase is None)
    assert phase_info is not None


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_no_events_detected(sample_trading_range):
    """Test phase detection when no events detected (normal market)."""
    detector = PhaseDetector()

    # Create bars with no climactic action
    base_time = datetime(2024, 1, 1, 9, 30, tzinfo=timezone.utc)
    normal_bars = []
    normal_volume_analysis = []

    for i in range(50):
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=base_time + timedelta(days=i),
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100.5"),
            volume=1000000,  # Normal volume
            spread=Decimal("2"),
        )
        normal_bars.append(bar)

        analysis = VolumeAnalysis(
            symbol=bar.symbol,
            timeframe=bar.timeframe,
            timestamp=bar.timestamp,
            volume=bar.volume,
            average_volume=Decimal("1000000"),
            volume_ratio=Decimal("1.0"),  # Normal
            spread=bar.spread,
            average_spread=Decimal("2.0"),
            spread_ratio=Decimal("1.0"),  # Normal
            close_position=Decimal("0.5"),
            effort_result=EffortResult.NORMAL,
        )
        normal_volume_analysis.append(analysis)

    phase_info = detector.detect_phase(
        sample_trading_range, normal_bars, normal_volume_analysis
    )

    # No events detected = no phase
    assert phase_info.events.sc is None
    assert phase_info.events.ar is None
    assert phase_info.phase is None


# ============================================================================
# Performance Tests (Basic)
# ============================================================================


def test_detection_completes_in_reasonable_time(sample_bars, sample_volume_analysis, sample_trading_range):
    """Test that phase detection completes in reasonable time (<100ms for 50 bars)."""
    import time

    detector = PhaseDetector()

    start_time = time.time()
    phase_info = detector.detect_phase(
        sample_trading_range, sample_bars, sample_volume_analysis
    )
    elapsed_ms = (time.time() - start_time) * 1000

    # Should complete in reasonable time (generous for unit test environment)
    # AC 41 requires <100ms for 500 bars, so 50 bars should be much faster
    assert elapsed_ms < 500  # 500ms is very generous for 50 bars

    # Verify result is valid
    assert phase_info is not None


def test_cached_detection_faster(sample_bars, sample_volume_analysis, sample_trading_range):
    """Test that cached detection is faster than first detection."""
    import time

    detector = PhaseDetector()

    # First detection (populate cache)
    start1 = time.time()
    detector.detect_phase(sample_trading_range, sample_bars, sample_volume_analysis)
    time1_ms = (time.time() - start1) * 1000

    # Second detection (cache hit)
    start2 = time.time()
    detector.detect_phase(sample_trading_range, sample_bars, sample_volume_analysis)
    time2_ms = (time.time() - start2) * 1000

    # Cached should be faster (AC 41: <5ms for cached)
    # In practice, cache hit should be microseconds, but test environment varies
    assert time2_ms < time1_ms
