"""
Volume Validation Stage (Story 8.3 + Story 8.3.1 Forex Support)

FR12: Volume validation is a non-negotiable gatekeeper. All volume failures
result in immediate signal rejection (FAIL status).

Pattern-specific volume requirements (WYCKOFF ENHANCED):
- Spring (FR4): volume_ratio < 0.7x (low volume confirms selling exhaustion)
  - Forex: < 0.85x tick volume (wider tolerance for noise)
- SOS (FR6): volume_ratio >= 1.5x (high volume confirms demand)
  - Forex: >= 1.80x tick volume (higher threshold to filter spikes)
- UTAD (FR5): volume_ratio >= 1.2x (elevated volume confirms supply climax)
  - Forex: >= 2.50x tick volume (WYCKOFF ENHANCEMENT)
- LPS (FR7): volume_ratio < 1.0x OR absorption pattern (WYCKOFF ENHANCEMENT)
- Test (FR13): test_volume < pattern_volume (decreased volume confirms test)

Forex Extensions (Story 8.3.1):
-------------------------------
- Session-aware baselines (compare to London/NY/Asian avg, not daily)
- News event filtering (reject patterns during NFP/FOMC tick spikes)
- Broker-relative percentile calculations (not absolute tick counts)
- Asian session stricter thresholds (60% spring, 200% SOS)

Author: Story 8.3, Story 8.3.1
"""

from decimal import Decimal
from typing import Any

import structlog

