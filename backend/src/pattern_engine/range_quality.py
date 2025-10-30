"""
Trading range quality scoring module for Wyckoff analysis.

This module implements a comprehensive quality scoring system (0-100 points) to filter
trading ranges and identify high-probability accumulation/distribution zones. Only ranges
scoring >= 70 meet Wyckoff standards for pattern detection (FR1 requirement).

Scoring Components (100 points total):
    - Duration (30 pts): Cause-effect relationship (longer cause = larger effect)
    - Touch Count (30 pts): Level strength (more tests = stronger levels)
    - Price Tightness (20 pts): Cluster precision (tight = reliable levels)
    - Volume Confirmation (20 pts): Smart money absorption (decreasing volume on tests)

Quality Threshold:
    - Score >= 70: Tradable range (proceed to Creek/Ice/Jump level calculation)
    - Score < 70: Low-quality range (skip, insufficient quality for patterns)

Example:
    >>> from backend.src.pattern_engine.range_quality import calculate_range_quality
    >>> from backend.src.pattern_engine.volume_analyzer import VolumeAnalyzer
    >>>
    >>> # Analyze volume
    >>> volume_analyzer = VolumeAnalyzer()
    >>> volume_analysis = volume_analyzer.analyze(bars)
    >>>
    >>> # Score range
    >>> score = calculate_range_quality(trading_range, bars, volume_analysis)
    >>> trading_range.quality_score = score
    >>>
    >>> # Filter for quality ranges
    >>> quality_ranges = filter_quality_ranges(all_ranges, min_score=70)
"""

from __future__ import annotations

from decimal import Decimal
from statistics import mean

import structlog

from src.models.ohlcv import OHLCVBar
from src.models.trading_range import TradingRange
from src.models.volume_analysis import VolumeAnalysis

logger = structlog.get_logger(__name__)


def calculate_range_quality(
    trading_range: TradingRange, bars: list[OHLCVBar], volume_analysis: list[VolumeAnalysis]
) -> int:
    """
    Calculate comprehensive quality score for trading range (0-100 points).

    Implements Wyckoff quality filtering (FR1) to identify high-probability
    accumulation/distribution zones. Scores ranges across 4 components:
    duration (30), touch count (30), tightness (20), volume confirmation (20).

    Args:
        trading_range: TradingRange to score
        bars: OHLCV bars for bar-level access (must span range indices)
        volume_analysis: VolumeAnalysis results from VolumeAnalyzer (must match bars length)

    Returns:
        int: Quality score 0-100
            - 90-100: Exceptional range (textbook accumulation/distribution)
            - 80-89: Very good range (strong pattern potential)
            - 70-79: Good range (tradable, minimum FR1 threshold)
            - 60-69: Marginal range (below threshold, skip)
            - <60: Poor range (structural issues, skip)

    Quality Threshold:
        Score >= 70 required for pattern detection (FR1 requirement)

    Raises:
        None - returns 0 for invalid inputs with logging

    Example:
        >>> score = calculate_range_quality(trading_range, bars, volume_analysis)
        >>> if score >= 70:
        ...     print(f"Quality range: {score} points")
        ... else:
        ...     print(f"Rejected: {score} points (below 70 threshold)")
    """
    # Validate inputs
    if trading_range is None:
        logger.error("null_trading_range", message="Cannot score None trading range")
        return 0

    if not bars:
        logger.warning("empty_bars_list", message="No bars for quality scoring")
        return 0

    if len(volume_analysis) != len(bars):
        logger.error(
            "volume_bars_mismatch",
            bars_count=len(bars),
            volume_count=len(volume_analysis),
            message="Volume analysis length must match bars length",
        )
        return 0

    # Validate array bounds (QA Issue #3 fix)
    if trading_range.start_index < 0 or trading_range.start_index >= len(bars):
        logger.error(
            "invalid_start_index",
            start_index=trading_range.start_index,
            bars_length=len(bars),
            message="Range start_index out of bounds",
        )
        return 0

    if trading_range.end_index < 0 or trading_range.end_index >= len(bars):
        logger.error(
            "invalid_end_index",
            end_index=trading_range.end_index,
            bars_length=len(bars),
            message="Range end_index out of bounds",
        )
        return 0

    if trading_range.start_index > trading_range.end_index:
        logger.error(
            "invalid_range_indices",
            start_index=trading_range.start_index,
            end_index=trading_range.end_index,
            message="Range start_index must be <= end_index",
        )
        return 0

    # Extract symbol for logging
    symbol = (
        volume_analysis[trading_range.start_index].bar.symbol
        if trading_range.start_index < len(volume_analysis)
        else "UNKNOWN"
    )

    logger.info(
        "quality_scoring_start",
        symbol=symbol,
        range_id=str(trading_range.id),
        support=float(trading_range.support),
        resistance=float(trading_range.resistance),
        duration=trading_range.duration,
    )

    # Calculate component scores
    duration_score = _score_duration(trading_range.duration)
    touch_score = _score_touch_count(trading_range)
    tightness_score = _score_price_tightness(trading_range)
    volume_score = _score_volume_confirmation(trading_range, bars, volume_analysis)

    # Calculate total score
    total_score = duration_score + touch_score + tightness_score + volume_score
    total_score = min(total_score, 100)  # Cap at 100

    # Log component breakdown
    logger.info(
        "quality_score_components",
        symbol=symbol,
        range_id=str(trading_range.id),
        duration_score=duration_score,
        touch_score=touch_score,
        tightness_score=tightness_score,
        volume_score=volume_score,
        total_score=total_score,
    )

    # Log rejection for low-quality ranges (AC 10)
    if total_score < 70:
        recommendation = _get_rejection_reason(
            duration_score, touch_score, tightness_score, volume_score
        )
        logger.debug(
            "range_rejected_low_quality",
            symbol=symbol,
            range_id=str(trading_range.id),
            score=total_score,
            threshold=70,
            duration=trading_range.duration,
            duration_score=duration_score,
            touch_count=trading_range.total_touches,
            touch_score=touch_score,
            tightness_pct=float(
                (
                    trading_range.support_cluster.std_deviation
                    / trading_range.support_cluster.average_price
                    + trading_range.resistance_cluster.std_deviation
                    / trading_range.resistance_cluster.average_price
                )
                / 2
            ),
            tightness_score=tightness_score,
            volume_score=volume_score,
            recommendation=recommendation,
        )

    logger.info(
        "quality_scoring_complete",
        symbol=symbol,
        range_id=str(trading_range.id),
        total_score=total_score,
        status="PASS" if total_score >= 70 else "REJECT",
    )

    return total_score


