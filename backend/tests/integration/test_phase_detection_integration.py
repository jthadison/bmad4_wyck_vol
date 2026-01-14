"""
Integration Tests for Phase Detection Integration (Story 13.7)

Tests the full integration between PhaseDetector, pattern-phase validation,
and the backtesting pipeline.

AC7.10: Integration test validating pattern rejection for phase mismatch
AC7.24: Combined validation pipeline test (phase → level → volume)
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from src.models.creek_level import CreekLevel
from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import (
    PhaseClassification,
    PhaseEvents,
    WyckoffPhase,
)
from src.models.pivot import Pivot, PivotType
from src.models.price_cluster import PriceCluster
from src.models.trading_range import RangeStatus, TradingRange
from src.pattern_engine.phase_detector_v2 import PhaseDetector
from src.pattern_engine.phase_validator import (
    adjust_pattern_confidence_for_phase_and_volume,
    is_valid_phase_transition,
    validate_pattern_phase_and_level,
)
from src.pattern_engine.volume_analyzer import VolumeAnalyzer

# ============================================================================
# Test Fixtures
# ============================================================================


def create_phase_classification(
    phase: WyckoffPhase,
    confidence: int = 85,
    duration: int = 20,
    trading_allowed: bool = True,
) -> PhaseClassification:
    """Create a valid PhaseClassification for testing."""
    return PhaseClassification(
        phase=phase,
        confidence=confidence,
        duration=duration,
        events_detected=PhaseEvents(),
        trading_allowed=trading_allowed,
        phase_start_index=0,
        phase_start_timestamp=datetime.now(UTC),
    )


def create_bar_sequence(
    num_bars: int = 50,
    start_price: float = 1.0500,
    trend: str = "neutral",
    symbol: str = "C:EURUSD",
    timeframe: str = "1h",
) -> list[OHLCVBar]:
    """Create a sequence of test bars for PhaseDetector."""
    bars = []
    base_time = datetime.now(UTC) - timedelta(hours=num_bars)
    price = Decimal(str(start_price))

    for i in range(num_bars):
        # Add some price movement
        if trend == "up":
            delta = Decimal("0.0001") * i
        elif trend == "down":
            delta = Decimal("-0.0001") * i
        else:
            delta = Decimal("0.0001") * (1 if i % 2 == 0 else -1)

        current_price = price + delta

        bar = OHLCVBar(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=base_time + timedelta(hours=i),
            open=current_price - Decimal("0.0005"),
            high=current_price + Decimal("0.0010"),
            low=current_price - Decimal("0.0010"),
            close=current_price,
            volume=1000 + (i * 10),
            spread=Decimal("0.0020"),
        )
        bars.append(bar)

    return bars


def create_trading_range(
    bars: list[OHLCVBar],
    symbol: str = "C:EURUSD",
    timeframe: str = "1h",
) -> TradingRange:
    """Create a trading range from bar sequence."""
    if not bars:
        raise ValueError("Bars list cannot be empty")

    # Calculate range
    highs = [bar.high for bar in bars]
    lows = [bar.low for bar in bars]

    range_high = max(highs)
    range_low = min(lows)
    midpoint = (range_high + range_low) / 2
    range_width = range_high - range_low

    timestamp = bars[-1].timestamp

    # Create pivots
    high_pivot = Pivot(
        bar=bars[-1],
        index=len(bars) - 1,
        price=range_high,
        timestamp=timestamp,
        type=PivotType.HIGH,
        strength=5,
    )
    low_pivot = Pivot(
        bar=bars[-1],
        index=len(bars) - 1,
        price=range_low,
        timestamp=timestamp,
        type=PivotType.LOW,
        strength=5,
    )

    # Create clusters
    resistance_cluster = PriceCluster(
        pivots=[high_pivot, high_pivot],
        average_price=range_high,
        min_price=range_high,
        max_price=range_high,
        price_range=Decimal("0"),
        touch_count=2,
        cluster_type=PivotType.HIGH,
        std_deviation=Decimal("0"),
        timestamp_range=(timestamp, timestamp),
    )
    support_cluster = PriceCluster(
        pivots=[low_pivot, low_pivot],
        average_price=range_low,
        min_price=range_low,
        max_price=range_low,
        price_range=Decimal("0"),
        touch_count=2,
        cluster_type=PivotType.LOW,
        std_deviation=Decimal("0"),
        timestamp_range=(timestamp, timestamp),
    )

    # Create Creek
    creek = CreekLevel(
        price=range_low,
        absolute_low=range_low,
        min_rally_height_pct=Decimal("2.0"),
        bars_since_formation=len(bars),
        touch_count=2,
        touch_details=[],
        strength_score=50,
        strength_rating="MODERATE",
        last_test_timestamp=timestamp,
        first_test_timestamp=bars[0].timestamp,
        hold_duration=len(bars),
        confidence="MEDIUM",
        volume_trend="FLAT",
    )

    return TradingRange(
        symbol=symbol,
        timeframe=timeframe,
        support_cluster=support_cluster,
        resistance_cluster=resistance_cluster,
        support=range_low,
        resistance=range_high,
        midpoint=midpoint,
        range_width=range_width,
        range_width_pct=Decimal("0.07"),
        start_index=0,
        end_index=len(bars) - 1,
        duration=len(bars),
        creek=creek,
        status=RangeStatus.ACTIVE,
    )


# ============================================================================
# PhaseDetector Integration Tests (AC7.10)
# ============================================================================


class TestPhaseDetectorIntegration:
    """Tests for PhaseDetector integration with validation pipeline."""

    def test_phase_detector_initialization(self):
        """PhaseDetector should initialize correctly."""
        detector = PhaseDetector()

        assert detector is not None
        assert detector._cache == {}

    def test_phase_detector_detects_phase(self):
        """PhaseDetector should detect phase from bar sequence."""
        detector = PhaseDetector()
        volume_analyzer = VolumeAnalyzer()

        bars = create_bar_sequence(num_bars=50)
        trading_range = create_trading_range(bars)
        volume_analysis = volume_analyzer.analyze(bars)

        phase_info = detector.detect_phase(
            trading_range=trading_range,
            bars=bars,
            volume_analysis=volume_analysis,
        )

        assert phase_info is not None
        assert phase_info.confidence >= 0
        assert phase_info.confidence <= 100

    def test_phase_detector_caching_works(self):
        """PhaseDetector should cache results for same bar count."""
        detector = PhaseDetector()
        volume_analyzer = VolumeAnalyzer()

        bars = create_bar_sequence(num_bars=50)
        trading_range = create_trading_range(bars)
        volume_analysis = volume_analyzer.analyze(bars)

        # First call
        phase_info_1 = detector.detect_phase(
            trading_range=trading_range,
            bars=bars,
            volume_analysis=volume_analysis,
        )

        # Second call (should hit cache)
        phase_info_2 = detector.detect_phase(
            trading_range=trading_range,
            bars=bars,
            volume_analysis=volume_analysis,
        )

        # Should get same result
        assert phase_info_1.phase == phase_info_2.phase
        assert phase_info_1.confidence == phase_info_2.confidence

    def test_phase_detector_cache_invalidation(self):
        """PhaseDetector cache should invalidate when bar count changes."""
        detector = PhaseDetector()
        volume_analyzer = VolumeAnalyzer()

        bars = create_bar_sequence(num_bars=50)
        trading_range = create_trading_range(bars)
        volume_analysis = volume_analyzer.analyze(bars)

        # First call with 50 bars
        detector.detect_phase(
            trading_range=trading_range,
            bars=bars,
            volume_analysis=volume_analysis,
        )

        # Add bar
        new_bar = create_bar_sequence(num_bars=1, start_price=1.0550)[0]
        bars.append(new_bar)
        trading_range = create_trading_range(bars)
        volume_analysis = volume_analyzer.analyze(bars)

        # Second call should not hit cache (different bar count)
        phase_info = detector.detect_phase(
            trading_range=trading_range,
            bars=bars,
            volume_analysis=volume_analysis,
        )

        assert phase_info is not None


# ============================================================================
# Pattern-Phase Validation Integration Tests (AC7.10)
# ============================================================================


class TestPatternRejectionForPhaseMismatch:
    """Tests for pattern rejection when phase doesn't match."""

    def test_spring_rejected_in_wrong_phase(self):
        """Spring pattern should be rejected if not in Phase C."""
        from unittest.mock import MagicMock

        # Create a mock Spring pattern
        bar = create_bar_sequence(num_bars=1)[0]
        spring = MagicMock()
        spring.__class__.__name__ = "Spring"
        spring.spring_low = bar.low
        spring.creek_reference = bar.low + Decimal("0.0005")

        # Wrong phase (Phase B, not C)
        phase = create_phase_classification(phase=WyckoffPhase.B, confidence=85)
        trading_range = create_trading_range(create_bar_sequence(50))

        # Validate
        is_valid, reason = validate_pattern_phase_and_level(
            pattern=spring,
            detected_phase=phase,
            trading_range=trading_range,
            current_price=bar.close,
        )

        # Should be rejected
        assert is_valid is False
        assert "Phase validation failed" in reason
        assert "expected C" in reason

    def test_sos_rejected_in_wrong_phase(self):
        """SOS pattern should be rejected if not in Phase D or E."""
        from unittest.mock import MagicMock

        bar = create_bar_sequence(num_bars=1, start_price=1.0560)[0]
        sos = MagicMock()
        sos.__class__.__name__ = "SOSBreakout"
        sos.breakout_price = bar.close
        sos.ice_reference = Decimal("1.0550")

        # Wrong phase (Phase B)
        phase = create_phase_classification(phase=WyckoffPhase.B, confidence=85)
        trading_range = create_trading_range(create_bar_sequence(50))

        is_valid, reason = validate_pattern_phase_and_level(
            pattern=sos,
            detected_phase=phase,
            trading_range=trading_range,
            current_price=bar.close,
        )

        assert is_valid is False
        assert "Phase validation failed" in reason

    def test_lps_valid_in_phase_d(self):
        """LPS should be valid in Phase D (AC7.23)."""
        from unittest.mock import MagicMock

        bar = create_bar_sequence(num_bars=1, start_price=1.0555)[0]
        lps = MagicMock()
        lps.__class__.__name__ = "LPS"
        lps.pullback_low = bar.low
        lps.ice_level = Decimal("1.0550")

        # Phase D (valid for LPS)
        phase = create_phase_classification(phase=WyckoffPhase.D, confidence=85)
        bars = create_bar_sequence(50, start_price=1.0530)
        trading_range = create_trading_range(bars)
        # Adjust trading range resistance to be near LPS price
        trading_range.resistance = Decimal("1.0550")

        is_valid, reason = validate_pattern_phase_and_level(
            pattern=lps,
            detected_phase=phase,
            trading_range=trading_range,
            current_price=Decimal("1.0555"),
        )

        assert is_valid is True
        assert reason is None


