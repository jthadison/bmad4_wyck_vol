"""
Multi-Stage Validation Chain Orchestrator (Story 8.2)

Purpose:
--------
Orchestrates the 5-stage validation workflow for signal generation:
Volume → Phase → Levels → Risk → Strategy

Provides:
- ValidationChainOrchestrator: Executes validators in order with early exit
- create_default_validation_chain(): Factory for default validator sequence
- Comprehensive structured logging for all validation events

Key Features:
-------------
- Early Exit: Stops processing on first FAIL (performance optimization)
- Warning Accumulation: Collects all warnings from WARN results
- Audit Trail: Stores complete validation history for compliance
- Structured Logging: All validation events logged with correlation IDs

Integration:
------------
- Story 8.2: Foundation for multi-stage validation
- Story 8.1: Will be used by Master Orchestrator to validate signals
- Stories 8.3-8.7: Individual validators implement full validation logic

Author: Story 8.2
"""

from datetime import UTC, datetime
from uuid import UUID

import structlog

from src.models.validation import (
    StageValidationResult,
    ValidationChain,
    ValidationContext,
    ValidationStatus,
)
from src.signal_generator.validators.base import BaseValidator
from src.signal_generator.validators.level_validator import LevelValidator
from src.signal_generator.validators.phase_validator import PhaseValidator
from src.signal_generator.validators.risk_validator import RiskValidator
from src.signal_generator.validators.strategy_validator import StrategyValidator
from src.signal_generator.validators.volume_validator import VolumeValidator

logger = structlog.get_logger()


class ValidationChainOrchestrator:
    """
    Orchestrates multi-stage validation chain execution.

    Executes validators in FR20 order (Volume → Phase → Levels → Risk → Strategy)
    with early exit on first FAIL and warning accumulation for all WARN results.

    Features:
    ---------
    - Early Exit: Stops at first FAIL to avoid wasted computation
    - Warning Accumulation: Continues processing on WARN, accumulates warnings
    - Structured Logging: Logs all validation events with detailed context
    - Audit Trail: Returns complete ValidationChain with all results

    Parameters:
    -----------
    validators : list[BaseValidator]
        Ordered list of validators to execute (must be in FR20 order)

    Example Usage:
    --------------
    >>> orchestrator = ValidationChainOrchestrator([
    ...     VolumeValidator(),
    ...     PhaseValidator(),
    ...     LevelValidator(),
    ...     RiskValidator(),
    ...     StrategyValidator()
    ... ])
    >>> chain = await orchestrator.run_validation_chain(context)
    >>> if chain.is_valid:
    ...     print("Signal approved")
    ... else:
    ...     print(f"Rejected at {chain.rejection_stage}: {chain.rejection_reason}")
    """

    def __init__(self, validators: list[BaseValidator]) -> None:
        """
        Initialize orchestrator with ordered list of validators.

        Parameters:
        -----------
        validators : list[BaseValidator]
            Validators to execute in order (must be in FR20 sequence)
        """
        self.validators = validators

    async def run_validation_chain(self, context: ValidationContext) -> ValidationChain:
        """
        Execute validation chain with early exit on failure.

        Iterates through validators in order, executing each validation stage.
        If any validator returns FAIL, the chain stops immediately (early exit).
        If any validator returns WARN, warning is accumulated and chain continues.

        Workflow:
        ---------
        1. Create ValidationChain with started_at timestamp
        2. Log chain start event
        3. For each validator in order:
           a. Log stage start
           b. Execute validator.validate(context)
           c. Add result to chain
           d. Log stage result (PASS/WARN/FAIL)
           e. If FAIL: Set rejection_stage/reason, break loop (early exit)
           f. If WARN: Append warning, continue
           g. If PASS: Continue
        4. Set completed_at timestamp
        5. Log chain completion
        6. Return ValidationChain

        Parameters:
        -----------
        context : ValidationContext
            Context with pattern, volume_analysis, and optional data for each stage

        Returns:
        --------
        ValidationChain
            Complete validation results with overall status, warnings, and audit trail

        Example:
        --------
        >>> context = ValidationContext(
        ...     pattern=spring_pattern,
        ...     symbol="AAPL",
        ...     timeframe="1d",
        ...     volume_analysis=volume_data
        ... )
        >>> chain = await orchestrator.run_validation_chain(context)
        >>> print(chain.overall_status)  # PASS, FAIL, or WARN
        """
        # Create validation chain
        # Extract pattern_id from pattern (could be object with .id or dict with "id" key)
        pattern_id = None
        if hasattr(context.pattern, "id"):
            pattern_id = context.pattern.id
        elif isinstance(context.pattern, dict) and "id" in context.pattern:
            pattern_id = (
                UUID(context.pattern["id"])
                if isinstance(context.pattern["id"], str)
                else context.pattern["id"]
            )

        chain = ValidationChain(pattern_id=pattern_id)

        # Log chain start
        logger.info(
            "validation_chain_started",
            pattern_id=str(chain.pattern_id) if chain.pattern_id else "unknown",
            symbol=context.symbol,
            timeframe=context.timeframe,
            validator_count=len(self.validators),
        )

        # Execute validators in order
        for validator in self.validators:
            # Log stage start
            logger.debug(
                "validation_stage_started",
                stage=validator.stage_name,
                validator_id=validator.validator_id,
                pattern_id=str(chain.pattern_id) if chain.pattern_id else "unknown",
            )

            stage_start = datetime.now(UTC)

            # Execute validation
            result: StageValidationResult = await validator.validate(context)

            # Add result to chain (updates overall_status automatically)
            chain.add_result(result)

            # Calculate stage duration
            stage_duration_ms = (datetime.now(UTC) - stage_start).total_seconds() * 1000

            # Log stage result based on status
            if result.status == ValidationStatus.PASS:
                logger.info(
                    "validation_stage_passed",
                    stage=validator.stage_name,
                    validator_id=validator.validator_id,
                    duration_ms=stage_duration_ms,
                )
            elif result.status == ValidationStatus.WARN:
                logger.warning(
                    "validation_stage_warning",
                    stage=validator.stage_name,
                    validator_id=validator.validator_id,
                    reason=result.reason,
                    metadata=result.metadata,
                    duration_ms=stage_duration_ms,
                )
            elif result.status == ValidationStatus.FAIL:
                logger.error(
                    "validation_stage_failed",
                    stage=validator.stage_name,
                    validator_id=validator.validator_id,
                    reason=result.reason,
                    metadata=result.metadata,
                    duration_ms=stage_duration_ms,
                )

                # Early exit on failure
                logger.warning(
                    "validation_chain_early_exit",
                    rejection_stage=chain.rejection_stage,
                    rejection_reason=chain.rejection_reason,
                    stages_completed=len(chain.validation_results),
                    total_stages=len(self.validators),
                )
                break  # Stop processing remaining validators

        # Set completion timestamp
        chain.completed_at = datetime.now(UTC)

        # Log chain completion
        total_duration_ms = (chain.completed_at - chain.started_at).total_seconds() * 1000
        logger.info(
            "validation_chain_completed",
            pattern_id=str(chain.pattern_id) if chain.pattern_id else "unknown",
            overall_status=chain.overall_status.value,
            is_valid=chain.is_valid,
            has_warnings=chain.has_warnings,
            duration_ms=total_duration_ms,
            stages_executed=len(chain.validation_results),
            total_stages=len(self.validators),
        )

        return chain


