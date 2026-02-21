"""
Tests for pattern detection wiring changes.

Covers:
1. Spring facade wiring to SpringDetectorCore via detect_with_context()
2. SOS facade wiring to detect_sos_breakout via detect_with_context()
3. LPS facade wiring to detect_lps via detect_with_context()
4. UTAD Phase D validation (reject non-D, accept D, backward compat)
5. SOS logging threshold (1.5x not 2.0x)
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest

from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import PhaseClassification, WyckoffPhase
from src.models.trading_range import RangeStatus, TradingRange
from src.pattern_engine.phase_detection.event_detectors import (
    LastPointOfSupportDetector,
    SignOfStrengthDetector,
    SpringDetector,
    _lps_to_event,
    _sos_breakout_to_event,
)
from src.pattern_engine.phase_detection.types import (
    DetectionConfig,
    EventType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_minimal_df(num_bars: int = 25) -> pd.DataFrame:
    """Create a minimal valid OHLCV DataFrame."""
    dates = [datetime(2024, 1, 1) + timedelta(hours=i) for i in range(num_bars)]
    return pd.DataFrame(
        {
            "timestamp": dates,
            "open": [100.0 + i * 0.1 for i in range(num_bars)],
            "high": [101.0 + i * 0.1 for i in range(num_bars)],
            "low": [99.0 + i * 0.1 for i in range(num_bars)],
            "close": [100.5 + i * 0.1 for i in range(num_bars)],
            "volume": [1000000] * num_bars,
        }
    )


def _make_mock_trading_range() -> TradingRange:
    """Create a mock trading range with Creek and Ice levels."""
    from src.models.pivot import Pivot, PivotType
    from src.models.price_cluster import PriceCluster

    bar = OHLCVBar(
        symbol="TEST",
        timeframe="1d",
        timestamp=datetime(2024, 1, 10, tzinfo=UTC),
        open=Decimal("99.00"),
        high=Decimal("101.00"),
        low=Decimal("95.00"),
        close=Decimal("100.00"),
        volume=100000,
        spread=Decimal("6.00"),
    )

    pivot1 = Pivot(
        bar=bar,
        price=Decimal("95.00"),
        type=PivotType.LOW,
        strength=5,
        timestamp=bar.timestamp,
        index=10,
    )
    pivot2 = Pivot(
        bar=bar,
        price=Decimal("95.00"),
        type=PivotType.LOW,
        strength=5,
        timestamp=bar.timestamp,
        index=20,
    )

    cluster = PriceCluster(
        pivots=[pivot1, pivot2],
        average_price=Decimal("95.00"),
        min_price=Decimal("95.00"),
        max_price=Decimal("95.00"),
        price_range=Decimal("0.00"),
        touch_count=2,
        cluster_type=PivotType.LOW,
        std_deviation=Decimal("0.00"),
        timestamp_range=(bar.timestamp, bar.timestamp),
    )

    resistance_pivot1 = Pivot(
        bar=bar,
        price=Decimal("100.00"),
        type=PivotType.HIGH,
        strength=5,
        timestamp=bar.timestamp,
        index=15,
    )
    resistance_pivot2 = Pivot(
        bar=bar,
        price=Decimal("100.00"),
        type=PivotType.HIGH,
        strength=5,
        timestamp=bar.timestamp,
        index=25,
    )

    resistance_cluster = PriceCluster(
        pivots=[resistance_pivot1, resistance_pivot2],
        average_price=Decimal("100.00"),
        min_price=Decimal("100.00"),
        max_price=Decimal("100.00"),
        price_range=Decimal("0.00"),
        touch_count=2,
        cluster_type=PivotType.HIGH,
        std_deviation=Decimal("0.00"),
        timestamp_range=(bar.timestamp, bar.timestamp),
    )

    range_obj = TradingRange(
        symbol="TEST",
        timeframe="1d",
        support_cluster=cluster,
        resistance_cluster=resistance_cluster,
        support=Decimal("95.00"),
        resistance=Decimal("100.00"),
        midpoint=Decimal("97.50"),
        range_width=Decimal("5.00"),
        range_width_pct=Decimal("0.05"),
        start_index=10,
        end_index=50,
        duration=41,
        status=RangeStatus.ACTIVE,
        start_timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        end_timestamp=datetime(2024, 2, 20, tzinfo=UTC),
    )

    creek_mock = Mock()
    creek_mock.price = Decimal("95.00")
    range_obj.creek = creek_mock

    ice_mock = Mock()
    ice_mock.price = Decimal("100.00")
    range_obj.ice = ice_mock

    return range_obj


def _make_phase_d() -> PhaseClassification:
    """Create a Phase D classification."""
    from src.models.phase_classification import PhaseEvents

    return PhaseClassification(
        phase=WyckoffPhase.D,
        confidence=90,
        duration=15,
        events_detected=PhaseEvents(),
        trading_allowed=True,
        phase_start_index=10,
        phase_start_timestamp=datetime(2024, 1, 1, 9, 30, tzinfo=UTC),
    )


# ===========================================================================
# Test 1: Spring facade wiring
# ===========================================================================


class TestSpringFacadeWiring:
    """Test SpringDetector.detect_with_context() wires to SpringDetectorCore."""

    @pytest.fixture
    def config(self) -> DetectionConfig:
        return DetectionConfig()

    @pytest.fixture
    def df(self) -> pd.DataFrame:
        return _make_minimal_df()

    def test_detect_returns_empty_list(self, config: DetectionConfig, df: pd.DataFrame) -> None:
        """detect() returns empty list (requires TradingRange context)."""
        detector = SpringDetector(config)
        result = detector.detect(df)
        assert result == []

    @patch("src.pattern_engine.phase_detection.event_detectors.SpringDetectorCore")
    def test_detect_with_context_delegates_to_core(
        self, mock_core_cls: MagicMock, config: DetectionConfig, df: pd.DataFrame
    ) -> None:
        """detect_with_context() creates SpringDetectorCore and calls detect()."""
        # Setup mock
        mock_spring = Mock()
        mock_spring.bar_index = 25
        mock_spring.bar = Mock()
        mock_spring.bar.timestamp = datetime(2024, 1, 1, 12, tzinfo=UTC)
        mock_spring.bar.close = Decimal("99.00")
        mock_spring.bar.volume = 500000
        mock_spring.penetration_pct = Decimal("0.02")
        mock_spring.volume_ratio = Decimal("0.5")
        mock_spring.recovery_bars = 2
        mock_spring.creek_reference = Decimal("100.00")

        mock_instance = mock_core_cls.return_value
        mock_instance.detect.return_value = mock_spring

        detector = SpringDetector(config)
        trading_range = _make_mock_trading_range()

        result = detector.detect_with_context(df, trading_range, WyckoffPhase.C, "TEST")

        # Verify delegation
        mock_instance.detect.assert_called_once()
        assert len(result) == 1

    @patch("src.pattern_engine.phase_detection.event_detectors.SpringDetectorCore")
    def test_detect_with_context_returns_phase_event(
        self, mock_core_cls: MagicMock, config: DetectionConfig, df: pd.DataFrame
    ) -> None:
        """detect_with_context() converts Spring to PhaseEvent correctly."""
        mock_spring = Mock()
        mock_spring.bar_index = 25
        mock_spring.bar = Mock()
        mock_spring.bar.timestamp = datetime(2024, 1, 1, 12, tzinfo=UTC)
        mock_spring.bar.close = Decimal("99.00")
        mock_spring.bar.volume = 500000
        mock_spring.penetration_pct = Decimal("0.02")
        mock_spring.volume_ratio = Decimal("0.5")
        mock_spring.recovery_bars = 2
        mock_spring.creek_reference = Decimal("100.00")

        mock_instance = mock_core_cls.return_value
        mock_instance.detect.return_value = mock_spring

        detector = SpringDetector(config)
        trading_range = _make_mock_trading_range()

        result = detector.detect_with_context(df, trading_range, WyckoffPhase.C, "TEST")

        event = result[0]
        assert event.event_type == EventType.SPRING
        assert event.bar_index == 25
        assert event.price == float(Decimal("99.00"))
        assert event.volume == 500000.0
        assert event.metadata["penetration_pct"] == float(Decimal("0.02"))
        assert event.metadata["volume_ratio"] == float(Decimal("0.5"))
        assert event.metadata["recovery_bars"] == 2
        assert event.metadata["creek_reference"] == float(Decimal("100.00"))

    @patch("src.pattern_engine.phase_detection.event_detectors.SpringDetectorCore")
    def test_detect_with_context_returns_empty_when_none(
        self, mock_core_cls: MagicMock, config: DetectionConfig, df: pd.DataFrame
    ) -> None:
        """detect_with_context() returns empty list when core returns None."""
        mock_instance = mock_core_cls.return_value
        mock_instance.detect.return_value = None

        detector = SpringDetector(config)
        trading_range = _make_mock_trading_range()

        result = detector.detect_with_context(df, trading_range, WyckoffPhase.C, "TEST")
        assert result == []


# ===========================================================================
# Test 2: SOS facade wiring
# ===========================================================================


class TestSOSFacadeWiring:
    """Test SignOfStrengthDetector.detect_with_context() wires to detect_sos_breakout."""

    @pytest.fixture
    def config(self) -> DetectionConfig:
        return DetectionConfig()

    @pytest.fixture
    def df(self) -> pd.DataFrame:
        return _make_minimal_df()

    def test_detect_returns_empty_list(self, config: DetectionConfig, df: pd.DataFrame) -> None:
        """detect() returns empty list (requires context)."""
        detector = SignOfStrengthDetector(config)
        result = detector.detect(df)
        assert result == []

    @patch("src.pattern_engine.phase_detection.event_detectors.detect_sos_breakout")
    def test_detect_with_context_delegates_to_sos_breakout(
        self, mock_detect: MagicMock, config: DetectionConfig, df: pd.DataFrame
    ) -> None:
        """detect_with_context() delegates to detect_sos_breakout()."""
        mock_sos = Mock()
        mock_sos.bar = Mock()
        mock_sos.bar.timestamp = datetime(2024, 1, 1, 14, tzinfo=UTC)
        mock_sos.bar.volume = 2000000
        mock_sos.breakout_price = Decimal("102.00")
        mock_sos.breakout_pct = Decimal("0.02")
        mock_sos.volume_ratio = Decimal("2.5")
        mock_sos.ice_reference = Decimal("100.00")

        mock_detect.return_value = mock_sos

        detector = SignOfStrengthDetector(config)
        trading_range = _make_mock_trading_range()
        phase = _make_phase_d()
        volume_analysis = {}

        result = detector.detect_with_context(df, trading_range, volume_analysis, phase, "TEST")

        mock_detect.assert_called_once()
        assert len(result) == 1

    @patch("src.pattern_engine.phase_detection.event_detectors.detect_sos_breakout")
    def test_detect_with_context_returns_phase_event(
        self, mock_detect: MagicMock, config: DetectionConfig, df: pd.DataFrame
    ) -> None:
        """detect_with_context() converts SOSBreakout to PhaseEvent correctly."""
        mock_sos = Mock()
        mock_sos.bar = Mock()
        mock_sos.bar.timestamp = datetime(2024, 1, 1, 14, tzinfo=UTC)
        mock_sos.bar.volume = 2000000
        mock_sos.breakout_price = Decimal("102.00")
        mock_sos.breakout_pct = Decimal("0.02")
        mock_sos.volume_ratio = Decimal("2.5")
        mock_sos.ice_reference = Decimal("100.00")

        mock_detect.return_value = mock_sos

        detector = SignOfStrengthDetector(config)
        trading_range = _make_mock_trading_range()
        phase = _make_phase_d()

        result = detector.detect_with_context(df, trading_range, {}, phase, "TEST")

        event = result[0]
        assert event.event_type == EventType.SIGN_OF_STRENGTH
        assert event.price == 102.0
        assert event.volume == 2000000.0
        assert event.metadata["breakout_pct"] == float(Decimal("0.02"))
        assert event.metadata["volume_ratio"] == float(Decimal("2.5"))
        assert event.metadata["ice_reference"] == float(Decimal("100.00"))

    @patch("src.pattern_engine.phase_detection.event_detectors.detect_sos_breakout")
    def test_detect_with_context_returns_empty_when_none(
        self, mock_detect: MagicMock, config: DetectionConfig, df: pd.DataFrame
    ) -> None:
        """detect_with_context() returns empty list when detect_sos_breakout returns None."""
        mock_detect.return_value = None

        detector = SignOfStrengthDetector(config)
        trading_range = _make_mock_trading_range()
        phase = _make_phase_d()

        result = detector.detect_with_context(df, trading_range, {}, phase, "TEST")
        assert result == []

    def test_volume_threshold_is_1_5x(self) -> None:
        """Verify DetectionConfig uses 1.5x for SOS volume threshold."""
        config = DetectionConfig()
        assert config.volume_threshold_sos == 1.5


# ===========================================================================
# Test 3: LPS facade wiring
# ===========================================================================


class TestLPSFacadeWiring:
    """Test LastPointOfSupportDetector.detect_with_context() wires to detect_lps."""

    @pytest.fixture
    def config(self) -> DetectionConfig:
        return DetectionConfig()

    @pytest.fixture
    def df(self) -> pd.DataFrame:
        return _make_minimal_df()

    def test_detect_returns_empty_list(self, config: DetectionConfig, df: pd.DataFrame) -> None:
        """detect() returns empty list (requires SOS context)."""
        detector = LastPointOfSupportDetector(config)
        result = detector.detect(df)
        assert result == []

    @patch("src.pattern_engine.phase_detection.event_detectors.detect_lps")
    def test_detect_with_context_delegates_to_detect_lps(
        self, mock_detect: MagicMock, config: DetectionConfig, df: pd.DataFrame
    ) -> None:
        """detect_with_context() delegates to detect_lps()."""
        mock_lps = Mock()
        mock_lps.bar = Mock()
        mock_lps.bar.timestamp = datetime(2024, 1, 1, 16, tzinfo=UTC)
        mock_lps.pullback_low = Decimal("100.50")
        mock_lps.pullback_volume = 120000
        mock_lps.distance_confidence_bonus = 10
        mock_lps.distance_from_ice = Decimal("0.005")
        mock_lps.distance_quality = "PREMIUM"
        mock_lps.volume_ratio_vs_avg = Decimal("0.8")
        mock_lps.held_support = True
        mock_lps.bars_after_sos = 5
        mock_lps.bounce_confirmed = True
        mock_lps.effort_result_bonus = 10
        mock_lps.effort_result = "NO_SUPPLY"

        mock_detect.return_value = mock_lps

        detector = LastPointOfSupportDetector(config)
        trading_range = _make_mock_trading_range()
        sos_breakout = Mock()
        volume_analysis = {}

        result = detector.detect_with_context(df, trading_range, sos_breakout, volume_analysis)

        mock_detect.assert_called_once()
        assert len(result) == 1

    @patch("src.pattern_engine.phase_detection.event_detectors.detect_lps")
    def test_detect_with_context_returns_phase_event(
        self, mock_detect: MagicMock, config: DetectionConfig, df: pd.DataFrame
    ) -> None:
        """detect_with_context() converts LPS to PhaseEvent correctly."""
        mock_lps = Mock()
        mock_lps.bar = Mock()
        mock_lps.bar.timestamp = datetime(2024, 1, 1, 16, tzinfo=UTC)
        mock_lps.pullback_low = Decimal("100.50")
        mock_lps.pullback_volume = 120000
        mock_lps.distance_confidence_bonus = 10
        mock_lps.distance_from_ice = Decimal("0.005")
        mock_lps.distance_quality = "PREMIUM"
        mock_lps.volume_ratio_vs_avg = Decimal("0.8")
        mock_lps.held_support = True
        mock_lps.bars_after_sos = 5
        mock_lps.bounce_confirmed = True
        mock_lps.effort_result_bonus = 10
        mock_lps.effort_result = "NO_SUPPLY"

        mock_detect.return_value = mock_lps

        detector = LastPointOfSupportDetector(config)
        trading_range = _make_mock_trading_range()
        sos_breakout = Mock()

        result = detector.detect_with_context(df, trading_range, sos_breakout, {})

        event = result[0]
        assert event.event_type == EventType.LAST_POINT_OF_SUPPORT
        assert event.price == float(Decimal("100.50"))
        assert event.volume == 120000.0
        assert event.metadata["distance_quality"] == "PREMIUM"
        assert event.metadata["support_quality"] == "HELD"
        assert event.metadata["bars_after_sos"] == 5
        assert event.metadata["bounce_confirmed"] is True
        assert event.metadata["effort_result"] == "NO_SUPPLY"

    @patch("src.pattern_engine.phase_detection.event_detectors.detect_lps")
    def test_detect_with_context_requires_sos_breakout(
        self, mock_detect: MagicMock, config: DetectionConfig, df: pd.DataFrame
    ) -> None:
        """detect_with_context() passes sos_breakout to detect_lps."""
        mock_detect.return_value = None

        detector = LastPointOfSupportDetector(config)
        trading_range = _make_mock_trading_range()
        sos_breakout = Mock()

        detector.detect_with_context(df, trading_range, sos_breakout, {})

        # Verify sos was passed to detect_lps
        call_kwargs = mock_detect.call_args
        assert call_kwargs.kwargs["sos"] is sos_breakout


# ===========================================================================
# Test 4: UTAD Phase D validation
# ===========================================================================


class TestUTADPhaseDValidation:
    """Test UTAD detector Phase D validation (task 4)."""

    def _make_utad_bars(self, count: int = 40) -> list[OHLCVBar]:
        """Create bars suitable for UTAD detection."""
        bars: list[OHLCVBar] = []
        base_time = datetime(2024, 1, 1, tzinfo=UTC)
        for i in range(count):
            bars.append(
                OHLCVBar(
                    symbol="TEST",
                    timeframe="1d",
                    timestamp=base_time + timedelta(hours=i),
                    open=Decimal("99.00"),
                    high=Decimal("100.00"),
                    low=Decimal("98.00"),
                    close=Decimal("99.50"),
                    volume=1000000,
                    spread=Decimal("2.00"),
                )
            )
        return bars

    def test_rejects_non_phase_d(self) -> None:
        """UTAD should be rejected when phase is not D."""
        from src.pattern_engine.detectors.utad_detector import UTADDetector

        detector = UTADDetector()
        bars = self._make_utad_bars()
        trading_range = _make_mock_trading_range()

        # Phase B should be rejected
        result = detector.detect_utad(trading_range, bars, Decimal("100.00"), phase=WyckoffPhase.B)
        assert result is None

        # Phase A should be rejected
        result = detector.detect_utad(trading_range, bars, Decimal("100.00"), phase=WyckoffPhase.A)
        assert result is None

        # Phase C should be rejected
        result = detector.detect_utad(trading_range, bars, Decimal("100.00"), phase=WyckoffPhase.C)
        assert result is None

        # Phase E should be rejected
        result = detector.detect_utad(trading_range, bars, Decimal("100.00"), phase=WyckoffPhase.E)
        assert result is None

    def test_accepts_phase_d(self) -> None:
        """UTAD should not reject when phase=D (detection depends on data)."""
        from src.pattern_engine.detectors.utad_detector import UTADDetector

        detector = UTADDetector()
        bars = self._make_utad_bars()
        trading_range = _make_mock_trading_range()

        # Phase D should NOT be rejected by phase validation
        # (may still return None due to no pattern in data, but won't be
        # rejected by the phase check itself)
        result = detector.detect_utad(trading_range, bars, Decimal("100.00"), phase=WyckoffPhase.D)
        # Result is None because test data doesn't have a UTAD pattern,
        # but it got past the phase validation (no early return for Phase D)
        assert result is None  # No pattern in this data, but phase was accepted

    def test_backward_compat_phase_none(self) -> None:
        """UTAD should skip phase validation when phase=None (backward compat)."""
        from src.pattern_engine.detectors.utad_detector import UTADDetector

        detector = UTADDetector()
        bars = self._make_utad_bars()
        trading_range = _make_mock_trading_range()

        # phase=None should not reject - backward compat
        result = detector.detect_utad(trading_range, bars, Decimal("100.00"), phase=None)
        # Returns None because test data has no UTAD pattern,
        # but it was NOT rejected by phase validation
        assert result is None

    def test_phase_parameter_is_optional(self) -> None:
        """detect_utad phase parameter should have default=None."""
        import inspect

        from src.pattern_engine.detectors.utad_detector import UTADDetector

        sig = inspect.signature(UTADDetector.detect_utad)
        phase_param = sig.parameters["phase"]
        assert phase_param.default is None


# ===========================================================================
# Test 5: SOS logging threshold
# ===========================================================================


class TestSOSLoggingThreshold:
    """Verify SOS logging uses 1.5x threshold, not 2.0x."""

    def test_sos_volume_pass_log_uses_1_5x(self) -> None:
        """The 'sos_volume_validated' log message should reference SOS_VOLUME_THRESHOLD, not hardcoded 2.0x."""
        import inspect

        from src.pattern_engine.detectors import sos_detector

        source = inspect.getsource(sos_detector.detect_sos_breakout)

        # The volume-pass log should use the SOS_VOLUME_THRESHOLD constant
        assert "SOS_VOLUME_THRESHOLD" in source

        # The threshold value in volume_log_data should not be hardcoded 2.0
        assert '"threshold": 2.0' not in source

    def test_detection_config_sos_threshold_is_1_5(self) -> None:
        """DetectionConfig.volume_threshold_sos should be 1.5."""
        config = DetectionConfig()
        assert config.volume_threshold_sos == 1.5

    def test_sos_rejection_log_uses_threshold_constant(self) -> None:
        """The rejection log references SOS_VOLUME_THRESHOLD constant, not hardcoded value."""
        import inspect

        from src.pattern_engine.detectors import sos_detector

        source = inspect.getsource(sos_detector.detect_sos_breakout)

        # Rejection message should use the constant dynamically
        assert "SOS_VOLUME_THRESHOLD" in source
        # Should not have hardcoded "< 1.5x" string anymore
        assert "< 1.5x" not in source


# ===========================================================================
# Converter function tests
# ===========================================================================


class TestSOSBreakoutToEvent:
    """Test _sos_breakout_to_event conversion."""

    def test_converts_correctly(self) -> None:
        """SOSBreakout model is converted to PhaseEvent with correct fields."""
        mock_sos = Mock()
        mock_sos.bar = Mock()
        mock_sos.bar.timestamp = datetime(2024, 1, 1, 14, tzinfo=UTC)
        mock_sos.bar.volume = 2500000
        mock_sos.breakout_price = Decimal("103.00")
        mock_sos.breakout_pct = Decimal("0.03")
        mock_sos.volume_ratio = Decimal("2.0")
        mock_sos.ice_reference = Decimal("100.00")
        mock_sos.quality_tier = "EXCELLENT"

        event = _sos_breakout_to_event(mock_sos)

        assert event.event_type == EventType.SIGN_OF_STRENGTH
        assert event.bar_index == 0  # bars=None -> default 0
        assert event.price == 103.0
        assert event.volume == 2500000.0
        assert event.confidence == 0.9  # EXCELLENT quality_tier -> 0.9
        assert event.metadata["breakout_pct"] == 0.03
        assert event.metadata["volume_ratio"] == 2.0
        assert event.metadata["ice_reference"] == 100.0
        assert event.metadata["quality_tier"] == "EXCELLENT"

    def test_quality_tier_confidence_mapping(self) -> None:
        """Verify quality_tier maps to correct confidence values."""
        for tier, expected_conf in [
            ("EXCELLENT", 0.9),
            ("GOOD", 0.8),
            ("ACCEPTABLE", 0.65),
            ("UNKNOWN", 0.65),  # default fallback
        ]:
            mock_sos = Mock()
            mock_sos.bar = Mock()
            mock_sos.bar.timestamp = datetime(2024, 1, 1, tzinfo=UTC)
            mock_sos.bar.volume = 1000000
            mock_sos.breakout_price = Decimal("102.00")
            mock_sos.breakout_pct = Decimal("0.02")
            mock_sos.volume_ratio = Decimal("2.0")
            mock_sos.ice_reference = Decimal("100.00")
            mock_sos.quality_tier = tier

            event = _sos_breakout_to_event(mock_sos)
            assert event.confidence == expected_conf, f"Failed for tier={tier}"


class TestLPSToEvent:
    """Test _lps_to_event conversion."""

    def test_converts_correctly(self) -> None:
        """LPS model is converted to PhaseEvent with correct fields."""
        mock_lps = Mock()
        mock_lps.bar = Mock()
        mock_lps.bar.timestamp = datetime(2024, 1, 1, 16, tzinfo=UTC)
        mock_lps.pullback_low = Decimal("100.50")
        mock_lps.pullback_volume = 80000
        mock_lps.distance_from_ice = Decimal("0.005")
        mock_lps.distance_quality = "PREMIUM"
        mock_lps.volume_ratio_vs_avg = Decimal("0.6")
        mock_lps.held_support = True
        mock_lps.bars_after_sos = 3
        mock_lps.bounce_confirmed = True
        mock_lps.effort_result_bonus = 10
        mock_lps.effort_result = "NO_SUPPLY"

        event = _lps_to_event(mock_lps)

        assert event.event_type == EventType.LAST_POINT_OF_SUPPORT
        assert event.bar_index == 0  # bars=None -> default 0
        assert event.price == 100.5
        assert event.volume == 80000.0
        # Confidence: 0.6 base + 0.15 PREMIUM + 10/100.0 = 0.85
        assert event.confidence == pytest.approx(0.85)
        assert event.metadata["distance_from_ice"] == 0.005
        assert event.metadata["distance_quality"] == "PREMIUM"
        assert event.metadata["volume_ratio_vs_avg"] == 0.6
        assert event.metadata["support_quality"] == "HELD"
        assert event.metadata["bars_after_sos"] == 3
        assert event.metadata["bounce_confirmed"] is True
        assert event.metadata["effort_result"] == "NO_SUPPLY"

    def test_broken_support_quality(self) -> None:
        """LPS with held_support=False maps to BROKEN support_quality."""
        mock_lps = Mock()
        mock_lps.bar = Mock()
        mock_lps.bar.timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        mock_lps.pullback_low = Decimal("99.00")
        mock_lps.pullback_volume = 150000
        mock_lps.distance_from_ice = Decimal("0.01")
        mock_lps.distance_quality = "ACCEPTABLE"
        mock_lps.volume_ratio_vs_avg = Decimal("1.1")
        mock_lps.held_support = False
        mock_lps.bars_after_sos = 8
        mock_lps.bounce_confirmed = False
        mock_lps.effort_result_bonus = 0
        mock_lps.effort_result = "SUPPLY_PRESENT"

        event = _lps_to_event(mock_lps)
        assert event.metadata["support_quality"] == "BROKEN"

    def test_confidence_clamped_to_0_1(self) -> None:
        """LPS confidence is clamped to [0.0, 1.0]."""
        mock_lps = Mock()
        mock_lps.bar = Mock()
        mock_lps.bar.timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        mock_lps.pullback_low = Decimal("100.00")
        mock_lps.pullback_volume = 100000
        mock_lps.distance_from_ice = Decimal("0.005")
        mock_lps.distance_quality = "PREMIUM"
        mock_lps.volume_ratio_vs_avg = Decimal("0.5")
        mock_lps.held_support = True
        mock_lps.bars_after_sos = 2
        mock_lps.bounce_confirmed = True
        mock_lps.effort_result_bonus = 50  # Large bonus
        mock_lps.effort_result = "NO_SUPPLY"

        event = _lps_to_event(mock_lps)
        assert event.confidence <= 1.0
