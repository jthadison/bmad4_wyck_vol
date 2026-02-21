"""
Unit tests for signal generation and risk assessment pipeline stages.

Story 18.10.4: Signal Generation and Risk Assessment Stages (AC5)
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.models.validation import ValidationChain, ValidationStatus
from src.orchestrator.pipeline.context import PipelineContextBuilder
from src.orchestrator.stages.risk_assessment_stage import RiskAssessmentStage
from src.orchestrator.stages.signal_generation_stage import SignalGenerationStage
from src.orchestrator.stages.validation_stage import ValidationResults

# =============================
# Test Fixtures
# =============================


@pytest.fixture
def mock_trading_range():
    """Create mock trading range."""
    mock = MagicMock()
    mock.is_active = True
    mock.end_index = 49
    return mock


@pytest.fixture
def mock_signal_generator():
    """Create mock signal generator."""
    generator = MagicMock()
    mock_signal = MagicMock()
    mock_signal.symbol = "AAPL"
    generator.generate_signal = AsyncMock(return_value=mock_signal)
    return generator


@pytest.fixture
def mock_signal_generator_returns_none():
    """Create mock signal generator that returns None."""
    generator = MagicMock()
    generator.generate_signal = AsyncMock(return_value=None)
    return generator


@pytest.fixture
def mock_signal_generator_raises():
    """Create mock signal generator that raises an exception."""
    generator = MagicMock()
    generator.generate_signal = AsyncMock(side_effect=RuntimeError("Generator error"))
    return generator


@pytest.fixture
def mock_risk_assessor():
    """Create mock risk assessor."""
    assessor = MagicMock()
    mock_assessed_signal = MagicMock()
    mock_assessed_signal.symbol = "AAPL"
    mock_assessed_signal.position_size = 100
    assessor.apply_sizing = AsyncMock(return_value=mock_assessed_signal)
    return assessor


@pytest.fixture
def mock_risk_assessor_rejects():
    """Create mock risk assessor that rejects signals."""
    assessor = MagicMock()
    assessor.apply_sizing = AsyncMock(return_value=None)
    return assessor


@pytest.fixture
def mock_risk_assessor_raises():
    """Create mock risk assessor that raises an exception."""
    assessor = MagicMock()
    assessor.apply_sizing = AsyncMock(side_effect=RuntimeError("Risk error"))
    return assessor


@pytest.fixture
def empty_validation_results():
    """Create empty validation results."""
    return ValidationResults()


@pytest.fixture
def validation_results_with_valid_patterns():
    """Create validation results with valid patterns."""
    results = ValidationResults()
    chain1 = ValidationChain(pattern_id=uuid4())
    pattern1 = MagicMock()
    pattern1.pattern_type = "SPRING"
    results.add(chain1, pattern1)

    chain2 = ValidationChain(pattern_id=uuid4())
    pattern2 = MagicMock()
    pattern2.pattern_type = "SOS"
    results.add(chain2, pattern2)
    return results


@pytest.fixture
def validation_results_with_invalid_patterns():
    """Create validation results with invalid patterns."""
    results = ValidationResults()
    chain1 = ValidationChain(pattern_id=uuid4())
    chain1.overall_status = ValidationStatus.FAIL
    pattern1 = MagicMock()
    results.add(chain1, pattern1)
    return results


@pytest.fixture
def validation_results_mixed():
    """Create validation results with mix of valid and invalid patterns."""
    results = ValidationResults()

    # Valid pattern
    chain1 = ValidationChain(pattern_id=uuid4())
    pattern1 = MagicMock()
    pattern1.pattern_type = "SPRING"
    results.add(chain1, pattern1)

    # Invalid pattern
    chain2 = ValidationChain(pattern_id=uuid4())
    chain2.overall_status = ValidationStatus.FAIL
    pattern2 = MagicMock()
    results.add(chain2, pattern2)

    return results


# =============================
# SignalGenerationStage Tests
# =============================


class TestSignalGenerationStage:
    """Tests for SignalGenerationStage."""

    def test_stage_name(self, mock_signal_generator):
        """Test stage has correct name."""
        stage = SignalGenerationStage(mock_signal_generator)
        assert stage.name == "signal_generation"

    def test_context_keys(self, mock_signal_generator):
        """Test stage uses correct context keys."""
        stage = SignalGenerationStage(mock_signal_generator)
        assert stage.CONTEXT_KEY == "generated_signals"
        assert stage.RANGE_CONTEXT_KEY == "current_trading_range"

    @pytest.mark.asyncio
    async def test_execute_empty_validation_results(
        self,
        mock_signal_generator,
        empty_validation_results,
    ):
        """Test execution with empty validation results."""
        stage = SignalGenerationStage(mock_signal_generator)
        context = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1d").build()

        result = await stage.run(empty_validation_results, context)

        assert result.success is True
        assert result.output == []
        assert context.get("generated_signals") == []
        mock_signal_generator.generate_signal.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_no_valid_patterns(
        self,
        mock_signal_generator,
        validation_results_with_invalid_patterns,
    ):
        """Test execution with only invalid patterns."""
        stage = SignalGenerationStage(mock_signal_generator)
        context = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1d").build()

        result = await stage.run(validation_results_with_invalid_patterns, context)

        assert result.success is True
        assert result.output == []
        mock_signal_generator.generate_signal.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_invalid_input_type(self, mock_signal_generator):
        """Test execution with non-ValidationResults input raises TypeError."""
        stage = SignalGenerationStage(mock_signal_generator)
        context = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1d").build()

        result = await stage.run("not a ValidationResults", context)  # type: ignore

        assert result.success is False
        assert "Expected ValidationResults" in result.error

    @pytest.mark.asyncio
    async def test_execute_single_valid_pattern(
        self,
        mock_signal_generator,
        mock_trading_range,
    ):
        """Test signal generation for a single valid pattern."""
        results = ValidationResults()
        chain = ValidationChain(pattern_id=uuid4())
        pattern = MagicMock()
        results.add(chain, pattern)

        stage = SignalGenerationStage(mock_signal_generator)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("current_trading_range", mock_trading_range)
            .build()
        )

        result = await stage.run(results, context)

        assert result.success is True
        assert len(result.output) == 1
        mock_signal_generator.generate_signal.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_multiple_valid_patterns(
        self,
        mock_signal_generator,
        validation_results_with_valid_patterns,
        mock_trading_range,
    ):
        """Test signal generation for multiple valid patterns."""
        stage = SignalGenerationStage(mock_signal_generator)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("current_trading_range", mock_trading_range)
            .build()
        )

        result = await stage.run(validation_results_with_valid_patterns, context)

        assert result.success is True
        assert len(result.output) == 2
        assert mock_signal_generator.generate_signal.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_mixed_results_only_generates_for_valid(
        self,
        mock_signal_generator,
        validation_results_mixed,
        mock_trading_range,
    ):
        """Test that signals are only generated for valid patterns."""
        stage = SignalGenerationStage(mock_signal_generator)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("current_trading_range", mock_trading_range)
            .build()
        )

        result = await stage.run(validation_results_mixed, context)

        assert result.success is True
        assert len(result.output) == 1  # Only 1 valid pattern
        mock_signal_generator.generate_signal.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_generator_returns_none(
        self,
        mock_signal_generator_returns_none,
        validation_results_with_valid_patterns,
        mock_trading_range,
    ):
        """Test handling when generator returns None."""
        stage = SignalGenerationStage(mock_signal_generator_returns_none)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("current_trading_range", mock_trading_range)
            .build()
        )

        result = await stage.run(validation_results_with_valid_patterns, context)

        assert result.success is True
        assert len(result.output) == 0  # All returned None

    @pytest.mark.asyncio
    async def test_execute_generator_raises_exception(
        self,
        mock_signal_generator_raises,
        validation_results_with_valid_patterns,
        mock_trading_range,
    ):
        """Test that generator exceptions don't fail the entire stage."""
        stage = SignalGenerationStage(mock_signal_generator_raises)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("current_trading_range", mock_trading_range)
            .build()
        )

        result = await stage.run(validation_results_with_valid_patterns, context)

        # Stage succeeds even though individual generators failed
        assert result.success is True
        assert len(result.output) == 0

    @pytest.mark.asyncio
    async def test_execute_stores_in_context(
        self,
        mock_signal_generator,
        validation_results_with_valid_patterns,
        mock_trading_range,
    ):
        """Test that signals are stored in context."""
        stage = SignalGenerationStage(mock_signal_generator)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("current_trading_range", mock_trading_range)
            .build()
        )

        await stage.run(validation_results_with_valid_patterns, context)

        signals = context.get("generated_signals")
        assert signals is not None
        assert len(signals) == 2

    @pytest.mark.asyncio
    async def test_execute_records_timing(
        self,
        mock_signal_generator,
        validation_results_with_valid_patterns,
        mock_trading_range,
    ):
        """Test that execution timing is recorded."""
        stage = SignalGenerationStage(mock_signal_generator)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("current_trading_range", mock_trading_range)
            .build()
        )

        result = await stage.run(validation_results_with_valid_patterns, context)

        assert result.execution_time_ms > 0
        timing = context.get_timing("signal_generation")
        assert timing is not None
        assert timing.duration_ms > 0

    @pytest.mark.asyncio
    async def test_execute_passes_context_to_generator(
        self,
        mock_signal_generator,
        mock_trading_range,
    ):
        """Test that context and trading range are passed to generator."""
        results = ValidationResults()
        chain = ValidationChain(pattern_id=uuid4())
        pattern = MagicMock()
        pattern.pattern_type = "SPRING"  # Add identifiable attribute
        results.add(chain, pattern)

        # Mark the trading range for identification
        mock_trading_range.test_marker = "expected_range"

        stage = SignalGenerationStage(mock_signal_generator)
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("current_trading_range", mock_trading_range)
            .build()
        )

        await stage.run(results, context)

        # Verify generator was called with correct arguments
        mock_signal_generator.generate_signal.assert_called_once()
        call_kwargs = mock_signal_generator.generate_signal.call_args.kwargs
        # Check pattern has expected attribute (proves same object)
        assert call_kwargs["pattern"].pattern_type == "SPRING"
        # Check trading range has expected marker
        assert call_kwargs["trading_range"].test_marker == "expected_range"
        assert call_kwargs["context"].symbol == "AAPL"


