"""
Signal Generation Pipeline Stage.

Generates trade signals from validated patterns.

Story 18.10.4: Signal Generation and Risk Assessment Stages (AC1, AC3)

Type Flexibility Note:
    This stage uses `Any` for pattern and signal types intentionally.
    The pipeline supports multiple pattern types (Spring, SOS, LPS, UTAD)
    and signal types (TradeSignal, pattern-specific signals). Using `Any`
    allows different generator implementations without requiring a common
    base class. Type safety is enforced at the generator implementation level.

Error Handling Policy:
    Individual pattern errors are logged but do NOT fail the entire stage.
    This is intentional - a single bad pattern should not prevent other
    valid patterns from generating signals. All errors are logged at WARNING
    level with full context for debugging.
"""

from typing import Any, Protocol, runtime_checkable

import structlog

from src.orchestrator.pipeline.context import PipelineContext
from src.orchestrator.stages.base import PipelineStage
from src.orchestrator.stages.validation_stage import ValidationResults

logger = structlog.get_logger(__name__)


@runtime_checkable
class SignalGenerator(Protocol):
    """
    Protocol for signal generators.

    Signal generators take a validated pattern and trading context
    to produce a trade signal.
    """

    async def generate_signal(
        self,
        pattern: Any,
        trading_range: Any | None,
        context: PipelineContext,
    ) -> Any | None:
        """
        Generate a signal from a validated pattern.

        Args:
            pattern: Validated pattern to generate signal from
            trading_range: Current trading range context
            context: Pipeline context with symbol/timeframe

        Returns:
            Generated signal or None if signal generation fails
        """
        ...


class SignalGenerationStage(PipelineStage[ValidationResults, list[Any]]):
    """
    Pipeline stage for generating signals from validated patterns.

    Stage 6 in the analysis pipeline. Takes patterns that passed validation
    and generates trade signals with entry, stop, and target levels.

    Input: ValidationResults - Results from ValidationStage
    Output: list[Any] - List of generated signals (TradeSignal or pattern-specific)

    Context Keys Required:
        - "current_trading_range": TradingRange | None (from PhaseDetectionStage)
        - "phase_info": PhaseInfo | None (from PhaseDetectionStage)
        - "volume_analysis": list[VolumeAnalysis] (from VolumeAnalysisStage)

    Context Keys Set:
        - "generated_signals": list[Any] (for downstream stages)

    Example:
        >>> generator = MySignalGenerator()
        >>> stage = SignalGenerationStage(generator)
        >>> result = await stage.run(validation_results, context)
        >>> if result.success:
        ...     signals = result.output
        ...     print(f"Generated {len(signals)} signals")
    """

    CONTEXT_KEY = "generated_signals"
    RANGE_CONTEXT_KEY = "current_trading_range"

    def __init__(self, signal_generator: SignalGenerator) -> None:
        """
        Initialize the signal generation stage.

        Args:
            signal_generator: Generator implementing SignalGenerator protocol
        """
        self._generator = signal_generator

    @property
    def name(self) -> str:
        """Unique identifier for this stage."""
        return "signal_generation"

    async def execute(
        self,
        validation_results: ValidationResults,
        context: PipelineContext,
    ) -> list[Any]:
        """
        Generate signals from validated patterns.

        Iterates through patterns that passed validation and generates
        trade signals for each. Signals that fail generation are logged
        but don't cause stage failure.

        Args:
            validation_results: Results from ValidationStage with valid patterns
            context: Pipeline context with trading_range and other data

        Returns:
            List of generated signals

        Raises:
            TypeError: If validation_results is not ValidationResults
        """
        # Validate input type
        if not isinstance(validation_results, ValidationResults):
            raise TypeError(f"Expected ValidationResults, got {type(validation_results).__name__}")

        signals: list[Any] = []

        # Get valid patterns
        valid_patterns = validation_results.valid_patterns

        # Handle empty patterns list
        if not valid_patterns:
            logger.debug(
                "signal_generation_skipped",
                reason="No valid patterns to generate signals from",
                total_patterns=validation_results.total_count,
                invalid_count=validation_results.invalid_count,
                symbol=context.symbol,
                correlation_id=str(context.correlation_id),
            )
            context.set(self.CONTEXT_KEY, signals)
            return signals

        # Get trading range from context
        trading_range = context.get(self.RANGE_CONTEXT_KEY)

        logger.debug(
            "signal_generation_executing",
            valid_pattern_count=len(valid_patterns),
            has_trading_range=trading_range is not None,
            symbol=context.symbol,
            timeframe=context.timeframe,
            correlation_id=str(context.correlation_id),
        )

        # Generate signals for each valid pattern
        for i, pattern in enumerate(valid_patterns):
            logger.debug(
                "signal_generation_pattern_start",
                pattern_index=i,
                pattern_type=type(pattern).__name__,
                symbol=context.symbol,
                correlation_id=str(context.correlation_id),
            )

            try:
                signal = await self._generator.generate_signal(
                    pattern=pattern,
                    trading_range=trading_range,
                    context=context,
                )

                if signal is not None:
                    signals.append(signal)
                    logger.debug(
                        "signal_generation_pattern_success",
                        pattern_index=i,
                        signal_type=type(signal).__name__,
                        symbol=context.symbol,
                        correlation_id=str(context.correlation_id),
                    )
                else:
                    logger.debug(
                        "signal_generation_pattern_skipped",
                        pattern_index=i,
                        reason="Generator returned None",
                        symbol=context.symbol,
                        correlation_id=str(context.correlation_id),
                    )

            except Exception as e:
                # INTENTIONAL: Log error but don't fail entire stage.
                # A single bad pattern should not prevent other valid patterns
                # from generating signals. See module docstring for policy.
                logger.warning(
                    "signal_generation_pattern_error",
                    pattern_index=i,
                    pattern_type=type(pattern).__name__,
                    error=str(e),
                    error_type=type(e).__name__,
                    symbol=context.symbol,
                    correlation_id=str(context.correlation_id),
                )

        context.set(self.CONTEXT_KEY, signals)

        logger.debug(
            "signal_generation_complete",
            valid_patterns=len(valid_patterns),
            signals_generated=len(signals),
            symbol=context.symbol,
            correlation_id=str(context.correlation_id),
        )

        return signals
