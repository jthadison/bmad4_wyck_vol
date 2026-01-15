"""
Volume Validation Stage Facade (Story 18.6.3)

FR12: Volume validation is a non-negotiable gatekeeper. All volume failures
result in immediate signal rejection (FAIL status).

This module is now a facade that delegates to extracted analyzers (Story 18.6.3):
- NewsEventDetector: Detects news-driven tick spikes
- VolumeAnomalyDetector: Detects volume spike anomalies
- ForexThresholdAdjuster: Session-aware threshold calculation
- PercentileCalculator: Broker-relative percentile calculation

Pattern-specific volume requirements (WYCKOFF ENHANCED):
- Spring (FR4): volume_ratio < 0.7x (low volume confirms selling exhaustion)
  - Forex: < 0.85x tick volume (wider tolerance for noise)
- SOS (FR6): volume_ratio >= 1.5x (high volume confirms demand)
  - Forex: >= 1.80x tick volume (higher threshold to filter spikes)
- UTAD (FR5): volume_ratio >= 1.2x (elevated volume confirms supply climax)
  - Forex: >= 2.50x tick volume (WYCKOFF ENHANCEMENT)
- LPS (FR7): volume_ratio < 1.0x OR absorption pattern (WYCKOFF ENHANCEMENT)
- Test (FR13): test_volume < pattern_volume (decreased volume confirms test)

Refactored per CF-006 from Critical Foundation Refactoring document.

Author: Story 8.3, Story 8.3.1, Story 18.6.3 (Facade Refactoring)
"""

from decimal import Decimal
from typing import Any

import structlog

from src.models.effort_result import EffortResult
from src.models.validation import (
    StageValidationResult,
    ValidationContext,
    ValidationStatus,
    VolumeValidationConfig,
)
from src.signal_generator.validators.base import BaseValidator
from src.signal_generator.validators.volume.analyzers import (
    NewsEventDetector,
    PercentileCalculator,
    VolumeAnomalyDetector,
)
from src.signal_generator.validators.volume.forex import ForexThresholdAdjuster

logger = structlog.get_logger()