# ============================================================================
# Combined Validation Pipeline Tests (AC7.24)
# ============================================================================


class TestCombinedValidationPipeline:
    """Tests for the complete phase → level → volume validation pipeline."""

    def test_pipeline_rejects_invalid_phase(self):
        """Pipeline should reject pattern with invalid phase first."""
        from unittest.mock import MagicMock

        bar = create_bar_sequence(num_bars=1)[0]
        spring = MagicMock()
        spring.__class__.__name__ = "Spring"
        spring.spring_low = bar.low
        spring.creek_reference = bar.low + Decimal("0.0005")

        # Wrong phase
        phase = create_phase_classification(phase=WyckoffPhase.D, confidence=85)
        trading_range = create_trading_range(create_bar_sequence(50))

        is_valid, reason = validate_pattern_phase_and_level(spring, phase, trading_range, bar.close)

        assert is_valid is False
        assert "Phase validation failed" in reason

    def test_pipeline_rejects_invalid_level(self):
        """Pipeline should reject pattern with invalid level after phase check."""
        from unittest.mock import MagicMock

        # Spring too far above Creek
        bar = create_bar_sequence(num_bars=1, start_price=1.0540)[0]
        spring = MagicMock()
        spring.__class__.__name__ = "Spring"
        spring.spring_low = bar.low
        spring.creek_reference = Decimal("1.0480")  # Creek is much lower

        # Right phase
        phase = create_phase_classification(phase=WyckoffPhase.C, confidence=85)
        trading_range = create_trading_range(create_bar_sequence(50))
        trading_range.support = Decimal("1.0480")
        trading_range.creek.price = Decimal("1.0480")

        is_valid, reason = validate_pattern_phase_and_level(
            spring, phase, trading_range, Decimal("1.0540")
        )

        assert is_valid is False
        assert "Level validation failed" in reason
        assert "too far above Creek" in reason

    def test_pipeline_applies_volume_adjustment(self):
        """Pipeline should apply volume-phase confidence adjustment."""
        phase = create_phase_classification(phase=WyckoffPhase.C, confidence=87)

        # Good volume for Phase C (low)
        adjusted_good = adjust_pattern_confidence_for_phase_and_volume(
            pattern_confidence=85,
            phase_classification=phase,
            volume_ratio=0.58,
        )

        # Bad volume for Phase C (high)
        adjusted_bad = adjust_pattern_confidence_for_phase_and_volume(
            pattern_confidence=85,
            phase_classification=phase,
            volume_ratio=1.4,
        )

        # Good volume should boost confidence
        # Bad volume should reduce confidence
        assert adjusted_good > adjusted_bad

    def test_full_pipeline_successful_validation(self):
        """Full pipeline should pass for valid pattern."""
        from unittest.mock import MagicMock

        bars = create_bar_sequence(50)
        trading_range = create_trading_range(bars)
        bar = bars[-1]

        # Create mock Spring at Creek level
        spring = MagicMock()
        spring.__class__.__name__ = "Spring"
        spring.spring_low = trading_range.support
        spring.creek_reference = trading_range.support

        # Phase C (correct for Spring)
        phase = create_phase_classification(phase=WyckoffPhase.C, confidence=87)

        # Validate at Creek level
        current_price = trading_range.support + Decimal("0.0002")

        is_valid, reason = validate_pattern_phase_and_level(
            spring, phase, trading_range, current_price
        )

        assert is_valid is True
        assert reason is None

        # Apply volume adjustment
        adjusted_confidence = adjust_pattern_confidence_for_phase_and_volume(
            pattern_confidence=85,
            phase_classification=phase,
            volume_ratio=0.58,  # Good for Phase C
        )

        # Confidence should be maintained or boosted
        assert adjusted_confidence >= 70  # Minimum trading threshold


