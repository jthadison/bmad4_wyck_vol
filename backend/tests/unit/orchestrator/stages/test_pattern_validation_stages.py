"""
Unit tests for pattern detection and validation pipeline stages.

Story 18.10.3: Pattern Detection and Validation Stages (AC5)
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.models.effort_result import EffortResult
from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import WyckoffPhase
from src.models.validation import ValidationChain, ValidationStatus
from src.models.volume_analysis import VolumeAnalysis
from src.orchestrator.pipeline.context import PipelineContextBuilder
from src.orchestrator.stages.pattern_detection_stage import (
    DetectorRegistry,
    PatternDetectionStage,
)
from src.orchestrator.stages.validation_stage import ValidationResults, ValidationStage

# =============================
# Test Fixtures
# =============================


@pytest.fixture
def sample_bars() -> list[OHLCVBar]:
    """Create sample OHLCV bars for testing."""
    base_time = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)
    bars = []
    for i in range(50):
        increment = Decimal(i) / Decimal(10)
        open_price = Decimal("150.00") + increment
        high_price = Decimal("151.00") + increment
        low_price = Decimal("149.00") + increment
        close_price = Decimal("150.50") + increment
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=base_time + timedelta(days=i),
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=1000000 + i * 10000,
            spread=high_price - low_price,
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
def mock_phase_info():
    """Create mock PhaseInfo for testing."""
    mock = MagicMock()
    mock.phase = WyckoffPhase.C
    mock.confidence = 80
    mock.duration = 15
    mock.is_trading_allowed.return_value = True
    return mock


@pytest.fixture
def mock_phase_info_no_trading():
    """Create mock PhaseInfo where trading is not allowed."""
    mock = MagicMock()
    mock.phase = WyckoffPhase.A
    mock.confidence = 60
    mock.duration = 5
    mock.is_trading_allowed.return_value = False
    return mock


@pytest.fixture
def mock_trading_range():
    """Create mock trading range."""
    mock = MagicMock()
    mock.is_active = True
    mock.end_index = 49
    return mock


@pytest.fixture
def mock_spring_detector():
    """Create mock spring detector."""
    detector = MagicMock()
    # Mock SpringHistory result
    mock_history = MagicMock()
    mock_history.springs = [MagicMock(volume_ratio=Decimal("0.5"))]
    detector.detect_all_springs.return_value = mock_history
    return detector


@pytest.fixture
def mock_sos_detector():
    """Create mock SOS detector."""
    detector = MagicMock()
    # Mock SOSDetectionResult
    mock_result = MagicMock()
    mock_result.sos_detected = True
    mock_result.sos = MagicMock(volume_ratio=Decimal("1.8"))
    detector.detect.return_value = mock_result
    return detector


@pytest.fixture
def mock_validation_orchestrator():
    """Create mock validation chain orchestrator."""
    orchestrator = MagicMock()
    # Create async mock for run_validation_chain
    chain = ValidationChain(pattern_id=uuid4())
    orchestrator.run_validation_chain = AsyncMock(return_value=chain)
    return orchestrator


@pytest.fixture
def mock_validation_orchestrator_fail():
    """Create mock validation chain orchestrator that fails."""
    orchestrator = MagicMock()
    chain = ValidationChain(pattern_id=uuid4())
    chain.overall_status = ValidationStatus.FAIL
    chain.rejection_stage = "Volume"
    chain.rejection_reason = "Volume too high"
    orchestrator.run_validation_chain = AsyncMock(return_value=chain)
    return orchestrator


# =============================
# DetectorRegistry Tests
# =============================


class TestDetectorRegistry:
    """Tests for DetectorRegistry."""

    def test_empty_registry(self):
        """Test registry starts empty."""
        registry = DetectorRegistry()
        assert registry.registered_phases == []
        assert not registry.has_detector(WyckoffPhase.C)

    def test_register_detector(self, mock_spring_detector):
        """Test registering a detector."""
        registry = DetectorRegistry()
        registry.register(WyckoffPhase.C, mock_spring_detector)

        assert registry.has_detector(WyckoffPhase.C)
        assert WyckoffPhase.C in registry.registered_phases

    def test_get_detector(self, mock_spring_detector):
        """Test getting a registered detector."""
        registry = DetectorRegistry()
        registry.register(WyckoffPhase.C, mock_spring_detector)

        detector = registry.get_detector(WyckoffPhase.C)
        assert detector is mock_spring_detector

    def test_get_detector_not_registered(self):
        """Test getting detector for unregistered phase."""
        registry = DetectorRegistry()
        detector = registry.get_detector(WyckoffPhase.D)
        assert detector is None

    def test_multiple_detectors(self, mock_spring_detector, mock_sos_detector):
        """Test registering multiple detectors."""
        registry = DetectorRegistry()
        registry.register(WyckoffPhase.C, mock_spring_detector)
        registry.register(WyckoffPhase.D, mock_sos_detector)

        assert len(registry.registered_phases) == 2
        assert registry.get_detector(WyckoffPhase.C) is mock_spring_detector
        assert registry.get_detector(WyckoffPhase.D) is mock_sos_detector


# =============================
# PatternDetectionStage Tests
# =============================


class TestPatternDetectionStage:
    """Tests for PatternDetectionStage."""

    def test_stage_name(self, mock_spring_detector):
        """Test stage has correct name."""
        registry = DetectorRegistry()
        registry.register(WyckoffPhase.C, mock_spring_detector)
        stage = PatternDetectionStage(registry)
        assert stage.name == "pattern_detection"

    def test_context_keys(self, mock_spring_detector):
        """Test stage uses correct context keys."""
        registry = DetectorRegistry()
        stage = PatternDetectionStage(registry)
        assert stage.CONTEXT_KEY == "patterns"
        assert stage.BARS_CONTEXT_KEY == "bars"
        assert stage.VOLUME_CONTEXT_KEY == "volume_analysis"
        assert stage.RANGE_CONTEXT_KEY == "current_trading_range"

    @pytest.mark.asyncio
    async def test_execute_with_none_phase_info(self, mock_spring_detector, sample_bars):
        """Test execution with None phase_info returns empty list."""
        registry = DetectorRegistry()
        registry.register(WyckoffPhase.C, mock_spring_detector)
        stage = PatternDetectionStage(registry)

        context = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1d").build()

        result = await stage.run(None, context)

        assert result.success is True
        assert result.output == []
        assert context.get("patterns") == []

    @pytest.mark.asyncio
    async def test_execute_trading_not_allowed(
        self,
        mock_spring_detector,
        mock_phase_info_no_trading,
        sample_bars,
        sample_volume_analysis,
    ):
        """Test execution when trading not allowed returns empty list."""
        registry = DetectorRegistry()
        registry.register(WyckoffPhase.C, mock_spring_detector)
        stage = PatternDetectionStage(registry)

        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("bars", sample_bars)
            .with_data("volume_analysis", sample_volume_analysis)
            .build()
        )

        result = await stage.run(mock_phase_info_no_trading, context)

        assert result.success is True
        assert result.output == []

    @pytest.mark.asyncio
    async def test_execute_missing_bars_raises(
        self,
        mock_spring_detector,
        mock_phase_info,
        sample_volume_analysis,
    ):
        """Test execution without bars raises RuntimeError."""
        registry = DetectorRegistry()
        registry.register(WyckoffPhase.C, mock_spring_detector)
        stage = PatternDetectionStage(registry)

        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("volume_analysis", sample_volume_analysis)
            .build()
        )

        result = await stage.run(mock_phase_info, context)

        assert result.success is False
        assert "bars" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_missing_volume_analysis_raises(
        self,
        mock_spring_detector,
        mock_phase_info,
        sample_bars,
    ):
        """Test execution without volume_analysis raises RuntimeError."""
        registry = DetectorRegistry()
        registry.register(WyckoffPhase.C, mock_spring_detector)
        stage = PatternDetectionStage(registry)

        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("bars", sample_bars)
            .build()
        )

        result = await stage.run(mock_phase_info, context)

        assert result.success is False
        assert "volume_analysis" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_no_detector_for_phase(
        self,
        mock_phase_info,
        sample_bars,
        sample_volume_analysis,
        mock_trading_range,
    ):
        """Test execution with no detector for phase returns empty list."""
        registry = DetectorRegistry()  # Empty registry
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

        result = await stage.run(mock_phase_info, context)

        assert result.success is True
        assert result.output == []

    @pytest.mark.asyncio
    async def test_execute_spring_detection(
        self,
        mock_spring_detector,
        mock_phase_info,
        sample_bars,
        sample_volume_analysis,
        mock_trading_range,
    ):
        """Test spring detection in Phase C."""
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

        result = await stage.run(mock_phase_info, context)

        assert result.success is True
        assert len(result.output) == 1
        mock_spring_detector.detect_all_springs.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_sos_detection(
        self,
        mock_sos_detector,
        sample_bars,
        sample_volume_analysis,
        mock_trading_range,
    ):
        """Test SOS detection in Phase D."""
        mock_phase_info = MagicMock()
        mock_phase_info.phase = WyckoffPhase.D
        mock_phase_info.is_trading_allowed.return_value = True

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

        result = await stage.run(mock_phase_info, context)

        assert result.success is True
        assert len(result.output) == 1
        mock_sos_detector.detect.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_stores_in_context(
        self,
        mock_spring_detector,
        mock_phase_info,
        sample_bars,
        sample_volume_analysis,
        mock_trading_range,
    ):
        """Test that patterns are stored in context."""
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

        await stage.run(mock_phase_info, context)

        patterns = context.get("patterns")
        assert patterns is not None
        assert len(patterns) == 1

    @pytest.mark.asyncio
    async def test_execute_records_timing(
        self,
        mock_spring_detector,
        mock_phase_info,
        sample_bars,
        sample_volume_analysis,
        mock_trading_range,
    ):
        """Test that execution timing is recorded."""
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

        result = await stage.run(mock_phase_info, context)

        assert result.execution_time_ms > 0
        timing = context.get_timing("pattern_detection")
        assert timing is not None
        assert timing.duration_ms > 0


# =============================
# ValidationResults Tests
# =============================


class TestValidationResults:
    """Tests for ValidationResults."""

    def test_empty_results(self):
        """Test empty results."""
        results = ValidationResults()
        assert results.total_count == 0
        assert results.valid_count == 0
        assert results.invalid_count == 0
        assert len(results) == 0

    def test_add_valid_result(self):
        """Test adding a valid result."""
        results = ValidationResults()
        chain = ValidationChain(pattern_id=uuid4())
        pattern = MagicMock()

        results.add(chain, pattern)

        assert results.total_count == 1
        assert results.valid_count == 1
        assert results.invalid_count == 0

    def test_add_invalid_result(self):
        """Test adding an invalid result."""
        results = ValidationResults()
        chain = ValidationChain(pattern_id=uuid4())
        chain.overall_status = ValidationStatus.FAIL
        pattern = MagicMock()

        results.add(chain, pattern)

        assert results.total_count == 1
        assert results.valid_count == 0
        assert results.invalid_count == 1

    def test_multiple_results(self):
        """Test adding multiple results."""
        results = ValidationResults()

        # Add valid pattern
        chain1 = ValidationChain(pattern_id=uuid4())
        pattern1 = MagicMock()
        results.add(chain1, pattern1)

        # Add invalid pattern
        chain2 = ValidationChain(pattern_id=uuid4())
        chain2.overall_status = ValidationStatus.FAIL
        pattern2 = MagicMock()
        results.add(chain2, pattern2)

        assert results.total_count == 2
        assert results.valid_count == 1
        assert results.invalid_count == 1
        assert pattern1 in results.valid_patterns
        assert pattern2 in results.invalid_patterns

    def test_get_chain_for_pattern(self):
        """Test retrieving chain for a specific pattern."""
        results = ValidationResults()
        chain = ValidationChain(pattern_id=uuid4())
        pattern = MagicMock()
        results.add(chain, pattern)

        retrieved_chain = results.get_chain_for_pattern(pattern)
        assert retrieved_chain is chain

    def test_get_chain_for_unknown_pattern(self):
        """Test retrieving chain for unknown pattern."""
        results = ValidationResults()
        unknown_pattern = MagicMock()

        retrieved_chain = results.get_chain_for_pattern(unknown_pattern)
        assert retrieved_chain is None

    def test_iteration(self):
        """Test iterating over results."""
        results = ValidationResults()
        chain1 = ValidationChain(pattern_id=uuid4())
        pattern1 = MagicMock()
        chain2 = ValidationChain(pattern_id=uuid4())
        pattern2 = MagicMock()

        results.add(chain1, pattern1)
        results.add(chain2, pattern2)

        items = list(results)
        assert len(items) == 2
        assert items[0] == (chain1, pattern1)
        assert items[1] == (chain2, pattern2)


# =============================
# ValidationStage Tests
# =============================


class TestValidationStage:
    """Tests for ValidationStage."""

    def test_stage_name(self, mock_validation_orchestrator):
        """Test stage has correct name."""
        stage = ValidationStage(mock_validation_orchestrator)
        assert stage.name == "validation"

    def test_context_keys(self, mock_validation_orchestrator):
        """Test stage uses correct context keys."""
        stage = ValidationStage(mock_validation_orchestrator)
        assert stage.CONTEXT_KEY == "validation_results"
        assert stage.VOLUME_CONTEXT_KEY == "volume_analysis"
        assert stage.PHASE_CONTEXT_KEY == "phase_info"
        assert stage.RANGE_CONTEXT_KEY == "current_trading_range"

    @pytest.mark.asyncio
    async def test_execute_empty_patterns(
        self,
        mock_validation_orchestrator,
        sample_volume_analysis,
    ):
        """Test execution with empty patterns list."""
        stage = ValidationStage(mock_validation_orchestrator)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("volume_analysis", sample_volume_analysis)
            .build()
        )

        result = await stage.run([], context)

        assert result.success is True
        assert result.output.total_count == 0
        mock_validation_orchestrator.run_validation_chain.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_invalid_input_type(
        self,
        mock_validation_orchestrator,
        sample_volume_analysis,
    ):
        """Test execution with non-list input raises TypeError."""
        stage = ValidationStage(mock_validation_orchestrator)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("volume_analysis", sample_volume_analysis)
            .build()
        )

        result = await stage.run("not a list", context)  # type: ignore

        assert result.success is False
        assert "Expected list" in result.error

    @pytest.mark.asyncio
    async def test_execute_missing_volume_analysis_raises(
        self,
        mock_validation_orchestrator,
    ):
        """Test execution without volume_analysis raises RuntimeError."""
        stage = ValidationStage(mock_validation_orchestrator)
        context = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1d").build()

        patterns = [MagicMock()]
        result = await stage.run(patterns, context)

        assert result.success is False
        assert "volume_analysis" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_single_pattern(
        self,
        mock_validation_orchestrator,
        sample_volume_analysis,
        mock_phase_info,
        mock_trading_range,
    ):
        """Test validation of a single pattern."""
        stage = ValidationStage(mock_validation_orchestrator)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("volume_analysis", sample_volume_analysis)
            .with_data("phase_info", mock_phase_info)
            .with_data("current_trading_range", mock_trading_range)
            .build()
        )

        patterns = [MagicMock()]
        result = await stage.run(patterns, context)

        assert result.success is True
        assert result.output.total_count == 1
        mock_validation_orchestrator.run_validation_chain.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_multiple_patterns(
        self,
        mock_validation_orchestrator,
        sample_volume_analysis,
        mock_phase_info,
        mock_trading_range,
    ):
        """Test validation of multiple patterns."""
        stage = ValidationStage(mock_validation_orchestrator)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("volume_analysis", sample_volume_analysis)
            .with_data("phase_info", mock_phase_info)
            .with_data("current_trading_range", mock_trading_range)
            .build()
        )

        patterns = [MagicMock(), MagicMock(), MagicMock()]
        result = await stage.run(patterns, context)

        assert result.success is True
        assert result.output.total_count == 3
        assert mock_validation_orchestrator.run_validation_chain.call_count == 3

    @pytest.mark.asyncio
    async def test_execute_stores_in_context(
        self,
        mock_validation_orchestrator,
        sample_volume_analysis,
    ):
        """Test that results are stored in context."""
        stage = ValidationStage(mock_validation_orchestrator)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("volume_analysis", sample_volume_analysis)
            .build()
        )

        patterns = [MagicMock()]
        await stage.run(patterns, context)

        validation_results = context.get("validation_results")
        assert validation_results is not None
        assert validation_results.total_count == 1

    @pytest.mark.asyncio
    async def test_execute_with_failing_validation(
        self,
        mock_validation_orchestrator_fail,
        sample_volume_analysis,
    ):
        """Test validation with failing patterns."""
        stage = ValidationStage(mock_validation_orchestrator_fail)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("volume_analysis", sample_volume_analysis)
            .build()
        )

        patterns = [MagicMock()]
        result = await stage.run(patterns, context)

        assert result.success is True  # Stage succeeds even if validation fails
        assert result.output.total_count == 1
        assert result.output.invalid_count == 1

    @pytest.mark.asyncio
    async def test_execute_records_timing(
        self,
        mock_validation_orchestrator,
        sample_volume_analysis,
    ):
        """Test that execution timing is recorded."""
        stage = ValidationStage(mock_validation_orchestrator)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("volume_analysis", sample_volume_analysis)
            .build()
        )

        patterns = [MagicMock()]
        result = await stage.run(patterns, context)

        assert result.execution_time_ms > 0
        timing = context.get_timing("validation")
        assert timing is not None
        assert timing.duration_ms > 0

    @pytest.mark.asyncio
    async def test_build_validation_context_with_test_volume_ratio(
        self,
        mock_validation_orchestrator,
        sample_volume_analysis,
    ):
        """Test that test_volume_ratio is extracted from pattern."""
        stage = ValidationStage(mock_validation_orchestrator)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("volume_analysis", sample_volume_analysis)
            .build()
        )

        # Pattern with test_volume_ratio
        pattern = MagicMock()
        pattern.test_volume_ratio = Decimal("0.5")

        await stage.run([pattern], context)

        # Verify run_validation_chain was called with context containing volume ratio
        call_args = mock_validation_orchestrator.run_validation_chain.call_args
        validation_context = call_args[0][0]
        assert validation_context.test_volume_ratio == Decimal("0.5")


# =============================
# Integration Tests (Stage Chaining)
# =============================


class TestPatternValidationChaining:
    """Tests for chaining pattern detection and validation stages."""

    @pytest.mark.asyncio
    async def test_pattern_to_validation_chaining(
        self,
        mock_spring_detector,
        mock_validation_orchestrator,
        mock_phase_info,
        sample_bars,
        sample_volume_analysis,
        mock_trading_range,
    ):
        """Test chaining PatternDetectionStage to ValidationStage."""
        # Setup pattern detection
        registry = DetectorRegistry()
        registry.register(WyckoffPhase.C, mock_spring_detector)
        pattern_stage = PatternDetectionStage(registry)

        # Setup validation
        validation_stage = ValidationStage(mock_validation_orchestrator)

        # Build context with all required data
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("bars", sample_bars)
            .with_data("volume_analysis", sample_volume_analysis)
            .with_data("current_trading_range", mock_trading_range)
            .with_data("phase_info", mock_phase_info)
            .build()
        )

        # Run pattern detection
        pattern_result = await pattern_stage.run(mock_phase_info, context)
        assert pattern_result.success is True
        patterns = pattern_result.output
        assert len(patterns) == 1

        # Run validation
        validation_result = await validation_stage.run(patterns, context)
        assert validation_result.success is True
        assert validation_result.output.total_count == 1

        # Verify context has all results
        assert context.get("patterns") is not None
        assert context.get("validation_results") is not None


# =============================
# Exception Propagation Tests
# =============================


class TestExceptionPropagation:
    """Tests for detector/orchestrator exception propagation."""

    @pytest.mark.asyncio
    async def test_detector_exception_propagates(
        self,
        mock_phase_info,
        sample_bars,
        sample_volume_analysis,
        mock_trading_range,
    ):
        """Test that detector exceptions are captured in result."""
        mock_detector = MagicMock()
        mock_detector.detect_all_springs.side_effect = RuntimeError("Detector error")

        registry = DetectorRegistry()
        registry.register(WyckoffPhase.C, mock_detector)
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

        result = await stage.run(mock_phase_info, context)

        assert result.success is False
        assert "Detector error" in result.error

    @pytest.mark.asyncio
    async def test_validation_orchestrator_exception_propagates(
        self,
        sample_volume_analysis,
    ):
        """Test that orchestrator exceptions are captured in result."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.run_validation_chain = AsyncMock(
            side_effect=RuntimeError("Validation error")
        )

        stage = ValidationStage(mock_orchestrator)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("volume_analysis", sample_volume_analysis)
            .build()
        )

        patterns = [MagicMock()]
        result = await stage.run(patterns, context)

        assert result.success is False
        assert "Validation error" in result.error