# =============================
# RiskAssessmentStage Tests
# =============================


class TestRiskAssessmentStage:
    """Tests for RiskAssessmentStage."""

    def test_stage_name(self, mock_risk_assessor):
        """Test stage has correct name."""
        stage = RiskAssessmentStage(mock_risk_assessor)
        assert stage.name == "risk_assessment"

    def test_context_keys(self, mock_risk_assessor):
        """Test stage uses correct context keys."""
        stage = RiskAssessmentStage(mock_risk_assessor)
        assert stage.CONTEXT_KEY == "assessed_signals"
        assert stage.RANGE_CONTEXT_KEY == "current_trading_range"
        assert stage.PORTFOLIO_CONTEXT_KEY == "portfolio_context"

    @pytest.mark.asyncio
    async def test_execute_empty_signals(self, mock_risk_assessor):
        """Test execution with empty signals list."""
        stage = RiskAssessmentStage(mock_risk_assessor)
        context = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1d").build()

        result = await stage.run([], context)

        assert result.success is True
        assert result.output == []
        assert context.get("assessed_signals") == []
        mock_risk_assessor.apply_sizing.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_invalid_input_type(self, mock_risk_assessor):
        """Test execution with non-list input raises TypeError."""
        stage = RiskAssessmentStage(mock_risk_assessor)
        context = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1d").build()

        result = await stage.run("not a list", context)  # type: ignore

        assert result.success is False
        assert "Expected list" in result.error

    @pytest.mark.asyncio
    async def test_execute_single_signal(self, mock_risk_assessor):
        """Test risk assessment for a single signal."""
        stage = RiskAssessmentStage(mock_risk_assessor)
        context = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1d").build()

        signals = [MagicMock()]
        result = await stage.run(signals, context)

        assert result.success is True
        assert len(result.output) == 1
        mock_risk_assessor.apply_sizing.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_multiple_signals(self, mock_risk_assessor):
        """Test risk assessment for multiple signals."""
        stage = RiskAssessmentStage(mock_risk_assessor)
        context = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1d").build()

        signals = [MagicMock(), MagicMock(), MagicMock()]
        result = await stage.run(signals, context)

        assert result.success is True
        assert len(result.output) == 3
        assert mock_risk_assessor.apply_sizing.call_count == 3

    @pytest.mark.asyncio
    async def test_execute_assessor_rejects_signal(self, mock_risk_assessor_rejects):
        """Test handling when assessor rejects signals."""
        stage = RiskAssessmentStage(mock_risk_assessor_rejects)
        context = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1d").build()

        signals = [MagicMock(), MagicMock()]
        result = await stage.run(signals, context)

        assert result.success is True
        assert len(result.output) == 0  # All rejected

    @pytest.mark.asyncio
    async def test_execute_assessor_raises_exception(self, mock_risk_assessor_raises):
        """Test that assessor exceptions don't fail the entire stage."""
        stage = RiskAssessmentStage(mock_risk_assessor_raises)
        context = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1d").build()

        signals = [MagicMock(), MagicMock()]
        result = await stage.run(signals, context)

        # Stage succeeds even though individual assessments failed
        assert result.success is True
        assert len(result.output) == 0

    @pytest.mark.asyncio
    async def test_execute_partial_rejection(self, mock_risk_assessor):
        """Test mix of approved and rejected signals."""
        # Create assessor that alternates approve/reject
        assessor = MagicMock()
        approved_signal = MagicMock()
        assessor.apply_sizing = AsyncMock(side_effect=[approved_signal, None, approved_signal])

        stage = RiskAssessmentStage(assessor)
        context = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1d").build()

        signals = [MagicMock(), MagicMock(), MagicMock()]
        result = await stage.run(signals, context)

        assert result.success is True
        assert len(result.output) == 2  # 2 approved, 1 rejected

    @pytest.mark.asyncio
    async def test_execute_stores_in_context(self, mock_risk_assessor):
        """Test that assessed signals are stored in context."""
        stage = RiskAssessmentStage(mock_risk_assessor)
        context = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1d").build()

        signals = [MagicMock(), MagicMock()]
        await stage.run(signals, context)

        assessed = context.get("assessed_signals")
        assert assessed is not None
        assert len(assessed) == 2

    @pytest.mark.asyncio
    async def test_execute_records_timing(self, mock_risk_assessor):
        """Test that execution timing is recorded."""
        stage = RiskAssessmentStage(mock_risk_assessor)
        context = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1d").build()

        signals = [MagicMock()]
        result = await stage.run(signals, context)

        assert result.execution_time_ms > 0
        timing = context.get_timing("risk_assessment")
        assert timing is not None
        assert timing.duration_ms > 0

    @pytest.mark.asyncio
    async def test_execute_passes_context_to_assessor(self, mock_risk_assessor):
        """Test that context is passed to assessor."""
        stage = RiskAssessmentStage(mock_risk_assessor)
        context = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1d").build()

        signal = MagicMock()
        await stage.run([signal], context)

        call_args = mock_risk_assessor.apply_sizing.call_args
        assert call_args.kwargs["signal"] is signal
        assert call_args.kwargs["context"] is context


