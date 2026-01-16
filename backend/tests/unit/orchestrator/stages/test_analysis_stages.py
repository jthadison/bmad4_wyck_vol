"""
Unit tests for analysis pipeline stages.

Story 18.10.2: Volume, Range, and Phase Analysis Stages (AC1-5)
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.models.effort_result import EffortResult
from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import WyckoffPhase
from src.models.trading_range import RangeStatus
from src.models.volume_analysis import VolumeAnalysis
from src.orchestrator.pipeline.context import PipelineContextBuilder
from src.orchestrator.stages.phase_detection_stage import PhaseDetectionStage
from src.orchestrator.stages.range_detection_stage import RangeDetectionStage
from src.orchestrator.stages.volume_analysis_stage import VolumeAnalysisStage

# =============================
# Test Fixtures
# =============================


@pytest.fixture
def sample_bars() -> list[OHLCVBar]:
    """Create sample OHLCV bars for testing."""
    base_time = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)
    bars = []
    for i in range(50):
        # Use integer math to avoid floating-point precision issues
        increment = Decimal(i) / Decimal(10)  # 0.0, 0.1, 0.2, ...
        open_price = Decimal("150.00") + increment
        high_price = Decimal("151.00") + increment
        low_price = Decimal("149.00") + increment
        close_price = Decimal("150.50") + increment
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",  # lowercase required
            timestamp=base_time + timedelta(days=i),
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=1000000 + i * 10000,
            spread=high_price - low_price,  # Required field
        )
        bars.append(bar)
    return bars


@pytest.fixture
def sample_volume_analysis(sample_bars: list[OHLCVBar]) -> list[VolumeAnalysis]:
    """Create sample volume analysis results for testing."""
    results = []
    for i, bar in enumerate(sample_bars):
        # Use integer math to avoid floating-point precision issues
        increment = Decimal(i) / Decimal(100)  # 0.00, 0.01, 0.02, ...
        va = VolumeAnalysis(
            bar=bar,
            volume_ratio=Decimal("1.0") + increment,
            spread_ratio=Decimal("1.0"),
            close_position=Decimal("0.5"),  # Middle of bar
            effort_result=EffortResult.NORMAL,
        )
        results.append(va)
    return results


@pytest.fixture
def mock_volume_analyzer(sample_bars: list[OHLCVBar]):
    """Create mock VolumeAnalyzer."""
    analyzer = MagicMock()
    # Create volume analysis for each bar
    volume_analysis = [
        VolumeAnalysis(
            bar=bar,
            volume_ratio=Decimal("1.0"),
            spread_ratio=Decimal("1.0"),
            close_position=Decimal("0.5"),
            effort_result=EffortResult.NORMAL,
        )
        for bar in sample_bars
    ]
    analyzer.analyze.return_value = volume_analysis
    return analyzer


@pytest.fixture
def mock_range_detector():
    """Create mock TradingRangeDetector."""
    detector = MagicMock()
    # Mock will return empty list by default (tests can customize)
    detector.detect_ranges.return_value = []
    return detector


@pytest.fixture
def mock_phase_detector():
    """Create mock PhaseDetector."""
    detector = MagicMock()
    # Mock will return a basic PhaseInfo mock by default
    mock_phase_info = MagicMock()
    mock_phase_info.phase = WyckoffPhase.B
    mock_phase_info.confidence = 75
    mock_phase_info.duration = 30
    mock_phase_info.current_risk_level = "normal"
    detector.detect_phase.return_value = mock_phase_info
    return detector


def create_mock_trading_range(is_active: bool = True, end_index: int = 49) -> MagicMock:
    """Create a mock trading range with correct structure."""
    mock_range = MagicMock()  # Don't use spec to avoid property issues
    # Configure as PropertyMock for is_active to ensure it works correctly
    type(mock_range).is_active = property(lambda self: is_active)
    mock_range.end_index = end_index
    mock_range.status = RangeStatus.ACTIVE if is_active else RangeStatus.ARCHIVED
    return mock_range


# =============================
# VolumeAnalysisStage Tests
# =============================


class TestVolumeAnalysisStage:
    """Tests for VolumeAnalysisStage."""

    def test_stage_name(self, mock_volume_analyzer):
        """Test stage has correct name."""
        stage = VolumeAnalysisStage(mock_volume_analyzer)
        assert stage.name == "volume_analysis"

    def test_context_key(self, mock_volume_analyzer):
        """Test stage uses correct context key."""
        stage = VolumeAnalysisStage(mock_volume_analyzer)
        assert stage.CONTEXT_KEY == "volume_analysis"

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_volume_analyzer, sample_bars):
        """Test successful volume analysis execution."""
        stage = VolumeAnalysisStage(mock_volume_analyzer)
        context = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1d").build()

        result = await stage.run(sample_bars, context)

        assert result.success is True
        assert result.output is not None
        assert len(result.output) == 50
        assert result.stage_name == "volume_analysis"
        mock_volume_analyzer.analyze.assert_called_once_with(sample_bars)

    @pytest.mark.asyncio
    async def test_execute_stores_in_context(self, mock_volume_analyzer, sample_bars):
        """Test that results are stored in context."""
        stage = VolumeAnalysisStage(mock_volume_analyzer)
        context = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1d").build()

        await stage.run(sample_bars, context)

        stored = context.get(VolumeAnalysisStage.CONTEXT_KEY)
        assert stored is not None
        assert len(stored) == 50

    @pytest.mark.asyncio
    async def test_execute_empty_bars_raises(self, mock_volume_analyzer):
        """Test that empty bars list raises ValueError."""
        stage = VolumeAnalysisStage(mock_volume_analyzer)
        context = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1d").build()

        result = await stage.run([], context)

        assert result.success is False
        assert "empty bars" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_records_timing(self, mock_volume_analyzer, sample_bars):
        """Test that execution timing is recorded."""
        stage = VolumeAnalysisStage(mock_volume_analyzer)
        context = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1d").build()

        result = await stage.run(sample_bars, context)

        assert result.execution_time_ms > 0
        timing = context.get_timing("volume_analysis")
        assert timing is not None
        assert timing.duration_ms > 0


# =============================
# RangeDetectionStage Tests
# =============================


class TestRangeDetectionStage:
    """Tests for RangeDetectionStage."""

    def test_stage_name(self, mock_range_detector):
        """Test stage has correct name."""
        stage = RangeDetectionStage(mock_range_detector)
        assert stage.name == "range_detection"

    def test_context_keys(self, mock_range_detector):
        """Test stage uses correct context keys."""
        stage = RangeDetectionStage(mock_range_detector)
        assert stage.CONTEXT_KEY == "trading_ranges"
        assert stage.VOLUME_CONTEXT_KEY == "volume_analysis"

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_range_detector, sample_bars, sample_volume_analysis):
        """Test successful range detection execution."""
        mock_ranges = [create_mock_trading_range()]
        mock_range_detector.detect_ranges.return_value = mock_ranges

        stage = RangeDetectionStage(mock_range_detector)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("volume_analysis", sample_volume_analysis)
            .build()
        )

        result = await stage.run(sample_bars, context)

        assert result.success is True
        assert result.output is not None
        assert len(result.output) == 1
        assert result.stage_name == "range_detection"
        mock_range_detector.detect_ranges.assert_called_once_with(
            sample_bars, sample_volume_analysis
        )

    @pytest.mark.asyncio
    async def test_execute_stores_in_context(
        self, mock_range_detector, sample_bars, sample_volume_analysis
    ):
        """Test that results are stored in context."""
        mock_ranges = [create_mock_trading_range()]
        mock_range_detector.detect_ranges.return_value = mock_ranges

        stage = RangeDetectionStage(mock_range_detector)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("volume_analysis", sample_volume_analysis)
            .build()
        )

        await stage.run(sample_bars, context)

        stored = context.get(RangeDetectionStage.CONTEXT_KEY)
        assert stored is not None
        assert len(stored) == 1

    @pytest.mark.asyncio
    async def test_execute_empty_bars_raises(self, mock_range_detector, sample_volume_analysis):
        """Test that empty bars list raises ValueError."""
        stage = RangeDetectionStage(mock_range_detector)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("volume_analysis", sample_volume_analysis)
            .build()
        )

        result = await stage.run([], context)

        assert result.success is False
        assert "empty bars" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_missing_volume_analysis_raises(self, mock_range_detector, sample_bars):
        """Test that missing volume_analysis raises RuntimeError."""
        stage = RangeDetectionStage(mock_range_detector)
        context = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1d").build()

        result = await stage.run(sample_bars, context)

        assert result.success is False
        assert "volume_analysis" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_records_timing(
        self, mock_range_detector, sample_bars, sample_volume_analysis
    ):
        """Test that execution timing is recorded."""
        stage = RangeDetectionStage(mock_range_detector)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("volume_analysis", sample_volume_analysis)
            .build()
        )

        result = await stage.run(sample_bars, context)

        assert result.execution_time_ms > 0
        timing = context.get_timing("range_detection")
        assert timing is not None
        assert timing.duration_ms > 0


# =============================
# PhaseDetectionStage Tests
# =============================


class TestPhaseDetectionStage:
    """Tests for PhaseDetectionStage."""

    def test_stage_name(self, mock_phase_detector):
        """Test stage has correct name."""
        stage = PhaseDetectionStage(mock_phase_detector)
        assert stage.name == "phase_detection"

    def test_context_keys(self, mock_phase_detector):
        """Test stage uses correct context keys."""
        stage = PhaseDetectionStage(mock_phase_detector)
        assert stage.CONTEXT_KEY == "phase_info"
        assert stage.VOLUME_CONTEXT_KEY == "volume_analysis"
        assert stage.RANGES_CONTEXT_KEY == "trading_ranges"
        assert stage.CURRENT_RANGE_KEY == "current_trading_range"

    @pytest.mark.asyncio
    async def test_execute_success(
        self,
        mock_phase_detector,
        sample_bars,
        sample_volume_analysis,
    ):
        """Test successful phase detection execution."""
        mock_ranges = [create_mock_trading_range()]

        stage = PhaseDetectionStage(mock_phase_detector)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("volume_analysis", sample_volume_analysis)
            .with_data("trading_ranges", mock_ranges)
            .build()
        )

        result = await stage.run(sample_bars, context)

        assert result.success is True
        assert result.output is not None
        assert result.output.phase == WyckoffPhase.B
        assert result.stage_name == "phase_detection"
        mock_phase_detector.detect_phase.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_stores_in_context(
        self,
        mock_phase_detector,
        sample_bars,
        sample_volume_analysis,
    ):
        """Test that results are stored in context."""
        mock_ranges = [create_mock_trading_range()]

        stage = PhaseDetectionStage(mock_phase_detector)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("volume_analysis", sample_volume_analysis)
            .with_data("trading_ranges", mock_ranges)
            .build()
        )

        await stage.run(sample_bars, context)

        phase_info = context.get(PhaseDetectionStage.CONTEXT_KEY)
        current_range = context.get(PhaseDetectionStage.CURRENT_RANGE_KEY)

        assert phase_info is not None
        assert current_range is not None

    @pytest.mark.asyncio
    async def test_execute_no_active_ranges_returns_none(
        self,
        mock_phase_detector,
        sample_bars,
        sample_volume_analysis,
    ):
        """Test that no active ranges returns None."""
        # Create inactive range
        inactive_range = create_mock_trading_range(is_active=False)

        stage = PhaseDetectionStage(mock_phase_detector)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("volume_analysis", sample_volume_analysis)
            .with_data("trading_ranges", [inactive_range])
            .build()
        )

        result = await stage.run(sample_bars, context)

        assert result.success is True
        assert result.output is None
        mock_phase_detector.detect_phase.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_empty_ranges_returns_none(
        self,
        mock_phase_detector,
        sample_bars,
        sample_volume_analysis,
    ):
        """Test that empty ranges list returns None."""
        stage = PhaseDetectionStage(mock_phase_detector)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("volume_analysis", sample_volume_analysis)
            .with_data("trading_ranges", [])
            .build()
        )

        result = await stage.run(sample_bars, context)

        assert result.success is True
        assert result.output is None
        mock_phase_detector.detect_phase.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_empty_bars_raises(
        self,
        mock_phase_detector,
        sample_volume_analysis,
    ):
        """Test that empty bars list raises ValueError."""
        mock_ranges = [create_mock_trading_range()]

        stage = PhaseDetectionStage(mock_phase_detector)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("volume_analysis", sample_volume_analysis)
            .with_data("trading_ranges", mock_ranges)
            .build()
        )

        result = await stage.run([], context)

        assert result.success is False
        assert "empty bars" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_missing_volume_analysis_raises(
        self,
        mock_phase_detector,
        sample_bars,
    ):
        """Test that missing volume_analysis raises RuntimeError."""
        mock_ranges = [create_mock_trading_range()]

        stage = PhaseDetectionStage(mock_phase_detector)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("trading_ranges", mock_ranges)
            .build()
        )

        result = await stage.run(sample_bars, context)

        assert result.success is False
        assert "volume_analysis" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_missing_trading_ranges_raises(
        self,
        mock_phase_detector,
        sample_bars,
        sample_volume_analysis,
    ):
        """Test that missing trading_ranges raises RuntimeError."""
        stage = PhaseDetectionStage(mock_phase_detector)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("volume_analysis", sample_volume_analysis)
            .build()
        )

        result = await stage.run(sample_bars, context)

        assert result.success is False
        assert "trading_ranges" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_records_timing(
        self,
        mock_phase_detector,
        sample_bars,
        sample_volume_analysis,
    ):
        """Test that execution timing is recorded."""
        mock_ranges = [create_mock_trading_range()]

        stage = PhaseDetectionStage(mock_phase_detector)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("volume_analysis", sample_volume_analysis)
            .with_data("trading_ranges", mock_ranges)
            .build()
        )

        result = await stage.run(sample_bars, context)

        assert result.execution_time_ms > 0
        timing = context.get_timing("phase_detection")
        assert timing is not None
        assert timing.duration_ms > 0

    @pytest.mark.asyncio
    async def test_get_most_recent_active_range(
        self,
        mock_phase_detector,
    ):
        """Test selecting most recent active range."""
        ranges = [
            create_mock_trading_range(is_active=True, end_index=30),
            create_mock_trading_range(is_active=True, end_index=49),  # More recent
            create_mock_trading_range(is_active=False, end_index=60),  # Inactive
        ]

        stage = PhaseDetectionStage(mock_phase_detector)
        result = stage._get_most_recent_active_range(ranges)

        assert result is not None
        assert result.end_index == 49  # Most recent active


# =============================
# Integration Tests (Stage Chaining)
# =============================


class TestStageChaining:
    """Tests for chaining analysis stages together."""

    @pytest.mark.asyncio
    async def test_volume_to_range_chaining(
        self,
        mock_volume_analyzer,
        mock_range_detector,
        sample_bars,
    ):
        """Test chaining VolumeAnalysisStage to RangeDetectionStage."""
        mock_range_detector.detect_ranges.return_value = [create_mock_trading_range()]

        volume_stage = VolumeAnalysisStage(mock_volume_analyzer)
        range_stage = RangeDetectionStage(mock_range_detector)

        context = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1d").build()

        # Run volume stage first
        volume_result = await volume_stage.run(sample_bars, context)
        assert volume_result.success is True

        # Range stage should now have volume_analysis in context
        range_result = await range_stage.run(sample_bars, context)
        assert range_result.success is True

        # Verify context has both results
        assert context.get("volume_analysis") is not None
        assert context.get("trading_ranges") is not None

    @pytest.mark.asyncio
    async def test_full_pipeline_chaining(
        self,
        mock_volume_analyzer,
        mock_range_detector,
        mock_phase_detector,
        sample_bars,
    ):
        """Test chaining all three analysis stages."""
        mock_range_detector.detect_ranges.return_value = [create_mock_trading_range()]

        volume_stage = VolumeAnalysisStage(mock_volume_analyzer)
        range_stage = RangeDetectionStage(mock_range_detector)
        phase_stage = PhaseDetectionStage(mock_phase_detector)

        context = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1d").build()

        # Run stages in order
        volume_result = await volume_stage.run(sample_bars, context)
        assert volume_result.success is True

        range_result = await range_stage.run(sample_bars, context)
        assert range_result.success is True

        phase_result = await phase_stage.run(sample_bars, context)
        assert phase_result.success is True

        # Verify all results in context
        assert context.get("volume_analysis") is not None
        assert context.get("trading_ranges") is not None
        assert context.get("phase_info") is not None
        assert context.get("current_trading_range") is not None

        # Verify timing for all stages
        assert len(context.timings) == 3
