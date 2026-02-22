"""
Validation Pipeline Stage.

Runs validation chain on detected patterns.

Story 18.10.3: Pattern Detection and Validation Stages (AC2, AC4)
"""

from datetime import UTC
from decimal import Decimal
from typing import Any

import structlog

from src.models.validation import ValidationChain, ValidationContext
from src.orchestrator.pipeline.context import PipelineContext
from src.orchestrator.stages.base import PipelineStage
from src.signal_generator.validation_chain import ValidationChainOrchestrator

logger = structlog.get_logger(__name__)


class ValidationResults:
    """
    Aggregated results from validating multiple patterns.

    Collects ValidationChain results for each pattern and provides
    convenience methods for querying validation outcomes.

    Attributes:
        results: List of ValidationChain results
        patterns: Original patterns that were validated

    Example:
        >>> results = ValidationResults()
        >>> results.add(validation_chain, pattern)
        >>> print(f"Valid: {results.valid_count}, Invalid: {results.invalid_count}")
    """

    def __init__(self) -> None:
        """Initialize empty results."""
        self._results: list[tuple[ValidationChain, Any]] = []

    def add(self, chain: ValidationChain, pattern: Any) -> None:
        """
        Add a validation result for a pattern.

        Args:
            chain: ValidationChain with validation results
            pattern: Original pattern that was validated
        """
        self._results.append((chain, pattern))

    @property
    def results(self) -> list[ValidationChain]:
        """Get list of validation chains."""
        return [chain for chain, _ in self._results]

    @property
    def patterns(self) -> list[Any]:
        """Get list of validated patterns."""
        return [pattern for _, pattern in self._results]

    @property
    def valid_patterns(self) -> list[Any]:
        """Get patterns that passed validation."""
        return [pattern for chain, pattern in self._results if chain.is_valid]

    @property
    def invalid_patterns(self) -> list[Any]:
        """Get patterns that failed validation."""
        return [pattern for chain, pattern in self._results if not chain.is_valid]

    @property
    def valid_count(self) -> int:
        """Count of patterns that passed validation."""
        return len(self.valid_patterns)

    @property
    def invalid_count(self) -> int:
        """Count of patterns that failed validation."""
        return len(self.invalid_patterns)

    @property
    def total_count(self) -> int:
        """Total number of patterns validated."""
        return len(self._results)

    def get_chain_for_pattern(self, pattern: Any) -> ValidationChain | None:
        """
        Get validation chain for a specific pattern.

        Args:
            pattern: Pattern to look up

        Returns:
            ValidationChain for the pattern, or None if not found
        """
        for chain, p in self._results:
            if p is pattern:
                return chain
        return None

    def __len__(self) -> int:
        """Return number of validated patterns."""
        return len(self._results)

    def __iter__(self):
        """Iterate over (chain, pattern) tuples."""
        return iter(self._results)


