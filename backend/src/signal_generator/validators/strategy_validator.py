"""
Strategy Validator - Final Validation Stage (Story 8.7 - William)

Purpose:
--------
Validates Wyckoff strategic sanity checks that technical analysis alone cannot capture.
Fifth and final stage in validation chain (Volume → Phase → Levels → Risk → Strategy).

This validator embodies "William's wisdom" - catches signals that technically pass
but violate trading common sense and Wyckoff principles.

Validation Rules:
-----------------
- Market regime appropriateness (avoid springs in extreme volatility)
- Earnings blackout windows (FR29 - 24hr before, 2hr after for stocks)
- Forex high-impact events (NFP 6hr/2hr, FOMC 4hr/2hr, CPI 2hr/1hr)
- Recent invalidations (don't re-enter failed campaigns within cooldown)
- Time-based checks (avoid end-of-day entries for stocks, Friday PM for forex)
- High-conviction overrides for exceptional signals (≥90% confidence)
- Human review flagging for borderline cases

Integration:
------------
- Story 8.2: BaseValidator, ValidationResult framework
- Story 8.6: campaign_id from RiskValidator context
- Epic 2: Volume analysis (ATR for volatility)
- Epic 4: Phase detection (ADX for trend strength)
- Epic 7: Campaign tracking (recent_invalidations)

Author: Story 8.7 - William (Mentor)
"""

from datetime import time

import structlog

from src.models.market_context import (
    AssetClass,
    MarketContext,
    MarketRegime,
)
from src.models.validation import (
    StageValidationResult,
    ValidationContext,
    ValidationStatus,
)
from src.services.news_calendar_factory import NewsCalendarFactory
from src.signal_generator.validators.base import BaseValidator

logger = structlog.get_logger()


