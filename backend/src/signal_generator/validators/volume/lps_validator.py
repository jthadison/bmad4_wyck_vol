"""
LPS Volume Validator - Story 25.4

Validates LPS (Last Point of Support) patterns have moderate volume.

LPS Wyckoff Theory:
-------------------
LPS is a pullback after SOS breakout. Volume should be:
- Lighter than SOS (shows lack of selling pressure)
- Heavier than Spring (shows demand still present)
- Moderate range: 0.5x < volume_ratio < 1.5x

Rationale:
----------
- Too low (< 0.5x): Lack of demand, not a confirmed retest
- Too high (>= 1.5x): Selling pressure, not a healthy pullback
- Moderate: Orderly profit-taking with demand still present

Author: Story 25.4
"""

import math
from decimal import Decimal

import structlog

from src.models.validation import (
    StageValidationResult,
    ValidationContext,
    ValidationStatus,
    VolumeValidationConfig,
)
from src.signal_generator.validators.volume.base import VolumeValidationStrategy

logger = structlog.get_logger(__name__)

# LPS moderate volume band: between Spring (0.7) and SOS (1.5)
LPS_MIN_VOLUME = Decimal("0.5")  # Minimum to show demand present
LPS_MAX_VOLUME = Decimal("1.5")  # Maximum before supply pressure concerns


class LPSVolumeValidator(VolumeValidationStrategy):
    """
    Validates LPS patterns have moderate volume (0.5x to 1.5x).

    LPS (Last Point of Support) is a pullback retest after SOS breakout.
    Volume should be moderate - lighter than SOS but not as low as Spring.
    """

    @property
    def pattern_type(self) -> str:
        return "LPS"

    @property
    def volume_threshold_type(self) -> str:
        return "moderate"  # Neither pure min nor pure max

    @property
    def default_stock_threshold(self) -> Decimal:
        return Decimal("1.0")  # Mid-point for config purposes

    @property
    def default_forex_threshold(self) -> Decimal:
        return Decimal("1.0")  # Same across asset classes (ratio)

    def validate(
        self, context: ValidationContext, config: VolumeValidationConfig
    ) -> StageValidationResult:
        """Execute LPS volume validation."""
        self.log_validation_start(context)

        # Extract volume_ratio from pattern
        volume_ratio = getattr(context.pattern, "volume_ratio", None)

        # Null check
        if volume_ratio is None:
            reason = "LPS volume_ratio is None (missing from pattern)"
            logger.error("lps_volume_validation_failed", reason=reason)
            return self.create_result(ValidationStatus.FAIL, reason=reason)

        # NaN check
        try:
            if math.isnan(float(volume_ratio)):
                reason = "LPS volume_ratio is NaN (invalid data)"
                logger.error("lps_volume_validation_failed", reason=reason)
                return self.create_result(ValidationStatus.FAIL, reason=reason)
        except (ValueError, TypeError, OverflowError):
            reason = f"LPS volume_ratio {volume_ratio} is not a valid number"
            logger.error("lps_volume_validation_failed", reason=reason)
            return self.create_result(ValidationStatus.FAIL, reason=reason)

        # LPS moderate volume band check
        if volume_ratio <= LPS_MIN_VOLUME:
            reason = (
                f"LPS volume_ratio {float(volume_ratio):.3f} too low "
                f"(<= {float(LPS_MIN_VOLUME):.1f}x) - demand absent on retest"
            )
            metadata = {
                "volume_ratio": float(volume_ratio),
                "min_threshold": float(LPS_MIN_VOLUME),
                "max_threshold": float(LPS_MAX_VOLUME),
                "asset_class": context.asset_class,
            }
            logger.error(
                "lps_volume_too_low",
                volume_ratio=float(volume_ratio),
                min_threshold=float(LPS_MIN_VOLUME),
                reason=reason,
            )
            return self.create_result(ValidationStatus.FAIL, reason=reason, metadata=metadata)

        if volume_ratio >= LPS_MAX_VOLUME:
            reason = (
                f"LPS volume_ratio {float(volume_ratio):.3f} too high "
                f"(>= {float(LPS_MAX_VOLUME):.1f}x) - supply pressure on pullback"
            )
            metadata = {
                "volume_ratio": float(volume_ratio),
                "min_threshold": float(LPS_MIN_VOLUME),
                "max_threshold": float(LPS_MAX_VOLUME),
                "asset_class": context.asset_class,
            }
            logger.error(
                "lps_volume_too_high",
                volume_ratio=float(volume_ratio),
                max_threshold=float(LPS_MAX_VOLUME),
                reason=reason,
            )
            return self.create_result(ValidationStatus.FAIL, reason=reason, metadata=metadata)

        # Validation passed - moderate volume
        logger.info(
            "lps_volume_validation_passed",
            volume_ratio=float(volume_ratio),
            symbol=context.symbol,
            interpretation="Moderate volume - healthy pullback",
        )
        metadata = {
            "volume_ratio": float(volume_ratio),
            "min_threshold": float(LPS_MIN_VOLUME),
            "max_threshold": float(LPS_MAX_VOLUME),
        }
        return self.create_result(ValidationStatus.PASS, metadata=metadata)