class ValidationStage(PipelineStage[list[Any], ValidationResults]):
    """
    Pipeline stage for pattern validation.

    Runs multi-stage validation chain on each detected pattern.
    Validation includes: Volume -> Phase -> Levels -> Risk -> Strategy

    Input: list[Any] - List of patterns from PatternDetectionStage
    Output: ValidationResults - Aggregated validation results

    Context Keys Required:
        - "volume_analysis": list[VolumeAnalysis] (from VolumeAnalysisStage)
        - "phase_info": PhaseInfo | None (from PhaseDetectionStage)
        - "current_trading_range": TradingRange | None (from PhaseDetectionStage)

    Context Keys Set:
        - "validation_results": ValidationResults (for downstream stages)

    Example:
        >>> orchestrator = ValidationChainOrchestrator([...])
        >>> stage = ValidationStage(orchestrator)
        >>> result = await stage.run(patterns, context)
        >>> if result.success:
        ...     validation_results = result.output
        ...     print(f"Valid: {validation_results.valid_count}")
    """

    CONTEXT_KEY = "validation_results"
    VOLUME_CONTEXT_KEY = "volume_analysis"
    PHASE_CONTEXT_KEY = "phase_info"
    RANGE_CONTEXT_KEY = "current_trading_range"

    def __init__(self, validation_orchestrator: ValidationChainOrchestrator) -> None:
        """
        Initialize the validation stage.

        Args:
            validation_orchestrator: Orchestrator with configured validators
        """
        self._orchestrator = validation_orchestrator

    @property
    def name(self) -> str:
        """Unique identifier for this stage."""
        return "validation"

    async def execute(
        self,
        patterns: list[Any],
        context: PipelineContext,
    ) -> ValidationResults:
        """
        Validate patterns through validation chain.

        Runs each pattern through the 5-stage validation pipeline:
        Volume -> Phase -> Levels -> Risk -> Strategy

        Args:
            patterns: List of patterns from PatternDetectionStage
            context: Pipeline context with volume_analysis, phase_info, trading_range

        Returns:
            ValidationResults with validation chains for each pattern

        Raises:
            TypeError: If patterns is not a list
            RuntimeError: If required context keys not found
        """
        # Read patterns from context if available (set by PatternDetectionStage).
        # The coordinator passes initial_input (bars) to all stages; cross-stage
        # data flows through PipelineContext.
        context_patterns: list[Any] | None = context.get("patterns")
        if context_patterns is not None:
            patterns = context_patterns

        # Validate input type
        if not isinstance(patterns, list):
            raise TypeError(f"Expected list of patterns, got {type(patterns).__name__}")

        results = ValidationResults()

        # Handle empty patterns list
        if not patterns:
            logger.debug(
                "validation_skipped",
                reason="No patterns to validate",
                symbol=context.symbol,
                correlation_id=str(context.correlation_id),
            )
            context.set(self.CONTEXT_KEY, results)
            return results

        # Get required context data
        volume_analysis = context.get(self.VOLUME_CONTEXT_KEY)
        if volume_analysis is None:
            raise RuntimeError(
                f"Required context key '{self.VOLUME_CONTEXT_KEY}' not found. "
                "Ensure VolumeAnalysisStage runs before ValidationStage."
            )

        phase_info = context.get(self.PHASE_CONTEXT_KEY)
        trading_range = context.get(self.RANGE_CONTEXT_KEY)

        logger.debug(
            "validation_executing",
            pattern_count=len(patterns),
            has_phase_info=phase_info is not None,
            has_trading_range=trading_range is not None,
            symbol=context.symbol,
            timeframe=context.timeframe,
            correlation_id=str(context.correlation_id),
        )

        # Validate each pattern
        for i, pattern in enumerate(patterns):
            validation_context = self._build_validation_context(
                pattern=pattern,
                volume_analysis=volume_analysis,
                phase_info=phase_info,
                trading_range=trading_range,
                context=context,
            )

            logger.debug(
                "validation_pattern_start",
                pattern_index=i,
                pattern_type=type(pattern).__name__,
                symbol=context.symbol,
                correlation_id=str(context.correlation_id),
            )

            chain = await self._orchestrator.run_validation_chain(validation_context)
            results.add(chain, pattern)

            logger.debug(
                "validation_pattern_complete",
                pattern_index=i,
                is_valid=chain.is_valid,
                overall_status=chain.overall_status.value,
                rejection_stage=chain.rejection_stage,
                symbol=context.symbol,
                correlation_id=str(context.correlation_id),
            )

        context.set(self.CONTEXT_KEY, results)

        logger.debug(
            "validation_complete",
            total_patterns=results.total_count,
            valid_count=results.valid_count,
            invalid_count=results.invalid_count,
            symbol=context.symbol,
            correlation_id=str(context.correlation_id),
        )

        return results

    def _build_validation_context(
        self,
        pattern: Any,
        volume_analysis: list,
        phase_info: Any | None,
        trading_range: Any | None,
        context: PipelineContext,
    ) -> ValidationContext:
        """
        Build ValidationContext for a pattern.

        Extracts relevant data from pipeline context and pattern
        to create a ValidationContext suitable for the validation chain.

        Story 25.16: Find matching VolumeAnalysis from list by pattern timestamp.
        VolumeValidator expects a single VolumeAnalysis object, not a list.

        Args:
            pattern: Pattern to validate
            volume_analysis: List of VolumeAnalysis from VolumeAnalysisStage
            phase_info: Phase info from PhaseDetectionStage
            trading_range: Trading range from PhaseDetectionStage
            context: Pipeline context for symbol/timeframe

        Returns:
            ValidationContext configured for the pattern
        """
        # Story 25.16: Find matching VolumeAnalysis by pattern timestamp
        # VolumeValidator expects single object, not list
        matched_volume_analysis = None
        if volume_analysis:
            # Get pattern timestamp (handles both direct fields and nested pattern.bar.timestamp)
            pattern_timestamp = (
                getattr(pattern, "bar_timestamp", None)
                or getattr(pattern, "timestamp", None)
                or (getattr(pattern, "bar", None).timestamp if hasattr(pattern, "bar") else None)
            )

            if pattern_timestamp:
                # Normalize pattern timestamp to UTC for comparison
                # (handles timezone-aware vs naive datetime equality)
                if pattern_timestamp.tzinfo is None:
                    pattern_timestamp_utc = pattern_timestamp.replace(tzinfo=UTC)
                else:
                    pattern_timestamp_utc = pattern_timestamp.astimezone(UTC)

                # Find VolumeAnalysis matching pattern bar timestamp
                matched_volume_analysis = next(
                    (
                        va
                        for va in volume_analysis
                        if va.bar.timestamp.astimezone(UTC) == pattern_timestamp_utc
                    ),
                    None,
                )

        # Extract volume ratio from pattern if available
        # Safely check for Decimal-compatible values only
        test_volume_ratio = None
        try:
            if hasattr(pattern, "test_volume_ratio"):
                value = pattern.test_volume_ratio
                if value is not None and isinstance(value, int | float | str | Decimal):
                    test_volume_ratio = value
            elif hasattr(pattern, "volume_ratio"):
                value = pattern.volume_ratio
                if value is not None and isinstance(value, int | float | str | Decimal):
                    test_volume_ratio = value
        except (AttributeError, TypeError):
            # If attribute access fails or value is incompatible, leave as None
            pass

        return ValidationContext(
            pattern=pattern,
            symbol=context.symbol,
            timeframe=context.timeframe,
            volume_analysis=matched_volume_analysis,  # Single object or None
            test_volume_ratio=test_volume_ratio,
            phase_info=phase_info,
            trading_range=trading_range,
        )