# ============================================================================
# Phase Transition Tracking Tests (AC7.5, AC7.6)
# ============================================================================


class TestPhaseTransitionTracking:
    """Tests for campaign phase progression tracking."""

    def test_valid_wyckoff_progression(self):
        """Valid Wyckoff progression A -> B -> C -> D -> E should pass."""
        assert is_valid_phase_transition(None, WyckoffPhase.A) is True
        assert is_valid_phase_transition(WyckoffPhase.A, WyckoffPhase.B) is True
        assert is_valid_phase_transition(WyckoffPhase.B, WyckoffPhase.C) is True
        assert is_valid_phase_transition(WyckoffPhase.C, WyckoffPhase.D) is True
        assert is_valid_phase_transition(WyckoffPhase.D, WyckoffPhase.E) is True

    def test_schematic_1_progression(self):
        """Schematic #1 progression (B -> D, skipping C) should be valid."""
        assert is_valid_phase_transition(None, WyckoffPhase.B) is True
        assert is_valid_phase_transition(WyckoffPhase.B, WyckoffPhase.D) is True
        assert is_valid_phase_transition(WyckoffPhase.D, WyckoffPhase.E) is True

    def test_invalid_regression_blocked(self):
        """Invalid phase regressions should be blocked."""
        assert is_valid_phase_transition(WyckoffPhase.D, WyckoffPhase.A) is False
        assert is_valid_phase_transition(WyckoffPhase.E, WyckoffPhase.B) is False
        assert is_valid_phase_transition(WyckoffPhase.C, WyckoffPhase.A) is False
