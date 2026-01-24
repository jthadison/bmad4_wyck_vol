"""
Comparison tests between backtest and realtime pattern detection.

Story 19.3: Pattern Detection Integration

These tests verify that the RealtimePatternDetector calls the SAME detection
functions used by the backtesting engine, ensuring consistency between
real-time and historical analysis.

The tests verify:
1. Same function calls are made for each pattern type
2. Same parameters are passed to detection functions
3. Same results would be produced given identical inputs
"""

from datetime import UTC, datetime, timedelta
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
from src.pattern_engine.realtime_detector import RealtimePatternDetector

# =============================
# Fixtures
# =============================


@pytest.fixture
def historical_bars() -> list[OHLCVBar]:
    """Create historical bar data for comparison testing."""
    base_time = datetime.now(UTC) - timedelta(hours=2)
    bars = []

    # Create 100 bars of historical data
    for i in range(100):
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1m",
            timestamp=base_time + timedelta(minutes=i),
            open=Decimal("150.00") + Decimal("0.10") * i,
            high=Decimal("151.00") + Decimal("0.10") * i,
            low=Decimal("149.00") + Decimal("0.10") * i,
            close=Decimal("150.50") + Decimal("0.10") * i,
            volume=100000 + i * 500,
            spread=Decimal("2.00"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),
        )
        bars.append(bar)

    return bars


@pytest.fixture
def pivot_bars_for_range() -> list[OHLCVBar]:
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
def trading_range_with_levels(pivot_bars_for_range) -> TradingRange:
    """Create a trading range with Creek and Ice levels."""
    now = datetime.now(UTC)

    # Create pivots for support cluster (LOW pivots)
    support_pivot1 = Pivot(
        bar=pivot_bars_for_range[0],
        price=pivot_bars_for_range[0].low,
        type=PivotType.LOW,
        strength=5,
        timestamp=now,
        index=10,
    )
    support_pivot2 = Pivot(
        bar=pivot_bars_for_range[1],
        price=pivot_bars_for_range[1].low,
        type=PivotType.LOW,
        strength=5,
        timestamp=now,
        index=20,
    )

    # Create pivots for resistance cluster (HIGH pivots)
    resistance_pivot1 = Pivot(
        bar=pivot_bars_for_range[2],
        price=pivot_bars_for_range[2].high,
        type=PivotType.HIGH,
        strength=5,
        timestamp=now,
        index=15,
    )
    resistance_pivot2 = Pivot(
        bar=pivot_bars_for_range[3],
        price=pivot_bars_for_range[3].high,
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
        average_price=Decimal("160.00"),
        min_price=Decimal("159.00"),
        max_price=Decimal("161.00"),
        price_range=Decimal("2.00"),
        touch_count=2,
        cluster_type=PivotType.HIGH,
        std_deviation=Decimal("0.50"),
        timestamp_range=(now, now),
    )

    # Create TouchDetails for Creek
    touch_detail = TouchDetail(
        index=10,
        price=Decimal("149.00"),
        volume=100000,
        volume_ratio=Decimal("1.0"),
        close_position=Decimal("0.7"),
        rejection_wick=Decimal("0.3"),
        timestamp=now,
    )

    creek = CreekLevel(
        price=Decimal("149.00"),
        absolute_low=Decimal("148.50"),
        touch_count=3,
        touch_details=[touch_detail, touch_detail, touch_detail],
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
        price=Decimal("160.00"),
        volume=120000,
        volume_ratio=Decimal("1.2"),
        close_position=Decimal("0.3"),
        rejection_wick=Decimal("0.4"),
        timestamp=now,
    )

    ice = IceLevel(
        price=Decimal("160.00"),
        absolute_high=Decimal("160.50"),
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
    support = Decimal("149.00")
    resistance = Decimal("160.00")
    midpoint = (support + resistance) / 2
    range_width = resistance - support
    range_width_pct = Decimal("0.0738")  # Pre-calculated to meet max_digits constraint

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
        start_timestamp=now - timedelta(hours=2),
        end_timestamp=None,
        status=RangeStatus.ACTIVE,
        creek=creek,
        ice=ice,
    )


@pytest.fixture
def phase_c_classification() -> PhaseClassification:
    """Create Phase C classification."""
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
def phase_d_classification() -> PhaseClassification:
    """Create Phase D classification."""
    return PhaseClassification(
        phase=WyckoffPhase.D,
        confidence=85,
        duration=20,
        events_detected=PhaseEvents(),
        trading_allowed=True,
        phase_start_index=70,
        phase_start_timestamp=datetime.now(UTC),
    )


# =============================
# Spring Detection Comparison
# =============================


