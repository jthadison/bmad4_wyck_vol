"""
Spring Volume Validation Strategy (Story 18.6.2)

Implements volume validation for Spring patterns per Wyckoff principles:
- Spring requires LOW volume (< 0.7x for stocks, < 0.85x for forex)
- Low volume indicates selling exhaustion - supply has dried up
- Asian session forex uses stricter threshold (< 0.60x) due to low liquidity

Reference: FR4, FR12 from PRD; CF-006 from Critical Foundation Refactoring.

Author: Story 18.6.2
"""

from decimal import Decimal

from src.models.validation import (
    StageValidationResult,
    ValidationContext,
    ValidationStatus,
    VolumeValidationConfig,
)
from src.signal_generator.validators.volume.base import VolumeValidationStrategy
from src.signal_generator.validators.volume.helpers import (
    ValidationMetadataBuilder,
    build_failure_reason,
)


class SpringVolumeStrategy(VolumeValidationStrategy):
    """
    Volume validation strategy for Spring patterns.

    Spring patterns require LOW volume to confirm selling exhaustion.
    Per Wyckoff principles, a spring on low volume indicates that
    supply has dried up and sellers are depleted.

    Thresholds:
    -----------
    - Stock: < 0.7x average volume (configurable via spring_max_volume)
    - Forex: < 0.85x average tick volume (configurable via forex_spring_max_volume)
    - Forex Asian: < 0.60x (stricter due to low liquidity)

    Example:
    --------
    >>> strategy = SpringVolumeStrategy()
    >>> result = strategy.validate(context, config)
    >>> if result.status == ValidationStatus.FAIL:
    ...     print(f"Spring volume too high: {result.reason}")
    """

    @property
    def pattern_type(self) -> str:
        """Return pattern type this strategy handles."""
        return "SPRING"

    @property
    def volume_threshold_type(self) -> str:
        """Spring requires volume BELOW threshold (max)."""
        return "max"

    @property
    def default_stock_threshold(self) -> Decimal:
        """Default stock threshold: 0.7x average volume."""
        return Decimal("0.7")

    @property
    def default_forex_threshold(self) -> Decimal:
        """Default forex threshold: 0.85x tick volume (wider tolerance)."""
        return Decimal("0.85")

    def get_threshold(self, context: ValidationContext, config: VolumeValidationConfig) -> Decimal:
        """
        Get appropriate Spring volume threshold.

        Uses config values when available, with session-specific
        adjustments for forex Asian session.

        Parameters:
        -----------
        context : ValidationContext
            Context with asset_class and forex_session
        config : VolumeValidationConfig
            Configuration with threshold values

        Returns:
        --------
        Decimal
            Threshold for Spring volume validation
        """
        if context.asset_class == "FOREX":
            # Asian session uses stricter threshold due to low liquidity
            if context.forex_session and context.forex_session.value == "ASIAN":
                return config.forex_asian_spring_max_volume
            return config.forex_spring_max_volume
        return config.spring_max_volume

    def validate(
        self, context: ValidationContext, config: VolumeValidationConfig
    ) -> StageValidationResult:
        """
        Validate Spring pattern volume.

        Spring patterns MUST have low volume to confirm selling exhaustion.
        Per FR12, this is a hard validation - FAIL if volume too high.

        Parameters:
        -----------
        context : ValidationContext
            Context with pattern, volume_analysis, asset_class, forex_session
        config : VolumeValidationConfig
            Configuration with volume thresholds

        Returns:
        --------
        StageValidationResult
            PASS if volume below threshold, FAIL otherwise
        """
        self.log_validation_start(context)

        # Get volume ratio from volume analysis
        volume_ratio = Decimal(str(context.volume_analysis.volume_ratio))
        threshold = self.get_threshold(context, config)
        volume_source = "TICK" if context.asset_class == "FOREX" else "ACTUAL"

        # Build metadata for result
        metadata = (
            ValidationMetadataBuilder()
            .with_volume_ratio(volume_ratio)
            .with_threshold(threshold)
            .with_pattern_info(self.pattern_type, context)
            .with_volume_source(context.asset_class)
            .with_forex_info(context)
            .build()
        )

        # Spring requires volume BELOW threshold (max)
        if volume_ratio >= threshold:
            reason = build_failure_reason(
                pattern_type=self.pattern_type,
                volume_ratio=volume_ratio,
                threshold=threshold,
                threshold_type=self.volume_threshold_type,
                context=context,
                volume_source=volume_source,
            )
            self.log_validation_failed(context, volume_ratio, threshold, reason)
            return self.create_result(
                ValidationStatus.FAIL,
                reason=reason,
                metadata=metadata,
            )

        # Validation passed
        self.log_validation_passed(context, volume_ratio, threshold)
        return self.create_result(
            ValidationStatus.PASS,
            metadata=metadata,
        )
