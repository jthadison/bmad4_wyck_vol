"""
Integration tests for Story 23.2: Wire Orchestrator Pipeline with Real Detectors.

Tests validate that:
- AC1: DetectorRegistry correctly maps phases to detectors
- AC2: PatternDetectionStage dispatches to registered detectors
- AC4: No false positives when registry is empty or data absent
- AC5: Container exposes spring_detector and utad_detector properties

Story 23.2: Wire Orchestrator Pipeline with Real Detectors
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.models.effort_result import EffortResult
from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import WyckoffPhase
from src.models.volume_analysis import VolumeAnalysis
from src.orchestrator.container import OrchestratorContainer
from src.orchestrator.pipeline.context import PipelineContextBuilder
from src.orchestrator.stages.pattern_detection_stage import (
    DetectorRegistry,
    PatternDetectionStage,
    PhaseDCompositeDetector,
)

# =============================
# Shared Test Fixtures
# =============================


@pytest.fixture
def sample_bars() -> list[OHLCVBar]:
    """Create sample OHLCV bars for testing."""
    base_time = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)
    bars = []
    for i in range(50):
        increment = Decimal(i) / Decimal(10)
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=base_time + timedelta(days=i),
            open=Decimal("150.00") + increment,
            high=Decimal("151.00") + increment,
            low=Decimal("149.00") + increment,
            close=Decimal("150.50") + increment,
            volume=1000000 + i * 10000,
            spread=Decimal("2.00"),
        )
        bars.append(bar)
    return bars


@pytest.fixture
def sample_volume_analysis(sample_bars: list[OHLCVBar]) -> list[VolumeAnalysis]:
    """Create sample volume analysis results for testing."""
    results = []
    for i, bar in enumerate(sample_bars):
        increment = Decimal(i) / Decimal(100)
        va = VolumeAnalysis(
            bar=bar,
            volume_ratio=Decimal("1.0") + increment,
            spread_ratio=Decimal("1.0"),
            close_position=Decimal("0.5"),
            effort_result=EffortResult.NORMAL,
        )
        results.append(va)
    return results


@pytest.fixture
def mock_trading_range():
    """Create mock trading range with ice_level."""
    mock = MagicMock()
    mock.is_active = True
    mock.end_index = 49
    mock.ice_level = Decimal("151.00")
    return mock


@pytest.fixture
def mock_phase_info_c():
    """Create mock PhaseInfo for Phase C."""
    mock = MagicMock()
    mock.phase = WyckoffPhase.C
    mock.confidence = 80
    mock.duration = 15
    mock.is_trading_allowed.return_value = True
    return mock


@pytest.fixture
def mock_phase_info_d():
    """Create mock PhaseInfo for Phase D."""
    mock = MagicMock()
    mock.phase = WyckoffPhase.D
    mock.confidence = 85
    mock.duration = 10
    mock.is_trading_allowed.return_value = True
    return mock


@pytest.fixture
def mock_phase_info_e():
    """Create mock PhaseInfo for Phase E."""
    mock = MagicMock()
    mock.phase = WyckoffPhase.E
    mock.confidence = 90
    mock.duration = 20
    mock.is_trading_allowed.return_value = True
    return mock


@pytest.fixture
def mock_phase_info_a():
    """Create mock PhaseInfo for Phase A (trading not allowed)."""
    mock = MagicMock()
    mock.phase = WyckoffPhase.A
    mock.confidence = 60
    mock.duration = 5
    mock.is_trading_allowed.return_value = False
    return mock


@pytest.fixture
def mock_spring_detector():
    """Create mock Spring detector."""
    detector = MagicMock()
    mock_history = MagicMock()
    mock_history.springs = [MagicMock(volume_ratio=Decimal("0.5"))]
    detector.detect_all_springs.return_value = mock_history
    return detector


@pytest.fixture
def mock_sos_detector():
    """Create mock SOS detector."""
    detector = MagicMock()
    mock_result = MagicMock()
    mock_result.sos_detected = True
    mock_result.sos = MagicMock(volume_ratio=Decimal("1.8"))
    detector.detect.return_value = mock_result
    # SOS detector should not have utad_detector attribute
    del detector.utad_detector
    return detector


@pytest.fixture
def mock_lps_detector():
    """Create mock LPS detector."""
    detector = MagicMock()
    mock_result = MagicMock()
    mock_result.lps_detected = True
    mock_result.lps = MagicMock(distance_from_ice=Decimal("0.5"))
    # Ensure lps_detected check works and sos_detected is absent
    mock_result.sos_detected = False
    del mock_result.sos_detected
    detector.detect.return_value = mock_result
    return detector


@pytest.fixture
def mock_utad_detector():
    """Create mock UTAD detector."""
    detector = MagicMock()
    mock_utad = MagicMock(
        penetration_pct=Decimal("2.5"),
        volume_ratio=Decimal("1.8"),
    )
    detector.detect_utad.return_value = mock_utad
    return detector


# =============================
# Group 1: DetectorRegistry Tests (AC1)
# =============================


class TestDetectorRegistryWiring:
    """Tests for DetectorRegistry phase-to-detector mapping (AC1)."""

    def test_detector_registry_registers_spring_for_phase_c(self, mock_spring_detector):
        """Registry registers Spring detector for Phase C and returns it."""
        registry = DetectorRegistry()
        registry.register(WyckoffPhase.C, mock_spring_detector)

        detector = registry.get_detector(WyckoffPhase.C)
        assert detector is mock_spring_detector

    def test_detector_registry_registers_sos_for_phase_d(self, mock_sos_detector):
        """Registry registers SOS detector for Phase D and returns it."""
        registry = DetectorRegistry()
        registry.register(WyckoffPhase.D, mock_sos_detector)

        detector = registry.get_detector(WyckoffPhase.D)
        assert detector is mock_sos_detector

    def test_detector_registry_registers_lps_for_phase_e(self, mock_lps_detector):
        """Registry registers LPS detector for Phase E and returns it."""
        registry = DetectorRegistry()
        registry.register(WyckoffPhase.E, mock_lps_detector)

        detector = registry.get_detector(WyckoffPhase.E)
        assert detector is mock_lps_detector

    def test_detector_registry_registered_phases(
        self, mock_spring_detector, mock_sos_detector, mock_lps_detector
    ):
        """Registry tracks all registered phases (C, D, E)."""
        registry = DetectorRegistry()
        registry.register(WyckoffPhase.C, mock_spring_detector)
        registry.register(WyckoffPhase.D, mock_sos_detector)
        registry.register(WyckoffPhase.E, mock_lps_detector)

        phases = registry.registered_phases
        assert WyckoffPhase.C in phases
        assert WyckoffPhase.D in phases
        assert WyckoffPhase.E in phases
        assert len(phases) == 3

    def test_detector_registry_has_detector(self, mock_spring_detector):
        """has_detector returns True for registered, False for unregistered phases."""
        registry = DetectorRegistry()
        registry.register(WyckoffPhase.C, mock_spring_detector)

        assert registry.has_detector(WyckoffPhase.C) is True
        assert registry.has_detector(WyckoffPhase.D) is False
        assert registry.has_detector(WyckoffPhase.E) is False
        assert registry.has_detector(WyckoffPhase.A) is False


# =============================
# Group 2: PhaseDCompositeDetector Tests
# =============================


class TestPhaseDCompositeDetector:
    """Tests for PhaseDCompositeDetector combining SOS + UTAD."""

    def test_composite_detector_delegates_detect_to_sos(self, mock_sos_detector):
        """Composite detect() delegates to SOS detector's detect()."""
        composite = PhaseDCompositeDetector(sos_detector=mock_sos_detector)

        result = composite.detect(
            symbol="AAPL", range=None, bars=[], volume_analysis=[], phase=WyckoffPhase.D
        )

        mock_sos_detector.detect.assert_called_once()
        assert result is mock_sos_detector.detect.return_value

    def test_composite_detector_exposes_utad_detector(self, mock_sos_detector, mock_utad_detector):
        """Composite exposes utad_detector attribute for Phase D UTAD checks."""
        composite = PhaseDCompositeDetector(
            sos_detector=mock_sos_detector,
            utad_detector=mock_utad_detector,
        )

        assert composite.utad_detector is mock_utad_detector

    def test_composite_detector_handles_none_sos(self, mock_utad_detector):
        """Composite with no SOS detector returns None from detect()."""
        composite = PhaseDCompositeDetector(
            sos_detector=None,
            utad_detector=mock_utad_detector,
        )

        result = composite.detect()
        assert result is None

    def test_composite_detector_handles_none_utad(self, mock_sos_detector):
        """Composite with no UTAD detector has utad_detector as None."""
        composite = PhaseDCompositeDetector(
            sos_detector=mock_sos_detector,
            utad_detector=None,
        )

        assert composite.utad_detector is None
        # SOS still works
        result = composite.detect()
        assert result is not None