class TestSpringDetectionConsistency:
    """Verify Spring detection uses same function as backtesting."""

    @pytest.mark.asyncio
    async def test_spring_uses_detect_spring_function(
        self,
        historical_bars,
        trading_range_with_levels,
        phase_c_classification,
    ):
        """RealtimePatternDetector calls detect_spring from spring_detector module."""
        mock_manager = MagicMock()
        mock_manager.get_bars = MagicMock(return_value=historical_bars)

        detector = RealtimePatternDetector(window_manager=mock_manager)
        detector.update_context(
            "AAPL",
            trading_range=trading_range_with_levels,
            phase_classification=phase_c_classification,
        )

        current_bar = historical_bars[-1]

        with patch("src.pattern_engine.detectors.spring_detector.detect_spring") as mock_detect:
            mock_detect.return_value = None

            await detector.process_bar(current_bar)

            # Verify detect_spring was called
            mock_detect.assert_called_once()

            # Verify trading_range was passed
            call_kwargs = mock_detect.call_args.kwargs
            assert call_kwargs["trading_range"] == trading_range_with_levels
            assert call_kwargs["phase"] == WyckoffPhase.C
            assert call_kwargs["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_spring_detection_same_parameters_as_backtest(
        self,
        historical_bars,
        trading_range_with_levels,
        phase_c_classification,
    ):
        """Spring detection parameters match what backtesting uses."""
        mock_manager = MagicMock()
        mock_manager.get_bars = MagicMock(return_value=historical_bars)

        detector = RealtimePatternDetector(window_manager=mock_manager)
        detector.update_context(
            "AAPL",
            trading_range=trading_range_with_levels,
            phase_classification=phase_c_classification,
        )

        current_bar = historical_bars[-1]

        with patch("src.pattern_engine.detectors.spring_detector.detect_spring") as mock_detect:
            mock_detect.return_value = None

            await detector.process_bar(current_bar)

            # Verify bars list is passed (same data backtesting would use)
            call_kwargs = mock_detect.call_args.kwargs
            assert "bars" in call_kwargs
            assert call_kwargs["bars"] == historical_bars


# =============================
# SOS Detection Comparison
# =============================


class TestSOSDetectionConsistency:
    """Verify SOS detection uses same function as backtesting."""

    @pytest.mark.asyncio
    async def test_sos_uses_detect_sos_breakout_function(
        self,
        historical_bars,
        trading_range_with_levels,
        phase_c_classification,
    ):
        """RealtimePatternDetector calls detect_sos_breakout from sos_detector module."""
        mock_manager = MagicMock()
        mock_manager.get_bars = MagicMock(return_value=historical_bars)

        detector = RealtimePatternDetector(window_manager=mock_manager)
        detector.update_context(
            "AAPL",
            trading_range=trading_range_with_levels,
            phase_classification=phase_c_classification,
        )

        current_bar = historical_bars[-1]

        with patch(
            "src.pattern_engine.detectors.spring_detector.detect_spring"
        ) as mock_spring, patch(
            "src.pattern_engine.detectors.sos_detector.detect_sos_breakout"
        ) as mock_sos:
            mock_spring.return_value = None
            mock_sos.return_value = None

            await detector.process_bar(current_bar)

            # Verify detect_sos_breakout was called
            mock_sos.assert_called_once()

            # Verify trading_range was passed
            call_kwargs = mock_sos.call_args.kwargs
            assert call_kwargs["trading_range"] == trading_range_with_levels


# =============================
# UTAD Detection Comparison
# =============================


class TestUTADDetectionConsistency:
    """Verify UTAD detection uses same class as backtesting."""

    @pytest.mark.asyncio
    async def test_utad_uses_utad_detector_class(
        self,
        historical_bars,
        trading_range_with_levels,
        phase_c_classification,
    ):
        """RealtimePatternDetector uses UTADDetector class."""
        mock_manager = MagicMock()
        mock_manager.get_bars = MagicMock(return_value=historical_bars)

        detector = RealtimePatternDetector(window_manager=mock_manager)
        detector.update_context(
            "AAPL",
            trading_range=trading_range_with_levels,
            phase_classification=phase_c_classification,
        )

        current_bar = historical_bars[-1]

        with patch(
            "src.pattern_engine.detectors.spring_detector.detect_spring"
        ) as mock_spring, patch(
            "src.pattern_engine.detectors.sos_detector.detect_sos_breakout"
        ) as mock_sos, patch(
            "src.pattern_engine.detectors.utad_detector.UTADDetector"
        ) as MockUTADDetector:
            mock_spring.return_value = None
            mock_sos.return_value = None

            mock_utad_instance = MagicMock()
            mock_utad_instance.detect_utad = MagicMock(return_value=None)
            MockUTADDetector.return_value = mock_utad_instance

            await detector.process_bar(current_bar)

            # Verify UTADDetector was instantiated
            MockUTADDetector.assert_called_once()

            # Verify detect_utad was called with correct parameters
            mock_utad_instance.detect_utad.assert_called_once()
            call_kwargs = mock_utad_instance.detect_utad.call_args.kwargs
            assert call_kwargs["trading_range"] == trading_range_with_levels
            assert call_kwargs["bars"] == historical_bars


# =============================
# SC Detection Comparison
# =============================