class StrategyValidator(BaseValidator):
    """
    Final validation stage: Wyckoff strategic sanity checks (William - Mentor).

    Validates signals against strategic context that technical analysis alone cannot capture:
    - Market regime appropriateness (avoid springs in extreme volatility)
    - Earnings blackout windows (FR29 - 24hr before, 2hr after)
    - Forex high-impact events (event-specific windows: NFP 6hr/2hr, FOMC 4hr/2hr)
    - Recent invalidations (don't re-enter failed campaigns)
    - Time-based checks (avoid end-of-day entries, Friday PM forex)
    - High-conviction overrides for exceptional signals
    - Human review flagging for borderline cases

    Example:
        ```python
        validator = StrategyValidator(news_calendar_factory=factory)
        result = await validator.validate(context)

        if result.status == ValidationStatus.FAIL:
            # Signal rejected - earnings blackout or other critical issue
            print(f"Rejected: {result.reason}")
        elif result.status == ValidationStatus.WARN:
            # Signal has warnings but can proceed
            print(f"Warning: {result.reason}")
        ```
    """

    def __init__(
        self,
        news_calendar_factory: NewsCalendarFactory,
        invalidation_cooldown_days_stock: int = 5,
        invalidation_cooldown_days_forex: int = 3,
        high_conviction_threshold: float = 0.90,
    ):
        """
        Initialize strategy validator.

        Args:
            news_calendar_factory: NewsCalendarFactory for asset-class-aware news checks
            invalidation_cooldown_days_stock: Cooldown for stock invalidations (default 5)
            invalidation_cooldown_days_forex: Cooldown for forex invalidations (default 3)
            high_conviction_threshold: Confidence threshold for overrides (default 0.90)
        """
        self.news_calendar_factory = news_calendar_factory
        self.cooldown_days_stock = invalidation_cooldown_days_stock
        self.cooldown_days_forex = invalidation_cooldown_days_forex
        self.high_conviction_threshold = high_conviction_threshold

    @property
    def validator_id(self) -> str:
        """Unique identifier for this validator."""
        return "STRATEGY_VALIDATOR"

    @property
    def stage_name(self) -> str:
        """Human-readable stage name."""
        return "Strategy"

    async def validate(self, context: ValidationContext) -> StageValidationResult:
        """
        Execute William's strategic validation checks.

        Validation steps:
        1. Validate market_context presence
        2. Validate market regime (extreme volatility check)
        3. Validate news blackout window (FR29 - asset-class-aware)
        4. Validate recent invalidations (cooldown period)
        5. Validate time of day (end-of-day, Friday PM forex, etc.)
        6. Check strategic overrides (high-conviction signals)
        7. Flag for human review if borderline

        Args:
            context: ValidationContext with pattern and market_context

        Returns:
            StageValidationResult with PASS/WARN/FAIL and William's reasoning
        """
        logger.info(
            "william_strategy_validation_started",
            pattern_id=str(context.pattern.id),
            pattern_type=context.pattern.pattern_type,
            symbol=context.symbol,
            confidence=context.pattern.confidence_score,
        )

        # Step 1: Validate market_context presence
        if context.market_context is None:
            return self.create_result(
                ValidationStatus.FAIL,
                reason="Market context not available for strategy validation",
                metadata={
                    "william_reasoning": "Cannot assess strategic suitability without market context"
                },
            )

        market_context = context.market_context
        pattern = context.pattern
        warnings: list[str] = []

        # Step 2: Validate market regime
        regime_passes, regime_reason, regime_status = self._validate_market_regime(
            pattern.pattern_type, market_context
        )
        if regime_status == ValidationStatus.FAIL:
            return self.create_result(
                ValidationStatus.FAIL,
                reason=regime_reason,
                metadata=self._build_metadata(
                    market_context, [], False, False, None, regime_reason
                ),
            )
        elif regime_status == ValidationStatus.WARN and regime_reason:
            warnings.append(regime_reason)

        # Step 3: Validate news blackout (FR29) - NON-NEGOTIABLE
        news_passes, news_reason = await self._validate_news_blackout(
            context.symbol, market_context.asset_class, self.news_calendar_factory
        )
        if not news_passes:
            return self.create_result(
                ValidationStatus.FAIL,
                reason=news_reason,
                metadata=self._build_metadata(
                    market_context, warnings, False, False, None, news_reason
                ),
            )

        # Step 4: Validate recent invalidations
        invalidation_passes, invalidation_reason = self._validate_recent_invalidations(
            pattern.pattern_type,
            getattr(context, "campaign_id", None),
            market_context.recent_invalidations,
            market_context.asset_class,
        )
        if not invalidation_passes:
            return self.create_result(
                ValidationStatus.FAIL,
                reason=invalidation_reason,
                metadata=self._build_metadata(
                    market_context, warnings, False, False, None, invalidation_reason
                ),
            )

        # Step 5: Validate time of day
        time_passes, time_reason, time_status = self._validate_time_of_day(
            market_context.asset_class,
            market_context.time_of_day,
            market_context.market_session,
            market_context.forex_session,
            market_context.data_timestamp,
        )
        if time_status == ValidationStatus.FAIL:
            return self.create_result(
                ValidationStatus.FAIL,
                reason=time_reason,
                metadata=self._build_metadata(
                    market_context, warnings, False, False, None, time_reason
                ),
            )
        elif time_status == ValidationStatus.WARN and time_reason:
            warnings.append(time_reason)

        # Step 6: Check strategic overrides (high-conviction signals)
        current_status = ValidationStatus.WARN if warnings else ValidationStatus.PASS
        final_status, final_reason = self._check_override_eligibility(
            pattern.confidence_score, current_status, warnings
        )
        override_applied = (
            current_status == ValidationStatus.WARN and final_status == ValidationStatus.PASS
        )

        # Step 7: Flag for human review if borderline
        needs_review, review_reason = self._flag_for_human_review(
            warnings, pattern.confidence_score
        )

        # Build comprehensive metadata
        metadata = self._build_metadata(
            market_context,
            warnings,
            override_applied,
            needs_review,
            review_reason,
            final_reason,
        )

        # Log final decision
        if final_status == ValidationStatus.PASS:
            logger.info(
                "william_strategy_validation_passed",
                pattern_type=pattern.pattern_type,
                regime=market_context.market_regime.value,
                warnings_count=len(warnings),
                override_applied=override_applied,
                needs_review=needs_review,
                reasoning=metadata.get("william_reasoning", ""),
            )
        else:
            logger.warning(
                "william_strategy_validation_warned",
                pattern_type=pattern.pattern_type,
                warnings=warnings,
                needs_review=needs_review,
                reasoning=metadata.get("william_reasoning", ""),
            )

        return self.create_result(
            final_status,
            reason=final_reason,
            metadata=metadata,
        )

    def _validate_market_regime(
        self, pattern_type: str, market_context: MarketContext
    ) -> tuple[bool, str | None, ValidationStatus]:
        """
        Validate market regime appropriateness for pattern.

        Rules (ASSET-CLASS-AWARE):
        - Spring in HIGH_VOLATILITY (ATR ≥95th %ile stocks, ≥90th forex + volume ≥85th) → FAIL
        - SOS in SIDEWAYS (ADX <25) → WARN
        - UTAD in TRENDING_UP → WARN (contrarian)

        Args:
            pattern_type: Pattern type (SPRING, SOS, LPS, UTAD)
            market_context: MarketContext with regime and volatility

        Returns:
            Tuple of (passes, reason, status)
        """
        # Spring in extreme volatility → FAIL
        if pattern_type == "SPRING" and market_context.is_extreme_volatility:
            atr_threshold = 90 if market_context.asset_class == AssetClass.FOREX else 95
            reason = (
                f"William's assessment: Spring pattern in extreme volatility "
                f"(ATR {market_context.volatility_percentile}th percentile ≥ {atr_threshold}, "
                f"volume {market_context.volume_percentile}th percentile ≥ 85) carries high false breakout risk. "
                f"**Wyckoff Principle**: 'Genuine accumulation occurs in calm markets where Composite Operators "
                f"can methodically accumulate without drawing attention. Chaos and panic create noise, not opportunity.' "
                f"Wait for volatility to normalize before entering."
            )
            logger.debug(
                "william_market_regime_check",
                regime=market_context.market_regime.value,
                volatility_pct=market_context.volatility_percentile,
                volume_pct=market_context.volume_percentile,
                assessment=reason,
            )
            return False, reason, ValidationStatus.FAIL

        # SOS in sideways market → WARN
        if pattern_type == "SOS" and market_context.market_regime == MarketRegime.SIDEWAYS:
            adx_val = float(market_context.adx) if market_context.adx else 0
            if adx_val < 25:
                reason = (
                    f"William's caution: SOS breakout attempt in sideways market "
                    f"(ADX {adx_val:.1f} < 25 indicates weak trend). "
                    f"**Wyckoff Principle**: 'Sign of Strength is most reliable when emerging from "
                    f"established accumulation Phase C into markup Phase D. Sideways breakouts lack "
                    f"the foundational cause.' Monitor closely for follow-through volume and price action."
                )
                logger.debug(
                    "william_market_regime_check",
                    regime=market_context.market_regime.value,
                    adx=adx_val,
                    assessment=reason,
                )
                return True, reason, ValidationStatus.WARN

        # UTAD in uptrending market → WARN (contrarian)
        if pattern_type == "UTAD" and market_context.market_regime == MarketRegime.TRENDING_UP:
            reason = (
                "William's caution: UTAD (distribution) pattern in uptrending market - "
                "contrarian signal requires strong confirmation. **Wyckoff Principle**: "
                "'Distribution can occur in uptrends when smart money exits, but it's a "
                "contrarian play. Ensure volume confirmation is exceptional.'"
            )
            logger.debug(
                "william_market_regime_check",
                regime=market_context.market_regime.value,
                assessment=reason,
            )
            return True, reason, ValidationStatus.WARN

        # All other regime/pattern combinations pass
        logger.debug(
            "william_market_regime_check",
            regime=market_context.market_regime.value,
            volatility_pct=market_context.volatility_percentile,
            adx=float(market_context.adx) if market_context.adx else None,
            assessment="Market regime suitable for pattern",
        )
        return True, None, ValidationStatus.PASS

    async def _validate_news_blackout(
        self,
        symbol: str,
        asset_class: AssetClass,
        news_calendar_factory: NewsCalendarFactory,
    ) -> tuple[bool, str | None]:
        """
        Validate news blackout window - ASSET-CLASS-AWARE (FR29).

        Rules:
        - STOCK: 24hr before OR 2hr after earnings → FAIL
        - FOREX: Event-specific windows (NFP 6hr/2hr, FOMC 4hr/2hr, CPI 2hr/1hr) → FAIL

        Args:
            symbol: Trading symbol or currency pair
            asset_class: AssetClass (STOCK or FOREX)
            news_calendar_factory: Factory for asset-class routing

        Returns:
            Tuple of (passes, reason)
        """
        try:
            news_service = news_calendar_factory.get_calendar(asset_class)
            in_blackout, news_event = await news_service.check_blackout_window(symbol)

            if news_event is None:
                logger.info(
                    "william_news_check",
                    symbol=symbol,
                    asset_class=asset_class.value,
                    has_upcoming_news=False,
                    reasoning="No high-impact events scheduled - clear for entry",
                )
                return True, None

            if in_blackout:
                if asset_class == AssetClass.STOCK:
                    reason = (
                        f"William's rule: Earnings announcement for {symbol} in "
                        f"{news_event.hours_until_event:.1f} hours violates 24-hour pre-earnings "
                        f"blackout (FR29). **Wyckoff Principle**: 'Wyckoff never advocated gambling on "
                        f"binary events. His method reads price and volume action - not speculative event "
                        f"outcomes. Gap risk is antithetical to methodical analysis.' Wait until after "
                        f"earnings settles (Reference: Wyckoff, Studies in Tape Reading)."
                    )
                else:  # FOREX
                    reason = (
                        f"William's rule: {news_event.event_type} event affecting {symbol} in "
                        f"{news_event.hours_until_event:.1f} hours violates forex news blackout window. "
                        f"High-impact events cause extreme tick volume spikes and spread widening - not "
                        f"valid for Wyckoff analysis. **Wyckoff Principle**: 'Patterns are invalidated by "
                        f"news-driven volatility. Wait for organic price action to resume.'"
                    )

                logger.info(
                    "william_news_check",
                    symbol=symbol,
                    asset_class=asset_class.value,
                    has_upcoming_news=True,
                    event_type=news_event.event_type,
                    hours_until=news_event.hours_until_event,
                    blackout_active=True,
                    reasoning=reason,
                )
                return False, reason

            # Outside blackout window
            logger.info(
                "william_news_check",
                symbol=symbol,
                asset_class=asset_class.value,
                has_upcoming_news=True,
                event_type=news_event.event_type,
                hours_until=news_event.hours_until_event,
                blackout_active=False,
                reasoning="Event scheduled but outside blackout window",
            )
            return True, None

        except Exception as e:
            # Graceful degradation on API failure
            logger.warning(
                "william_news_check_error",
                symbol=symbol,
                asset_class=asset_class.value,
                error=str(e),
                reasoning="News API unavailable, proceeding without news check",
            )
            return True, None  # Don't block signal on API failure

    def _validate_recent_invalidations(
        self,
        pattern_type: str,
        campaign_id: str | None,
        recent_invalidations: list,
        asset_class: AssetClass,
    ) -> tuple[bool, str | None]:
        """
        Validate no recent invalidations in same campaign.

        Asset-class-aware cooldown (Rachel enhancement):
        - Stocks: 5 days (campaigns develop slower, daily close matters)
        - Forex: 3 days (24/5 market, faster structure development)

        Args:
            pattern_type: Pattern type
            campaign_id: Campaign ID (or None if not tracked)
            recent_invalidations: List of InvalidationEvent
            asset_class: AssetClass (STOCK or FOREX)

        Returns:
            Tuple of (passes, reason)
        """
        if campaign_id is None:
            # No campaign tracking - skip check
            logger.debug(
                "william_invalidation_check",
                campaign_id=None,
                reasoning="Campaign tracking disabled - skip invalidation check",
            )
            return True, None

        # Asset-class-aware cooldown
        if asset_class == AssetClass.STOCK:
            cooldown_days = self.cooldown_days_stock  # Default 5 days
        elif asset_class == AssetClass.FOREX:
            cooldown_days = self.cooldown_days_forex  # Default 3 days
        else:
            cooldown_days = self.cooldown_days_stock  # Default to stock

        # Check for matching invalidations within cooldown
        for invalidation in recent_invalidations:
            if invalidation.campaign_id == campaign_id and invalidation.days_ago <= cooldown_days:
                reason = (
                    f"William's wisdom: Recent stop-out in campaign {campaign_id} just "
                    f"{invalidation.days_ago:.1f} days ago (reason: {invalidation.invalidation_reason}). "
                    f"**Wyckoff Principle**: 'When the Composite Operator invalidates a campaign by "
                    f"breaking key levels, respect their intention. They have shown their hand - "
                    f"distribution is underway. Wait for a new structure to develop, not a rehash of "
                    f"the failed one.' [{asset_class.value}: {cooldown_days}-day cooldown] "
                    f"(Reference: Wyckoff, Law of Effort vs Result)."
                )
                logger.debug(
                    "william_invalidation_check",
                    campaign_id=campaign_id,
                    recent_invalidations=len(recent_invalidations),
                    days_ago=invalidation.days_ago,
                    cooldown_days=cooldown_days,
                    asset_class=asset_class.value,
                    cooldown_active=True,
                    reasoning=reason,
                )
                return False, reason

        # No recent invalidations within cooldown
        logger.debug(
            "william_invalidation_check",
            campaign_id=campaign_id,
            recent_invalidations=len(recent_invalidations),
            cooldown_days=cooldown_days,
            asset_class=asset_class.value,
            cooldown_active=False,
            reasoning="No recent invalidations within cooldown period",
        )
        return True, None

    def _validate_time_of_day(
        self,
        asset_class: AssetClass,
        time_of_day: time,
        market_session: str,
        forex_session,
        current_datetime,
    ) -> tuple[bool, str | None, ValidationStatus]:
        """
        Validate time-based entry rules - ASSET-CLASS-AWARE.

        STOCK Rules:
        - End-of-day (15:00-16:00 EST) → WARN
        - PRE_MARKET → WARN (liquidity)
        - AFTER_HOURS → WARN (slippage)

        FOREX Rules:
        - Friday after 17:00 UTC (12pm EST) → FAIL (weekend gap)
        - Friday 13:00-17:00 UTC (8am-12pm EST) → WARN (weekend approaching)
        - ASIAN session → WARN (spread widening)
        - Wednesday after 17:00 UTC (5pm EST) → WARN (triple rollover)

        Args:
            asset_class: AssetClass (STOCK or FOREX)
            time_of_day: Current market time
            market_session: Stock market session
            forex_session: Forex session (or None)
            current_datetime: Current datetime

        Returns:
            Tuple of (passes, reason, status)
        """
        if asset_class == AssetClass.STOCK:
            # Stock market hours validation
            if market_session == "PRE_MARKET":
                reason = (
                    "William's timing advice: Pre-market entry - ensure sufficient liquidity "
                    "and be prepared for gap risk at market open."
                )
                logger.debug(
                    "william_time_check",
                    time=time_of_day.strftime("%H:%M"),
                    session=market_session,
                    asset_class=asset_class.value,
                    reasoning=reason,
                )
                return True, reason, ValidationStatus.WARN

            if market_session == "AFTER_HOURS":
                reason = (
                    "William's timing advice: After-hours entry - low liquidity may cause slippage. "
                    "Consider waiting for regular session."
                )
                logger.debug(
                    "william_time_check",
                    time=time_of_day.strftime("%H:%M"),
                    session=market_session,
                    asset_class=asset_class.value,
                    reasoning=reason,
                )
                return True, reason, ValidationStatus.WARN

            if market_session == "REGULAR" and time_of_day >= time(15, 0):
                reason = (
                    f"William's timing advice: Entry at {time_of_day.strftime('%H:%M')} near market close - "
                    f"insufficient time for pattern to develop intraday. **Wyckoff Principle**: 'Patterns need "
                    f"time and volume to unfold properly. Price movements are campaigns, not isolated events. "
                    f"Rushing entry violates the natural rhythm of market action.' Consider waiting for next session."
                )
                logger.debug(
                    "william_time_check",
                    time=time_of_day.strftime("%H:%M"),
                    session=market_session,
                    asset_class=asset_class.value,
                    end_of_day_warning=True,
                    reasoning=reason,
                )
                return True, reason, ValidationStatus.WARN

            # Regular session, before 15:00 - optimal
            return True, None, ValidationStatus.PASS

        elif asset_class == AssetClass.FOREX:
            # Forex time-based validation
            weekday = current_datetime.weekday()  # 0=Mon, 4=Fri, 2=Wed
            hour = current_datetime.hour  # UTC

            # Friday after 17:00 UTC (12pm EST) → FAIL (weekend gap risk)
            if weekday == 4 and hour >= 17:
                reason = (
                    f"William's rule: Friday entry after 12pm EST rejected. Forex markets close in "
                    f"{24 - hour} hours. Weekend gap risk violates Wyckoff controlled-risk principle. "
                    f"Position would hold through 48-hour market closure with potential for major news-driven "
                    f"gaps (e.g., central bank emergency meetings, geopolitical events)."
                )
                logger.debug(
                    "william_time_check",
                    time=time_of_day.strftime("%H:%M"),
                    weekday="Friday",
                    hour=hour,
                    asset_class=asset_class.value,
                    reasoning=reason,
                )
                return False, reason, ValidationStatus.FAIL

            # Friday morning 13:00-17:00 UTC (8am-12pm EST) → WARN
            if weekday == 4 and 13 <= hour < 17:
                reason = (
                    "William's caution: Friday morning entry - WARNING: Position will likely hold over weekend. "
                    "Consider reducing position size to 50% to mitigate weekend gap risk. Forex markets close "
                    "at 5pm EST today."
                )
                logger.debug(
                    "william_time_check",
                    time=time_of_day.strftime("%H:%M"),
                    weekday="Friday",
                    hour=hour,
                    asset_class=asset_class.value,
                    reasoning=reason,
                )
                return True, reason, ValidationStatus.WARN

            # Wednesday after 17:00 UTC (5pm EST) → WARN (triple rollover)
            if weekday == 2 and hour >= 17:
                reason = (
                    "William's cost awareness: Wednesday PM entry incurs triple rollover swap charge overnight "
                    "(accounting for weekend). **Wyckoff Principle**: 'Total cost analysis includes carrying costs.' "
                    "Triple swap can be 0.1-0.3% of position - material for tight structural setups. Consider entry "
                    "cost vs setup quality."
                )
                logger.debug(
                    "william_time_check",
                    time=time_of_day.strftime("%H:%M"),
                    weekday="Wednesday",
                    hour=hour,
                    asset_class=asset_class.value,
                    reasoning=reason,
                )
                return True, reason, ValidationStatus.WARN

            # Session-based warnings
            if forex_session:
                from src.models.market_context import ForexSession

                if forex_session == ForexSession.ASIAN:
                    reason = (
                        "William's session awareness: Asian session entry - Lower liquidity and ranging behavior common. "
                        "Wyckoff patterns more reliable during London/NY sessions (higher professional participation). "
                        "WARNING: Spread widening (2-3x normal) during Asian session - ensure stop loss accounts for "
                        "wider spreads to avoid stop-out on spread volatility alone, not genuine supply. "
                        "(Victoria: Low volume = low Composite Operator activity. Rachel: Structural Wyckoff stops may "
                        "be breached by spread alone.)"
                    )
                    logger.debug(
                        "william_time_check",
                        time=time_of_day.strftime("%H:%M"),
                        session=forex_session.value,
                        asset_class=asset_class.value,
                        reasoning=reason,
                    )
                    return True, reason, ValidationStatus.WARN

            # Optimal forex sessions (LONDON, NY, OVERLAP) or regular hours
            return True, None, ValidationStatus.PASS

        # Other asset classes - pass
        return True, None, ValidationStatus.PASS

    def _check_override_eligibility(
        self, pattern_confidence: float, validation_status: ValidationStatus, warnings: list[str]
    ) -> tuple[ValidationStatus, str | None]:
        """
        Check if high-conviction signal can override warnings.

        Rules:
        - Confidence ≥90% can override WARN → PASS
        - Cannot override FAIL (safety-critical)
        - All overrides logged for pattern learning

        Args:
            pattern_confidence: Pattern confidence score (0.0-1.0)
            validation_status: Current validation status
            warnings: List of warning messages

        Returns:
            Tuple of (final_status, final_reason)
        """
        if validation_status == ValidationStatus.FAIL:
            # Cannot override FAIL
            return validation_status, "; ".join(warnings) if warnings else None

        if (
            validation_status == ValidationStatus.WARN
            and pattern_confidence >= self.high_conviction_threshold
        ):
            # High-conviction override
            original_warnings = "; ".join(warnings)
            override_reason = (
                f"HIGH-CONVICTION OVERRIDE (confidence {pattern_confidence*100:.0f}%): "
                f"Original warnings: {original_warnings}. Signal approved despite warnings due to "
                f"exceptional pattern quality."
            )
            logger.warning(
                "william_high_conviction_override",
                pattern_confidence=pattern_confidence,
                original_warnings=original_warnings,
                override_applied=True,
                reasoning="Exceptional pattern quality warrants accepting borderline conditions",
            )
            return ValidationStatus.PASS, override_reason

        # No override - return original status
        return validation_status, "; ".join(warnings) if warnings else None

    def _flag_for_human_review(
        self, warnings: list[str], pattern_confidence: float
    ) -> tuple[bool, str | None]:
        """
        Flag borderline signals for human review.

        Criteria:
        - Low confidence (70-80%) with any warnings
        - Normal confidence with 2+ warnings

        Args:
            warnings: List of warning messages
            pattern_confidence: Pattern confidence score

        Returns:
            Tuple of (needs_review, review_reason)
        """
        # Low confidence with warnings
        if 0.70 <= pattern_confidence < 0.80 and len(warnings) > 0:
            reason = (
                f"Flagged for human review: {len(warnings)} warning(s), "
                f"confidence {pattern_confidence*100:.0f}%. Review before execution."
            )
            logger.info(
                "william_human_review_flagged",
                confidence=pattern_confidence,
                warning_count=len(warnings),
                flag_reason=reason,
                reasoning="William recommends manual review: borderline setup with warnings",
            )
            return True, reason

        # Multiple warnings (≥2)
        if len(warnings) >= 2:
            reason = (
                f"Flagged for human review: {len(warnings)} warnings issued. "
                f"Multiple concerns warrant manual review."
            )
            logger.info(
                "william_human_review_flagged",
                confidence=pattern_confidence,
                warning_count=len(warnings),
                flag_reason=reason,
                reasoning="William recommends manual review: multiple strategic concerns",
            )
            return True, reason

        return False, None

    def _build_metadata(
        self,
        market_context: MarketContext,
        warnings: list[str],
        override_applied: bool,
        needs_human_review: bool,
        review_reason: str | None,
        final_reason: str | None,
    ) -> dict:
        """
        Build comprehensive metadata for audit trail and pattern learning.

        Args:
            market_context: MarketContext with all market data
            warnings: List of warning messages
            override_applied: Whether high-conviction override was applied
            needs_human_review: Whether signal flagged for manual review
            review_reason: Human review reason if flagged
            final_reason: Final validation reason

        Returns:
            Metadata dictionary
        """
        return {
            "asset_class": market_context.asset_class.value,
            "market_regime": market_context.market_regime.value,
            "volatility_percentile": market_context.volatility_percentile,
            "volume_percentile": market_context.volume_percentile,
            "is_extreme_volatility": market_context.is_extreme_volatility,
            "adx": float(market_context.adx) if market_context.adx else None,
            "time_of_day": market_context.time_of_day.strftime("%H:%M"),
            "market_session": market_context.market_session,
            "forex_session": (
                market_context.forex_session.value if market_context.forex_session else None
            ),
            "has_upcoming_news": market_context.has_upcoming_news,
            "recent_invalidation_count": len(market_context.recent_invalidations),
            "warnings_issued": warnings,
            "override_applied": override_applied,
            "needs_human_review": needs_human_review,
            "review_reason": review_reason,
            "william_reasoning": final_reason
            or "William approves: Clean strategic setup with optimal conditions",
        }
