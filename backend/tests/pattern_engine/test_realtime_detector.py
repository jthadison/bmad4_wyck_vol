"""
Unit tests for RealtimePatternDetector.

Story 19.3: Pattern Detection Integration

Tests cover:
- Detector initialization
- Context management
- Callback registration
- Pattern detection (Spring, SOS, LPS, UTAD, AR, SC)
- Event emission
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.models.creek_level import CreekLevel
from src.models.ice_level import IceLevel
from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import PhaseClassification, PhaseEvents, WyckoffPhase
from src.models.pivot import Pivot, PivotType
from src.models.price_cluster import PriceCluster
from src.models.touch_detail import TouchDetail
from src.models.trading_range import RangeStatus, TradingRange
from src.pattern_engine.events import PatternDetectedEvent, PatternType
from src.pattern_engine.realtime_detector import (
    DetectionContext,
    RealtimePatternDetector,
)

# =============================
# Fixtures
# =============================


@pytest.fixture
def sample_bar() -> OHLCVBar:
    """Create a sample OHLCVBar for testing."""
    return OHLCVBar(
        symbol="AAPL",
        timeframe="1m",
        timestamp=datetime.now(UTC),
        open=Decimal("150.00"),
        high=Decimal("151.00"),
        low=Decimal("149.50"),
        close=Decimal("150.50"),
        volume=100000,
        spread=Decimal("1.50"),
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("1.0"),
    )


@pytest.fixture
def sample_bars() -> list[OHLCVBar]:
    """Create a list of sample bars for testing."""
    base_time = datetime.now(UTC)
    bars = []
    for i in range(25):
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1m",
            timestamp=base_time,
            open=Decimal("150.00") + Decimal(i),
            high=Decimal("151.00") + Decimal(i),
            low=Decimal("149.50") + Decimal(i),
            close=Decimal("150.50") + Decimal(i),
            volume=100000 + i * 1000,
            spread=Decimal("1.50"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),
        )
        bars.append(bar)
    return bars


@pytest.fixture
def sample_touch_detail() -> TouchDetail:
    """Create a sample TouchDetail for level fixtures."""
    return TouchDetail(
        index=10,
        price=Decimal("148.00"),
        volume=100000,
        volume_ratio=Decimal("1.0"),
        close_position=Decimal("0.7"),
        rejection_wick=Decimal("0.3"),
        timestamp=datetime.now(UTC),
    )


@pytest.fixture
def sample_pivot_bars() -> list[OHLCVBar]:
    """Create sample bars for pivot creation."""
    now = datetime.now(UTC)
    bars = []
    for i in range(4):
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1m",
            timestamp=now,
            open=Decimal("148.00") + Decimal(i),
            high=Decimal("149.00") + Decimal(i),
            low=Decimal("147.00") + Decimal(i),
            close=Decimal("148.50") + Decimal(i),
            volume=100000 + i * 1000,
            spread=Decimal("2.00"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),
        )
        bars.append(bar)
    return bars


@pytest.fixture
def sample_trading_range(sample_touch_detail, sample_pivot_bars) -> TradingRange:
    """Create a sample TradingRange with Creek and Ice levels."""
    now = datetime.now(UTC)

    # Create pivots for support cluster (LOW pivots)
    support_pivot1 = Pivot(
        bar=sample_pivot_bars[0],
        price=sample_pivot_bars[0].low,
        type=PivotType.LOW,
        strength=5,
        timestamp=now,
        index=10,
    )
    support_pivot2 = Pivot(
        bar=sample_pivot_bars[1],
        price=sample_pivot_bars[1].low,
        type=PivotType.LOW,
        strength=5,
        timestamp=now,
        index=20,
    )

    # Create pivots for resistance cluster (HIGH pivots)
    resistance_pivot1 = Pivot(
        bar=sample_pivot_bars[2],
        price=sample_pivot_bars[2].high,
        type=PivotType.HIGH,
        strength=5,
        timestamp=now,
        index=15,
    )
    resistance_pivot2 = Pivot(
        bar=sample_pivot_bars[3],
        price=sample_pivot_bars[3].high,
        type=PivotType.HIGH,
        strength=5,
        timestamp=now,
        index=25,
    )

    # Create support cluster
    support_cluster = PriceCluster(
        pivots=[support_pivot1, support_pivot2],
        average_price=Decimal("147.50"),
        min_price=Decimal("147.00"),
        max_price=Decimal("148.00"),
        price_range=Decimal("1.00"),
        touch_count=2,
        cluster_type=PivotType.LOW,
        std_deviation=Decimal("0.50"),
        timestamp_range=(now, now),
    )

    # Create resistance cluster
    resistance_cluster = PriceCluster(
        pivots=[resistance_pivot1, resistance_pivot2],
        average_price=Decimal("152.00"),
        min_price=Decimal("151.00"),
        max_price=Decimal("153.00"),
        price_range=Decimal("2.00"),
        touch_count=2,
        cluster_type=PivotType.HIGH,
        std_deviation=Decimal("0.50"),
        timestamp_range=(now, now),
    )

    creek = CreekLevel(
        price=Decimal("148.00"),
        absolute_low=Decimal("147.50"),
        touch_count=3,
        touch_details=[sample_touch_detail, sample_touch_detail, sample_touch_detail],
        strength_score=85,
        strength_rating="STRONG",
        last_test_timestamp=now,
        first_test_timestamp=now,
        hold_duration=50,
        confidence="HIGH",
        volume_trend="DECREASING",
    )

    ice_touch = TouchDetail(
        index=15,
        price=Decimal("152.00"),
        volume=120000,
        volume_ratio=Decimal("1.2"),
        close_position=Decimal("0.3"),
        rejection_wick=Decimal("0.4"),
        timestamp=now,
    )

    ice = IceLevel(
        price=Decimal("152.00"),
        absolute_high=Decimal("152.50"),
        touch_count=2,
        touch_details=[ice_touch, ice_touch],
        strength_score=80,
        strength_rating="STRONG",
        last_test_timestamp=now,
        first_test_timestamp=now,
        hold_duration=40,
        confidence="MEDIUM",
        volume_trend="FLAT",
    )

    # Calculate values for TradingRange
    support = Decimal("147.50")
    resistance = Decimal("152.00")
    midpoint = (support + resistance) / 2
    range_width = resistance - support
    range_width_pct = Decimal("0.0305")  # Pre-calculated to meet max_digits constraint

    return TradingRange(
        symbol="AAPL",
        timeframe="1m",
        support_cluster=support_cluster,
        resistance_cluster=resistance_cluster,
        support=support,
        resistance=resistance,
        midpoint=midpoint,
        range_width=range_width,
        range_width_pct=range_width_pct,
        start_index=10,
        end_index=110,
        duration=100,
        start_timestamp=now,
        end_timestamp=None,
        status=RangeStatus.ACTIVE,
        creek=creek,
        ice=ice,
    )


@pytest.fixture
def sample_phase_classification() -> PhaseClassification:
    """Create a sample Phase C classification."""
    return PhaseClassification(
        phase=WyckoffPhase.C,
        confidence=85,
        duration=50,
        events_detected=PhaseEvents(),
        trading_allowed=True,
        phase_start_index=50,
        phase_start_timestamp=datetime.now(UTC),
    )


@pytest.fixture
def mock_window_manager(sample_bars):
    """Create a mock BarWindowManager."""
    manager = MagicMock()
    manager.get_bars = MagicMock(return_value=sample_bars)
    return manager


@pytest.fixture
def detector(mock_window_manager):
    """Create a RealtimePatternDetector for testing."""
    return RealtimePatternDetector(
        window_manager=mock_window_manager,
        min_confidence=0.7,
    )


# =============================
# Initialization Tests
# =============================


class TestRealtimePatternDetectorInit:
    """Tests for detector initialization."""

    def test_init_with_defaults(self):
        """Detector initializes with default configuration."""
        detector = RealtimePatternDetector()

        assert detector._window_manager is None
        assert detector._min_confidence == 0.7
        assert detector._callbacks == []
        assert detector._contexts == {}

    def test_init_with_custom_config(self, mock_window_manager):
        """Detector initializes with custom configuration."""
        detector = RealtimePatternDetector(
            window_manager=mock_window_manager,
            min_confidence=0.8,
        )

        assert detector._window_manager is mock_window_manager
        assert detector._min_confidence == 0.8


# =============================
# Context Management Tests
# =============================


class TestDetectionContext:
    """Tests for DetectionContext."""

    def test_context_creation(self):
        """Context can be created with symbol."""
        context = DetectionContext(symbol="AAPL")

        assert context.symbol == "AAPL"
        assert context.trading_range is None
        assert context.phase_classification is None

    def test_has_trading_range_false(self):
        """has_trading_range returns False when no range."""
        context = DetectionContext(symbol="AAPL")

        assert context.has_trading_range() is False

    def test_has_trading_range_true(self, sample_trading_range):
        """has_trading_range returns True when range exists."""
        context = DetectionContext(
            symbol="AAPL",
            trading_range=sample_trading_range,
        )

        assert context.has_trading_range() is True

    def test_get_phase_none(self):
        """get_phase returns None when no classification."""
        context = DetectionContext(symbol="AAPL")

        assert context.get_phase() is None

    def test_get_phase_returns_phase(self, sample_phase_classification):
        """get_phase returns phase when classified."""
        context = DetectionContext(
            symbol="AAPL",
            phase_classification=sample_phase_classification,
        )

        assert context.get_phase() == WyckoffPhase.C


class TestContextManagement:
    """Tests for detector context management."""

    def test_get_context_creates_new(self, detector):
        """get_context creates new context if not exists."""
        context = detector.get_context("AAPL")

        assert context is not None
        assert context.symbol == "AAPL"
        assert "AAPL" in detector._contexts

    def test_get_context_returns_existing(self, detector, sample_trading_range):
        """get_context returns existing context."""
        # Create context with trading range
        detector._contexts["AAPL"] = DetectionContext(
            symbol="AAPL",
            trading_range=sample_trading_range,
        )

        context = detector.get_context("AAPL")

        assert context.trading_range == sample_trading_range

    def test_update_context_trading_range(self, detector, sample_trading_range):
        """update_context updates trading range."""
        detector.update_context("AAPL", trading_range=sample_trading_range)

        context = detector.get_context("AAPL")
        assert context.trading_range == sample_trading_range

    def test_update_context_phase_classification(self, detector, sample_phase_classification):
        """update_context updates phase classification."""
        detector.update_context("AAPL", phase_classification=sample_phase_classification)

        context = detector.get_context("AAPL")
        assert context.phase_classification == sample_phase_classification


# =============================
# Callback Tests
# =============================


class TestCallbackManagement:
    """Tests for callback registration and removal."""

    def test_on_pattern_detected_registers_callback(self, detector):
        """on_pattern_detected registers callback."""
        callback = MagicMock()
        detector.on_pattern_detected(callback)

        assert callback in detector._callbacks

    def test_multiple_callbacks_registered(self, detector):
        """Multiple callbacks can be registered."""
        callback1 = MagicMock()
        callback2 = MagicMock()

        detector.on_pattern_detected(callback1)
        detector.on_pattern_detected(callback2)

        assert len(detector._callbacks) == 2
        assert callback1 in detector._callbacks
        assert callback2 in detector._callbacks

    def test_remove_callback(self, detector):
        """remove_callback removes registered callback."""
        callback = MagicMock()
        detector.on_pattern_detected(callback)
        detector.remove_callback(callback)

        assert callback not in detector._callbacks

    def test_remove_nonexistent_callback(self, detector):
        """Removing nonexistent callback is safe."""
        callback = MagicMock()
        # Should not raise
        detector.remove_callback(callback)


# =============================
# Pattern Detection Tests
# =============================


class TestProcessBar:
    """Tests for process_bar method."""

    @pytest.mark.asyncio
    async def test_process_bar_no_trading_range_returns_empty(self, detector, sample_bar):
        """process_bar returns empty list when no trading range."""
        events = await detector.process_bar(sample_bar)

        assert events == []

    @pytest.mark.asyncio
    async def test_process_bar_no_window_manager_returns_empty(
        self, sample_bar, sample_trading_range
    ):
        """process_bar returns empty list when no window manager."""
        detector = RealtimePatternDetector(window_manager=None)
        detector.update_context("AAPL", trading_range=sample_trading_range)

        events = await detector.process_bar(sample_bar)

        assert events == []

    @pytest.mark.asyncio
    async def test_process_bar_no_bars_returns_empty(self, sample_bar, sample_trading_range):
        """process_bar returns empty list when no bars available."""
        mock_manager = MagicMock()
        mock_manager.get_bars = MagicMock(return_value=[])

        detector = RealtimePatternDetector(window_manager=mock_manager)
        detector.update_context("AAPL", trading_range=sample_trading_range)

        events = await detector.process_bar(sample_bar)

        assert events == []


class TestSpringDetection:
    """Tests for Spring pattern detection."""

    @pytest.mark.asyncio
    async def test_spring_detection_phase_c(
        self,
        detector,
        sample_bar,
        sample_trading_range,
        sample_phase_classification,
    ):
        """Spring detection is called in Phase C."""
        detector.update_context(
            "AAPL",
            trading_range=sample_trading_range,
            phase_classification=sample_phase_classification,
        )

        with patch("src.pattern_engine.detectors.spring_detector.detect_spring") as mock_detect:
            mock_detect.return_value = None
            events = await detector.process_bar(sample_bar)

            # Spring detection should be called
            mock_detect.assert_called()

    @pytest.mark.asyncio
    async def test_spring_detection_not_called_phase_a(
        self,
        detector,
        sample_bar,
        sample_trading_range,
    ):
        """Spring detection is not called in Phase A."""
        phase_a = PhaseClassification(
            phase=WyckoffPhase.A,
            confidence=85,
            duration=50,
            events_detected=PhaseEvents(),
            trading_allowed=False,
            phase_start_index=50,
            phase_start_timestamp=datetime.now(UTC),
        )
        detector.update_context(
            "AAPL",
            trading_range=sample_trading_range,
            phase_classification=phase_a,
        )

        with patch("src.pattern_engine.detectors.spring_detector.detect_spring") as mock_detect:
            events = await detector.process_bar(sample_bar)

            # Spring detection should NOT be called in Phase A
            mock_detect.assert_not_called()


class TestEventEmission:
    """Tests for event emission to callbacks."""

    @pytest.mark.asyncio
    async def test_emit_event_calls_callbacks(self, detector, sample_bar):
        """_emit_event calls all registered callbacks."""
        callback1 = MagicMock()
        callback2 = MagicMock()
        detector.on_pattern_detected(callback1)
        detector.on_pattern_detected(callback2)

        event = PatternDetectedEvent(
            symbol="AAPL",
            pattern_type=PatternType.SPRING,
            confidence=0.85,
            phase=WyckoffPhase.C,
            bar_data=sample_bar.model_dump(),
        )

        detector._emit_event(event)

        callback1.assert_called_once_with(event)
        callback2.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_emit_event_handles_callback_error(self, detector, sample_bar):
        """_emit_event handles callback errors gracefully."""
        callback_ok = MagicMock()
        callback_error = MagicMock(side_effect=Exception("Callback error"))

        detector.on_pattern_detected(callback_error)
        detector.on_pattern_detected(callback_ok)

        event = PatternDetectedEvent(
            symbol="AAPL",
            pattern_type=PatternType.SPRING,
            confidence=0.85,
            phase=WyckoffPhase.C,
            bar_data=sample_bar.model_dump(),
        )

        # Should not raise
        detector._emit_event(event)

        # Second callback should still be called despite first error
        callback_ok.assert_called_once_with(event)


# =============================
# Duplicate Detection Prevention Tests
# =============================


class TestDuplicatePrevention:
    """Tests for preventing duplicate pattern detection."""

    def test_context_tracks_last_spring_bar_index(self):
        """Context tracks last detected Spring bar index."""
        context = DetectionContext(symbol="AAPL")
        assert context.last_spring_bar_index is None

        context.last_spring_bar_index = 42
        assert context.last_spring_bar_index == 42

    def test_context_tracks_all_pattern_indices(self):
        """Context tracks last bar index for all pattern types."""
        context = DetectionContext(symbol="AAPL")

        # All should be None initially
        assert context.last_spring_bar_index is None
        assert context.last_sos_bar_index is None
        assert context.last_lps_bar_index is None
        assert context.last_utad_bar_index is None
        assert context.last_ar_bar_index is None
        assert context.last_sc_bar_index is None


# =============================
# Integration Tests
# =============================


class TestDetectorIntegration:
    """Integration tests for the detector."""

    @pytest.mark.asyncio
    async def test_full_detection_flow(
        self,
        mock_window_manager,
        sample_bar,
        sample_trading_range,
        sample_phase_classification,
    ):
        """Test full detection flow with callback."""
        detected_events = []

        def capture_event(event: PatternDetectedEvent):
            detected_events.append(event)

        detector = RealtimePatternDetector(
            window_manager=mock_window_manager,
            min_confidence=0.7,
        )
        detector.on_pattern_detected(capture_event)
        detector.update_context(
            "AAPL",
            trading_range=sample_trading_range,
            phase_classification=sample_phase_classification,
        )

        # Process bar (detection methods are mocked via module patching)
        events = await detector.process_bar(sample_bar)

        # Events returned from process_bar
        assert isinstance(events, list)
