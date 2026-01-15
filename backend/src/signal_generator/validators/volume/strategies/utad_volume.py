"""
UTAD (Upthrust After Distribution) Volume Validation Strategy (Story 18.6.2)

Implements volume validation for UTAD patterns per Wyckoff principles:
- UTAD requires HIGH volume on the initial bar (failure/rejection)
- High volume on failure confirms supply overwhelming demand
- This is a shorting signal in distribution ranges

Reference: FR5, FR12 from PRD; CF-006 from Critical Foundation Refactoring.

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


class UTADVolumeStrategy(VolumeValidationStrategy):
    """
    Volume validation strategy for UTAD (Upthrust After Distribution) patterns.

    UTAD patterns require HIGH volume on the initial failure bar to confirm
    supply overwhelming demand. Per Wyckoff principles, an upthrust on high
    volume indicates sellers are aggressively defending the distribution zone.

    Thresholds:
    -----------
    - Stock: > 1.2x average volume (configurable via utad_min_volume)
    - Forex: > 2.5x average tick volume (configurable via forex_utad_min_volume)

    Example:
    --------
    >>> strategy = UTADVolumeStrategy()
    >>> result = strategy.validate(context, config)
    >>> if result.status == ValidationStatus.FAIL:
    ...     print(f"UTAD volume too low: {result.reason}")
    """

    @property
    def pattern_type(self) -> str:
        """Return pattern type this strategy handles."""
        return "UTAD"

    @property
    def volume_threshold_type(self) -> str:
        """UTAD requires volume ABOVE threshold (min)."""
        return "min"

    @property
    def default_stock_threshold(self) -> Decimal:
        """Default stock threshold: 1.2x average volume."""
        return Decimal("1.2")

    @property
    def default_forex_threshold(self) -> Decimal:
        """Default forex threshold: 2.5x tick volume."""
        return Decimal("2.5")

    def get_threshold(self, context: ValidationContext, config: VolumeValidationConfig) -> Decimal:
        """
        Get appropriate UTAD volume threshold.

        Uses config values when available.

        Parameters:
        -----------
        context : ValidationContext
            Context with asset_class
        config : VolumeValidationConfig
            Configuration with threshold values

        Returns:
        --------
        Decimal
            Threshold for UTAD volume validation
        """
        if context.asset_class == "FOREX":
            return config.forex_utad_min_volume
        return config.utad_min_volume

    def validate(
        self, context: ValidationContext, config: VolumeValidationConfig
    ) -> StageValidationResult:
        """
        Validate UTAD pattern volume.

        UTAD patterns MUST have high volume on failure to confirm supply
        overwhelming demand. Per FR12, this is a hard validation.

        Parameters:
        -----------
        context : ValidationContext
            Context with pattern, volume_analysis, asset_class
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

        # UTAD requires volume ABOVE threshold (min)
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