def _score_duration(duration: int) -> int:
    """
    Score duration component (0-30 points based on cause adequacy).

    Implements Wyckoff's Law of Cause and Effect (FR10): longer accumulation/
    distribution (cause) creates larger price moves (effect). Duration scoring
    rewards adequate cause for meaningful effect.

    Args:
        duration: Range duration in bars

    Returns:
        int: Duration score 0-30 points
            - 40+ bars: 30 pts (excellent cause, 3.0x target multiplier)
            - 25-39 bars: 20 pts (good cause, 2.5x target multiplier)
            - 15-24 bars: 15 pts (adequate cause, 2.0x target multiplier)
            - 10-14 bars: 10 pts (minimal cause, 1.5x target multiplier)
            - <10 bars: 0 pts (insufficient cause, filtered by Story 3.2)

    Wyckoff Context:
        - 40+ bars: Mature campaign, high probability of significant move
        - 25-39 bars: Good accumulation, decent target potential
        - 15-24 bars: Minimum for reliable patterns
        - <15 bars: Insufficient cause, weak patterns, skip
    """
    if duration >= 40:
        return 30  # Excellent cause
    elif duration >= 25:
        return 20  # Good cause
    elif duration >= 15:
        return 15  # Adequate cause
    elif duration >= 10:
        return 10  # Minimal cause
    else:
        return 0  # Insufficient cause


def _score_touch_count(trading_range: TradingRange) -> int:
    """
    Score touch count component (0-30 points based on level strength).

    More touches = stronger, better-defined support/resistance levels. Each test
    that holds validates the level's significance. Symmetry bonus rewards balanced
    touches (indicates genuine range, not one-sided consolidation).

    Args:
        trading_range: TradingRange with support/resistance clusters

    Returns:
        int: Touch count score 0-30 points (capped at 30)
            - 8+ touches: 30 pts (very strong levels, 4+ each)
            - 6-7 touches: 25 pts (strong levels, 3 each)
            - 4-5 touches: 15 pts (adequate levels, 2 each minimum)
            - <4 touches: 5 pts (weak levels, at minimum from Story 3.2)
            - +5 bonus: Symmetry (touch_ratio >= 0.8, balanced tests)

    Wyckoff Context:
        - 4+ touches each level: Composite operator building large campaign
        - 3 touches each: Well-defined range, good pattern potential
        - 2 touches each: Minimum valid range (Story 3.2 requirement)
        - Symmetry bonus: Balanced tests indicate genuine range
    """
    support_touches = trading_range.support_cluster.touch_count
    resistance_touches = trading_range.resistance_cluster.touch_count
    total_touches = support_touches + resistance_touches

    # Base score
    if total_touches >= 8:
        score = 30  # Very strong levels
    elif total_touches >= 6:
        score = 25  # Strong levels
    elif total_touches >= 4:
        score = 15  # Adequate levels
    else:
        score = 5  # Weak levels

    # Symmetry bonus: balanced touches indicate well-defined range
    max_touches = max(support_touches, resistance_touches)
    if max_touches > 0:  # Avoid division by zero
        min_touches = min(support_touches, resistance_touches)
        touch_ratio = Decimal(min_touches) / Decimal(max_touches)
        if touch_ratio >= Decimal("0.8"):  # Within 20% balance
            score += 5

    return min(score, 30)