class TestSCDetectionConsistency:
    """Verify SC detection uses same function as backtesting."""

    @pytest.mark.asyncio
    async def test_sc_uses_detect_selling_climax_function(
        self,
        historical_bars,
        trading_range_with_levels,
    ):
        """RealtimePatternDetector calls detect_selling_climax from phase_detector module."""
        # Use Phase A or no phase for SC detection
        phase_none = PhaseClassification(
            phase=None,
            confidence=0,
            duration=0,
            events_detected=PhaseEvents(),
            trading_allowed=False,
            phase_start_index=0,
            phase_start_timestamp=datetime.now(UTC),
        )

        mock_manager = MagicMock()
        mock_manager.get_bars = MagicMock(return_value=historical_bars)

        detector = RealtimePatternDetector(window_manager=mock_manager)
        detector.update_context(
            "AAPL",
            trading_range=trading_range_with_levels,
            phase_classification=phase_none,
        )

        current_bar = historical_bars[-1]

        with patch("src.pattern_engine.phase_detector.detect_selling_climax") as mock_sc, patch(
            "src.pattern_engine.detectors.utad_detector.UTADDetector"
        ) as MockUTAD:
            mock_sc.return_value = None
            mock_utad_instance = MagicMock()
            mock_utad_instance.detect_utad = MagicMock(return_value=None)
            MockUTAD.return_value = mock_utad_instance

            await detector.process_bar(current_bar)

            # Verify detect_selling_climax was called
            mock_sc.assert_called_once()


# =============================
# Deterministic Results Tests
# =============================


class TestDeterministicResults:
    """Verify same inputs produce same outputs."""

    @pytest.mark.asyncio
    async def test_same_bars_same_result(
        self,
        historical_bars,
        trading_range_with_levels,
        phase_c_classification,
    ):
        """Processing same bars multiple times produces same result."""
        mock_manager = MagicMock()
        mock_manager.get_bars = MagicMock(return_value=historical_bars)

        detector = RealtimePatternDetector(window_manager=mock_manager)
        detector.update_context(
            "AAPL",
            trading_range=trading_range_with_levels,
            phase_classification=phase_c_classification,
        )

        current_bar = historical_bars[-1]

        # Process same bar twice
        events1 = await detector.process_bar(current_bar)
        events2 = await detector.process_bar(current_bar)

        # Results should be consistent (both empty or both have same patterns)
        assert len(events1) == len(events2)

        for e1, e2 in zip(events1, events2, strict=False):
            assert e1.pattern_type == e2.pattern_type
            assert e1.symbol == e2.symbol
            assert e1.confidence == e2.confidence

    @pytest.mark.asyncio
    async def test_two_detectors_same_result(
        self,
        historical_bars,
        trading_range_with_levels,
        phase_c_classification,
    ):
        """Two detector instances produce same results for same inputs."""
        mock_manager = MagicMock()
        mock_manager.get_bars = MagicMock(return_value=historical_bars)

        detector1 = RealtimePatternDetector(window_manager=mock_manager)
        detector1.update_context(
            "AAPL",
            trading_range=trading_range_with_levels,
            phase_classification=phase_c_classification,
        )

        detector2 = RealtimePatternDetector(window_manager=mock_manager)
        detector2.update_context(
            "AAPL",
            trading_range=trading_range_with_levels,
            phase_classification=phase_c_classification,
        )

        current_bar = historical_bars[-1]

        events1 = await detector1.process_bar(current_bar)
        events2 = await detector2.process_bar(current_bar)

        # Results should be identical
        assert len(events1) == len(events2)


# =============================
# Module Import Verification
# =============================


class TestModuleImports:
    """Verify correct modules are imported for detection functions."""

    def test_imports_spring_detector(self):
        """Spring detector is importable from correct module."""
        from src.pattern_engine.detectors.spring_detector import detect_spring

        assert callable(detect_spring)

    def test_imports_sos_detector(self):
        """SOS detector is importable from correct module."""
        from src.pattern_engine.detectors.sos_detector import detect_sos_breakout

        assert callable(detect_sos_breakout)

    def test_imports_lps_detector(self):
        """LPS detector is importable from correct module."""
        from src.pattern_engine.detectors.lps_detector import detect_lps

        assert callable(detect_lps)

    def test_imports_utad_detector(self):
        """UTAD detector is importable from correct module."""
        from src.pattern_engine.detectors.utad_detector import UTADDetector

        assert UTADDetector is not None

    def test_imports_ar_detector(self):
        """AR detector is importable from correct module."""
        from src.pattern_engine.detectors.ar_detector import (
            detect_ar_after_sc,
            detect_ar_after_spring,
        )

        assert callable(detect_ar_after_spring)
        assert callable(detect_ar_after_sc)

    def test_imports_sc_detector(self):
        """SC detector is importable from correct module."""
        from src.pattern_engine.phase_detector import detect_selling_climax

        assert callable(detect_selling_climax)