# =============================
# Integration Tests (Stage Chaining)
# =============================


class TestSignalRiskStageChaining:
    """Tests for chaining signal generation and risk assessment stages."""

    @pytest.mark.asyncio
    async def test_signal_to_risk_chaining(
        self,
        mock_signal_generator,
        mock_risk_assessor,
        mock_trading_range,
    ):
        """Test chaining SignalGenerationStage to RiskAssessmentStage."""
        # Create validation results with valid pattern
        results = ValidationResults()
        chain = ValidationChain(pattern_id=uuid4())
        pattern = MagicMock()
        results.add(chain, pattern)

        # Setup stages
        signal_stage = SignalGenerationStage(mock_signal_generator)
        risk_stage = RiskAssessmentStage(mock_risk_assessor)

        # Build context
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("current_trading_range", mock_trading_range)
            .build()
        )

        # Run signal generation
        signal_result = await signal_stage.run(results, context)
        assert signal_result.success is True
        signals = signal_result.output
        assert len(signals) == 1

        # Run risk assessment
        risk_result = await risk_stage.run(signals, context)
        assert risk_result.success is True
        assert len(risk_result.output) == 1

        # Verify context has all results
        assert context.get("generated_signals") is not None
        assert context.get("assessed_signals") is not None

    @pytest.mark.asyncio
    async def test_empty_signals_propagate_through_chain(
        self,
        mock_signal_generator_returns_none,
        mock_risk_assessor,
        mock_trading_range,
    ):
        """Test that empty signals propagate correctly through chain."""
        # Create validation results with valid pattern
        results = ValidationResults()
        chain = ValidationChain(pattern_id=uuid4())
        pattern = MagicMock()
        results.add(chain, pattern)

        # Setup stages
        signal_stage = SignalGenerationStage(mock_signal_generator_returns_none)
        risk_stage = RiskAssessmentStage(mock_risk_assessor)

        # Build context
        context = (
            PipelineContextBuilder()
            .with_symbol("AAPL")
            .with_timeframe("1d")
            .with_data("current_trading_range", mock_trading_range)
            .build()
        )

        # Run signal generation (returns no signals)
        signal_result = await signal_stage.run(results, context)
        assert signal_result.success is True
        signals = signal_result.output
        assert len(signals) == 0

        # Run risk assessment (receives empty list)
        risk_result = await risk_stage.run(signals, context)
        assert risk_result.success is True
        assert len(risk_result.output) == 0

        # Risk assessor should not be called
        mock_risk_assessor.apply_sizing.assert_not_called()


