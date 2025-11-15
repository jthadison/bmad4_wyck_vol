"""
Forex Market Confidence Scorer.

This module implements confidence scoring for forex markets with tick volume only.
Forex markets provide tick volume (price changes per period), NOT real institutional
volume, requiring adaptation of Wyckoff confidence scoring methodology.

Tick Volume Limitations
------------------------
Forex markets provide tick volume (number of price changes per period), NOT
real institutional volume (shares/contracts traded).

Critical Difference:
- Stock 2.0x volume: Institutional participation confirmed (2x shares traded)
- Forex 2.0x tick volume: Increased activity (could be news, retail, or institutional)

Tick volume measures VOLATILITY and ACTIVITY, NOT institutional accumulation/distribution.
A high tick volume could result from:
- News events (non-institutional)
- Retail trading surges (non-institutional)
- Asian session volatility (different market dynamics)
- Institutional activity (what we want to detect)

We cannot differentiate between these sources with tick volume alone.

Wyckoff Adaptation for Forex
------------------------------
Wyckoff's core principle: "Volume precedes price" and "Effort must produce result"

In stocks:
- Can measure EFFORT (institutional volume) and RESULT (price)
- Volume is direct evidence of Composite Operator activity

In forex:
- Can only measure ACTIVITY (tick volume) and RESULT (price)
- Must rely primarily on PRICE STRUCTURE for confirmation
- Volume weight reduced to 10 points (pattern consistency only)

Scoring Adaptations:
1. Volume weight: 40pts → 10pts (Spring), 35pts → 10pts (SOS)
2. Price structure weight increased: Penetration, Recovery, Spread, Close Position
3. Max confidence: 85 (not 100) - 15-point "volume uncertainty discount"
4. Volume trend bonuses: DISABLED (tick volume trends meaningless)

The 85 max confidence embodies intellectual honesty:
"This pattern is valid according to price structure and timing, but we cannot
confirm institutional participation due to tick volume limitations."

Spring Confidence Scoring (Forex Adaptation)
----------------------------------------------
Formula (120 points max, capped at 85):
- Volume Quality: 10 points (reduced from 40 - tick volume unreliable)
  * <0.3x = 10pts (pattern consistency, not institutional confirmation)
  * 0.3-0.5x = 7pts (acceptable pattern consistency)
  * 0.5-0.7x = 3pts (marginal - higher volatility than ideal)
- Penetration Depth: 45 points (increased from 35 - price structure primary)
  * 0-2% = 45pts (shallow spring - ideal)
  * 2-3% = 35pts (acceptable spring depth)
  * 3-4% = 25pts (deeper spring - still valid)
  * 4-5% = 15pts (maximum penetration allowed)
- Recovery Speed: 35 points (increased from 25 - demand via price action)
  * 1 bar = 35pts (rapid recovery - strong demand)
  * 2 bars = 28pts (quick recovery - good demand)
  * 3 bars = 21pts (moderate recovery - acceptable)
  * 4-5 bars = 14pts (slow recovery - weak demand)
- Test Confirmation: 20 points (unchanged - price-based)
- Creek Strength Bonus: +10 points (unchanged - price-based)
- Volume Trend Bonus: DISABLED (tick volume trends meaningless)

Total: 120 points possible, capped at 85 for final score

SOS Confidence Scoring (Forex Adaptation)
-------------------------------------------
Formula (190 points total, capped at 85):
- Entry baseline: LPS 75 (vs 80 stock), SOS direct 60 (vs 65 stock)
- Volume Strength: 10 points (reduced from 35)
  * 2.5x+ tick volume = 10pts (strong breakout momentum)
  * 2.0-2.5x = 7pts (good breakout activity)
  * 1.7-2.0x = 5pts (moderate activity)
  * 1.5-1.7x = 3pts (weak momentum)
- Spread Expansion: 30 points (increased from 20 - price conviction key)
- Close Position: 25 points (increased from 20 - buyer control via price)
- Breakout Size: 20 points (increased from 15 - clear trend needed)
- Range Duration: 15 points (increased from 10 - time-based accumulation)
- LPS Bonus: +10 points (reduced from +15 - no volume double-confirmation)
- Phase Bonus: +5 points (unchanged)
- Volume Trend Bonus: DISABLED (tick volume trends meaningless)

Example (EUR/USD Spring):
--------------------------
    >>> from backend.src.pattern_engine.scoring.forex_scorer import ForexConfidenceScorer
    >>> scorer = ForexConfidenceScorer()
    >>> confidence = scorer.calculate_spring_confidence(
    ...     spring=spring,  # Tick Volume: 220 ticks (0.22x avg 1000)
    ...     creek=creek_level,
    ...     previous_tests=[test1, test2]
    ... )
    >>> # Volume: 0.22x = 10 pts (pattern consistency)
    >>> # Penetration: 1.8% = 45 pts (price structure primary)
    >>> # Recovery: 2 bars = 28 pts (demand via price action)
    >>> # Test: Yes = 20 pts
    >>> # Creek strength (85): +10 pts
    >>> # Total: 113 pts → capped at 85
    >>> confidence.total_score
    85

Note: Same spring in stocks would score 100/100 with volume confirmation.
Forex scores 85/85 max due to tick volume uncertainty.

Example (GBP/USD SOS):
-----------------------
    >>> confidence = scorer.calculate_sos_confidence(
    ...     sos=sos,  # Tick Volume: 4500 ticks (2.1x avg 2150)
    ...     lps=lps,
    ...     range_=trading_range,
    ...     phase=phase_d
    ... )
    >>> # Volume: 2.1x = 7 pts (breakout momentum only)
    >>> # Spread: 1.4x = 28 pts (price conviction)
    >>> # Close: 0.85 = 25 pts (buyer control)
    >>> # Breakout: 2.5% = 18 pts (clear trend)
    >>> # Duration: 22 bars = 10 pts
    >>> # LPS: Yes = 10 pts
    >>> # Phase D (88 confidence): 5 pts
    >>> # Baseline: 75 (LPS entry)
    >>> # Total: 75 + 113 = 188 → capped at 85
    >>> confidence
    85

Wyckoff Team Review - APPROVED
--------------------------------
Victoria (Volume Specialist):
"The 40pts → 10pts volume weight reduction is NON-NEGOTIABLE for forex.
Tick volume cannot confirm institutional activity. Volume trend bonus MUST
be disabled. Declining tick volume means lower volatility - NOT institutional
accumulation."

Rachel (Risk Manager):
"The 85 max confidence cap is appropriate risk adjustment for tick volume
uncertainty. Entry baseline reductions (LPS 75 vs 80, SOS 60 vs 65) properly
reflect lost volume double-confirmation value."

Richard (Wyckoff Mentor):
"This demonstrates proper Wyckoff adaptation: The principles are universal
(supply/demand, cause/effect), but the measurement tools vary by market.
The 15-point discount is our humility tax for working in a market without
real volume data."

See Also:
---------
- Story 0.1: Asset-Class Base Interfaces (ConfidenceScorer base class)
- Story 0.2: Stock Confidence Scorer (HIGH volume reliability reference)
- Story 5.4: Spring Confidence Scoring (stock implementation)
- Story 6.5: SOS/LPS Confidence Scoring (stock implementation)

Author: Story 0.3 - Forex Confidence Scorer Implementation
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

import structlog

from src.models.creek_level import CreekLevel
from src.models.lps import LPS
from src.models.phase_classification import PhaseClassification, WyckoffPhase
from src.models.sos_breakout import SOSBreakout
from src.models.spring import Spring
from src.models.spring_confidence import SpringConfidence
from src.models.test import Test
from src.models.trading_range import TradingRange
from src.pattern_engine.base.confidence_scorer import ConfidenceScorer

logger = structlog.get_logger(__name__)

# Constants (from Story 6.5)
MINIMUM_CONFIDENCE = 70  # Minimum threshold for signal generation


class ForexConfidenceScorer(ConfidenceScorer):
    """
    Confidence scorer for forex markets with tick volume only.

    Forex markets provide tick volume (price changes per period), NOT
    real institutional volume. Tick volume measures volatility/activity,
    not institutional accumulation. Volume weight reduced to 10 points.
    Price structure becomes primary confirmation.

    Tick Volume Limitations:
        - Tick volume = price changes per period (NOT shares traded)
        - Measures volatility/activity, NOT institutional participation
        - 2.0x tick volume ≠ institutional buying (could be news, retail, etc.)
        - Cannot confirm Wyckoff accumulation/distribution with tick volume

    Wyckoff Adaptation for Forex:
        - Volume weight: 10 points (pattern consistency only)
        - Price structure: PRIMARY confirmation (penetration, recovery, spread)
        - Max confidence: 85 (15-point volume uncertainty discount)
        - Volume trends: DISABLED (meaningless in tick volume)

    Class Properties:
        asset_class: "forex"
        volume_reliability: "LOW"
        max_confidence: 85

    Methods:
        calculate_spring_confidence: Score spring pattern with forex adaptations
        calculate_sos_confidence: Score SOS/LPS pattern with forex adaptations

    Example:
        >>> scorer = ForexConfidenceScorer()
        >>> # Spring scoring (forex adaptation)
        >>> spring_confidence = scorer.calculate_spring_confidence(
        ...     spring=spring,
        ...     creek=creek_level,
        ...     previous_tests=[test1, test2]
        ... )
        >>> print(f"Spring: {spring_confidence.total_score}% (max 85 for forex)")
        >>>
        >>> # SOS scoring (forex adaptation)
        >>> sos_confidence = scorer.calculate_sos_confidence(
        ...     sos=sos,
        ...     lps=lps,
        ...     range_=trading_range,
        ...     phase=phase
        ... )
        >>> print(f"SOS: {sos_confidence}% (max 85 for forex)")

    See Also:
        - ConfidenceScorer: Abstract base class defining interface
        - StockConfidenceScorer: Stock variant with HIGH volume reliability
        - Story 0.3: Forex scorer implementation (this module)
    """

    def __init__(self) -> None:
        """
        Initialize forex confidence scorer with LOW volume reliability.

        Sets:
            asset_class="forex"
            volume_reliability="LOW"
            max_confidence=85

        Raises:
            ValueError: If base class validation fails (should never occur)
        """
        super().__init__(asset_class="forex", volume_reliability="LOW", max_confidence=85)

    def calculate_spring_confidence(
        self,
        spring: Spring,
        creek: CreekLevel,
        previous_tests: Optional[list[Test]] = None,
    ) -> SpringConfidence:
        """
        Calculate confidence score for Spring pattern in forex markets.

        Forex adaptation reduces volume weight to 10 points (from 40 in stocks)
        and increases price structure weights (penetration, recovery) to compensate.

        Purpose:
        --------
        Quantify spring quality using price structure as PRIMARY confirmation
        when tick volume cannot confirm institutional activity.

        Scoring Formula (Forex Adaptation):
        ------------------------------------
        Base Components (110 points):
        - Volume Quality: 10 points (pattern consistency only - NOT institutional proof)
        - Penetration Depth: 45 points (PRIMARY indicator without volume)
        - Recovery Speed: 35 points (demand strength via price action)
        - Test Confirmation: 20 points (price-based, reliable)

        Bonuses (+10 points max):
        - Creek Strength Bonus: +10 points (strong support quality)
        - Volume Trend Bonus: DISABLED (tick volume trends meaningless)

        Total: 120 points possible, capped at 85 for final score

        Args:
            spring: Detected Spring pattern (from detect_spring)
            creek: Creek level providing support strength (from TradingRange.creek)
            previous_tests: Optional list of previous Test patterns (NOT used for volume trend in forex)

        Returns:
            SpringConfidence: Dataclass with total_score (0-85), component_scores dict, quality_tier

        Raises:
            ValueError: If spring or creek is None

        Component Significance (Forex):
        --------------------------------
        1. Volume Quality (10 pts) - PATTERN CONSISTENCY ONLY:
           - <0.3x = 10pts (textbook tick volume pattern)
           - 0.3-0.5x = 7pts (acceptable pattern consistency)
           - 0.5-0.7x = 3pts (marginal - higher volatility)
           - NOTE: Does NOT confirm institutional absorption (only pattern consistency)

        2. Penetration Depth (45 pts) - PRIMARY INDICATOR:
           - 0-2% = 45pts (shallow spring - ideal)
           - 2-3% = 35pts (acceptable depth)
           - 3-4% = 25pts (deeper spring)
           - 4-5% = 15pts (maximum penetration)
           - WITHOUT volume confirmation, penetration depth becomes PRIMARY quality indicator

        3. Recovery Speed (35 pts) - DEMAND STRENGTH VIA PRICE ACTION:
           - 1 bar = 35pts (rapid recovery - strong demand)
           - 2 bars = 28pts (quick recovery - good demand)
           - 3 bars = 21pts (moderate recovery)
           - 4-5 bars = 14pts (slow recovery)
           - Time-based confirmation of demand strength

        4. Test Confirmation (20 pts) - PRICE-BASED:
           - Test present = 20pts (reliable in both stock and forex)

        5. Creek Strength Bonus (+10 pts) - PRICE-BASED:
           - Strength >=80 = 10pts (excellent support)
           - Strength 70-79 = 7pts (strong support)
           - Strength 60-69 = 5pts (moderate support)

        6. Volume Trend Bonus: DISABLED (0 pts):
           - Tick volume trends are meaningless for institutional activity
           - Declining tick volume ≠ accumulation (could be lower volatility, session change)
           - This bonus is NOT awarded in forex markets

        Maximum Confidence: 85 (Volume Uncertainty Discount):
        -------------------------------------------------------
        Total possible: 120 points (10+45+35+20+10+0)
        Capped at 85 for final score
        15-point discount acknowledges: "Pattern valid, but volume confirmation incomplete"

        Confidence Ranges (Forex):
        ---------------------------
        - 80-85%: EXCELLENT - Textbook spring, highest probability (given tick volume limitation)
        - 75-79%: GOOD - Very high quality, strong setup
        - 70-74%: ACCEPTABLE - Good quality, meets minimum (SIGNALS GENERATED)
        - <70%: REJECTED - Below threshold, no signal

        Example (EUR/USD):
            >>> from backend.src.pattern_engine.scoring.forex_scorer import ForexConfidenceScorer
            >>>
            >>> scorer = ForexConfidenceScorer()
            >>> # After detecting spring and test
            >>> confidence = scorer.calculate_spring_confidence(
            ...     spring=spring,  # Tick volume: 220 (0.22x avg 1000)
            ...     creek=trading_range.creek,
            ...     previous_tests=[test1, test2]
            ... )
            >>>
            >>> # Volume: 0.22x = 10 pts (pattern consistency)
            >>> # Penetration: 1.8% = 45 pts (primary indicator)
            >>> # Recovery: 2 bars = 28 pts (demand via price)
            >>> # Test: Yes = 20 pts
            >>> # Creek (85 strength): +10 pts
            >>> # Total: 113 pts → capped at 85
            >>> print(f"Confidence: {confidence.total_score}%")  # 85
            >>> print(f"Quality: {confidence.quality_tier}")  # EXCELLENT
            >>>
            >>> # Compare to stocks: Same spring in stocks would score 100/100
            >>> # Forex scores 85/85 max due to tick volume uncertainty

        See Also:
            - Story 5.4: Spring confidence scoring (stock implementation reference)
            - Story 0.3: Forex scorer implementation (this module)
        """
        # ============================================================
        # INPUT VALIDATION
        # ============================================================

        if spring is None:
            logger.error("spring_missing_for_confidence_calculation")
            raise ValueError("Spring required for confidence calculation")

        if creek is None:
            logger.error("creek_missing_for_confidence_calculation")
            raise ValueError("Creek level required for confidence calculation")

        if previous_tests is None:
            previous_tests = []

        logger.debug(
            "forex_spring_confidence_calculation_starting",
            spring_timestamp=spring.bar.timestamp.isoformat(),
            spring_volume_ratio=float(spring.volume_ratio),
            spring_penetration_pct=float(spring.penetration_pct),
            spring_recovery_bars=spring.recovery_bars,
            creek_strength=creek.strength_score,
            asset_class="forex",
            volume_reliability="LOW",
            max_confidence=85,
        )

        # Initialize component scores
        component_scores = {
            "volume_quality": 0,
            "penetration_depth": 0,
            "recovery_speed": 0,
            "test_confirmation": 0,
            "creek_strength_bonus": 0,
            "volume_trend_bonus": 0,  # Always 0 for forex
            "raw_total": 0,
        }

        # ============================================================
        # COMPONENT 1: VOLUME QUALITY SCORING (10 points max)
        # ============================================================
        # AC 1: Volume quality with gradient
        # Tick volume shows PATTERN CONSISTENCY, not institutional confirmation
        # Low tick volume = textbook spring pattern (not institutional absorption proof)

        volume_ratio = spring.volume_ratio

        if volume_ratio < Decimal("0.3"):
            volume_points = 10
            volume_quality = "PATTERN_CONSISTENCY"
            logger.info(
                "forex_spring_low_tick_volume",
                volume_ratio=float(volume_ratio),
                volume_points=volume_points,
                message=f"Low tick volume (<0.3x) shows pattern consistency: {volume_points} points "
                "(NOT institutional confirmation)",
            )
        elif volume_ratio < Decimal("0.5"):
            volume_points = 7
            volume_quality = "ACCEPTABLE_CONSISTENCY"
        elif volume_ratio < Decimal("0.7"):
            volume_points = 3
            volume_quality = "MARGINAL"
            logger.warning(
                "forex_spring_elevated_tick_volume",
                volume_ratio=float(volume_ratio),
                message="Elevated tick volume - higher volatility than ideal for spring pattern",
            )
        else:
            volume_points = 0
            volume_quality = "TOO_HIGH"

        component_scores["volume_quality"] = volume_points

        logger.debug(
            "forex_volume_quality_scored",
            volume_ratio=float(volume_ratio),
            volume_points=volume_points,
            volume_quality=volume_quality,
            message=f"Tick volume {volume_ratio:.2f}x scored {volume_points} points (pattern consistency only)",
        )

        # ============================================================
        # COMPONENT 2: PENETRATION DEPTH SCORING (45 points max)
        # ============================================================
        # AC 2: Price structure primary in forex
        # Without volume confirmation, penetration depth is PRIMARY quality indicator
        # Increased from 35pts (stock) to 45pts (forex)

        penetration_pct = spring.penetration_pct

        if penetration_pct <= Decimal("0.02"):
            penetration_points = 45
            penetration_quality = "IDEAL"
        elif penetration_pct <= Decimal("0.03"):
            penetration_points = 35
            penetration_quality = "ACCEPTABLE"
        elif penetration_pct <= Decimal("0.04"):
            penetration_points = 25
            penetration_quality = "DEEPER"
        else:  # 0.04 < penetration_pct <= 0.05
            penetration_points = 15
            penetration_quality = "MAXIMUM"

        component_scores["penetration_depth"] = penetration_points

        logger.debug(
            "forex_penetration_depth_scored",
            penetration_pct=float(penetration_pct),
            penetration_points=penetration_points,
            penetration_quality=penetration_quality,
            message=f"Penetration {penetration_pct:.1%} scored {penetration_points} points "
            "(PRIMARY indicator in forex)",
        )

        # ============================================================
        # COMPONENT 3: RECOVERY SPEED SCORING (35 points max)
        # ============================================================
        # AC 3: Demand strength via price action
        # Time-based confirmation of demand strength (no volume needed)
        # Increased from 25pts (stock) to 35pts (forex)

        recovery_bars = spring.recovery_bars

        if recovery_bars == 1:
            recovery_points = 35
            recovery_quality = "RAPID"
        elif recovery_bars == 2:
            recovery_points = 28
            recovery_quality = "QUICK"
        elif recovery_bars == 3:
            recovery_points = 21
            recovery_quality = "MODERATE"
        else:  # 4-5 bars
            recovery_points = 14
            recovery_quality = "SLOW"

        component_scores["recovery_speed"] = recovery_points

        logger.debug(
            "forex_recovery_speed_scored",
            recovery_bars=recovery_bars,
            recovery_points=recovery_points,
            recovery_quality=recovery_quality,
            message=f"Recovery in {recovery_bars} bars scored {recovery_points} points "
            "(demand strength via price action)",
        )

        # ============================================================
        # COMPONENT 4: TEST CONFIRMATION SCORING (20 points)
        # ============================================================
        # Same as stock - price-based confirmation is reliable in both markets

        has_test = len(previous_tests) > 0

        if has_test:
            test_points = 20
            test_quality = "PRESENT"
            logger.debug(
                "forex_test_confirmation_scored",
                test_present=True,
                test_points=test_points,
            )
        else:
            test_points = 0
            test_quality = "NONE"
            logger.warning(
                "forex_no_test_confirmation",
                message="No test confirmation - spring will not generate signal",
            )

        component_scores["test_confirmation"] = test_points

        # ============================================================
        # BONUS 1: CREEK STRENGTH BONUS (10 points max)
        # ============================================================
        # Same as stock - price-based support quality is reliable in both markets

        creek_strength = creek.strength_score

        if creek_strength >= 80:
            creek_bonus = 10
            creek_quality = "EXCELLENT"
        elif creek_strength >= 70:
            creek_bonus = 7
            creek_quality = "STRONG"
        elif creek_strength >= 60:
            creek_bonus = 5
            creek_quality = "MODERATE"
        else:
            creek_bonus = 0
            creek_quality = "WEAK"

        component_scores["creek_strength_bonus"] = creek_bonus

        logger.debug(
            "forex_creek_strength_bonus",
            creek_strength=creek_strength,
            creek_bonus=creek_bonus,
            creek_quality=creek_quality,
            message=f"Creek strength {creek_strength} earned {creek_bonus} bonus points",
        )

        # ============================================================
        # BONUS 2: VOLUME TREND BONUS (DISABLED FOR FOREX)
        # ============================================================
        # AC 6: Tick volume trends meaningless for institutional activity
        # Declining tick volume ≠ accumulation (could be lower volatility, session change)
        # DO NOT implement volume trend bonus for forex

        volume_trend_bonus = 0
        component_scores["volume_trend_bonus"] = volume_trend_bonus

        logger.debug(
            "forex_volume_trend_bonus_disabled",
            volume_trend_bonus=0,
            message="Volume trend bonus DISABLED for forex - tick volume trends meaningless",
        )

        # ============================================================
        # FINAL CONFIDENCE CALCULATION
        # ============================================================
        # AC 7: Total possible 120 points, capped at 85
        # 15-point volume uncertainty discount

        raw_total = (
            volume_points
            + penetration_points
            + recovery_points
            + test_points
            + creek_bonus
            + volume_trend_bonus  # Always 0 for forex
        )

        component_scores["raw_total"] = raw_total

        # Cap at 85 for final score (forex max confidence)
        final_confidence = min(raw_total, 85)

        # Determine quality tier (forex ranges)
        if final_confidence >= 80:
            quality_tier = "EXCELLENT"
        elif final_confidence >= 75:
            quality_tier = "GOOD"
        elif final_confidence >= 70:
            quality_tier = "ACCEPTABLE"
        else:
            quality_tier = "REJECTED"

        logger.info(
            "forex_spring_confidence_calculated",
            spring_timestamp=spring.bar.timestamp.isoformat(),
            total_confidence=final_confidence,
            raw_total=raw_total,
            quality_tier=quality_tier,
            volume_points=volume_points,
            penetration_points=penetration_points,
            recovery_points=recovery_points,
            test_points=test_points,
            creek_bonus=creek_bonus,
            volume_trend_bonus=volume_trend_bonus,
            meets_threshold=final_confidence >= 70,
            asset_class="forex",
            max_confidence=85,
            volume_uncertainty_discount=15,
        )

        # Validate minimum threshold (70%)
        if final_confidence < 70:
            logger.warning(
                "forex_spring_low_confidence",
                final_confidence=final_confidence,
                threshold=70,
                message=(
                    f"Forex spring confidence {final_confidence}% below minimum "
                    "(70%) - will not generate signal"
                ),
            )

        # ============================================================
        # CREATE AND RETURN SPRINGCONFIDENCE DATACLASS
        # ============================================================

        return SpringConfidence(
            total_score=final_confidence,
            component_scores=component_scores,
            quality_tier=quality_tier,
        )

    def calculate_sos_confidence(
        self,
        sos: SOSBreakout,
        lps: Optional[LPS],
        range_: TradingRange,
        phase: PhaseClassification,
    ) -> int:
        """
        Calculate confidence score for SOS breakout pattern in forex markets.

        Forex adaptation reduces volume weight to 10 points (from 35 in stocks)
        and increases price structure weights (spread, close position, breakout size)
        to compensate. Entry baselines reduced by 5 points (LPS 75 vs 80, SOS 60 vs 65).

        Combines multiple Wyckoff factors to generate 0-85 confidence score.
        Only patterns scoring >= 70% generate trade signals.

        Algorithm (Forex Adaptation):
        1. Volume strength (10 pts, reduced from 35) - tick volume shows momentum only
        2. Spread expansion (30 pts, increased from 20) - price conviction key
        3. Close position (25 pts, increased from 20) - buyer control via price
        4. Breakout size (20 pts, increased from 15) - clear trend needed
        5. Accumulation duration (15 pts, increased from 10) - time-based accumulation
        6. LPS bonus (10 pts, reduced from 15) - no volume double-confirmation
        7. Phase bonus (5 pts) - Wyckoff phase alignment
        8. Volume trend bonus: DISABLED (tick volume trends meaningless)
        9. Entry type baseline: LPS 75 (vs 80 stock), SOS direct 60 (vs 65 stock)
        10. Maximum confidence: 85 (15-point volume uncertainty discount)

        Args:
            sos: SOS breakout pattern
            lps: LPS pattern (optional - None for direct SOS entry)
            range_: Trading range context
            phase: Current Wyckoff phase classification

        Returns:
            int: Confidence score 0-85

        Example (EUR/USD):
            >>> # Excellent SOS with LPS entry
            >>> confidence = scorer.calculate_sos_confidence(sos, lps, trading_range, phase)
            >>> if confidence >= 70:
            ...     print(f"Signal generated: {confidence}% confidence (max 85 for forex)")

        See Also:
            - Story 6.5: SOS/LPS confidence scoring (stock implementation reference)
            - Story 0.3: Forex scorer implementation (this module)
        """
        # Alias parameter to match original implementation variable name
        trading_range = range_

        confidence = 0

        logger.debug(
            "forex_sos_confidence_calculation_start",
            sos_id=str(sos.id),
            lps_present=lps is not None,
            trading_range_id=str(trading_range.id),
            phase=phase.phase.value if phase.phase else None,
            asset_class="forex",
            volume_reliability="LOW",
            max_confidence=85,
            message="Starting forex SOS confidence calculation",
        )

        # ============================================================
        # COMPONENT 1: VOLUME STRENGTH (10 points max)
        # ============================================================
        # AC 2: Volume strength reduced from 35pts to 10pts
        # Tick volume shows MOMENTUM, not institutional participation
        # High tick volume = breakout activity (NOT institutional confirmation)

        volume_ratio = sos.volume_ratio
        volume_points = 0

        if volume_ratio >= Decimal("2.5"):
            volume_points = 10  # Strong breakout momentum
            volume_quality = "strong_momentum"
        elif volume_ratio >= Decimal("2.0"):
            volume_points = 7  # Good breakout activity
            volume_quality = "good_activity"
        elif volume_ratio >= Decimal("1.7"):
            volume_points = 5  # Moderate activity
            volume_quality = "moderate_activity"
        elif volume_ratio >= Decimal("1.5"):
            volume_points = 3  # Weak momentum
            volume_quality = "weak_momentum"
        else:
            # Should not occur - SOSBreakout validator requires >= 1.5x
            volume_points = 0
            volume_quality = "insufficient"

        confidence += volume_points

        logger.debug(
            "forex_sos_confidence_volume_scoring",
            volume_ratio=float(volume_ratio),
            volume_points=volume_points,
            volume_quality=volume_quality,
            message=f"Tick volume {volume_ratio:.2f}x scored {volume_points} points "
            "(momentum indicator only, NOT institutional confirmation)",
        )

        # ============================================================
        # COMPONENT 2: SPREAD EXPANSION (30 points)
        # ============================================================
        # AC 3: Spread expansion increased from 20pts to 30pts
        # Price conviction becomes key without volume confirmation

        spread_ratio = sos.spread_ratio
        spread_points = 0

        if spread_ratio >= Decimal("1.5"):
            spread_points = 30  # Wide spread - strong conviction
            spread_quality = "wide"
        elif spread_ratio >= Decimal("1.2"):
            # Linear interpolation between 1.2x and 1.5x
            # 1.2x = 20 pts, 1.5x = 30 pts
            normalized = (spread_ratio - Decimal("1.2")) / Decimal("0.3")
            spread_points = int(20 + (normalized * 10))
            spread_quality = "acceptable"
        else:
            # Should not occur - SOSBreakout validator requires >= 1.2x
            spread_points = 0
            spread_quality = "narrow"

        confidence += spread_points

        logger.debug(
            "forex_sos_confidence_spread_scoring",
            spread_ratio=float(spread_ratio),
            spread_points=spread_points,
            spread_quality=spread_quality,
            message=f"Spread {spread_ratio:.2f}x scored {spread_points} points "
            "(price conviction key in forex)",
        )

        # ============================================================
        # COMPONENT 3: CLOSE POSITION (25 points)
        # ============================================================
        # AC 4: Close position increased from 20pts to 25pts
        # Buyer control via price becomes more important without volume

        close_position = sos.close_position
        close_points = 0

        if close_position >= Decimal("0.8"):
            close_points = 25  # Very strong close - buyer control
            close_quality = "very_strong"
        elif close_position >= Decimal("0.7"):
            # Linear interpolation between 0.7 and 0.8
            # 0.7 = 18 pts, 0.8 = 25 pts
            normalized = (close_position - Decimal("0.7")) / Decimal("0.1")
            close_points = int(18 + (normalized * 7))
            close_quality = "strong"
        elif close_position >= Decimal("0.5"):
            # Weak close - linear scaling from 0.5 to 0.7: 8-18 pts
            normalized = (close_position - Decimal("0.5")) / Decimal("0.2")
            close_points = int(8 + (normalized * 10))
            close_quality = "weak"
        else:
            # Very weak close (lower half)
            close_points = int(close_position * 15)  # 0-7 pts
            close_quality = "very_weak"

        confidence += close_points

        logger.debug(
            "forex_sos_confidence_close_scoring",
            close_position=float(close_position),
            close_points=close_points,
            close_quality=close_quality,
            message=f"Close position {close_position:.2f} scored {close_points} points "
            "(buyer control via price)",
        )

        # ============================================================
        # COMPONENT 4: BREAKOUT SIZE (20 points)
        # ============================================================
        # AC 5: Breakout size increased from 15pts to 20pts
        # Clear trend needed without volume confirmation

        breakout_pct = sos.breakout_pct
        breakout_pct_value = breakout_pct * Decimal("100")  # Convert to percentage

        breakout_points = 0

        if breakout_pct_value >= Decimal("3.0"):
            breakout_points = 20  # Strong breakout (3%+)
            breakout_quality = "strong"
        elif breakout_pct_value >= Decimal("2.0"):
            # Linear interpolation between 2% and 3%
            # 2% = 15 pts, 3% = 20 pts
            normalized = (breakout_pct_value - Decimal("2.0")) / Decimal("1.0")
            breakout_points = int(15 + (normalized * 5))
            breakout_quality = "good"
        elif breakout_pct_value >= Decimal("1.0"):
            # Linear interpolation between 1% and 2%
            # 1% = 10 pts, 2% = 15 pts
            normalized = (breakout_pct_value - Decimal("1.0")) / Decimal("1.0")
            breakout_points = int(10 + (normalized * 5))
            breakout_quality = "acceptable"
        else:
            # Should not occur - SOSBreakout validator requires >= 1%
            breakout_points = 0
            breakout_quality = "insufficient"

        confidence += breakout_points

        logger.debug(
            "forex_sos_confidence_breakout_size_scoring",
            breakout_pct=float(breakout_pct_value),
            breakout_points=breakout_points,
            breakout_quality=breakout_quality,
            message=f"Breakout size {breakout_pct_value:.2f}% scored {breakout_points} points "
            "(clear trend needed in forex)",
        )

        # ============================================================
        # COMPONENT 5: ACCUMULATION DURATION (15 points)
        # ============================================================
        # AC 6: Range duration increased from 10pts to 15pts
        # Time-based accumulation more important without volume

        range_start = trading_range.start_timestamp
        range_end = (
            trading_range.end_timestamp or sos.bar.timestamp
        )  # Use SOS bar if range still active

        # Calculate duration in days
        duration_days = (range_end - range_start).days if range_start and range_end else 0

        # Approximate bars based on timeframe (simplified calculation)
        range_duration_bars = duration_days  # Simplified: 1 bar/day for daily timeframe

        duration_points = 0

        if range_duration_bars >= 30:
            duration_points = 15  # Extended accumulation
            duration_quality = "extended"
        elif range_duration_bars >= 20:
            # Linear scaling between 20 and 30 bars: 10-15 pts
            duration_points = int(10 + ((range_duration_bars - 20) / 10) * 5)
            duration_quality = "long"
        elif range_duration_bars >= 10:
            # Linear scaling between 10 and 20 bars: 5-10 pts
            duration_points = int(5 + ((range_duration_bars - 10) / 10) * 5)
            duration_quality = "medium"
        elif range_duration_bars >= 5:
            # Short accumulation: 2-5 pts
            duration_points = int(2 + ((range_duration_bars - 5) / 5) * 3)
            duration_quality = "short"
        else:
            # Very short accumulation: minimal points
            duration_points = int(range_duration_bars * 0.4)  # 0-2 pts
            duration_quality = "very_short"

        confidence += duration_points

        logger.debug(
            "forex_sos_confidence_duration_scoring",
            range_duration_bars=range_duration_bars,
            duration_points=duration_points,
            duration_quality=duration_quality,
            message=f"Range duration {range_duration_bars} bars scored {duration_points} points "
            "(time-based accumulation in forex)",
        )

        # ============================================================
        # BONUS 1: LPS BONUS (10 points)
        # ============================================================
        # AC 7: LPS bonus reduced from 15pts to 10pts
        # No volume double-confirmation in forex (tick volume unreliable)

        lps_bonus_points = 0

        if lps is not None:
            if lps.held_support:
                lps_bonus_points = 10  # Reduced from 15pts (stock)

                logger.info(
                    "forex_sos_confidence_lps_bonus",
                    lps_present=True,
                    held_support=True,
                    distance_from_ice=float(lps.distance_from_ice),
                    volume_ratio=float(lps.volume_ratio),
                    bonus_points=lps_bonus_points,
                    message="LPS present and held support - adding 10 point bonus "
                    "(reduced from 15 - no volume double-confirmation in forex)",
                )
            else:
                lps_bonus_points = 0
                logger.warning(
                    "forex_sos_confidence_lps_failed",
                    lps_present=True,
                    held_support=False,
                    message="LPS present but broke support - no bonus",
                )
        else:
            lps_bonus_points = 0
            logger.debug(
                "forex_sos_confidence_no_lps",
                lps_present=False,
                message="No LPS detected - SOS direct entry (no LPS bonus)",
            )

        confidence += lps_bonus_points

        # ============================================================
        # BONUS 2: PHASE CONFIDENCE BONUS (5 points)
        # ============================================================
        # AC 8: Phase bonus unchanged (price-based, reliable in both markets)

        phase_bonus_points = 0

        current_phase = phase.phase
        phase_confidence_value = phase.confidence

        if current_phase == WyckoffPhase.D:
            # Phase D is ideal for SOS (markup phase)
            if phase_confidence_value >= 85:
                phase_bonus_points = 5  # High-confidence Phase D
                phase_quality = "ideal"
            elif phase_confidence_value >= 70:
                phase_bonus_points = 3  # Medium confidence Phase D
                phase_quality = "good"
            else:
                phase_bonus_points = 1  # Low confidence Phase D
                phase_quality = "acceptable"
        elif current_phase == WyckoffPhase.C and phase_confidence_value >= 85:
            # Late Phase C acceptable (transition into Phase D)
            phase_bonus_points = 3
            phase_quality = "late_phase_c"
        else:
            phase_bonus_points = 0
            phase_quality = "wrong_phase"

        confidence += phase_bonus_points

        phase_name = current_phase.value if current_phase else "None"
        logger.debug(
            "forex_sos_confidence_phase_bonus",
            current_phase=current_phase.value if current_phase else None,
            phase_confidence=phase_confidence_value,
            phase_bonus_points=phase_bonus_points,
            phase_quality=phase_quality,
            message=f"Phase {phase_name} (confidence {phase_confidence_value}) "
            f"scored {phase_bonus_points} points ({phase_quality})",
        )

        # ============================================================
        # BONUS 3: VOLUME TREND BONUS (DISABLED FOR FOREX)
        # ============================================================
        # AC 9: Tick volume trends meaningless
        # DO NOT award volume trend bonus for forex

        volume_trend_bonus = 0

        logger.debug(
            "forex_sos_confidence_volume_trend_bonus_disabled",
            volume_trend_bonus=0,
            message="Volume trend bonus DISABLED for forex - tick volume trends meaningless",
        )

        confidence += volume_trend_bonus

        # ============================================================
        # ENTRY TYPE BASELINE ADJUSTMENT
        # ============================================================
        # AC 1: Entry baseline adjustment
        # LPS entry: 75 (vs 80 stock) - reduced baseline, no volume double-confirmation
        # SOS direct entry: 60 (vs 65 stock) - reduced baseline, no volume confirmation

        entry_type_adjustment = 0

        if lps is not None and lps.held_support:
            # LPS entry: higher baseline confidence (lower risk)
            entry_type = "LPS_ENTRY"
            baseline_confidence = 75  # Reduced from 80 (stock)

            logger.info(
                "forex_sos_confidence_entry_type",
                entry_type=entry_type,
                baseline_confidence=baseline_confidence,
                message="Forex LPS entry - baseline 75 (vs 80 stock, reduced due to no volume double-confirmation)",
            )
        else:
            # SOS direct entry: standard baseline
            entry_type = "SOS_DIRECT_ENTRY"
            baseline_confidence = 60  # Reduced from 65 (stock)

            logger.info(
                "forex_sos_confidence_entry_type",
                entry_type=entry_type,
                baseline_confidence=baseline_confidence,
                message="Forex SOS direct entry - baseline 60 (vs 65 stock, reduced due to no volume confirmation)",
            )

        # Calculate adjustment needed to reach baseline
        if confidence < baseline_confidence:
            entry_type_adjustment = baseline_confidence - confidence
            original_confidence = confidence
            confidence = baseline_confidence

            logger.debug(
                "forex_sos_confidence_baseline_adjustment",
                original_confidence=original_confidence,
                entry_type_adjustment=entry_type_adjustment,
                adjusted_confidence=confidence,
                message=f"Adjusted to {entry_type} baseline: +{entry_type_adjustment} pts",
            )
        else:
            entry_type_adjustment = 0
            logger.debug(
                "forex_sos_confidence_no_baseline_adjustment",
                current_confidence=confidence,
                baseline_confidence=baseline_confidence,
                message=f"Confidence {confidence} already exceeds {entry_type} baseline {baseline_confidence}",
            )

        # ============================================================
        # FINAL CONFIDENCE CALCULATION
        # ============================================================
        # AC 10: Maximum confidence 85 (15-point volume uncertainty discount)

        # Ensure confidence doesn't exceed 85 (forex max)
        if confidence > 85:
            logger.info(
                "forex_sos_confidence_exceeds_max",
                calculated_confidence=confidence,
                max_confidence=85,
                message="Confidence exceeds 85 (forex max) - capping at 85",
            )
            confidence = 85

        # Check minimum threshold (70%)
        meets_threshold = confidence >= MINIMUM_CONFIDENCE

        if meets_threshold:
            logger.info(
                "forex_sos_confidence_final",
                final_confidence=confidence,
                entry_type=entry_type,
                volume_points=volume_points,
                spread_points=spread_points,
                close_points=close_points,
                breakout_points=breakout_points,
                duration_points=duration_points,
                lps_bonus=lps_bonus_points,
                phase_bonus=phase_bonus_points,
                baseline_adjustment=entry_type_adjustment,
                volume_trend_bonus=volume_trend_bonus,
                meets_threshold=True,
                asset_class="forex",
                max_confidence=85,
                volume_uncertainty_discount=15,
                message=f"Forex SOS confidence {confidence}% - PASSES threshold (>= 70%) - signal eligible",
            )
        else:
            logger.warning(
                "forex_sos_confidence_below_threshold",
                final_confidence=confidence,
                minimum_threshold=MINIMUM_CONFIDENCE,
                deficit=MINIMUM_CONFIDENCE - confidence,
                meets_threshold=False,
                asset_class="forex",
                message=f"Forex SOS confidence {confidence}% - FAILS threshold (< 70%) - signal rejected",
            )

        return confidence