def _score_price_tightness(trading_range: TradingRange) -> int:
    """
    Score cluster tightness (0-20 points based on std deviation).

    Tight pivot clusters = precise, reliable support/resistance levels. Loose
    clusters = imprecise levels, unreliable for entry/stop placement.

    Args:
        trading_range: TradingRange with support/resistance clusters

    Returns:
        int: Tightness score 0-20 points
            - <1% avg std dev: 20 pts (very tight, precise levels)
            - 1-1.5% avg std dev: 15 pts (tight clusters)
            - 1.5-2% avg std dev: 10 pts (acceptable)
            - >2% avg std dev: 0 pts (loose clusters, imprecise)

    Wyckoff Context:
        - <1% std dev: Composite operator defending specific price level
        - 1-2% std dev: Acceptable range of support/resistance
        - >2% std dev: Poorly defined level, unreliable
    """
    # Calculate tightness as std_deviation / average_price (percentage)
    support_tightness = (
        trading_range.support_cluster.std_deviation / trading_range.support_cluster.average_price
    )
    resistance_tightness = (
        trading_range.resistance_cluster.std_deviation
        / trading_range.resistance_cluster.average_price
    )
    avg_tightness = (support_tightness + resistance_tightness) / 2

    # Score based on tightness
    if avg_tightness < Decimal("0.01"):  # <1%
        return 20  # Very tight, precise levels
    elif avg_tightness < Decimal("0.015"):  # 1-1.5%
        return 15  # Tight clusters
    elif avg_tightness < Decimal("0.02"):  # 1.5-2%
        return 10  # Acceptable
    else:  # >2%
        return 0  # Loose clusters, imprecise


def _score_volume_confirmation(
    trading_range: TradingRange, bars: list[OHLCVBar], volume_analysis: list[VolumeAnalysis]
) -> int:
    """
    Score volume confirmation (0-20 points based on volume behavior on tests).

    Decreasing volume on tests of support/resistance indicates smart money absorption.
    In accumulation, composite operator buys (absorbs supply) on tests of support,
    causing volume to decrease as supply is exhausted.

    Args:
        trading_range: TradingRange to analyze
        bars: OHLCV bars for the range period
        volume_analysis: VolumeAnalysis results matching bars

    Returns:
        int: Volume confirmation score 0-20 points
            - Support tests with decreasing volume: 10 pts
            - Support tests with flat volume: 5 pts
            - Support tests with increasing volume: 0 pts
            - Resistance tests with decreasing volume: 10 pts
            - Resistance tests with flat volume: 5 pts
            - Resistance tests with increasing volume: 0 pts

    Wyckoff Context:
        - Accumulation: Decreasing volume on support tests = supply exhaustion
        - Distribution: Decreasing volume on resistance tests = demand exhaustion
        - Flat volume: Neutral, no clear absorption pattern
        - Increasing volume: Distribution (acc) or absorption (dist), phase-dependent
    """
    # Extract bars and volume for range period
    bars[trading_range.start_index : trading_range.end_index + 1]
    range_vol = volume_analysis[trading_range.start_index : trading_range.end_index + 1]

    # Identify support test bars (low within 2% of support)
    support_tests = [
        vol
        for vol in range_vol
        if abs(float(vol.bar.low - trading_range.support)) / float(trading_range.support) < 0.02
        and vol.volume_ratio is not None
    ]

    # Identify resistance test bars (high within 2% of resistance)
    resistance_tests = [
        vol
        for vol in range_vol
        if abs(float(vol.bar.high - trading_range.resistance)) / float(trading_range.resistance)
        < 0.02
        and vol.volume_ratio is not None
    ]

    score = 0

    # Score support volume trend
    if len(support_tests) >= 2:
        half = len(support_tests) // 2
        first_half_vol = mean([float(vol.volume_ratio) for vol in support_tests[:half]])
        second_half_vol = mean([float(vol.volume_ratio) for vol in support_tests[half:]])

        if second_half_vol < first_half_vol * 0.85:  # Decreasing
            score += 10
        elif second_half_vol < first_half_vol * 1.15:  # Flat
            score += 5
        # Increasing: 0 points

    # Score resistance volume trend
    if len(resistance_tests) >= 2:
        half = len(resistance_tests) // 2
        first_half_vol = mean([float(vol.volume_ratio) for vol in resistance_tests[:half]])
        second_half_vol = mean([float(vol.volume_ratio) for vol in resistance_tests[half:]])

        if second_half_vol < first_half_vol * 0.85:  # Decreasing
            score += 10
        elif second_half_vol < first_half_vol * 1.15:  # Flat
            score += 5
        # Increasing: 0 points

    return score