# =============================
# Group 3: PatternDetectionStage Tests (AC2)
# =============================


class TestPatternDetectionStageWiring:
    """Tests for PatternDetectionStage dispatching to registered detectors (AC2)."""

    def test_pattern_detection_stage_default_empty_registry(self):
        """PatternDetectionStage() creates with empty registry when no arg given."""
        stage = PatternDetectionStage()
        assert stage.name == "pattern_detection"
        # Internal registry should have no phases
        assert stage._registry.registered_phases == []

    @pytest.mark.asyncio
    async def test_pattern_detection_stage_skips_no_phase_info(self):
        """None phase_info returns empty patterns list."""
        stage = PatternDetectionStage()
        context = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1d").build()

        result = await stage.run(None, context)

        assert result.success is True
        assert result.output == []
        assert context.get("patterns") == []

    @pytest.mark.asyncio
    async def test_pattern_detection_stage_skips_non_trading_phase(
        self, mock_phase_info_a, sample_bars, sample_volume_analysis
    ):
        """Phase A (trading not allowed) returns empty patterns list."""
        stage = PatternDetectionStage()
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("bars", sample_bars)
            .with_data("volume_analysis", sample_volume_analysis)
            .build()
        )

        result = await stage.run(mock_phase_info_a, context)

        assert result.success is True
        assert result.output == []

    @pytest.mark.asyncio
    async def test_pattern_detection_stage_skips_unregistered_phase(
        self, mock_phase_info_c, sample_bars, sample_volume_analysis, mock_trading_range
    ):
        """Phase with no registered detector returns empty patterns list."""
        # Empty registry - no detector for Phase C
        registry = DetectorRegistry()
        stage = PatternDetectionStage(registry)

        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("bars", sample_bars)
            .with_data("volume_analysis", sample_volume_analysis)
            .with_data("current_trading_range", mock_trading_range)
            .build()
        )

        result = await stage.run(mock_phase_info_c, context)

        assert result.success is True
        assert result.output == []

    @pytest.mark.asyncio
    async def test_pattern_detection_stage_spring_detection_phase_c(
        self,
        mock_spring_detector,
        mock_phase_info_c,
        sample_bars,
        sample_volume_analysis,
        mock_trading_range,
    ):
        """Phase C with Spring detector produces spring patterns."""
        registry = DetectorRegistry()
        registry.register(WyckoffPhase.C, mock_spring_detector)
        stage = PatternDetectionStage(registry)

        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("bars", sample_bars)
            .with_data("volume_analysis", sample_volume_analysis)
            .with_data("current_trading_range", mock_trading_range)
            .build()
        )

        result = await stage.run(mock_phase_info_c, context)

        assert result.success is True
        assert len(result.output) == 1
        mock_spring_detector.detect_all_springs.assert_called_once()

    @pytest.mark.asyncio
    async def test_pattern_detection_stage_sos_detection_phase_d(
        self,
        mock_sos_detector,
        mock_phase_info_d,
        sample_bars,
        sample_volume_analysis,
        mock_trading_range,
    ):
        """Phase D with SOS detector produces SOS patterns."""
        registry = DetectorRegistry()
        registry.register(WyckoffPhase.D, mock_sos_detector)
        stage = PatternDetectionStage(registry)

        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("bars", sample_bars)
            .with_data("volume_analysis", sample_volume_analysis)
            .with_data("current_trading_range", mock_trading_range)
            .build()
        )

        result = await stage.run(mock_phase_info_d, context)

        assert result.success is True
        assert len(result.output) == 1
        mock_sos_detector.detect.assert_called_once()

    @pytest.mark.asyncio
    async def test_pattern_detection_stage_utad_detection_phase_d(
        self,
        mock_sos_detector,
        mock_utad_detector,
        mock_phase_info_d,
        sample_bars,
        sample_volume_analysis,
        mock_trading_range,
    ):
        """Phase D with PhaseDCompositeDetector detects both SOS and UTAD patterns."""
        composite = PhaseDCompositeDetector(
            sos_detector=mock_sos_detector,
            utad_detector=mock_utad_detector,
        )
        registry = DetectorRegistry()
        registry.register(WyckoffPhase.D, composite)
        stage = PatternDetectionStage(registry)

        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("bars", sample_bars)
            .with_data("volume_analysis", sample_volume_analysis)
            .with_data("current_trading_range", mock_trading_range)
            .build()
        )

        result = await stage.run(mock_phase_info_d, context)

        assert result.success is True
        # SOS pattern + UTAD pattern = 2 patterns
        assert len(result.output) == 2
        mock_sos_detector.detect.assert_called_once()
        mock_utad_detector.detect_utad.assert_called_once()

    @pytest.mark.asyncio
    async def test_pattern_detection_stage_lps_detection_phase_e(
        self,
        mock_lps_detector,
        mock_phase_info_e,
        sample_bars,
        sample_volume_analysis,
        mock_trading_range,
    ):
        """Phase E with LPS detector produces LPS patterns."""
        registry = DetectorRegistry()
        registry.register(WyckoffPhase.E, mock_lps_detector)
        stage = PatternDetectionStage(registry)

        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("bars", sample_bars)
            .with_data("volume_analysis", sample_volume_analysis)
            .with_data("current_trading_range", mock_trading_range)
            .build()
        )

        result = await stage.run(mock_phase_info_e, context)

        assert result.success is True
        assert len(result.output) == 1
        mock_lps_detector.detect.assert_called_once()