class VolumeValidator(BaseValidator):
    """
    Validates pattern volume requirements (FR12).

    This is the FIRST stage in the validation chain (FR20). Early exit on
    volume failure avoids expensive phase/level/risk validation.

    Story 18.6.3 Refactoring:
    -------------------------
    This class is now a facade that delegates to extracted analyzers:
    - NewsEventDetector: For news-driven tick spike detection
    - VolumeAnomalyDetector: For volume anomaly detection
    - ForexThresholdAdjuster: For session-aware threshold calculation
    - PercentileCalculator: For broker-relative percentile calculation

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

    def __init__(self) -> None:
        """Initialize the facade with analyzer instances."""
        self._news_detector = NewsEventDetector()
        self._anomaly_detector = VolumeAnomalyDetector()
        self._threshold_adjuster = ForexThresholdAdjuster()
        self._percentile_calculator = PercentileCalculator()

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

    def _calculate_volume_percentile(
        self, current_volume: Decimal, historical_volumes: list[Decimal]
    ) -> int:
        """
        Calculate broker-relative percentile for tick volume.

        Delegates to PercentileCalculator (Story 18.6.3).

        Parameters:
        -----------
        current_volume : Decimal
            Current bar tick volume
        historical_volumes : list[Decimal]
            Last 100+ bars of tick volume from same broker

        Returns:
        --------
        int
            Percentile (0-100) where current volume ranks
        """
        return self._percentile_calculator.calculate(current_volume, historical_volumes)

    def _interpret_volume_percentile(self, percentile: int, pattern_type: str) -> str:
        """
        Generate human-readable interpretation of volume percentile.

        Delegates to PercentileCalculator (Story 18.6.3).

        Parameters:
        -----------
        percentile : int
            Volume percentile (0-100)
        pattern_type : str
            Pattern type (SPRING, SOS, etc.)

        Returns:
        --------
        str
            Human-readable interpretation
        """
        return self._percentile_calculator.interpret(percentile, pattern_type)

    def _get_forex_threshold(
        self,
        pattern_type: str,
        threshold_type: str,
        config: VolumeValidationConfig,
        context: ValidationContext,
    ) -> Decimal:
        """
        Get forex-specific threshold with session adjustments.

        Delegates to ForexThresholdAdjuster (Story 18.6.3).

        Parameters:
        -----------
        pattern_type : str
            Pattern type (SPRING, SOS, UTAD, etc.)
        threshold_type : str
            "max" or "min"
        config : VolumeValidationConfig
            VolumeValidationConfig with forex thresholds
        context : ValidationContext
            Context with forex_session

        Returns:
        --------
        Decimal
            Session-adjusted threshold
        """
        return self._threshold_adjuster.get_threshold(pattern_type, threshold_type, config, context)

    async def validate(self, context: ValidationContext) -> StageValidationResult:
        """
        Execute volume validation for the pattern.

        Supports both stock (actual volume) and forex (tick volume) validation
        with session-aware thresholds and news event filtering.

        Parameters:
        -----------
        context : ValidationContext
            ValidationContext with pattern and volume_analysis

        Returns:
        --------
        StageValidationResult
            Result with PASS or FAIL (never WARN per FR12)
        """
        logger.debug(
            "volume_validation_started",
            pattern_id=str(context.pattern.id),
            pattern_type=context.pattern.pattern_type,
            symbol=context.symbol,
            asset_class=context.asset_class,
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

        # Get volume ratio early for checks
        volume_ratio = context.volume_analysis.volume_ratio

        # Forex-specific: Check for volume spike anomaly (delegates to VolumeAnomalyDetector)
        if context.asset_class == "FOREX":
            is_anomaly, anomaly_reason = await self._anomaly_detector.check(context, volume_ratio)
            if is_anomaly:
                metadata = self._anomaly_detector.build_rejection_metadata(volume_ratio, context)
                logger.error(
                    "volume_validation_failed",
                    reason="Volume spike anomaly",
                    volume_ratio=float(volume_ratio),
                    pattern_id=str(context.pattern.id),
                )
                return self.create_result(ValidationStatus.FAIL, anomaly_reason, metadata)

        # Forex-specific: Check for news event tick spike (delegates to NewsEventDetector)
        if context.asset_class == "FOREX":
            is_news_spike, event_type = await self._news_detector.check(context)
            if is_news_spike:
                reason = self._news_detector.build_rejection_reason(event_type, context)
                metadata = self._news_detector.build_rejection_metadata(event_type, context)
                logger.error(
                    "volume_validation_failed",
                    reason="News-driven tick spike",
                    event_type=event_type,
                    pattern_id=str(context.pattern.id),
                )
                return self.create_result(ValidationStatus.FAIL, reason, metadata)

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
        """
        Validate Spring volume requirements (FR4, FR12, Story 8.3.1).

        Stock: volume < 0.7x (low volume confirms selling exhaustion)
        Forex: tick volume < 0.85x (wider tolerance for volatility)
        Forex Asian: tick volume < 0.60x (stricter for low liquidity)
        """
        # Determine threshold based on asset class
        if context.asset_class == "FOREX":
            threshold = self._get_forex_threshold("SPRING", "max", config, context)
            volume_source = "TICK"
            session_info = (
                f", session: {context.forex_session.value if context.forex_session else 'UNKNOWN'}"
            )
        else:
            threshold = config.spring_max_volume
            volume_source = "ACTUAL"
            session_info = ""

        # FR4: Spring requires low volume (confirms exhaustion)
        if volume_ratio >= threshold:
            reason = (
                f"Spring {volume_source.lower()} volume too high: {volume_ratio}x >= "
                f"{threshold}x threshold "
                f"(symbol: {context.symbol}{session_info}, "
                f"pattern_bar: {context.pattern.pattern_bar_timestamp.isoformat()})"
            )

            # Build metadata with forex-specific fields
            metadata: dict[str, Any] = {
                "actual_volume_ratio": float(volume_ratio),
                "threshold": float(threshold),
                "symbol": context.symbol,
                "pattern_type": "SPRING",
                "pattern_bar_timestamp": context.pattern.pattern_bar_timestamp.isoformat(),
                "volume_source": volume_source,
                "asset_class": context.asset_class,
            }

            # Add forex-specific metadata
            if context.asset_class == "FOREX":
                metadata["forex_session"] = (
                    context.forex_session.value if context.forex_session else None
                )
                if context.historical_volumes:
                    current_volume = Decimal(str(context.volume_analysis.bar.volume))
                    percentile = self._calculate_volume_percentile(
                        current_volume, context.historical_volumes
                    )
                    metadata["volume_percentile"] = percentile
                    metadata["volume_interpretation"] = self._interpret_volume_percentile(
                        percentile, "SPRING"
                    )

            logger.error(
                "volume_validation_failed",
                pattern_type="SPRING",
                volume_ratio=float(volume_ratio),
                threshold=float(threshold),
                volume_source=volume_source,
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

        # Validation passed - build metadata with forex info if applicable
        pass_metadata: dict[str, Any] | None = None
        if context.asset_class == "FOREX":
            pass_metadata = {
                "volume_source": "TICK",
                "volume_ratio": float(volume_ratio),
                "threshold": float(threshold),
                "forex_session": context.forex_session.value if context.forex_session else None,
                "baseline_type": "session_average",
            }
            if context.historical_volumes:
                current_volume = Decimal(str(context.volume_analysis.bar.volume))
                percentile = self._calculate_volume_percentile(
                    current_volume, context.historical_volumes
                )
                pass_metadata["volume_percentile"] = percentile
                pass_metadata["volume_interpretation"] = self._interpret_volume_percentile(
                    percentile, "SPRING"
                )

        logger.info(
            "volume_validation_passed",
            pattern_type="SPRING",
            volume_ratio=float(volume_ratio),
            symbol=context.symbol,
            volume_source=volume_source,
            asset_class=context.asset_class,
        )
        return self.create_result(ValidationStatus.PASS, metadata=pass_metadata)

    def _validate_sos(
        self, context: ValidationContext, volume_ratio: Decimal, config: VolumeValidationConfig
    ) -> StageValidationResult:
        """
        Validate SOS volume requirements (FR6, FR12, Story 8.3.1).

        Stock: volume >= 1.5x (high volume confirms demand)
        Forex: tick volume >= 1.80x (higher threshold to filter noise)
        Forex Asian: tick volume >= 2.00x (even higher for low liquidity)
        """
        # Determine threshold based on asset class
        if context.asset_class == "FOREX":
            threshold = self._get_forex_threshold("SOS", "min", config, context)
            volume_source = "TICK"
            session_info = (
                f", session: {context.forex_session.value if context.forex_session else 'UNKNOWN'}"
            )
        else:
            threshold = config.sos_min_volume
            volume_source = "ACTUAL"
            session_info = ""

        # FR6: SOS requires high volume (confirms demand overwhelming supply)
        if volume_ratio < threshold:
            reason = (
                f"SOS {volume_source.lower()} volume too low: {volume_ratio}x < "
                f"{threshold}x threshold "
                f"(symbol: {context.symbol}{session_info}, "
                f"pattern_bar: {context.pattern.pattern_bar_timestamp.isoformat()})"
            )

            # Build metadata with forex-specific fields
            metadata: dict[str, Any] = {
                "actual_volume_ratio": float(volume_ratio),
                "threshold": float(threshold),
                "symbol": context.symbol,
                "pattern_type": "SOS",
                "pattern_bar_timestamp": context.pattern.pattern_bar_timestamp.isoformat(),
                "volume_source": volume_source,
                "asset_class": context.asset_class,
            }

            # Add forex-specific metadata
            if context.asset_class == "FOREX":
                metadata["forex_session"] = (
                    context.forex_session.value if context.forex_session else None
                )
                if context.historical_volumes:
                    current_volume = Decimal(str(context.volume_analysis.bar.volume))
                    percentile = self._calculate_volume_percentile(
                        current_volume, context.historical_volumes
                    )
                    metadata["volume_percentile"] = percentile
                    metadata["volume_interpretation"] = self._interpret_volume_percentile(
                        percentile, "SOS"
                    )

            logger.error(
                "volume_validation_failed",
                pattern_type="SOS",
                volume_ratio=float(volume_ratio),
                threshold=float(threshold),
                volume_source=volume_source,
                reason=reason,
            )
            return self.create_result(ValidationStatus.FAIL, reason, metadata)

        # Validation passed - build metadata with forex info if applicable
        pass_metadata: dict[str, Any] | None = None
        if context.asset_class == "FOREX":
            pass_metadata = {
                "volume_source": "TICK",
                "volume_ratio": float(volume_ratio),
                "threshold": float(threshold),
                "forex_session": context.forex_session.value if context.forex_session else None,
                "baseline_type": "session_average",
            }
            if context.historical_volumes:
                current_volume = Decimal(str(context.volume_analysis.bar.volume))
                percentile = self._calculate_volume_percentile(
                    current_volume, context.historical_volumes
                )
                pass_metadata["volume_percentile"] = percentile
                pass_metadata["volume_interpretation"] = self._interpret_volume_percentile(
                    percentile, "SOS"
                )

        logger.info(
            "volume_validation_passed",
            pattern_type="SOS",
            volume_ratio=float(volume_ratio),
            symbol=context.symbol,
            volume_source=volume_source,
            asset_class=context.asset_class,
        )
        return self.create_result(ValidationStatus.PASS, metadata=pass_metadata)

    def _validate_lps(
        self, context: ValidationContext, volume_ratio: Decimal, config: VolumeValidationConfig
    ) -> StageValidationResult:
        """Validate LPS volume requirements (FR7 - WYCKOFF ENHANCED)."""
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
        """Validate UTAD volume requirements (FR5 - WYCKOFF ENHANCEMENT)."""
        # WYCKOFF ENHANCEMENT: UTAD requires elevated volume (supply climax)
        # Threshold: 1.2x average (stock), 2.5x (forex)

        # Determine threshold based on asset class
        if context.asset_class == "FOREX":
            threshold = self._get_forex_threshold("UTAD", "min", config, context)
        else:
            threshold = config.utad_min_volume

        if volume_ratio < threshold:
            # Wyckoff crew P2: Log forex UTAD near-misses (200-250% range)
            if context.asset_class == "FOREX" and Decimal("2.0") <= volume_ratio < threshold:
                logger.info(
                    "forex_utad_near_miss",
                    volume_ratio=float(volume_ratio),
                    threshold=float(threshold),
                    symbol=context.symbol,
                    session=context.forex_session.value if context.forex_session else None,
                    note="UTAD rejected but would pass at 200% threshold",
                )

            reason = (
                f"UTAD volume too low: {volume_ratio}x < "
                f"{threshold}x threshold "
                f"(supply climax requires elevated volume) "
                f"(symbol: {context.symbol}, "
                f"pattern_bar: {context.pattern.pattern_bar_timestamp.isoformat()})"
            )
            metadata = {
                "actual_volume_ratio": float(volume_ratio),
                "threshold": float(threshold),
                "symbol": context.symbol,
                "pattern_type": "UTAD",
                "pattern_bar_timestamp": context.pattern.pattern_bar_timestamp.isoformat(),
            }
            logger.error(
                "volume_validation_failed",
                pattern_type="UTAD",
                volume_ratio=float(volume_ratio),
                threshold=float(threshold),
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
