"""
SOS Volume Validator - Story 25.4

Validates SOS patterns require HIGH volume (>1.5x average) per FR12.
SOS patterns with volume <= 1.5x are rejected immediately (non-negotiable).

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


class SOSVolumeValidator(VolumeValidationStrategy):
    """
    Validates SOS patterns have high volume (>1.5x average).

    Per FR12 (non-negotiable): SOS (Sign of Strength) breakouts MUST have
    high volume to confirm institutional demand. Volume <= threshold = rejection.
    """

    @property
    def pattern_type(self) -> str:
        return "SOS"

    @property
    def volume_threshold_type(self) -> str:
        return "min"  # SOS requires volume ABOVE threshold

    @property
    def default_stock_threshold(self) -> Decimal:
        return SOS_VOLUME_THRESHOLD

    @property
    def default_forex_threshold(self) -> Decimal:
        return SOS_VOLUME_THRESHOLD  # Ratio is constant across asset classes

    def validate(
        self, context: ValidationContext, config: VolumeValidationConfig
    ) -> StageValidationResult:
        """Execute SOS volume validation."""
        self.log_validation_start(context)

        # Extract volume_ratio from pattern
        volume_ratio = getattr(context.pattern, "volume_ratio", None)

        # Null check
        if volume_ratio is None:
            reason = "SOS volume_ratio is None (missing from pattern)"
            self.log_validation_failed(context, Decimal("0"), Decimal("0"), reason)
            return self.create_result(ValidationStatus.FAIL, reason=reason)

        # NaN check
        try:
            if math.isnan(float(volume_ratio)):
                reason = "SOS volume_ratio is NaN (invalid data)"
                self.log_validation_failed(context, volume_ratio, Decimal("0"), reason)
                return self.create_result(ValidationStatus.FAIL, reason=reason)
        except (ValueError, TypeError, OverflowError):
            reason = f"SOS volume_ratio {volume_ratio} is not a valid number"
            self.log_validation_failed(context, volume_ratio, Decimal("0"), reason)
            return self.create_result(ValidationStatus.FAIL, reason=reason)

        # Get threshold
        threshold = self.get_threshold(context, config)

        # FR12: SOS volume must be ABOVE threshold (strictly greater than)
        if volume_ratio <= threshold:
            reason = (
                f"SOS volume_ratio {float(volume_ratio):.3f} below threshold "
                f"{float(threshold):.3f} (must exceed for high-volume breakout)"
            )
            metadata = {
                "volume_ratio": float(volume_ratio),
                "threshold": float(threshold),
                "asset_class": context.asset_class,
            }
            self.log_validation_failed(context, volume_ratio, threshold, reason)
            return self.create_result(ValidationStatus.FAIL, reason=reason, metadata=metadata)

        # Validation passed
        self.log_validation_passed(context, volume_ratio, threshold)
        metadata = {
            "volume_ratio": float(volume_ratio),
            "threshold": float(threshold),
        }
        return self.create_result(ValidationStatus.PASS, metadata=metadata)