def create_default_validation_chain() -> ValidationChainOrchestrator:
    """
    Create validation chain orchestrator with default FR20 validator sequence.

    Returns orchestrator configured with all 5 validators in correct order:
    1. VolumeValidator (Story 8.3)
    2. PhaseValidator (Story 8.4)
    3. LevelValidator (Story 8.5)
    4. RiskValidator (Story 8.6)
    5. StrategyValidator (Story 8.7)

    Returns:
    --------
    ValidationChainOrchestrator
        Orchestrator with default validators

    Example Usage:
    --------------
    >>> orchestrator = create_default_validation_chain()
    >>> chain = await orchestrator.run_validation_chain(context)
    """
    validators = [
        VolumeValidator(),
        PhaseValidator(),
        LevelValidator(),
        RiskValidator(),
        StrategyValidator(),
    ]
    return ValidationChainOrchestrator(validators)


def create_validation_chain(
    validators: list[BaseValidator] | None = None,
) -> ValidationChainOrchestrator:
    """
    Create validation chain orchestrator with custom or default validators.

    Factory function supporting dependency injection for testing.
    If validators provided, uses them (for testing with mocks).
    If None, uses default FR20 sequence.

    Parameters:
    -----------
    validators : list[BaseValidator] | None
        Custom validators (for testing), or None for defaults

    Returns:
    --------
    ValidationChainOrchestrator
        Orchestrator with specified validators

    Example (Default):
    ------------------
    >>> orchestrator = create_validation_chain()  # Uses defaults
    >>> chain = await orchestrator.run_validation_chain(context)

    Example (Testing with Mocks):
    ------------------------------
    >>> mock_validators = [MockPassValidator(), MockFailValidator()]
    >>> orchestrator = create_validation_chain(validators=mock_validators)
    >>> chain = await orchestrator.run_validation_chain(context)
    """
    if validators is None:
        return create_default_validation_chain()
    return ValidationChainOrchestrator(validators)
