"""
UTAD Volume Validator - Story 25.4

Validates UTAD (Upthrust After Distribution) patterns have high volume on upthrust.

UTAD Wyckoff Theory:
--------------------
UTAD should have TWO volume components:
1. Upthrust bar: HIGH volume (traps buyers)
2. Failure bar: LOW volume (shows weak demand, confirms trap)

Current Implementation Limitation:
----------------------------------
The UTAD model (utad_detector.py) currently only tracks a single volume_ratio
field for the upthrust bar. Failure bar volume validation is deferred to a
future story when the model is enhanced to track both volume fields separately.

This validator checks the upthrust volume requirement (>1.5x like SOS).

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
from src.pattern_engine.timeframe_config import SOS_VOLUME_THRESHOLD
from src.signal_generator.validators.volume.base import VolumeValidationStrategy

logger = structlog.get_logger(__name__)


class UTADVolumeValidator(VolumeValidationStrategy):
    """
    Validates UTAD patterns have high volume on upthrust bar (>1.5x).

    Note: This validator only checks upthrust bar volume due to model
    limitations. Complete UTAD validation should check both:
    - Upthrust bar: HIGH volume (traps buyers)
    - Failure bar: LOW volume (confirms trap)

    Failure bar volume validation deferred to future story.
    """

    @property
    def pattern_type(self) -> str:
        return "UTAD"

    @property
    def volume_threshold_type(self) -> str:
        return "min"  # Upthrust requires HIGH volume

    @property
    def default_stock_threshold(self) -> Decimal:
        return SOS_VOLUME_THRESHOLD  # Same as SOS (1.5x)

    @property
    def default_forex_threshold(self) -> Decimal:
        return SOS_VOLUME_THRESHOLD  # Ratio is constant across asset classes

    def validate(
        self, context: ValidationContext, config: VolumeValidationConfig
    ) -> StageValidationResult:
        """Execute UTAD volume validation (upthrust bar only)."""
        self.log_validation_start(context)

        # Extract volume_ratio from pattern (upthrust bar volume)
        volume_ratio = getattr(context.pattern, "volume_ratio", None)

        # Null check
        if volume_ratio is None:
            reason = "UTAD volume_ratio is None (missing from pattern)"
            self.log_validation_failed(context, Decimal("0"), Decimal("0"), reason)
            return self.create_result(ValidationStatus.FAIL, reason=reason)

        # NaN check
        try:
            if math.isnan(float(volume_ratio)):
                reason = "UTAD volume_ratio is NaN (invalid data)"
                self.log_validation_failed(context, volume_ratio, Decimal("0"), reason)
                return self.create_result(ValidationStatus.FAIL, reason=reason)
        except (ValueError, TypeError, OverflowError):
            reason = f"UTAD volume_ratio {volume_ratio} is not a valid number"
            self.log_validation_failed(context, volume_ratio, Decimal("0"), reason)
            return self.create_result(ValidationStatus.FAIL, reason=reason)

        # Get threshold
        threshold = self.get_threshold(context, config)

        # UTAD upthrust bar must have HIGH volume (like SOS)
        if volume_ratio <= threshold:
            reason = (
                f"UTAD upthrust volume_ratio {float(volume_ratio):.3f} below threshold "
                f"{float(threshold):.3f} (upthrust requires high volume to trap buyers)"
            )
            metadata = {
                "volume_ratio": float(volume_ratio),
                "threshold": float(threshold),
                "asset_class": context.asset_class,
                "note": "Failure bar volume validation not yet implemented",
            }
            self.log_validation_failed(context, volume_ratio, threshold, reason)
            return self.create_result(ValidationStatus.FAIL, reason=reason, metadata=metadata)

        # Validation passed
        self.log_validation_passed(context, volume_ratio, threshold)
        metadata = {
            "volume_ratio": float(volume_ratio),
            "threshold": float(threshold),
            "validation_scope": "upthrust_bar_only",
            "note": "Failure bar volume validation deferred to future story",
        }
        logger.info(
            "utad_volume_validation_passed",
            volume_ratio=float(volume_ratio),
            symbol=context.symbol,
            note="Upthrust bar has high volume (failure bar check deferred)",
        )
        return self.create_result(ValidationStatus.PASS, metadata=metadata)
