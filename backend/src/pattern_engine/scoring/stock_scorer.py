"""
Stock Market Confidence Scorer.

This module implements confidence scoring for stock markets with real institutional
volume. It preserves the exact scoring logic from Stories 5.4 (Spring) and 6.5 (SOS/LPS)
without any modifications.

CRITICAL REFACTOR NOTE:
-----------------------
This is a REFACTOR, not a REWRITE. The code has been moved from:
- Story 5.4: backend/src/pattern_engine/detectors/spring_detector.py (calculate_spring_confidence)
- Story 6.5: backend/src/pattern_engine/scoring/sos_confidence_scorer.py (calculate_sos_confidence)

ZERO LOGIC CHANGES have been made. All existing tests must pass without modification.
If confidence scores change by even 0.1%, the refactor has failed.

Stock Volume Characteristics:
------------------------------
Stock markets provide actual shares traded on the exchange, enabling full Wyckoff
volume analysis. This is REAL institutional volume, not tick volume approximations.

Volume Reliability: HIGH
- Real institutional volume (shares traded)
- 2.0x volume = institutional participation confirmed
- Low volume (<0.3x) = absorption/lack of supply confirmed
- Volume is primary confirmation (35-40 points in scoring)

Wyckoff Context:
----------------
Richard Wyckoff developed his methodology analyzing stock markets where volume
represents actual institutional activity. The volume weights in this scorer
(40 points for springs, 35 points for SOS) are NON-NEGOTIABLE for stocks.

> "In stock markets, volume IS the institutional footprint. When we see 2.0x
> volume on an SOS breakout, that's REAL professional accumulation completing.
> When we see <0.3x volume on a Spring, that's REAL supply exhaustion. These
> are not approximations - this is direct evidence of Composite Operator activity."
> - Victoria, Wyckoff Volume Specialist

Spring Confidence Scoring (Story 5.4):
---------------------------------------
Formula (120 points max, capped at 100):
- Volume Quality: 40 points (most important - supply exhaustion)
  * <0.3x = 40pts (exceptional)
  * 0.3-0.4x = 30pts (excellent)
  * 0.4-0.5x = 20pts (ideal)
  * 0.5-0.6x = 10pts (acceptable)
  * 0.6-0.69x = 5pts (marginal)
- Penetration Depth: 35 points (optimal shakeout depth)
  * 1-2% = 35pts (ideal)
  * 2-3% = 25pts (good)
  * 3-4% = 15pts (acceptable)
  * 4-5% = 5pts (deep)
- Recovery Speed: 25 points (demand strength)
  * 1 bar = 25pts (immediate)
  * 2 bars = 20pts (strong)
  * 3 bars = 15pts (good)
  * 4-5 bars = 10pts (slow)
- Test Confirmation: 20 points (required for signal)
- Creek Strength Bonus: +10 points (strong support quality)
- Volume Trend Bonus: +10 points (declining volume pattern)

SOS Confidence Scoring (Story 6.5):
------------------------------------
Formula (100+ points with bonuses):
- Volume Strength: 35 points (non-linear, institutional thresholds)
  * 2.0-2.3x = "ideal professional participation" (25-32pts)
  * This is the Wyckoff "sweet spot" for institutional volume
- Spread Expansion: 20 points (bar conviction)
- Close Position: 20 points (buyer control)
- Breakout Size: 15 points (penetration quality)
- Accumulation Duration: 10 points (cause building)
- LPS Bonus: +15 points (lower-risk entry)
- Phase Bonus: +5 points (Wyckoff phase alignment)
- Volume Trend Bonus: +5 points (accumulation signature)
- Entry type baseline: LPS 80, SOS direct 65

Example (AAPL Spring):
----------------------
    >>> from src.pattern_engine.scoring.stock_scorer import StockConfidenceScorer
    >>> scorer = StockConfidenceScorer()
    >>> confidence = scorer.calculate_spring_confidence(
    ...     spring=spring,  # Volume: 4M shares (0.22x avg 18M)
    ...     creek=creek_level,
    ...     previous_tests=[test1, test2]
    ... )
    >>> # Volume: 0.22x = 40 pts
    >>> # Penetration: 1.8% = 35 pts
    >>> # Recovery: 2 bars = 20 pts
    >>> # Test: Yes = 20 pts
    >>> # Total: 115 pts → capped at 100
    >>> confidence.total_score
    100
    >>> confidence.quality_tier
    'EXCELLENT'

Example (SPY SOS):
------------------
    >>> confidence = scorer.calculate_sos_confidence(
    ...     sos=sos,  # Volume: 95M shares (2.1x avg 45M)
    ...     lps=lps,
    ...     range_=trading_range,
    ...     phase=phase_d
    ... )
    >>> # Volume: 2.1x = 28 pts (in ideal 2.0-2.3x range)
    >>> # Spread: 1.4x = 18 pts
    >>> # Close: 0.85 = 20 pts
    >>> # Breakout: 2.5% = 13 pts
    >>> # Duration: 22 bars = 10 pts
    >>> # LPS: Yes = 15 pts
    >>> # Phase D: 88 confidence = 5 pts
    >>> # Baseline: 80 (LPS entry)
    >>> confidence
    92

See Also:
---------
- Story 0.1: Asset-Class Base Interfaces (ConfidenceScorer base class)
- Story 0.3: Forex Confidence Scorer (LOW volume reliability variant)
- Story 5.4: Spring Confidence Scoring (original implementation)
- Story 6.5: SOS/LPS Confidence Scoring (original implementation)

Author: Story 0.2 - Stock Confidence Scorer Refactor
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
MINIMUM_CONFIDENCE = 70  # AC 10: Minimum threshold for signal generation


class StockConfidenceScorer(ConfidenceScorer):
    """
    Confidence scorer for stock markets with real institutional volume.

    Stock markets provide actual shares traded, enabling full Wyckoff
    volume analysis. Volume weight is 35-40 points (primary confirmation).

    This class preserves the EXACT scoring logic from Stories 5.4 and 6.5.
    ZERO logic changes have been made - this is a pure refactor.

    Volume Characteristics:
        - Real institutional volume (shares traded on exchange)
        - Reliable indicator of professional activity
        - 2.0x volume = institutional participation confirmed
        - Low volume (<0.3x) = absorption/lack of supply confirmed

    Class Properties:
        asset_class: "stock"
        volume_reliability: "HIGH"
        max_confidence: 100

    Methods:
        calculate_spring_confidence: Score spring pattern (Story 5.4 formula)
        calculate_sos_confidence: Score SOS/LPS pattern (Story 6.5 formula)

    Validation:
        All existing tests from Epic 5 and Epic 6 must pass without modification.
        Confidence scores must be bit-for-bit identical to original implementations.

    Example:
        >>> scorer = StockConfidenceScorer()
        >>> # Spring scoring (Story 5.4)
        >>> spring_confidence = scorer.calculate_spring_confidence(
        ...     spring=spring,
        ...     creek=creek_level,
        ...     previous_tests=[test1, test2]
        ... )
        >>> print(f"Spring: {spring_confidence.total_score}%")
        >>>
        >>> # SOS scoring (Story 6.5)
        >>> sos_confidence = scorer.calculate_sos_confidence(
        ...     sos=sos,
        ...     lps=lps,
        ...     range_=trading_range,
        ...     phase=phase
        ... )
        >>> print(f"SOS: {sos_confidence}%")

    See Also:
        - ConfidenceScorer: Abstract base class defining interface
        - ForexConfidenceScorer: Forex variant with LOW volume reliability
        - Story 0.2: Stock scorer refactor (this implementation)
        - Story 0.3: Forex scorer implementation
    """

    def __init__(self) -> None:
        """
        Initialize stock confidence scorer with HIGH volume reliability.

        Sets:
            asset_class="stock"
            volume_reliability="HIGH"
            max_confidence=100

        Raises:
            ValueError: If base class validation fails (should never occur)
        """
        super().__init__(asset_class="stock", volume_reliability="HIGH", max_confidence=100)

    def calculate_spring_confidence(
        self,
        spring: Spring,
        creek: CreekLevel,
        previous_tests: Optional[list[Test]] = None,
    ) -> SpringConfidence:
        """
        Calculate confidence score for Spring pattern quality (FR4 requirement).

        REFACTOR NOTE: This is an EXACT copy from Story 5.4 spring_detector.py.
        ZERO logic changes have been made.

        Purpose:
        --------
        Quantify spring quality using multi-dimensional scoring to ensure only
        high-probability setups (70%+ confidence) generate trading signals.

        Scoring Formula (Team-Approved 2025-11-03):
        --------------------------------------------
        Base Components (100 points):
        - Volume Quality: 40 points (most important - supply exhaustion)
        - Penetration Depth: 35 points (optimal shakeout depth)
        - Recovery Speed: 25 points (demand strength)
        - Test Confirmation: 20 points (FR13 requirement)

        Bonuses (+20 points max):
        - Creek Strength Bonus: +10 points (strong support quality)
        - Volume Trend Bonus: +10 points (declining volume pattern)

        Total: 120 points possible, capped at 100 for final score

        Args:
            spring: Detected Spring pattern (from detect_spring)
            creek: Creek level providing support strength (from TradingRange.creek)
            previous_tests: Optional list of previous Test patterns for volume trend analysis

        Returns:
            SpringConfidence: Dataclass with total_score (0-100), component_scores dict, quality_tier

        Raises:
            ValueError: If spring or creek is None

        FR4 Requirement:
        ----------------
        Minimum 70% confidence required for signal generation.
        Springs scoring <70% are rejected.

        Wyckoff Context:
        ----------------
        > "Not all Springs are created equal. A Spring with ultra-low volume (0.3x),
        > ideal penetration (1-2%), and immediate recovery (1 bar) is VASTLY superior
        > to one with moderate volume (0.6x), deep penetration (4-5%), and slow recovery.
        > Confidence scoring quantifies spring quality."

        Component Significance:
        -----------------------
        1. Volume Quality (40 pts) - MOST IMPORTANT:
           - Low volume proves supply exhaustion
           - <0.3x = 40pts (exceptional)
           - 0.3-0.4x = 30pts (excellent)
           - 0.4-0.5x = 20pts (ideal)
           - 0.5-0.6x = 10pts (acceptable)
           - 0.6-0.69x = 5pts (marginal)

        2. Penetration Depth (35 pts):
           - 1-2% ideal shakeout depth = 35pts
           - 2-3% acceptable = 25pts
           - 3-4% deeper shakeout = 15pts
           - 4-5% maximum allowed = 5pts

        3. Recovery Speed (25 pts):
           - 1 bar = 25pts (immediate demand)
           - 2 bars = 20pts (strong demand)
           - 3 bars = 15pts (good demand)
           - 4-5 bars = 10pts (slow demand)

        4. Test Confirmation (20 pts):
           - Test present = 20pts (FR13 requirement)
           - No test = 0pts (will fail signal generation)

        5. Creek Strength Bonus (+10 pts):
           - Strength >=80 = 10pts (excellent support)
           - Strength 70-79 = 7pts (strong support)
           - Strength 60-69 = 5pts (moderate support)
           - Strength <60 = 0pts (weak support)

        6. Volume Trend Bonus (+10 pts):
           - Declining volume from previous tests (20%+ decrease) = 10pts
           - Stable volume (±20%) = 5pts
           - Rising volume = 0pts (warning signal)

        Confidence Ranges:
        ------------------
        - 90-100%: EXCELLENT - Textbook spring, highest probability
        - 80-89%: GOOD - Very high quality, strong setup
        - 70-79%: ACCEPTABLE - Good quality, meets minimum (SIGNALS GENERATED)
        - <70%: REJECTED - Below threshold, no signal

        Example:
            >>> from src.pattern_engine.scoring.stock_scorer import StockConfidenceScorer
            >>>
            >>> scorer = StockConfidenceScorer()
            >>> # After detecting spring and test
            >>> confidence = scorer.calculate_spring_confidence(
            ...     spring=spring,
            ...     creek=trading_range.creek,
            ...     previous_tests=[test1, test2]  # Optional
            ... )
            >>>
            >>> print(f"Confidence: {confidence.total_score}%")
            >>> print(f"Quality: {confidence.quality_tier}")
            >>> print(f"Meets threshold: {confidence.meets_threshold}")
            >>> print(f"Components: {confidence.component_scores}")
            >>>
            >>> if confidence.meets_threshold:
            ...     # Generate signal (Story 5.5)
            ...     signal = generate_spring_signal(spring, confidence)
            >>> else:
            ...     print(f"Spring rejected - {confidence.total_score}% < 70% minimum")
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
            "spring_confidence_calculation_starting",
            spring_timestamp=spring.bar.timestamp.isoformat(),
            spring_volume_ratio=float(spring.volume_ratio),
            spring_penetration_pct=float(spring.penetration_pct),
            spring_recovery_bars=spring.recovery_bars,
            creek_strength=creek.strength_score,
            previous_tests_count=len(previous_tests),
        )

        # Initialize component scores
        component_scores = {
            "volume_quality": 0,
            "penetration_depth": 0,
            "recovery_speed": 0,
            "test_confirmation": 0,
            "creek_strength_bonus": 0,
            "volume_trend_bonus": 0,
            "raw_total": 0,
        }

        # ============================================================
        # COMPONENT 1: VOLUME QUALITY SCORING (40 points max)
        # ============================================================
        # AC 2: Volume quality is MOST important indicator
        # Low volume proves supply exhaustion

        volume_ratio = spring.volume_ratio

        if volume_ratio < Decimal("0.3"):
            volume_points = 40
            volume_quality = "EXCEPTIONAL"
            logger.info(
                "exceptional_volume_spring",
                volume_ratio=float(volume_ratio),
                message=f"Exceptionally rare ultra-low volume spring (<0.3x): {volume_points} points",
            )
        elif volume_ratio < Decimal("0.4"):
            volume_points = 30
            volume_quality = "EXCELLENT"
        elif volume_ratio < Decimal("0.5"):
            volume_points = 20
            volume_quality = "IDEAL"
        elif volume_ratio < Decimal("0.6"):
            volume_points = 10
            volume_quality = "ACCEPTABLE"
        else:  # 0.6 <= volume_ratio < 0.7
            volume_points = 5
            volume_quality = "MARGINAL"

        component_scores["volume_quality"] = volume_points

        logger.debug(
            "volume_quality_scored",
            volume_ratio=float(volume_ratio),
            volume_points=volume_points,
            volume_quality=volume_quality,
            message=f"Volume {volume_ratio:.2f}x scored {volume_points} points",
        )

        # ============================================================
        # COMPONENT 2: PENETRATION DEPTH SCORING (35 points max)
        # ============================================================
        # AC 7: Penetration depth indicates shakeout quality
        # 1-2% ideal, 4-5% maximum allowed

        penetration_pct = spring.penetration_pct

        if Decimal("0.01") <= penetration_pct < Decimal("0.02"):
            penetration_points = 35
            penetration_quality = "IDEAL"
        elif Decimal("0.02") <= penetration_pct < Decimal("0.03"):
            penetration_points = 25
            penetration_quality = "GOOD"
        elif Decimal("0.03") <= penetration_pct < Decimal("0.04"):
            penetration_points = 15
            penetration_quality = "ACCEPTABLE"
        else:  # 0.04 <= penetration_pct <= 0.05
            penetration_points = 5
            penetration_quality = "DEEP"

        component_scores["penetration_depth"] = penetration_points

        logger.debug(
            "penetration_depth_scored",
            penetration_pct=float(penetration_pct),
            penetration_points=penetration_points,
            penetration_quality=penetration_quality,
            message=f"Penetration {penetration_pct:.1%} scored {penetration_points} points",
        )

        # ============================================================
        # COMPONENT 3: RECOVERY SPEED SCORING (25 points max)
        # ============================================================
        # AC 4: Recovery speed indicates demand strength
        # Faster recovery = stronger demand absorption

        recovery_bars = spring.recovery_bars

        if recovery_bars == 1:
            recovery_points = 25
            recovery_quality = "IMMEDIATE"
        elif recovery_bars == 2:
            recovery_points = 20
            recovery_quality = "STRONG"
        elif recovery_bars == 3:
            recovery_points = 15
            recovery_quality = "GOOD"
        else:  # 4-5 bars
            recovery_points = 10
            recovery_quality = "SLOW"

        component_scores["recovery_speed"] = recovery_points

        logger.debug(
            "recovery_speed_scored",
            recovery_bars=recovery_bars,
            recovery_points=recovery_points,
            recovery_quality=recovery_quality,
            message=f"Recovery in {recovery_bars} bars scored {recovery_points} points",
        )

        # ============================================================
        # COMPONENT 4: TEST CONFIRMATION SCORING (20 points)
        # ============================================================
        # AC 5: Test confirmation is FR13 requirement
        # Note: This function doesn't receive the Test object directly
        # For now, we assume if previous_tests has 1+ test, the spring has confirmation
        # This should be refactored when integrating with Story 5.5

        # TEMPORARY: Check if previous_tests list has any tests
        # Story 5.5 will pass the actual Test object for this spring
        has_test = len(previous_tests) > 0

        if has_test:
            test_points = 20
            test_quality = "PRESENT"
            logger.debug(
                "test_confirmation_scored",
                test_present=True,
                test_points=test_points,
                test_quality=test_quality,
            )
        else:
            test_points = 0
            test_quality = "NONE"
            logger.warning(
                "no_test_confirmation",
                message="No test confirmation - spring will not generate signal (FR13)",
            )

        component_scores["test_confirmation"] = test_points

        # ============================================================
        # BONUS 1: CREEK STRENGTH BONUS (10 points max)
        # ============================================================
        # AC 8: Creek strength indicates support quality
        # Strong support = more reliable spring

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
            "creek_strength_bonus",
            creek_strength=creek_strength,
            creek_bonus=creek_bonus,
            creek_quality=creek_quality,
            message=f"Creek strength {creek_strength} earned {creek_bonus} bonus points",
        )

        # ============================================================
        # BONUS 2: VOLUME TREND BONUS (10 points max)
        # ============================================================
        # AC 9: Volume trend from previous tests indicates accumulation pattern
        # Declining volume = bullish accumulation

        if len(previous_tests) >= 2:
            # Calculate average volume of previous 2 tests
            prev_volumes = [test.volume_ratio for test in previous_tests[-2:]]
            avg_prev_volume = sum(prev_volumes, Decimal("0")) / len(prev_volumes)

            # Compare spring volume to average previous test volume
            volume_change_pct = (avg_prev_volume - spring.volume_ratio) / avg_prev_volume

            if volume_change_pct >= Decimal("0.2"):  # 20%+ decrease
                volume_trend_bonus = 10
                logger.info(
                    "volume_trend_bonus_awarded",
                    avg_prev_volume=float(avg_prev_volume),
                    spring_volume=float(spring.volume_ratio),
                    volume_decrease=float(volume_change_pct),
                    message=f"Declining volume trend earned {volume_trend_bonus} bonus points",
                )
            elif volume_change_pct >= Decimal("-0.2"):  # Stable ±20%
                volume_trend_bonus = 5
            else:  # Rising volume (warning)
                volume_trend_bonus = 0
                logger.warning(
                    "rising_volume_trend",
                    avg_prev_volume=float(avg_prev_volume),
                    spring_volume=float(spring.volume_ratio),
                    message="Rising volume trend - potential warning signal",
                )
        else:
            # Not enough previous tests to calculate trend
            volume_trend_bonus = 0
            logger.debug(
                "volume_trend_insufficient_data",
                previous_tests_count=len(previous_tests),
                message="Need 2+ previous tests for volume trend bonus",
            )

        component_scores["volume_trend_bonus"] = volume_trend_bonus

        # ============================================================
        # FINAL CONFIDENCE CALCULATION
        # ============================================================
        # AC 10: Total possible 120 points, capped at 100

        raw_total = (
            volume_points
            + penetration_points
            + recovery_points
            + test_points
            + creek_bonus
            + volume_trend_bonus
        )

        component_scores["raw_total"] = raw_total

        # Cap at 100 for final score
        final_confidence = min(raw_total, 100)

        # Determine quality tier
        if final_confidence >= 90:
            quality_tier = "EXCELLENT"
        elif final_confidence >= 80:
            quality_tier = "GOOD"
        elif final_confidence >= 70:
            quality_tier = "ACCEPTABLE"
        else:
            quality_tier = "REJECTED"

        logger.info(
            "spring_confidence_calculated",
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
        )

        # Validate FR4 minimum threshold (70%)
        if final_confidence < 70:
            logger.warning(
                "spring_low_confidence",
                final_confidence=final_confidence,
                threshold=70,
                message=(
                    f"Spring confidence {final_confidence}% below FR4 minimum "
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
        Calculate confidence score for SOS breakout pattern.

        REFACTOR NOTE: This is an EXACT copy from Story 6.5 sos_confidence_scorer.py.
        ZERO logic changes have been made. Parameter name changed from trading_range
        to range_ to match base class signature.

        Combines multiple Wyckoff factors to generate 0-100 confidence score.
        Only patterns scoring >= 70% generate trade signals.

        Algorithm:
        1. Volume strength (35 pts, non-linear) - institutional volume thresholds
        2. Spread expansion (20 pts) - bar conviction
        3. Close position (20 pts) - buyer control
        4. Breakout size (15 pts) - penetration quality
        5. Accumulation duration (10 pts) - cause building
        6. LPS bonus (15 pts) - lower-risk entry confirmation
        7. Phase bonus (5 pts) - Wyckoff phase alignment
        8. Volume trend bonus (5 pts, OPTIONAL) - classic accumulation signature
        9. Market condition modifier (±5 pts, OPTIONAL) - broader market context
        10. Entry type baseline: LPS 80 (86% better expectancy), SOS direct 65

        Args:
            sos: SOS breakout pattern
            lps: LPS pattern (optional - None for direct SOS entry)
            range_: Trading range context
            phase: Current Wyckoff phase classification

        Returns:
            int: Confidence score 0-100

        Example:
            >>> # Excellent SOS with LPS entry
            >>> confidence = scorer.calculate_sos_confidence(sos, lps, trading_range, phase)
            >>> if confidence >= 70:
            ...     print(f"Signal generated: {confidence}% confidence")
        """
        # Alias parameter to match original implementation variable name
        trading_range = range_

        confidence = 0

        logger.debug(
            "sos_confidence_calculation_start",
            sos_id=str(sos.id),
            lps_present=lps is not None,
            trading_range_id=str(trading_range.id),
            phase=phase.phase.value if phase.phase else None,
            message="Starting SOS confidence calculation",
        )

        # AC 2: Volume strength (35 points) - NON-LINEAR SCORING
        # Professional volume operates on thresholds, not linear scales
        # 2.0x is the inflection point where institutional activity becomes clear

        volume_ratio = sos.volume_ratio
        volume_points = 0

        if volume_ratio >= Decimal("2.5"):
            volume_points = 35  # Excellent: climactic volume
            volume_quality = "excellent"
        elif volume_ratio >= Decimal("2.3"):
            # 2.3-2.5x: Very strong, approaching climactic (32-35 pts)
            normalized = (volume_ratio - Decimal("2.3")) / Decimal("0.2")
            volume_points = int(32 + (normalized * 3))
            volume_quality = "very_strong"
        elif volume_ratio >= Decimal("2.0"):
            # 2.0-2.3x: Ideal professional participation (25-32 pts)
            # This is the Wyckoff "sweet spot" - clear institutional activity
            normalized = (volume_ratio - Decimal("2.0")) / Decimal("0.3")
            volume_points = int(25 + (normalized * 7))
            volume_quality = "ideal"
        elif volume_ratio >= Decimal("1.7"):
            # 1.7-2.0x: Acceptable, institutional participation evident (18-25 pts)
            # Accelerating confidence as we approach 2.0x threshold
            normalized = (volume_ratio - Decimal("1.7")) / Decimal("0.3")
            volume_points = int(18 + (normalized * 7))
            volume_quality = "acceptable"
        elif volume_ratio >= Decimal("1.5"):
            # 1.5-1.7x: Weak, borderline institutional activity (15-18 pts)
            # Could be retail or false breakout - penalize more heavily
            normalized = (volume_ratio - Decimal("1.5")) / Decimal("0.2")
            volume_points = int(15 + (normalized * 3))
            volume_quality = "weak"
        else:
            # Should not occur - SOSBreakout validator requires >= 1.5x
            volume_points = 0
            volume_quality = "insufficient"

        confidence += volume_points

        logger.debug(
            "sos_confidence_volume_scoring",
            volume_ratio=float(volume_ratio),
            volume_points=volume_points,
            volume_quality=volume_quality,
            threshold_note="Non-linear scoring reflects professional volume thresholds",
            message=f"Volume {volume_ratio:.2f}x scored {volume_points} points ({volume_quality})",
        )

        # AC 3: Spread expansion (20 points)
        # 1.2x = 15 pts (minimum acceptable)
        # 1.5x+ = 20 pts (wide spread - strong conviction)

        spread_ratio = sos.spread_ratio
        spread_points = 0

        if spread_ratio >= Decimal("1.5"):
            spread_points = 20  # Wide spread earns full points
            spread_quality = "wide"
        elif spread_ratio >= Decimal("1.2"):
            # Linear interpolation between 1.2x and 1.5x
            # 1.2x = 15 pts, 1.5x = 20 pts
            normalized = (spread_ratio - Decimal("1.2")) / Decimal("0.3")
            spread_points = int(15 + (normalized * 5))
            spread_quality = "acceptable"
        else:
            # Should not occur - SOSBreakout validator requires >= 1.2x
            spread_points = 0
            spread_quality = "narrow"

        confidence += spread_points

        logger.debug(
            "sos_confidence_spread_scoring",
            spread_ratio=float(spread_ratio),
            spread_points=spread_points,
            spread_quality=spread_quality,
            message=f"Spread {spread_ratio:.2f}x scored {spread_points} points ({spread_quality})",
        )

        # AC 4: Close position (20 points)
        # 0.7 = 15 pts (minimum - closes in upper 30%)
        # 0.8+ = 20 pts (very strong close - closes near high)

        close_position = sos.close_position
        close_points = 0

        if close_position >= Decimal("0.8"):
            close_points = 20  # Very strong close earns full points
            close_quality = "very_strong"
        elif close_position >= Decimal("0.7"):
            # Linear interpolation between 0.7 and 0.8
            # 0.7 = 15 pts, 0.8 = 20 pts
            normalized = (close_position - Decimal("0.7")) / Decimal("0.1")
            close_points = int(15 + (normalized * 5))
            close_quality = "strong"
        elif close_position >= Decimal("0.5"):
            # Weak close (middle of bar) - reduced points
            # Linear scaling from 0.5 to 0.7: 5-15 pts
            normalized = (close_position - Decimal("0.5")) / Decimal("0.2")
            close_points = int(5 + (normalized * 10))
            close_quality = "weak"
        else:
            # Very weak close (lower half) - minimal points
            close_points = int(close_position * 10)  # 0-5 pts
            close_quality = "very_weak"

        confidence += close_points

        logger.debug(
            "sos_confidence_close_scoring",
            close_position=float(close_position),
            close_points=close_points,
            close_quality=close_quality,
            message=f"Close position {close_position:.2f} scored {close_points} points ({close_quality})",
        )

        # AC 5: Breakout size (15 points)
        # 1% = 10 pts (minimum acceptable per Story 6.1 AC 3)
        # 3%+ = 15 pts (strong breakout)

        breakout_pct = sos.breakout_pct
        breakout_pct_value = breakout_pct * Decimal("100")  # Convert to percentage

        breakout_points = 0

        if breakout_pct_value >= Decimal("3.0"):
            breakout_points = 15  # Strong breakout (3%+) earns full points
            breakout_quality = "strong"
        elif breakout_pct_value >= Decimal("1.0"):
            # Linear interpolation between 1% and 3%
            # 1% = 10 pts, 3% = 15 pts
            normalized = (breakout_pct_value - Decimal("1.0")) / Decimal("2.0")
            breakout_points = int(10 + (normalized * 5))
            breakout_quality = "acceptable"
        else:
            # Should not occur - SOSBreakout validator requires >= 1%
            breakout_points = 0
            breakout_quality = "insufficient"

        confidence += breakout_points

        logger.debug(
            "sos_confidence_breakout_size_scoring",
            breakout_pct=float(breakout_pct_value),
            breakout_points=breakout_points,
            breakout_quality=breakout_quality,
            message=f"Breakout size {breakout_pct_value:.2f}% scored {breakout_points} points ({breakout_quality})",
        )

        # AC 6: Accumulation duration (10 points)
        # Range duration 20+ bars = 10 pts (longer accumulation = higher confidence)

        # Extract range start and end timestamps
        range_start = trading_range.start_timestamp
        range_end = (
            trading_range.end_timestamp or sos.bar.timestamp
        )  # Use SOS bar if range still active

        # Calculate duration in days (simplified - assumes daily bars)
        duration_days = (range_end - range_start).days if range_start and range_end else 0

        # Approximate bars based on timeframe (simplified calculation)
        range_duration_bars = duration_days  # Simplified: 1 bar/day for daily timeframe

        duration_points = 0

        if range_duration_bars >= 20:
            duration_points = 10  # Long accumulation earns full points
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
            "sos_confidence_duration_scoring",
            range_duration_bars=range_duration_bars,
            duration_points=duration_points,
            duration_quality=duration_quality,
            message=f"Range duration {range_duration_bars} bars scored {duration_points} points ({duration_quality})",
        )

        # AC 11: Volume trend bonus (5 points) - OPTIONAL
        # Classic Wyckoff: declining volume before SOS = quiet accumulation
        # NOTE: Requires bar history - deferred for MVP (Story 6.6)
        # Placeholder for future implementation

        volume_trend_bonus = 0
        # TODO: Implement when bar history available (Story 6.6)
        # For now, skip volume trend analysis

        logger.debug(
            "sos_confidence_volume_trend_bonus",
            volume_trend_bonus=volume_trend_bonus,
            message="Volume trend bonus deferred to Story 6.6 (bar history required)",
        )

        confidence += volume_trend_bonus

        # AC 7: LPS bonus (15 points)
        # If LPS present and held support, add 15 pts
        # LPS provides lower-risk entry confirmation

        lps_bonus_points = 0

        if lps is not None:
            # LPS detected - check if support held (Story 6.3 AC 5)
            if lps.held_support:
                lps_bonus_points = 15  # Full LPS bonus

                logger.info(
                    "sos_confidence_lps_bonus",
                    lps_present=True,
                    held_support=True,
                    distance_from_ice=float(lps.distance_from_ice),
                    volume_ratio=float(lps.volume_ratio),
                    bonus_points=lps_bonus_points,
                    message="LPS present and held support - adding 15 point bonus",
                )
            else:
                # LPS detected but broke support (should be rare, validator should reject)
                lps_bonus_points = 0

                logger.warning(
                    "sos_confidence_lps_failed",
                    lps_present=True,
                    held_support=False,
                    message="LPS present but broke support - no bonus",
                )
        else:
            # No LPS detected - direct SOS entry
            lps_bonus_points = 0

            logger.debug(
                "sos_confidence_no_lps",
                lps_present=False,
                message="No LPS detected - SOS direct entry (no LPS bonus)",
            )

        confidence += lps_bonus_points

        # AC 8: Phase confidence bonus (5 points)
        # Phase D with high confidence adds 5 pts
        # Confirms proper Wyckoff phase for SOS

        phase_bonus_points = 0

        current_phase = phase.phase
        phase_confidence_value = phase.confidence

        if current_phase == WyckoffPhase.D:
            # Phase D is ideal for SOS (markup phase)
            if phase_confidence_value >= 85:
                phase_bonus_points = 5  # High-confidence Phase D earns full bonus
                phase_quality = "ideal"
            elif phase_confidence_value >= 70:
                # Medium confidence Phase D: partial bonus
                phase_bonus_points = 3
                phase_quality = "good"
            else:
                # Low confidence Phase D: minimal bonus
                phase_bonus_points = 1
                phase_quality = "acceptable"
        elif current_phase == WyckoffPhase.C and phase_confidence_value >= 85:
            # Late Phase C acceptable (Story 6.1 AC 8)
            # Late Phase C is the TRANSITION into Phase D - SOS may mark the shift
            phase_bonus_points = 3  # Partial bonus for late Phase C
            phase_quality = "late_phase_c"
        else:
            # Wrong phase or low confidence
            phase_bonus_points = 0
            phase_quality = "wrong_phase"

        confidence += phase_bonus_points

        phase_name = current_phase.value if current_phase else "None"
        logger.debug(
            "sos_confidence_phase_bonus",
            current_phase=current_phase.value if current_phase else None,
            phase_confidence=phase_confidence_value,
            phase_bonus_points=phase_bonus_points,
            phase_quality=phase_quality,
            message=f"Phase {phase_name} (confidence {phase_confidence_value}) "
            f"scored {phase_bonus_points} points ({phase_quality})",
        )

        # AC 9: Entry type adjustment
        # LPS entry base 80, SOS direct base 65 (LPS has 86% better expectancy)
        # This is a baseline adjustment, NOT a bonus

        entry_type_adjustment = 0

        if lps is not None and lps.held_support:
            # LPS entry: higher baseline confidence (lower risk)
            entry_type = "LPS_ENTRY"
            baseline_confidence = 80  # AC 9: LPS entry baseline (UPDATED from 75)

            logger.info(
                "sos_confidence_entry_type",
                entry_type=entry_type,
                baseline_confidence=baseline_confidence,
                message="LPS entry type - baseline confidence 80 (86% better expectancy than SOS direct)",
            )
        else:
            # SOS direct entry: standard baseline
            entry_type = "SOS_DIRECT_ENTRY"
            baseline_confidence = 65  # AC 9: SOS direct entry baseline

            logger.info(
                "sos_confidence_entry_type",
                entry_type=entry_type,
                baseline_confidence=baseline_confidence,
                message="SOS direct entry - baseline confidence 65 (standard risk)",
            )

        # Calculate adjustment needed to reach baseline
        # If current confidence < baseline, adjust up to baseline
        if confidence < baseline_confidence:
            entry_type_adjustment = baseline_confidence - confidence
            original_confidence = confidence
            confidence = baseline_confidence

            logger.debug(
                "sos_confidence_baseline_adjustment",
                original_confidence=original_confidence,
                entry_type_adjustment=entry_type_adjustment,
                adjusted_confidence=confidence,
                message=f"Adjusted to {entry_type} baseline: +{entry_type_adjustment} pts",
            )
        else:
            entry_type_adjustment = 0

            logger.debug(
                "sos_confidence_no_baseline_adjustment",
                current_confidence=confidence,
                baseline_confidence=baseline_confidence,
                message=f"Confidence {confidence} already exceeds {entry_type} baseline {baseline_confidence}",
            )

        # AC 12: Market condition modifier (-5 to +5 points) - OPTIONAL
        # Deferred to Epic 7 if SPY phase infrastructure not available
        market_modifier = 0

        logger.debug(
            "sos_confidence_market_modifier_unavailable",
            market_modifier=market_modifier,
            message="Market condition modifier deferred to Epic 7 (SPY phase infrastructure required)",
        )

        confidence += market_modifier

        # AC 10: Minimum confidence threshold
        # 70% required for signal generation
        # Below 70% = pattern rejected, no signal generated

        # Ensure confidence doesn't exceed 100
        if confidence > 100:
            logger.warning(
                "sos_confidence_exceeds_max",
                calculated_confidence=confidence,
                message="Confidence exceeds 100 - capping at 100",
            )
            confidence = 100

        # Check minimum threshold
        meets_threshold = confidence >= MINIMUM_CONFIDENCE

        if meets_threshold:
            logger.info(
                "sos_confidence_final",
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
                market_modifier=market_modifier,
                meets_threshold=True,
                message=f"SOS confidence {confidence}% - PASSES threshold (>= 70%) - signal eligible",
            )
        else:
            logger.warning(
                "sos_confidence_below_threshold",
                final_confidence=confidence,
                minimum_threshold=MINIMUM_CONFIDENCE,
                deficit=MINIMUM_CONFIDENCE - confidence,
                meets_threshold=False,
                message=f"SOS confidence {confidence}% - FAILS threshold (< 70%) - signal rejected",
            )

        return confidence
