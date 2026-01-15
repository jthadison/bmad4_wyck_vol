"""
SOS (Sign of Strength) Volume Validation Strategy (Story 18.6.2)

Implements volume validation for SOS patterns per Wyckoff principles:
- SOS requires HIGH volume (> 1.5x for stocks, > 1.8x for forex)
- High volume indicates strong buying - demand overwhelming supply
- Asian session forex uses higher threshold (> 2.0x) for confirmation

Reference: FR6, FR12 from PRD; CF-006 from Critical Foundation Refactoring.

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


class SOSVolumeStrategy(VolumeValidationStrategy):
    """
    Volume validation strategy for SOS (Sign of Strength) patterns.

    SOS patterns require HIGH volume to confirm strong buying pressure.
    Per Wyckoff principles, a SOS on high volume indicates that
    demand is overwhelming supply and institutional accumulation is completing.

    Thresholds:
    -----------
    - Stock: > 1.5x average volume (configurable via sos_min_volume)
    - Forex: > 1.8x average tick volume (configurable via forex_sos_min_volume)
    - Forex Asian: > 2.0x (higher threshold due to low liquidity baseline)

    Example:
    --------
    >>> strategy = SOSVolumeStrategy()
    >>> result = strategy.validate(context, config)
    >>> if result.status == ValidationStatus.FAIL:
    ...     print(f"SOS volume too low: {result.reason}")
    """

    @property
    def pattern_type(self) -> str:
        """Return pattern type this strategy handles."""
        return "SOS"

    @property
    def volume_threshold_type(self) -> str:
        """SOS requires volume ABOVE threshold (min)."""
        return "min"

    @property
    def default_stock_threshold(self) -> Decimal:
        """Default stock threshold: 1.5x average volume."""
        return Decimal("1.5")

    @property
    def default_forex_threshold(self) -> Decimal:
        """Default forex threshold: 1.8x tick volume."""
        return Decimal("1.8")

    def get_threshold(self, context: ValidationContext, config: VolumeValidationConfig) -> Decimal:
        """
        Get appropriate SOS volume threshold.

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
            Threshold for SOS volume validation
        """
        if context.asset_class == "FOREX":
            # Asian session uses higher threshold due to low liquidity baseline
            if context.forex_session and context.forex_session.value == "ASIAN":
                return config.forex_asian_sos_min_volume
            return config.forex_sos_min_volume
        return config.sos_min_volume

    def validate(
        self, context: ValidationContext, config: VolumeValidationConfig
    ) -> StageValidationResult:
        """
        Validate SOS pattern volume.

        SOS patterns MUST have high volume to confirm demand overwhelming supply.
        Per FR12, this is a hard validation - FAIL if volume too low.

        Parameters:
        -----------
        context : ValidationContext
            Context with pattern, volume_analysis, asset_class, forex_session
        config : VolumeValidationConfig
            Configuration with volume thresholds

        Returns:
        --------
        StageValidationResult
            PASS if volume above threshold, FAIL otherwise
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

        # SOS requires volume ABOVE threshold (min)
        if volume_ratio < threshold:
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
