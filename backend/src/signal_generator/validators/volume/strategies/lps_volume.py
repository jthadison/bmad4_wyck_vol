"""
LPS (Last Point of Support) Volume Validation Strategy (Story 18.6.2)

Implements volume validation for LPS patterns per Wyckoff principles:
- Standard LPS: Volume should be moderate (< 1.0x)
- Absorption LPS: Higher volume acceptable if close position is strong
  (demand absorbing supply, indicated by close near high)

Reference: FR7 from PRD; CF-006 from Critical Foundation Refactoring.

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


class LPSVolumeStrategy(VolumeValidationStrategy):
    """
    Volume validation strategy for LPS (Last Point of Support) patterns.

    LPS patterns typically require MODERATE volume to confirm a successful
    retest of support. However, Wyckoff also recognizes "absorption" patterns
    where higher volume is acceptable if the close is near the high (demand
    absorbing supply).

    Thresholds:
    -----------
    - Standard: < 1.0x average volume (configurable via lps_max_volume)
    - Absorption: < 1.5x if close_position >= 0.7 (configurable)

    Absorption Pattern:
    -------------------
    When lps_allow_absorption=True and close_position >= 0.7:
    - Higher volume is acceptable (up to lps_absorption_max_volume)
    - Close near high indicates demand absorbed the supply
    - This is a valid Wyckoff "absorption bar" pattern

    Example:
    --------
    >>> strategy = LPSVolumeStrategy()
    >>> result = strategy.validate(context, config)
    >>> if result.status == ValidationStatus.FAIL:
    ...     print(f"LPS volume validation failed: {result.reason}")
    """

    @property
    def pattern_type(self) -> str:
        """Return pattern type this strategy handles."""
        return "LPS"

    @property
    def volume_threshold_type(self) -> str:
        """LPS requires volume BELOW threshold (max)."""
        return "max"

    @property
    def default_stock_threshold(self) -> Decimal:
        """Default stock threshold: 1.0x average volume."""
        return Decimal("1.0")

    @property
    def default_forex_threshold(self) -> Decimal:
        """Default forex threshold: 1.0x tick volume."""
        return Decimal("1.0")

    def _check_absorption_pattern(
        self, context: ValidationContext, config: VolumeValidationConfig
    ) -> tuple[bool, Decimal | None]:
        """
        Check if LPS shows absorption pattern (Wyckoff enhancement).

        Absorption occurs when higher volume is present but close is near
        the high, indicating demand absorbed the supply.

        Parameters:
        -----------
        context : ValidationContext
            Context with volume_analysis containing close_position
        config : VolumeValidationConfig
            Configuration with absorption settings

        Returns:
        --------
        tuple[bool, Decimal | None]
            (is_absorption, close_position) - True if absorption detected
        """
        if not config.lps_allow_absorption:
            return False, None

        # Check close position from volume analysis
        close_position = context.volume_analysis.close_position
        if close_position is None:
            return False, None

        close_pos_decimal = Decimal(str(close_position))
        is_absorption = close_pos_decimal >= config.lps_absorption_min_close_position

        return is_absorption, close_pos_decimal

    def get_threshold(self, context: ValidationContext, config: VolumeValidationConfig) -> Decimal:
        """
        Get appropriate LPS volume threshold.

        Uses higher threshold if absorption pattern detected.

        Parameters:
        -----------
        context : ValidationContext
            Context with asset_class and volume_analysis
        config : VolumeValidationConfig
            Configuration with threshold values

        Returns:
        --------
        Decimal
            Threshold for LPS volume validation
        """
        is_absorption, _ = self._check_absorption_pattern(context, config)

        if is_absorption:
            return config.lps_absorption_max_volume

        return config.lps_max_volume

    def validate(
        self, context: ValidationContext, config: VolumeValidationConfig
    ) -> StageValidationResult:
        """
        Validate LPS pattern volume.

        LPS patterns should have moderate volume, unless showing absorption
        pattern (high volume with close near high).

        Parameters:
        -----------
        context : ValidationContext
            Context with pattern, volume_analysis, asset_class
        config : VolumeValidationConfig
            Configuration with volume thresholds

        Returns:
        --------
        StageValidationResult
            PASS if volume within acceptable range, FAIL otherwise
        """
        self.log_validation_start(context)

        # Get volume ratio from volume analysis
        volume_ratio = Decimal(str(context.volume_analysis.volume_ratio))
        volume_source = "TICK" if context.asset_class == "FOREX" else "ACTUAL"

        # Check for absorption pattern
        is_absorption, close_position = self._check_absorption_pattern(context, config)
        threshold = self.get_threshold(context, config)

        # Build metadata for result
        metadata_builder = (
            ValidationMetadataBuilder()
            .with_volume_ratio(volume_ratio)
            .with_threshold(threshold)
            .with_pattern_info(self.pattern_type, context)
            .with_volume_source(context.asset_class)
            .with_forex_info(context)
        )

        # Add absorption pattern info to metadata
        if config.lps_allow_absorption:
            metadata_builder.with_custom("absorption_enabled", True)
            metadata_builder.with_custom("is_absorption_pattern", is_absorption)
            if close_position is not None:
                metadata_builder.with_custom("close_position", float(close_position))
                metadata_builder.with_custom(
                    "absorption_threshold", float(config.lps_absorption_min_close_position)
                )

        metadata = metadata_builder.build()

        # LPS requires volume BELOW threshold (max)
        if volume_ratio >= threshold:
            if is_absorption:
                reason = (
                    f"LPS {volume_source.lower()} volume too high even for absorption: "
                    f"{volume_ratio}x >= {threshold}x threshold "
                    f"(close_position: {close_position}, symbol: {context.symbol})"
                )
            else:
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
