"""
Risk Assessment Pipeline Stage.

Applies risk management and position sizing to signals.

Story 18.10.4: Signal Generation and Risk Assessment Stages (AC2, AC4)

Type Flexibility Note:
    This stage uses `Any` for signal types intentionally. The pipeline
    supports multiple signal types (TradeSignal, pattern-specific signals)
    and the assessor may return enhanced versions. Using `Any` allows
    different assessor implementations without requiring a common base class.
    Type safety is enforced at the assessor implementation level.

Error Handling Policy:
    Individual signal errors are logged but do NOT fail the entire stage.
    This is intentional - a single bad signal should not prevent other
    valid signals from being assessed. All errors are logged at WARNING
    level with full context for debugging.
"""

from typing import Any, Protocol, runtime_checkable

import structlog

from src.orchestrator.pipeline.context import PipelineContext
from src.orchestrator.stages.base import PipelineStage

logger = structlog.get_logger(__name__)


@runtime_checkable
class RiskAssessor(Protocol):
    """
    Protocol for risk assessment.

    Risk assessors take a signal and apply position sizing
    and risk validation.
    """

    async def apply_sizing(
        self,
        signal: Any,
        context: PipelineContext,
    ) -> Any | None:
        """
        Apply position sizing and risk limits to a signal.

        Args:
            signal: Signal to apply risk assessment to
            context: Pipeline context with portfolio and risk config

        Returns:
            Signal with sizing applied, or None if rejected by risk rules
        """
        ...


class RiskAssessmentStage(PipelineStage[list[Any], list[Any]]):
    """
    Pipeline stage for applying risk management to signals.

    Stage 7 in the analysis pipeline. Takes generated signals and applies
    position sizing, validates against portfolio limits, and filters
    signals that exceed risk constraints.

    Input: list[Any] - List of signals from SignalGenerationStage
    Output: list[Any] - List of signals with position sizing applied

    Context Keys Required:
        - "current_trading_range": TradingRange | None (from PhaseDetectionStage)
        - "portfolio_context": PortfolioContext | None (optional, for risk limits)

    Context Keys Set:
        - "assessed_signals": list[Any] (final signals ready for execution)

    Risk Validation Steps:
        1. Position sizing calculation
        2. Portfolio heat validation
        3. Campaign risk validation
        4. Correlated risk validation

    Example:
        >>> assessor = MyRiskAssessor()
        >>> stage = RiskAssessmentStage(assessor)
        >>> result = await stage.run(signals, context)
        >>> if result.success:
        ...     assessed = result.output
        ...     print(f"Approved {len(assessed)} signals")
    """

    CONTEXT_KEY = "assessed_signals"
    RANGE_CONTEXT_KEY = "current_trading_range"
    PORTFOLIO_CONTEXT_KEY = "portfolio_context"

    def __init__(self, risk_assessor: RiskAssessor) -> None:
        """
        Initialize the risk assessment stage.

        Args:
            risk_assessor: Assessor implementing RiskAssessor protocol
        """
        self._assessor = risk_assessor

    @property
    def name(self) -> str:
        """Unique identifier for this stage."""
        return "risk_assessment"

    async def execute(
        self,
        signals: list[Any],
        context: PipelineContext,
    ) -> list[Any]:
        """
        Apply risk management to signals.

        Iterates through signals and applies position sizing and risk
        validation. Signals that fail risk checks are filtered out.

        Args:
            signals: List of signals from SignalGenerationStage
            context: Pipeline context with portfolio and risk configuration

        Returns:
            List of signals that passed risk validation with sizing applied

        Raises:
            TypeError: If signals is not a list
        """
        # Read signals from context if available (set by SignalGenerationStage).
        # The coordinator passes initial_input (bars) to all stages; cross-stage
        # data flows through PipelineContext.
        context_signals: list[Any] | None = context.get("generated_signals")
        if context_signals is not None:
            signals = context_signals

        # Validate input type
        if not isinstance(signals, list):
            raise TypeError(f"Expected list of signals, got {type(signals).__name__}")

        assessed_signals: list[Any] = []

        # Handle empty signals list
        if not signals:
            logger.debug(
                "risk_assessment_skipped",
                reason="No signals to assess",
                symbol=context.symbol,
                correlation_id=str(context.correlation_id),
            )
            context.set(self.CONTEXT_KEY, assessed_signals)
            return assessed_signals

        logger.debug(
            "risk_assessment_executing",
            signal_count=len(signals),
            symbol=context.symbol,
            timeframe=context.timeframe,
            correlation_id=str(context.correlation_id),
        )

        # Process each signal
        for i, signal in enumerate(signals):
            logger.debug(
                "risk_assessment_signal_start",
                signal_index=i,
                signal_type=type(signal).__name__,
                symbol=context.symbol,
                correlation_id=str(context.correlation_id),
            )

            try:
                assessed = await self._assessor.apply_sizing(
                    signal=signal,
                    context=context,
                )

                if assessed is not None:
                    assessed_signals.append(assessed)
                    logger.debug(
                        "risk_assessment_signal_approved",
                        signal_index=i,
                        symbol=context.symbol,
                        correlation_id=str(context.correlation_id),
                    )
                else:
                    logger.debug(
                        "risk_assessment_signal_rejected",
                        signal_index=i,
                        reason="Assessor returned None (risk limits exceeded)",
                        symbol=context.symbol,
                        correlation_id=str(context.correlation_id),
                    )

            except Exception as e:
                # INTENTIONAL: Log error but don't fail entire stage.
                # A single bad signal should not prevent other valid signals
                # from being assessed. See module docstring for policy.
                logger.warning(
                    "risk_assessment_signal_error",
                    signal_index=i,
                    signal_type=type(signal).__name__,
                    error=str(e),
                    error_type=type(e).__name__,
                    symbol=context.symbol,
                    correlation_id=str(context.correlation_id),
                )

        context.set(self.CONTEXT_KEY, assessed_signals)

        logger.debug(
            "risk_assessment_complete",
            input_signals=len(signals),
            approved_signals=len(assessed_signals),
            rejected_signals=len(signals) - len(assessed_signals),
            symbol=context.symbol,
            correlation_id=str(context.correlation_id),
        )

        return assessed_signals