# =============================
# Protocol Compliance Tests
# =============================


class TestRiskAdapterRejectsWhenContextMissing:
    """P0-2: _RiskManagerAdapter must reject signals when risk context is absent."""

    @pytest.mark.asyncio
    async def test_risk_adapter_rejects_when_portfolio_context_missing(self):
        """Signal REJECTED (None) when portfolio_context not in context."""
        from decimal import Decimal

        from src.orchestrator.orchestrator_facade import _RiskManagerAdapter

        adapter = _RiskManagerAdapter(MagicMock())
        ctx = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1d").build()
        ctx.set("current_trading_range", MagicMock())
        # portfolio_context intentionally NOT set

        sig = MagicMock()
        sig.entry_price = Decimal("100.00")
        sig.stop_loss = Decimal("95.00")
        sig.target_price = Decimal("115.00")
        sig.symbol = "AAPL"
        sig.pattern_type = "SPRING"
        sig.campaign_id = None

        result = await adapter.apply_sizing(sig, ctx)
        assert result is None, "Must reject signal when portfolio_context is missing"

    @pytest.mark.asyncio
    async def test_risk_adapter_rejects_when_trading_range_missing(self):
        """Signal REJECTED (None) when trading_range not in context."""
        from decimal import Decimal

        from src.orchestrator.orchestrator_facade import _RiskManagerAdapter

        adapter = _RiskManagerAdapter(MagicMock())
        ctx = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1d").build()
        ctx.set("portfolio_context", MagicMock())
        # current_trading_range intentionally NOT set

        sig = MagicMock()
        sig.entry_price = Decimal("100.00")
        sig.stop_loss = Decimal("95.00")
        sig.target_price = Decimal("115.00")
        sig.symbol = "AAPL"
        sig.pattern_type = "SPRING"
        sig.campaign_id = None

        result = await adapter.apply_sizing(sig, ctx)
        assert result is None, "Must reject signal when trading_range is missing"

    @pytest.mark.asyncio
    async def test_risk_adapter_rejects_when_both_missing(self):
        """Signal REJECTED (None) when both context fields are missing."""
        from decimal import Decimal

        from src.orchestrator.orchestrator_facade import _RiskManagerAdapter

        adapter = _RiskManagerAdapter(MagicMock())
        ctx = PipelineContextBuilder().with_symbol("AAPL").with_timeframe("1d").build()
        # Neither portfolio_context nor current_trading_range set

        sig = MagicMock()
        sig.entry_price = Decimal("100.00")
        sig.stop_loss = Decimal("95.00")
        sig.target_price = Decimal("115.00")
        sig.symbol = "AAPL"
        sig.pattern_type = "SPRING"
        sig.campaign_id = None

        result = await adapter.apply_sizing(sig, ctx)
        assert result is None


class TestProtocolCompliance:
    """Tests for protocol compliance."""

    def test_signal_generator_protocol(self):
        """Test that mock generator implements SignalGenerator protocol."""
        from src.orchestrator.stages.signal_generation_stage import SignalGenerator

        generator = MagicMock()
        generator.generate_signal = AsyncMock(return_value=MagicMock())

        # Check it implements the protocol
        assert hasattr(generator, "generate_signal")
        assert isinstance(generator, SignalGenerator)

    def test_risk_assessor_protocol(self):
        """Test that mock assessor implements RiskAssessor protocol."""
        from src.orchestrator.stages.risk_assessment_stage import RiskAssessor

        assessor = MagicMock()
        assessor.apply_sizing = AsyncMock(return_value=MagicMock())

        # Check it implements the protocol
        assert hasattr(assessor, "apply_sizing")
        assert isinstance(assessor, RiskAssessor)