from src.models.effort_result import EffortResult
from src.models.forex import ForexSession, NewsEvent
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

    def _calculate_volume_percentile(
        self, current_volume: Decimal, historical_volumes: list[Decimal]
    ) -> int:
        """
        Calculate broker-relative percentile for tick volume (Story 8.3.1, AC 5).

        Tick volume varies by broker, so absolute values are meaningless.
        Percentile ranking within broker's own historical data provides
        comparable measurements.

        Args:
            current_volume: Current bar tick volume
            historical_volumes: Last 100+ bars of tick volume from same broker

        Returns:
            int: Percentile (0-100) where current volume ranks

        Example:
            >>> historical = [Decimal(str(v)) for v in [500, 600, 700, 800, 900]]
            >>> self._calculate_volume_percentile(Decimal("750"), historical)
            60  # 750 is at 60th percentile (above 60% of historical bars)
        """
        if not historical_volumes or len(historical_volumes) == 0:
            logger.warning("forex_percentile_calculation_failed", reason="Empty historical volumes")
            return 50  # Default to median if no data

        # Sort volumes in ascending order
        sorted_volumes = sorted(historical_volumes)

        # Find position of current volume
        position = sum(1 for v in sorted_volumes if v <= current_volume)

        # Calculate percentile (0-100)
        percentile = int((position / len(sorted_volumes)) * 100)

        logger.debug(
            "forex_volume_percentile_calculated",
            current_volume=float(current_volume),
            percentile=percentile,
            sample_size=len(historical_volumes),
        )

        return percentile

    def _interpret_volume_percentile(self, percentile: int, pattern_type: str) -> str:
        """
        Generate human-readable interpretation of volume percentile (Wyckoff crew P2).

        Args:
            percentile: Volume percentile (0-100)
            pattern_type: Pattern type (SPRING, SOS, etc.)

        Returns:
            str: Human-readable interpretation explaining what the percentile means

        Example:
            >>> self._interpret_volume_percentile(15, "SPRING")
            "Very low activity (bottom 15% of recent volume). This supports the Wyckoff principle of 'selling exhaustion' - weak sellers are giving up."
        """
        if percentile < 10:
            if pattern_type == "SPRING":
                return (
                    f"Extremely low activity (bottom {percentile}% of recent volume). "
                    "This strongly supports the Wyckoff principle of 'selling exhaustion' - "
                    "supply has dried up, indicating sellers are depleted."
                )
            else:
                return (
                    f"Extremely low activity (bottom {percentile}% of recent volume). "
                    "This is unusually quiet and may indicate lack of institutional participation."
                )
        elif percentile < 25:
            if pattern_type == "SPRING":
                return (
                    f"Very low activity (bottom 25% of recent volume, specifically {percentile}th percentile). "
                    "This supports 'selling exhaustion' - weak hands are exiting without conviction."
                )
            else:
                return (
                    f"Very low activity (bottom 25%, specifically {percentile}th percentile). "
                    "Below-average participation suggests caution."
                )
        elif percentile < 50:
            return (
                f"Below average activity ({percentile}th percentile). "
                f"Volume is in the lower half of recent history."
            )
        elif percentile < 75:
            if pattern_type == "SOS":
                return (
                    f"Above average activity ({percentile}th percentile). "
                    "This shows increased participation, supporting institutional accumulation."
                )
            else:
                return (
                    f"Above average activity ({percentile}th percentile). "
                    "Volume is in the upper half of recent history."
                )
        elif percentile < 90:
            if pattern_type == "SOS":
                return (
                    f"High activity (top 25%, specifically {percentile}th percentile). "
                    "Strong participation confirms demand overwhelming supply (Wyckoff 'sign of strength')."
                )
            else:
                return (
                    f"High activity (top 25%, specifically {percentile}th percentile). "
                    "This indicates elevated institutional interest."
                )
        else:  # percentile >= 90
            if pattern_type == "SOS":
                return (
                    f"Climactic activity (top {100 - percentile}% of recent volume). "
                    "Exceptional participation confirms institutional accumulation completing (Wyckoff climax)."
                )
            else:
                return (
                    f"Climactic activity (top {100 - percentile}% of recent volume). "
                    "This represents extreme participation and potential turning point."
                )

    async def _check_volume_spike_anomaly(
        self, context: ValidationContext, volume_ratio: Decimal
    ) -> tuple[bool, str | None]:
        """
        Detect volume spike anomalies beyond news events (Wyckoff crew P2).

        Catches flash crashes, broker outages, 'fat finger' orders, and other
        non-Wyckoff volume spikes that news event filtering misses.

        Args:
            context: ValidationContext with volume_analysis
            volume_ratio: Current bar volume ratio

        Returns:
            tuple[bool, str | None]: (is_anomaly, reason if anomaly detected)

        Example:
            >>> # 5.5x volume spike without news event
            >>> is_anomaly, reason = await self._check_volume_spike_anomaly(context, Decimal("5.5"))
            >>> print(is_anomaly)  # True
            >>> print(reason)      # "Volume spike 5.5x exceeds 5.0x anomaly threshold..."
        """
        # Only applies to forex (stocks have different spike characteristics)
        if context.asset_class != "FOREX":
            return False, None

        # Define anomaly threshold: 5x volume spike is NEVER normal Wyckoff activity
        ANOMALY_THRESHOLD = Decimal("5.0")

        if volume_ratio >= ANOMALY_THRESHOLD:
            reason = (
                f"Volume spike {volume_ratio}x exceeds {ANOMALY_THRESHOLD}x anomaly threshold. "
                f"This is NOT normal Wyckoff activity - may be flash crash, broker outage, "
                f"or 'fat finger' order. Symbol: {context.symbol}, "
                f"Pattern bar: {context.pattern.pattern_bar_timestamp.isoformat()}"
            )
            logger.warning(
                "forex_volume_spike_anomaly",
                volume_ratio=float(volume_ratio),
                threshold=float(ANOMALY_THRESHOLD),
                symbol=context.symbol,
                pattern_type=context.pattern.pattern_type,
                pattern_bar=context.pattern.pattern_bar_timestamp.isoformat(),
            )
            return True, reason

        return False, None

    async def _check_news_event_tick_spike(
        self, context: ValidationContext
    ) -> tuple[bool, str | None]:
        """
        Check if pattern occurred during news-driven tick volume spike (Story 8.3.1, AC 4).

        High-impact forex events (NFP, FOMC, ECB) cause 500-1000% tick spikes that
        are NOT Wyckoff climactic volume - they're noise from retail panic/algos.

        Args:
            context: ValidationContext with pattern and market_context

        Returns:
            tuple[bool, str | None]: (is_news_spike, event_type if spike detected)

        Example:
            >>> # Pattern at 8:30am EST during NFP release
            >>> is_spike, event = await self._check_news_event_tick_spike(context)
            >>> print(is_spike)  # True
            >>> print(event)     # "NFP"
        """
        # Only applies to forex
        if context.asset_class != "FOREX":
            return False, None

        # Check if market_context has news events
        if context.market_context is None:
            return False, None

        # Extract news event if present
        news_event: NewsEvent | None = getattr(context.market_context, "news_event", None)
        if news_event is None:
            return False, None

        # Only high-impact events cause problematic tick spikes
        if news_event.impact_level != "HIGH":
            return False, None

        # Check if pattern bar within ±1 hour of event
        pattern_time = context.pattern.pattern_bar_timestamp
        event_time = news_event.event_date

        time_diff_hours = abs((pattern_time - event_time).total_seconds() / 3600)

        if time_diff_hours < 1.0:
            logger.warning(
                "forex_news_spike_detected",
                event_type=news_event.event_type,
                event_time=event_time.isoformat(),
                pattern_time=pattern_time.isoformat(),
                time_diff_hours=round(time_diff_hours, 2),
            )
            return True, news_event.event_type

        return False, None

    def _get_forex_threshold(
        self,
        pattern_type: str,
        threshold_type: str,
        config: VolumeValidationConfig,
        context: ValidationContext,
    ) -> Decimal:
        """
        Get forex-specific threshold with session adjustments (Story 8.3.1, AC 2, 6).

        Applies session-based adjustments for Asian session (stricter thresholds
        due to low liquidity).

        Args:
            pattern_type: Pattern type (SPRING, SOS, etc.)
            threshold_type: "max" or "min"
            config: VolumeValidationConfig with forex thresholds
            context: ValidationContext with forex_session

        Returns:
            Decimal: Session-adjusted threshold

        Example:
            >>> # Spring during London session
            >>> threshold = self._get_forex_threshold("SPRING", "max", config, context)
            >>> print(threshold)  # Decimal("0.85")
            >>>
            >>> # Spring during Asian session
            >>> threshold = self._get_forex_threshold("SPRING", "max", config, context)
            >>> print(threshold)  # Decimal("0.60") - stricter!
        """
        forex_session = context.forex_session

        # Asian session uses stricter thresholds (low liquidity)
        if forex_session == ForexSession.ASIAN:
            if pattern_type == "SPRING" and threshold_type == "max":
                return config.forex_asian_spring_max_volume
            elif pattern_type == "SOS" and threshold_type == "min":
                return config.forex_asian_sos_min_volume

        # All other sessions use standard forex thresholds
        if pattern_type == "SPRING" and threshold_type == "max":
            return config.forex_spring_max_volume
        elif pattern_type == "TEST" and threshold_type == "max":
            return config.forex_test_max_volume
        elif pattern_type == "SOS" and threshold_type == "min":
            return config.forex_sos_min_volume
        elif pattern_type == "UTAD" and threshold_type == "min":
            return config.forex_utad_min_volume
        else:
            # Fallback to stock thresholds if unknown pattern
            if threshold_type == "max":
                return config.spring_max_volume
            else:
                return config.sos_min_volume

    async def validate(self, context: ValidationContext) -> StageValidationResult:
        """
        Execute volume validation for the pattern.

        Supports both stock (actual volume) and forex (tick volume) validation
        with session-aware thresholds and news event filtering.

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

        # Forex-specific: Check for volume spike anomaly (Wyckoff crew P2)
        if context.asset_class == "FOREX":
            is_anomaly, anomaly_reason = await self._check_volume_spike_anomaly(
                context, volume_ratio
            )
            if is_anomaly:
                metadata = {
                    "volume_ratio": float(volume_ratio),
                    "anomaly_threshold": 5.0,
                    "pattern_bar_timestamp": context.pattern.pattern_bar_timestamp.isoformat(),
                    "symbol": context.symbol,
                }
                logger.error(
                    "volume_validation_failed",
                    reason="Volume spike anomaly",
                    volume_ratio=float(volume_ratio),
                    pattern_id=str(context.pattern.id),
                )
                return self.create_result(ValidationStatus.FAIL, anomaly_reason, metadata)

        # Forex-specific: Check for news event tick spike (Story 8.3.1, AC 4)
        if context.asset_class == "FOREX":
            is_news_spike, event_type = await self._check_news_event_tick_spike(context)
            if is_news_spike:
                reason = (
                    f"Pattern bar occurred during {event_type} news event. "
                    f"Tick volume spike is news-driven, not institutional Wyckoff activity. "
                    f"Symbol: {context.symbol}, "
                    f"Pattern: {context.pattern.pattern_bar_timestamp.isoformat()}"
                )
                metadata = {
                    "news_event": event_type,
                    "pattern_bar_timestamp": context.pattern.pattern_bar_timestamp.isoformat(),
                    "symbol": context.symbol,
                }
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
                    # Use Wyckoff crew P2 interpretation helper
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
                # Use Wyckoff crew P2 interpretation helper
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
                    # Use Wyckoff crew P2 interpretation helper
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
                # Use Wyckoff crew P2 interpretation helper
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