# =============================
# Group 4: Container Tests (AC5)
# =============================


class TestContainerDetectorProperties:
    """Tests for OrchestratorContainer spring_detector and utad_detector properties (AC5)."""

    def test_container_has_spring_detector_property(self):
        """Container in mock mode returns mock spring_detector."""
        container = OrchestratorContainer(mode="mock")
        mock_spring = MagicMock()
        container.set_mock("spring_detector", mock_spring)

        result = container.spring_detector
        assert result is mock_spring

    def test_container_has_utad_detector_property(self):
        """Container in mock mode returns mock utad_detector."""
        container = OrchestratorContainer(mode="mock")
        mock_utad = MagicMock()
        container.set_mock("utad_detector", mock_utad)

        result = container.utad_detector
        assert result is mock_utad

    def test_container_health_check_includes_spring_detector(self):
        """health_check() includes spring_detector in details."""
        container = OrchestratorContainer(mode="mock")
        mock_spring = MagicMock(spec=[])  # No health_check method
        container.set_mock("spring_detector", mock_spring)
        # Set up all critical detectors to avoid load failures
        container.set_mock("volume_analyzer", MagicMock(spec=[]))
        container.set_mock("trading_range_detector", MagicMock(spec=[]))
        container.set_mock("risk_manager", MagicMock(spec=[]))

        health = container.health_check()
        assert "spring_detector" in health.details

    def test_container_health_check_includes_utad_detector(self):
        """health_check() includes utad_detector in details."""
        container = OrchestratorContainer(mode="mock")
        mock_utad = MagicMock(spec=[])  # No health_check method
        container.set_mock("utad_detector", mock_utad)
        # Set up all critical detectors to avoid load failures
        container.set_mock("volume_analyzer", MagicMock(spec=[]))
        container.set_mock("trading_range_detector", MagicMock(spec=[]))
        container.set_mock("risk_manager", MagicMock(spec=[]))

        health = container.health_check()
        assert "utad_detector" in health.details


