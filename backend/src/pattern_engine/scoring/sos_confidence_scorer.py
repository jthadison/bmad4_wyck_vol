"""
SOS/LPS Confidence Scoring Module.

This module implements confidence scoring for SOS (Sign of Strength) breakout
patterns, combining multiple Wyckoff factors to generate a 0-100 confidence score.
Only patterns scoring 70%+ generate trade signals.

Algorithm Components:
- Volume strength (35 points, non-linear): Institutional volume threshold scoring
- Spread expansion (20 points): Bar conviction measurement
- Close position (20 points): Buyer control assessment
- Breakout size (15 points): Penetration quality
- Accumulation duration (10 points): Cause building measurement
- LPS bonus (15 points): Lower-risk entry confirmation
- Phase bonus (5 points): Wyckoff phase alignment
- Volume trend bonus (5 points): Classic accumulation signature
- Market condition modifier (±5 points, OPTIONAL): Broader market context
- Entry type baseline: LPS 80 (86% better expectancy), SOS direct 65

Minimum Threshold: 70% required for signal generation.

Wyckoff Context:
Non-linear volume scoring reflects professional volume operating on threshold
effects. The 2.0x volume ratio marks the inflection point where institutional
activity becomes undeniable. LPS entries receive higher baseline (80 vs 65)
reflecting 86.7% better trade expectancy from tighter stops and dual confirmation.

Example:
    >>> from decimal import Decimal
    >>> from backend.src.models.sos_breakout import SOSBreakout
    >>> from backend.src.models.lps import LPS
    >>> from backend.src.models.trading_range import TradingRange
    >>> from backend.src.models.phase_classification import PhaseClassification, WyckoffPhase
    >>>
    >>> # Ideal SOS with LPS entry
    >>> confidence = calculate_sos_confidence(sos, lps, trading_range, phase)
    >>> print(f"Confidence: {confidence}% ({get_confidence_quality(confidence)})")
    Confidence: 92% (EXCELLENT)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

import structlog

from src.models.lps import LPS
from src.models.phase_classification import PhaseClassification, WyckoffPhase
from src.models.sos_breakout import SOSBreakout
from src.models.trading_range import TradingRange

logger = structlog.get_logger(__name__)

# Constants
MINIMUM_CONFIDENCE = 70  # AC 10: Minimum threshold for signal generation


def calculate_sos_confidence(
    sos: SOSBreakout,
    lps: Optional[LPS],
    trading_range: TradingRange,
    phase: PhaseClassification,
) -> int:
    """
    Calculate confidence score for SOS breakout pattern.

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
        trading_range: Trading range context
        phase: Current Wyckoff phase classification

    Returns:
        int: Confidence score 0-100

    Example:
        >>> # Excellent SOS with LPS entry
        >>> confidence = calculate_sos_confidence(sos, lps, trading_range, phase)
        >>> if confidence >= 70:
        ...     print(f"Signal generated: {confidence}% confidence")
    """
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


def get_confidence_quality(confidence: int) -> str:
    """
    Get qualitative assessment of confidence score.

    Quality levels:
    - EXCELLENT: 90-100 (very high confidence)
    - STRONG: 80-89 (high confidence)
    - ACCEPTABLE: 70-79 (minimum acceptable)
    - WEAK: 0-69 (below threshold, rejected)

    Args:
        confidence: Confidence score 0-100

    Returns:
        str: Quality level (EXCELLENT, STRONG, ACCEPTABLE, WEAK)

    Example:
        >>> get_confidence_quality(92)
        'EXCELLENT'
        >>> get_confidence_quality(75)
        'ACCEPTABLE'
        >>> get_confidence_quality(65)
        'WEAK'
    """
    if confidence >= 90:
        return "EXCELLENT"
    elif confidence >= 80:
        return "STRONG"
    elif confidence >= 70:
        return "ACCEPTABLE"
    else:
        return "WEAK"
