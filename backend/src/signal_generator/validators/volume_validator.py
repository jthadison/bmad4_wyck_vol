"""
Volume Validation Stage (Story 8.3)

FR12: Volume validation is a non-negotiable gatekeeper. All volume failures
result in immediate signal rejection (FAIL status).

Pattern-specific volume requirements (WYCKOFF ENHANCED):
- Spring (FR4): volume_ratio < 0.7x (low volume confirms selling exhaustion)
- SOS (FR6): volume_ratio >= 1.5x (high volume confirms demand)
- UTAD (FR5): volume_ratio >= 1.2x (elevated volume confirms supply climax) - WYCKOFF ENHANCEMENT
- LPS (FR7): volume_ratio < 1.0x OR absorption pattern (WYCKOFF ENHANCEMENT)
- Test (FR13): test_volume < pattern_volume (decreased volume confirms test)

Author: Story 8.3
"""

from decimal import Decimal

import structlog

from src.models.effort_result import EffortResult
from src.models.validation import (
    StageValidationResult,
    ValidationContext,
    ValidationStatus,
    VolumeValidationConfig,
)
from src.signal_generator.validators.base import BaseValidator

logger = structlog.get_logger()


class VolumeValidator(BaseValidator):
    """
    Validates pattern volume requirements (FR12).

    This is the FIRST stage in the validation chain (FR20). Early exit on
    volume failure avoids expensive phase/level/risk validation.

    Pattern-Specific Validation Rules:
    ----------------------------------
    - Spring: volume_ratio < 0.7x (low volume = selling exhaustion)
    - SOS: volume_ratio >= 1.5x (high volume = demand overwhelming supply)
    - LPS: volume_ratio < 1.0x OR absorption pattern (WYCKOFF ENHANCEMENT)
    - UTAD: volume_ratio >= 1.2x (elevated volume = supply climax)
    - Test Confirmation: test_volume < pattern_volume (decreasing volume)

    Properties:
    -----------
    - validator_id: "VOLUME_VALIDATOR"
    - stage_name: "Volume"

    Example Usage:
    --------------
    >>> validator = VolumeValidator()
    >>> result = await validator.validate(context)
    >>> print(result.status)  # ValidationStatus.PASS or FAIL
    """

    @property
    def validator_id(self) -> str:
        """Unique identifier for this validator."""
        return "VOLUME_VALIDATOR"

    @property
    def stage_name(self) -> str:
        """Human-readable stage name."""
        return "Volume"

    def _load_config(self, context: ValidationContext) -> VolumeValidationConfig:
        """
        Load volume validation config from context or use defaults.

        Parameters:
        -----------
        context : ValidationContext
            Context with optional config overrides

        Returns:
        --------
        VolumeValidationConfig
            Configuration with defaults or overrides applied
        """
        config_dict = context.config.get("volume_validation", {})
        return VolumeValidationConfig(**config_dict)

    async def validate(self, context: ValidationContext) -> StageValidationResult:
        """
        Execute volume validation for the pattern.

        Args:
            context: ValidationContext with pattern and volume_analysis

        Returns:
            StageValidationResult with PASS or FAIL (never WARN per FR12)
        """
        logger.debug(
            "volume_validation_started",
            pattern_id=str(context.pattern.id),
            pattern_type=context.pattern.pattern_type,
            symbol=context.symbol,
        )

        # Edge case: missing volume analysis
        if context.volume_analysis is None:
            logger.error(
                "volume_validation_failed",
                reason="Volume analysis missing",
                pattern_id=str(context.pattern.id),
            )
            return self.create_result(
                ValidationStatus.FAIL, reason="Volume analysis missing for pattern validation"
            )

        # Edge case: insufficient data (volume_ratio = None)
        if context.volume_analysis.volume_ratio is None:
            logger.error(
                "volume_validation_failed",
                reason="Insufficient data for volume calculation",
                pattern_id=str(context.pattern.id),
            )
            return self.create_result(
                ValidationStatus.FAIL, reason="Insufficient data for volume validation (<20 bars)"
            )

        # Load configuration
        config = self._load_config(context)
        logger.debug(
            "volume_validation_config",
            spring_max=str(config.spring_max_volume),
            sos_min=str(config.sos_min_volume),
            utad_min=str(config.utad_min_volume),
            lps_max=str(config.lps_max_volume),
            lps_allow_absorption=config.lps_allow_absorption,
        )

        pattern_type = context.pattern.pattern_type.upper()
        volume_ratio = context.volume_analysis.volume_ratio

        # Pattern-specific validation
        if pattern_type == "SPRING":
            return self._validate_spring(context, volume_ratio, config)
        elif pattern_type == "SOS":
            return self._validate_sos(context, volume_ratio, config)
        elif pattern_type == "LPS":
            return self._validate_lps(context, volume_ratio, config)
        elif pattern_type == "UTAD":
            return self._validate_utad(context, volume_ratio, config)
        else:
            logger.error(
                "volume_validation_failed", reason="Unknown pattern type", pattern_type=pattern_type
            )
            return self.create_result(
                ValidationStatus.FAIL, reason=f"Unknown pattern type: {pattern_type}"
            )

    def _validate_spring(
        self, context: ValidationContext, volume_ratio: Decimal, config: VolumeValidationConfig
    ) -> StageValidationResult:
        """Validate Spring volume requirements (FR4, FR12)"""
        # FR4: Spring requires volume < 0.7x (low volume confirms exhaustion)
        if volume_ratio >= config.spring_max_volume:
            reason = (
                f"Spring volume too high: {volume_ratio}x >= "
                f"{config.spring_max_volume}x threshold "
                f"(symbol: {context.symbol}, "
                f"pattern_bar: {context.pattern.pattern_bar_timestamp.isoformat()})"
            )
            metadata = {
                "actual_volume_ratio": float(volume_ratio),
                "threshold": float(config.spring_max_volume),
                "symbol": context.symbol,
                "pattern_type": "SPRING",
                "pattern_bar_timestamp": context.pattern.pattern_bar_timestamp.isoformat(),
            }
            logger.error(
                "volume_validation_failed",
                pattern_type="SPRING",
                volume_ratio=float(volume_ratio),
                threshold=float(config.spring_max_volume),
                reason=reason,
            )
            return self.create_result(ValidationStatus.FAIL, reason, metadata)

        # FR13: Test confirmation volume must decrease
        if context.pattern.test_confirmed and config.test_volume_decrease_required:
            if context.test_volume_ratio is None:
                logger.error(
                    "volume_validation_failed",
                    pattern_type="SPRING",
                    reason="Test volume ratio missing for confirmed test",
                )
                return self.create_result(
                    ValidationStatus.FAIL, reason="Test volume ratio missing for confirmed test"
                )

            if context.test_volume_ratio >= volume_ratio:
                reason = (
                    f"Test volume not decreasing: "
                    f"test {context.test_volume_ratio}x >= "
                    f"pattern {volume_ratio}x"
                )
                metadata = {
                    "test_volume_ratio": float(context.test_volume_ratio),
                    "pattern_volume_ratio": float(volume_ratio),
                    "symbol": context.symbol,
                }
                logger.error(
                    "volume_validation_failed",
                    pattern_type="SPRING",
                    test_volume=float(context.test_volume_ratio),
                    pattern_volume=float(volume_ratio),
                    reason=reason,
                )
                return self.create_result(ValidationStatus.FAIL, reason, metadata)

        # Validation passed
        logger.info(
            "volume_validation_passed",
            pattern_type="SPRING",
            volume_ratio=float(volume_ratio),
            symbol=context.symbol,
        )
        return self.create_result(ValidationStatus.PASS)

    def _validate_sos(
        self, context: ValidationContext, volume_ratio: Decimal, config: VolumeValidationConfig
    ) -> StageValidationResult:
        """Validate SOS volume requirements (FR6, FR12)"""
        # FR6: SOS requires volume >= 1.5x (high volume confirms demand)
        if volume_ratio < config.sos_min_volume:
            reason = (
                f"SOS volume too low: {volume_ratio}x < "
                f"{config.sos_min_volume}x threshold "
                f"(symbol: {context.symbol}, "
                f"pattern_bar: {context.pattern.pattern_bar_timestamp.isoformat()})"
            )
            metadata = {
                "actual_volume_ratio": float(volume_ratio),
                "threshold": float(config.sos_min_volume),
                "symbol": context.symbol,
                "pattern_type": "SOS",
                "pattern_bar_timestamp": context.pattern.pattern_bar_timestamp.isoformat(),
            }
            logger.error(
                "volume_validation_failed",
                pattern_type="SOS",
                volume_ratio=float(volume_ratio),
                threshold=float(config.sos_min_volume),
                reason=reason,
            )
            return self.create_result(ValidationStatus.FAIL, reason, metadata)

        # Validation passed
        logger.info(
            "volume_validation_passed",
            pattern_type="SOS",
            volume_ratio=float(volume_ratio),
            symbol=context.symbol,
        )
        return self.create_result(ValidationStatus.PASS)

    def _validate_lps(
        self, context: ValidationContext, volume_ratio: Decimal, config: VolumeValidationConfig
    ) -> StageValidationResult:
        """Validate LPS volume requirements (FR7 - WYCKOFF ENHANCED)"""
        # FR7: Standard LPS requires volume < 1.0x (reduced volume shows resting)
        if volume_ratio < config.lps_max_volume:
            # Standard quiet LPS - validation passed
            logger.info(
                "volume_validation_passed",
                pattern_type="LPS",
                volume_ratio=float(volume_ratio),
                lps_type="quiet",
                symbol=context.symbol,
            )
            return self.create_result(ValidationStatus.PASS)

        # Volume >= 1.0x - check for WYCKOFF ENHANCEMENT: absorption pattern
        if config.lps_allow_absorption:
            # Check absorption pattern criteria
            volume_analysis = context.volume_analysis

            # All conditions must be met for shakeout absorption LPS:
            # 1. Volume not excessive (< 1.5x)
            # 2. Closes high in range (>= 0.7)
            # 3. Effort/Result = ABSORPTION (high volume + narrow spread)
            if (
                volume_ratio <= config.lps_absorption_max_volume
                and volume_analysis.close_position >= config.lps_absorption_min_close_position
                and volume_analysis.effort_result == EffortResult.ABSORPTION
            ):
                logger.info(
                    "volume_validation_passed",
                    pattern_type="LPS",
                    volume_ratio=float(volume_ratio),
                    lps_type="absorption_shakeout",
                    close_position=float(volume_analysis.close_position),
                    effort_result=volume_analysis.effort_result.value,
                    symbol=context.symbol,
                )
                metadata = {
                    "lps_type": "absorption_shakeout",
                    "volume_ratio": float(volume_ratio),
                    "close_position": float(volume_analysis.close_position),
                    "effort_result": volume_analysis.effort_result.value,
                }
                return self.create_result(ValidationStatus.PASS, metadata=metadata)

        # Standard LPS failed and no valid absorption pattern
        reason = (
            f"LPS volume too high: {volume_ratio}x >= "
            f"{config.lps_max_volume}x threshold "
            f"(symbol: {context.symbol}, "
            f"pattern_bar: {context.pattern.pattern_bar_timestamp.isoformat()})"
        )
        if config.lps_allow_absorption:
            reason += " - absorption pattern criteria not met"

        metadata = {
            "actual_volume_ratio": float(volume_ratio),
            "threshold": float(config.lps_max_volume),
            "symbol": context.symbol,
            "pattern_type": "LPS",
            "pattern_bar_timestamp": context.pattern.pattern_bar_timestamp.isoformat(),
            "absorption_check_enabled": config.lps_allow_absorption,
        }
        logger.error(
            "volume_validation_failed",
            pattern_type="LPS",
            volume_ratio=float(volume_ratio),
            threshold=float(config.lps_max_volume),
            reason=reason,
        )
        return self.create_result(ValidationStatus.FAIL, reason, metadata)

    def _validate_utad(
        self, context: ValidationContext, volume_ratio: Decimal, config: VolumeValidationConfig
    ) -> StageValidationResult:
        """Validate UTAD volume requirements (FR5 - WYCKOFF ENHANCEMENT)"""
        # WYCKOFF ENHANCEMENT: UTAD requires elevated volume (supply climax)
        # Threshold: 1.2x average (moderate to high volume confirms distribution)
        if volume_ratio < config.utad_min_volume:
            reason = (
                f"UTAD volume too low: {volume_ratio}x < "
                f"{config.utad_min_volume}x threshold "
                f"(supply climax requires elevated volume) "
                f"(symbol: {context.symbol}, "
                f"pattern_bar: {context.pattern.pattern_bar_timestamp.isoformat()})"
            )
            metadata = {
                "actual_volume_ratio": float(volume_ratio),
                "threshold": float(config.utad_min_volume),
                "symbol": context.symbol,
                "pattern_type": "UTAD",
                "pattern_bar_timestamp": context.pattern.pattern_bar_timestamp.isoformat(),
            }
            logger.error(
                "volume_validation_failed",
                pattern_type="UTAD",
                volume_ratio=float(volume_ratio),
                threshold=float(config.utad_min_volume),
                reason=reason,
            )
            return self.create_result(ValidationStatus.FAIL, reason, metadata)

        # Validation passed - UTAD has elevated volume confirming supply
        # NOTE: Failure bar volume dryup validation deferred to Story 8.7
        logger.info(
            "volume_validation_passed",
            pattern_type="UTAD",
            volume_ratio=float(volume_ratio),
            symbol=context.symbol,
            note="Failure bar volume validation in Story 8.7",
        )
        return self.create_result(ValidationStatus.PASS)
