"""
Strategy-Based Volume Validator Adapter - Story 25.4

Adapts VolumeValidationStrategy pattern-specific validators to BaseValidator interface.
This allows the orchestrator to use the new strategy-based validators without changing
the pipeline architecture.

Author: Story 25.4
"""

import structlog

from src.models.validation import (
    StageValidationResult,
    ValidationContext,
    ValidationStatus,
    VolumeValidationConfig,
)
from src.signal_generator.validators.base import BaseValidator
from src.signal_generator.validators.volume.factory import get_volume_validator

logger = structlog.get_logger(__name__)


class StrategyBasedVolumeValidator(BaseValidator):
    """
    BaseValidator adapter that delegates to pattern-specific VolumeValidationStrategy instances.

    This adapter bridges the orchestrator's BaseValidator interface with the new
    VolumeValidationStrategy pattern-specific validators. It uses the factory to
    retrieve the appropriate validator based on pattern_type.

    Example:
    --------
    >>> validator = StrategyBasedVolumeValidator()
    >>> result = await validator.validate(context)
    """

    @property
    def validator_id(self) -> str:
        return "VOLUME_VALIDATOR"

    @property
    def stage_name(self) -> str:
        return "Volume"

    async def validate(self, context: ValidationContext) -> StageValidationResult:
        """
        Execute volume validation using pattern-specific strategy.

        Parameters:
        -----------
        context : ValidationContext
            Context with pattern, volume_analysis, and configuration

        Returns:
        --------
        StageValidationResult
            Result from the pattern-specific validator (PASS or FAIL)
        """
        # Extract pattern type
        pattern_type = getattr(context.pattern, "pattern_type", None)
        if pattern_type is None:
            logger.error(
                "volume_validation_no_pattern_type",
                pattern_id=str(getattr(context.pattern, "id", "unknown")),
                symbol=context.symbol,
            )
            return self.create_result(
                ValidationStatus.FAIL,
                reason="Pattern missing pattern_type field",
            )

        # Get pattern-specific validator via factory
        try:
            strategy = get_volume_validator(pattern_type)
        except ValueError as e:
            logger.error(
                "volume_validation_unknown_pattern_type",
                pattern_type=pattern_type,
                symbol=context.symbol,
                error=str(e),
            )
            return self.create_result(
                ValidationStatus.FAIL,
                reason=f"Unknown pattern type: {pattern_type}",
            )

        # Load volume validation config from context
        config_dict = context.config.get("volume_validation", {})
        config = VolumeValidationConfig(**config_dict)

        # Delegate to strategy
        logger.debug(
            "volume_validation_delegating_to_strategy",
            pattern_type=pattern_type,
            strategy_class=type(strategy).__name__,
            symbol=context.symbol,
        )

        result = strategy.validate(context, config)

        # Log result
        if result.status == ValidationStatus.FAIL:
            logger.error(
                "volume_validation_failed_via_strategy",
                pattern_type=pattern_type,
                strategy=type(strategy).__name__,
                reason=result.reason,
            )
        else:
            logger.info(
                "volume_validation_passed_via_strategy",
                pattern_type=pattern_type,
                strategy=type(strategy).__name__,
            )

        return result