# =============================
# Group 5: Facade Wiring Tests (AC1, AC2)
# =============================


class TestFacadeDetectorWiring:
    """Tests for MasterOrchestratorFacade detector registry wiring (AC1, AC2)."""

    @staticmethod
    def _make_mock_stage(name: str):
        """Create a mock pipeline stage with the given name."""
        stage = MagicMock()
        stage.name = name
        return stage

    def test_facade_builds_detector_registry(self):
        """Facade populates registry with Phase C, D, E detectors from container."""
        from src.orchestrator.orchestrator_facade import MasterOrchestratorFacade

        container = OrchestratorContainer(mode="mock")
        mock_spring = MagicMock()
        mock_sos = MagicMock()
        mock_utad = MagicMock()
        mock_lps = MagicMock()

        container.set_mock("spring_detector", mock_spring)
        container.set_mock("sos_detector", mock_sos)
        container.set_mock("utad_detector", mock_utad)
        container.set_mock("lps_detector", mock_lps)
        # Critical detectors needed for other stages
        container.set_mock("volume_analyzer", MagicMock())
        container.set_mock("trading_range_detector", MagicMock())
        container.set_mock("risk_manager", MagicMock())

        # Patch stage constructors that require real dependencies
        # These are imported locally inside _build_coordinator from src.orchestrator.stages
        with (
            patch(
                "src.orchestrator.stages.PhaseDetectionStage",
                return_value=self._make_mock_stage("phase_detection"),
            ),
            patch(
                "src.orchestrator.stages.ValidationStage",
                return_value=self._make_mock_stage("validation"),
            ),
            patch(
                "src.orchestrator.stages.SignalGenerationStage",
                return_value=self._make_mock_stage("signal_generation"),
            ),
        ):
            facade = MasterOrchestratorFacade(container=container)

        # Find the PatternDetectionStage in the coordinator
        stages = facade._coordinator.get_stages()
        pattern_stages = [s for s in stages if s.name == "pattern_detection"]
        assert len(pattern_stages) == 1

        pattern_stage = pattern_stages[0]
        registry = pattern_stage._registry

        # Verify all three phases are registered
        assert registry.has_detector(WyckoffPhase.C)
        assert registry.has_detector(WyckoffPhase.D)
        assert registry.has_detector(WyckoffPhase.E)

        # Phase C should be the Spring detector
        assert registry.get_detector(WyckoffPhase.C) is mock_spring

        # Phase D should be a PhaseDCompositeDetector
        phase_d_detector = registry.get_detector(WyckoffPhase.D)
        assert isinstance(phase_d_detector, PhaseDCompositeDetector)
        assert phase_d_detector.sos_detector is mock_sos
        assert phase_d_detector.utad_detector is mock_utad

        # Phase E should be the LPS detector
        assert registry.get_detector(WyckoffPhase.E) is mock_lps

    def test_facade_coordinator_has_pattern_detection_stage(self):
        """Facade coordinator stages include pattern_detection."""
        from src.orchestrator.orchestrator_facade import MasterOrchestratorFacade

        container = OrchestratorContainer(mode="mock")
        container.set_mock("volume_analyzer", MagicMock())
        container.set_mock("trading_range_detector", MagicMock())
        container.set_mock("risk_manager", MagicMock())

        # Patch stage constructors that require real dependencies
        with (
            patch(
                "src.orchestrator.stages.PhaseDetectionStage",
                return_value=self._make_mock_stage("phase_detection"),
            ),
            patch(
                "src.orchestrator.stages.ValidationStage",
                return_value=self._make_mock_stage("validation"),
            ),
            patch(
                "src.orchestrator.stages.SignalGenerationStage",
                return_value=self._make_mock_stage("signal_generation"),
            ),
        ):
            facade = MasterOrchestratorFacade(container=container)

        stage_names = [s.name for s in facade._coordinator.get_stages()]
        assert "pattern_detection" in stage_names