def _get_rejection_reason(
    duration_score: int, touch_score: int, tightness_score: int, volume_score: int
) -> str:
    """
    Generate recommendation for rejected range based on component scores.

    Identifies which component(s) caused failure to meet 70-point threshold.

    Args:
        duration_score: Duration component score (0-30)
        touch_score: Touch count component score (0-30)
        tightness_score: Tightness component score (0-20)
        volume_score: Volume confirmation component score (0-20)

    Returns:
        str: Comma-separated list of failure reasons

    Failure Reasons:
        - insufficient_duration: Duration score < 15 (<25 bars)
        - weak_levels: Touch count score < 20 (<6 touches)
        - loose_clusters: Tightness score < 10 (>2% std dev)
        - no_volume_confirmation: Volume score < 10 (no clear absorption)
    """
    reasons = []
    if duration_score < 15:
        reasons.append("insufficient_duration")
    if touch_score < 20:
        reasons.append("weak_levels")
    if tightness_score < 10:
        reasons.append("loose_clusters")
    if volume_score < 10:
        reasons.append("no_volume_confirmation")

    return ", ".join(reasons) if reasons else "below_threshold"


def is_quality_range(trading_range: TradingRange) -> bool:
    """
    Check if range meets minimum quality threshold (70+ per FR1).

    Args:
        trading_range: TradingRange with quality_score set

    Returns:
        bool: True if quality_score >= 70, False otherwise

    Example:
        >>> if is_quality_range(trading_range):
        ...     print("Quality range, proceed to pattern detection")
        ... else:
        ...     print("Low-quality range, skip")
    """
    return trading_range.quality_score is not None and trading_range.quality_score >= 70


def filter_quality_ranges(ranges: list[TradingRange], min_score: int = 70) -> list[TradingRange]:
    """
    Filter ranges by quality score.

    Args:
        ranges: List of TradingRange objects with quality_score set
        min_score: Minimum quality score (default: 70 per FR1)

    Returns:
        List[TradingRange]: Filtered list containing only ranges with score >= min_score

    Example:
        >>> all_ranges = [range1, range2, range3]  # Scores: 85, 65, 75
        >>> quality_ranges = filter_quality_ranges(all_ranges, min_score=70)
        >>> len(quality_ranges)  # 2 (scores 85 and 75)
        2
    """
    return [r for r in ranges if r.quality_score is not None and r.quality_score >= min_score]


def get_quality_ranges(ranges: list[TradingRange]) -> list[TradingRange]:
    """
    Get quality ranges (score >= 70) sorted by quality score descending.

    Helper function for Stories 3.4-3.6 integration. Returns best ranges first
    for Creek/Ice/Jump level calculation.

    Args:
        ranges: List of TradingRange objects with quality_score set

    Returns:
        List[TradingRange]: Quality ranges sorted by score (highest first)

    Example:
        >>> # Stories 3.4-3.6: Only calculate levels for quality ranges
        >>> quality_ranges = get_quality_ranges(all_ranges)
        >>> for range in quality_ranges:
        ...     range.creek = calculate_creek_level(range, bars, volume_analysis)
        ...     range.ice = calculate_ice_level(range, bars, volume_analysis)
        ...     range.jump = calculate_jump_level(range)
    """
    quality = filter_quality_ranges(ranges, min_score=70)
    return sorted(quality, key=lambda r: r.quality_score or 0, reverse=True)