# =============================
# Group 6: No False Positives (AC4)
# =============================


class TestNoFalsePositives:
    """Tests that ensure no false positive pattern detections (AC4)."""

    @pytest.mark.asyncio
    async def test_pattern_detection_no_patterns_on_empty_registry(
        self, mock_phase_info_c, sample_bars, sample_volume_analysis, mock_trading_range
    ):
        """Empty registry produces no patterns even for a valid tradable phase."""
        registry = DetectorRegistry()
        stage = PatternDetectionStage(registry)

        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("bars", sample_bars)
            .with_data("volume_analysis", sample_volume_analysis)
            .with_data("current_trading_range", mock_trading_range)
            .build()
        )

        result = await stage.run(mock_phase_info_c, context)

        assert result.success is True
        assert result.output == []
        assert context.get("patterns") == []

    @pytest.mark.asyncio
    async def test_pattern_detection_no_patterns_on_no_data(
        self, mock_phase_info_c, sample_bars, sample_volume_analysis, mock_trading_range
    ):
        """Registered detector that finds nothing returns empty patterns."""
        # Spring detector that returns no springs
        empty_detector = MagicMock()
        mock_history = MagicMock()
        mock_history.springs = []
        empty_detector.detect_all_springs.return_value = mock_history

        registry = DetectorRegistry()
        registry.register(WyckoffPhase.C, empty_detector)
        stage = PatternDetectionStage(registry)

        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("bars", sample_bars)
            .with_data("volume_analysis", sample_volume_analysis)
            .with_data("current_trading_range", mock_trading_range)
            .build()
        )

        result = await stage.run(mock_phase_info_c, context)

        assert result.success is True
        assert result.output == []
        empty_detector.detect_all_springs.assert_called_once()

    @pytest.mark.asyncio
    async def test_pattern_detection_utad_error_handling(
        self, mock_phase_info_d, sample_bars, sample_volume_analysis, mock_trading_range
    ):
        """UTAD detection error is caught and logged, not propagated."""
        mock_sos = MagicMock()
        mock_sos_result = MagicMock()
        mock_sos_result.sos_detected = False
        del mock_sos_result.sos_detected
        del mock_sos_result.lps_detected
        mock_sos.detect.return_value = None

        mock_utad = MagicMock()
        mock_utad.detect_utad.side_effect = RuntimeError("UTAD detection failed")

        composite = PhaseDCompositeDetector(sos_detector=mock_sos, utad_detector=mock_utad)
        registry = DetectorRegistry()
        registry.register(WyckoffPhase.D, composite)
        stage = PatternDetectionStage(registry)

        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("bars", sample_bars)
            .with_data("volume_analysis", sample_volume_analysis)
            .with_data("current_trading_range", mock_trading_range)
            .build()
        )

        result = await stage.run(mock_phase_info_d, context)

        assert result.success is True
        # UTAD error caught, no patterns from error path
        mock_utad.detect_utad.assert_called_once()

    @pytest.mark.asyncio
    async def test_pattern_detection_phase_c_fallback_detect(
        self, mock_phase_info_c, sample_bars, sample_volume_analysis, mock_trading_range
    ):
        """Phase C uses fallback detect() when detect_all_springs not available."""
        detector = MagicMock(spec=["detect"])
        mock_spring = MagicMock()
        detector.detect.return_value = mock_spring

        registry = DetectorRegistry()
        registry.register(WyckoffPhase.C, detector)
        stage = PatternDetectionStage(registry)

        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("bars", sample_bars)
            .with_data("volume_analysis", sample_volume_analysis)
            .with_data("current_trading_range", mock_trading_range)
            .build()
        )

        result = await stage.run(mock_phase_info_c, context)

        assert result.success is True
        assert len(result.output) == 1
        detector.detect.assert_called_once()

    @pytest.mark.asyncio
    async def test_pattern_detection_phase_b_skips(
        self, sample_bars, sample_volume_analysis, mock_trading_range
    ):
        """Phase B with registered detector logs and returns empty (no patterns in Phase B)."""
        mock_phase_info_b = MagicMock()
        mock_phase_info_b.phase = WyckoffPhase.B
        mock_phase_info_b.is_trading_allowed.return_value = True

        detector = MagicMock()
        registry = DetectorRegistry()
        registry.register(WyckoffPhase.B, detector)
        stage = PatternDetectionStage(registry)

        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("bars", sample_bars)
            .with_data("volume_analysis", sample_volume_analysis)
            .with_data("current_trading_range", mock_trading_range)
            .build()
        )

        result = await stage.run(mock_phase_info_b, context)

        assert result.success is True
        assert result.output == []

    @pytest.mark.asyncio
    async def test_pattern_detection_phase_info_none_phase(
        self, sample_bars, sample_volume_analysis
    ):
        """PhaseInfo with phase=None returns empty patterns."""
        mock_phase_info = MagicMock()
        mock_phase_info.phase = None
        mock_phase_info.is_trading_allowed.return_value = True

        stage = PatternDetectionStage()

        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("bars", sample_bars)
            .with_data("volume_analysis", sample_volume_analysis)
            .build()
        )

        result = await stage.run(mock_phase_info, context)

        assert result.success is True
        assert result.output == []

    @pytest.mark.asyncio
    async def test_pattern_detection_generic_result_phase_d(
        self, mock_phase_info_d, sample_bars, sample_volume_analysis, mock_trading_range
    ):
        """Phase D detector returning generic (non-SOS/LPS) result is appended."""
        detector = MagicMock()
        generic_result = MagicMock(spec=[])  # No sos_detected or lps_detected
        detector.detect.return_value = generic_result
        # Prevent UTAD path
        del detector.utad_detector

        registry = DetectorRegistry()
        registry.register(WyckoffPhase.D, detector)
        stage = PatternDetectionStage(registry)

        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("bars", sample_bars)
            .with_data("volume_analysis", sample_volume_analysis)
            .with_data("current_trading_range", mock_trading_range)
            .build()
        )

        result = await stage.run(mock_phase_info_d, context)

        assert result.success is True
        assert len(result.output) == 1
        assert result.output[0] is generic_result
