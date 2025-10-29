"""
Level Calculator module for Wyckoff Creek and Ice level calculation.

This module calculates volume-weighted support (Creek) and resistance (Ice) levels
for Wyckoff accumulation and distribution zones. The Creek is the foundation of
accumulation where smart money absorbs supply with decreasing volume. The Ice is
the ceiling of accumulation, broken on Sign of Strength (SOS) with high volume.

Wyckoff Context:
    - Creek (support): Tested multiple times in Phase B, volume decreases each test
    - Ice (resistance): Upper boundary of range, breaks out in Phase D (SOS)
    - Spring pattern: Breaks below Creek absolute_low, then recovers
    - SOS pattern: Breaks above Ice price on high volume (>1.5x)
    - UTAD pattern: Breaks above Ice absolute_high, then fails (false breakout)
    - LPS (Last Point of Support): Final test of Creek before markup

Algorithm (Creek):
    1. Collect pivot lows within support cluster (1.5% tolerance)
    2. Volume-weighted average: creek = Σ(pivot_price × volume) / Σ(volume)
    3. Strength scoring (0-100):
       - Touch count: 40 pts (more touches = stronger)
       - Volume trend: 30 pts (decreasing = accumulation)
       - Rejection wicks: 20 pts (close near high = demand)
       - Hold duration: 10 pts (longer = stronger cause)
    4. Minimum strength: 60 required (FR9)

Algorithm (Ice):
    1. Collect pivot highs within resistance cluster (1.5% tolerance)
    2. Volume-weighted average: ice = Σ(pivot_price × volume) / Σ(volume)
    3. Strength scoring (0-100):
       - Touch count: 40 pts (same as Creek)
       - Volume trend: 30 pts (decreasing = absorption at resistance)
       - Rejection wicks: 20 pts (INVERTED: close near low = supply)
       - Hold duration: 10 pts (same as Creek)
    4. Minimum strength: 60 required (AC 5)

Example:
    >>> from src.pattern_engine.level_calculator import calculate_creek_level, calculate_ice_level
    >>> from src.pattern_engine.volume_analyzer import VolumeAnalyzer
    >>>
    >>> # Analyze volume
    >>> volume_analyzer = VolumeAnalyzer()
    >>> volume_analysis = volume_analyzer.analyze(bars)
    >>>
    >>> # Calculate creek and ice (only for quality ranges)
    >>> if trading_range.quality_score >= 70:
    ...     creek = calculate_creek_level(trading_range, bars, volume_analysis)
    ...     ice = calculate_ice_level(trading_range, bars, volume_analysis)
    ...     print(f"Creek: ${creek.price:.2f}, Ice: ${ice.price:.2f}")
    ...     print(f"Range Width: {((ice.price - creek.price) / creek.price * 100):.1f}%")
    ...     print(f"SOS Entry: ${ice.price:.2f}, Stop: ${creek.price * 0.98:.2f}")
"""

from __future__ import annotations

from decimal import Decimal
from typing import List, Tuple
from statistics import mean

import structlog

from src.models.ohlcv import OHLCVBar
from src.models.trading_range import TradingRange
from src.models.volume_analysis import VolumeAnalysis
from src.models.creek_level import CreekLevel
from src.models.ice_level import IceLevel
from src.models.touch_detail import TouchDetail

logger = structlog.get_logger(__name__)

# Constants
PIVOT_TOLERANCE_PCT = Decimal("0.015")  # 1.5% tolerance from cluster average (AC 2)
MIN_CREEK_STRENGTH = 60  # Minimum strength score for FR9 requirement (Creek AC 6)
MIN_ICE_STRENGTH = 60  # Minimum strength score for Ice (Story 3.5 AC 5)
VALIDATION_TOLERANCE_PCT = Decimal("0.005")  # 0.5% max deviation (AC 10)


def calculate_creek_level(
    trading_range: TradingRange,
    bars: List[OHLCVBar],
    volume_analysis: List[VolumeAnalysis]
) -> CreekLevel:
    """
    Calculate Creek level (volume-weighted support) for a trading range.

    The Creek represents the foundation of Wyckoff accumulation where smart money
    accumulates shares. High-volume tests are weighted more heavily than low-volume
    tests, reflecting their greater significance.

    Args:
        trading_range: TradingRange with quality_score >= 70 (quality ranges only)
        bars: List of OHLCV bars in chronological order
        volume_analysis: List of VolumeAnalysis matching bars (same length)

    Returns:
        CreekLevel: Volume-weighted support level with strength metrics

    Raises:
        ValueError: If quality_score < 70, support_cluster invalid, or strength < 60

    Algorithm:
        1. Validate inputs (quality >= 70, support cluster exists)
        2. Collect pivots within 1.5% tolerance of cluster average
        3. Calculate volume-weighted average price
        4. Score strength (touch count, volume trend, rejection wicks, duration)
        5. Validate strength >= 60 (FR9) and deviation <= 0.5% (AC 10)
        6. Return CreekLevel with all metadata

    Example:
        >>> creek = calculate_creek_level(trading_range, bars, volume_analysis)
        >>> print(f"Creek: ${creek.price:.2f}")
        >>> print(f"Strength: {creek.strength_score} ({creek.strength_rating})")
        >>> print(f"Volume Trend: {creek.volume_trend}")
        >>> print(f"Entry: ${creek.price:.2f}, Stop: ${creek.absolute_low * 0.98:.2f}")
    """
    # Validate inputs
    _validate_inputs(trading_range, bars, volume_analysis)

    symbol = bars[trading_range.start_index].symbol if trading_range.start_index < len(bars) else "UNKNOWN"
    support_cluster = trading_range.support_cluster
    cluster_avg = support_cluster.average_price

    logger.info(
        "creek_calculation_start",
        symbol=symbol,
        range_id=str(trading_range.id),
        cluster_avg=str(cluster_avg),
        cluster_touches=support_cluster.touch_count
    )

    # Task 4: Collect pivot lows within tolerance
    creek_touches = _collect_creek_touches(
        support_cluster=support_cluster,
        bars=bars,
        volume_analysis=volume_analysis,
        cluster_avg=cluster_avg
    )

    logger.info(
        "creek_touches_collected",
        symbol=symbol,
        total_pivots=support_cluster.touch_count,
        creek_touches=len(creek_touches)
    )

    # Task 5: Calculate volume-weighted average
    creek_price = _calculate_weighted_price(creek_touches)

    # Task 6: Identify absolute low (spring reference)
    absolute_low = min(touch.price for touch in creek_touches)

    # Task 7: Calculate touch count and timestamps
    touch_count = len(creek_touches)
    first_test_timestamp = min(touch.timestamp for touch in creek_touches)
    last_test_timestamp = max(touch.timestamp for touch in creek_touches)
    first_test_index = min(touch.index for touch in creek_touches)
    last_test_index = max(touch.index for touch in creek_touches)
    hold_duration = last_test_index - first_test_index

    # Task 8: Assess confidence level
    confidence = _assess_confidence(touch_count)

    # Tasks 9-13: Calculate strength score
    touch_score = _score_touch_count(creek_touches)
    volume_score, volume_trend = _score_volume_trend(creek_touches)
    wick_score = _score_rejection_wicks(creek_touches)
    duration_score = _score_hold_duration(hold_duration)

    strength_score = min(touch_score + volume_score + wick_score + duration_score, 100)
    strength_rating = _determine_strength_rating(strength_score)

    logger.info(
        "creek_strength_calculated",
        symbol=symbol,
        touch_score=touch_score,
        volume_score=volume_score,
        volume_trend=volume_trend,
        wick_score=wick_score,
        duration_score=duration_score,
        total_strength=strength_score,
        strength_rating=strength_rating
    )

    # Task 14: Validate creek level within tolerance
    _validate_creek_deviation(creek_price, cluster_avg, symbol)

    # Task 13: Validate minimum strength (FR9)
    if strength_score < MIN_CREEK_STRENGTH:
        logger.error(
            "creek_strength_too_low",
            symbol=symbol,
            strength_score=strength_score,
            minimum_required=MIN_CREEK_STRENGTH,
            message=f"Creek level strength {strength_score} below minimum {MIN_CREEK_STRENGTH} (FR9)"
        )
        raise ValueError(f"Creek level strength {strength_score} below minimum {MIN_CREEK_STRENGTH} (FR9)")

    # Task 15: Create CreekLevel object and return
    creek_level = CreekLevel(
        price=creek_price,
        absolute_low=absolute_low,
        touch_count=touch_count,
        touch_details=creek_touches,
        strength_score=strength_score,
        strength_rating=strength_rating,
        last_test_timestamp=last_test_timestamp,
        first_test_timestamp=first_test_timestamp,
        hold_duration=hold_duration,
        confidence=confidence,
        volume_trend=volume_trend
    )

    logger.info(
        "creek_calculation_complete",
        symbol=symbol,
        creek_price=str(creek_price),
        absolute_low=str(absolute_low),
        touch_count=touch_count,
        strength_score=strength_score,
        strength_rating=strength_rating,
        volume_trend=volume_trend,
        confidence=confidence,
        hold_duration=hold_duration
    )

    return creek_level


def _validate_inputs(
    trading_range: TradingRange,
    bars: List[OHLCVBar],
    volume_analysis: List[VolumeAnalysis]
) -> None:
    """
    Validate inputs for creek calculation.

    Raises:
        ValueError: If validation fails
    """
    # Validate trading_range exists
    if trading_range is None:
        raise ValueError("trading_range cannot be None")

    # Validate quality score >= 70 (Story 3.3 requirement)
    if trading_range.quality_score is None or trading_range.quality_score < 70:
        logger.error(
            "low_quality_range",
            range_id=str(trading_range.id),
            quality_score=trading_range.quality_score,
            message="Creek calculation requires quality score >= 70"
        )
        raise ValueError(f"Cannot calculate creek for range with quality score {trading_range.quality_score} (minimum 70)")

    # Validate support cluster exists
    if not trading_range.support_cluster or trading_range.support_cluster.touch_count < 2:
        logger.error(
            "invalid_support_cluster",
            range_id=str(trading_range.id),
            message="Support cluster missing or insufficient touches"
        )
        raise ValueError("Invalid support cluster for creek calculation (minimum 2 touches required)")

    # Validate bars not empty
    if not bars:
        raise ValueError("Bars list cannot be empty")

    # Validate volume_analysis matches bars
    if len(volume_analysis) != len(bars):
        logger.error(
            "bars_volume_mismatch",
            bars_count=len(bars),
            volume_count=len(volume_analysis)
        )
        raise ValueError(f"Bars and volume_analysis length mismatch ({len(bars)} vs {len(volume_analysis)})")


def _collect_creek_touches(
    support_cluster,
    bars: List[OHLCVBar],
    volume_analysis: List[VolumeAnalysis],
    cluster_avg: Decimal
) -> List[TouchDetail]:
    """
    Collect pivot lows within tolerance of cluster average.

    Args:
        support_cluster: PriceCluster with pivot lows
        bars: OHLCV bars
        volume_analysis: Volume analysis matching bars
        cluster_avg: Cluster average price

    Returns:
        List[TouchDetail]: Creek touches within tolerance
    """
    tolerance_band = cluster_avg * PIVOT_TOLERANCE_PCT
    creek_touches = []

    for pivot in support_cluster.pivots:
        # Check if pivot within tolerance (1.5%)
        if abs(pivot.price - cluster_avg) <= tolerance_band:
            # Get bar and volume analysis for this pivot
            bar = bars[pivot.index]
            vol_analysis = volume_analysis[pivot.index]

            # Calculate rejection wick: (close - low) / spread
            spread = bar.high - bar.low
            if spread > 0:
                rejection_wick = (bar.close - bar.low) / spread
            else:
                rejection_wick = Decimal("0")  # Doji bar

            # Create TouchDetail
            touch = TouchDetail(
                index=pivot.index,
                price=pivot.price,
                volume=bar.volume,
                volume_ratio=vol_analysis.volume_ratio,
                close_position=vol_analysis.close_position,
                rejection_wick=rejection_wick,
                timestamp=bar.timestamp
            )
            creek_touches.append(touch)

    return creek_touches


def _calculate_weighted_price(creek_touches: List[TouchDetail]) -> Decimal:
    """
    Calculate volume-weighted average price.

    Args:
        creek_touches: List of creek touches

    Returns:
        Decimal: Volume-weighted average price (quantized to 8 decimal places)
    """
    total_volume = sum(touch.volume for touch in creek_touches)

    if total_volume == 0:
        # Defensive: fall back to simple average if all volumes are zero
        logger.warning("zero_total_volume", message="Total volume is zero, using simple average")
        avg = sum(touch.price for touch in creek_touches) / len(creek_touches)
        return avg.quantize(Decimal("0.00000001"))

    weighted_sum = sum(touch.price * touch.volume for touch in creek_touches)
    weighted_price = weighted_sum / total_volume

    # Quantize to 8 decimal places to match model max_digits=18, decimal_places=8
    return weighted_price.quantize(Decimal("0.00000001"))


def _assess_confidence(touch_count: int) -> str:
    """
    Assess confidence level based on touch count.

    Args:
        touch_count: Number of creek touches

    Returns:
        str: "HIGH", "MEDIUM", or "LOW"
    """
    if touch_count >= 5:
        return "HIGH"
    elif touch_count >= 3:
        return "MEDIUM"
    else:
        return "LOW"


def _score_touch_count(creek_touches: List[TouchDetail]) -> int:
    """
    Score touch count component (0-40 points).

    More touches indicate stronger, more tested support level.

    Args:
        creek_touches: List of creek touches

    Returns:
        int: Score 0-40
    """
    touch_count = len(creek_touches)

    if touch_count >= 5:
        return 40  # Very strong, multiple tests
    elif touch_count >= 4:
        return 30  # Strong
    elif touch_count >= 3:
        return 20  # Good
    else:  # touch_count == 2 (minimum from Story 3.2)
        return 10  # Adequate


def _score_volume_trend(creek_touches: List[TouchDetail]) -> Tuple[int, str]:
    """
    Score volume trend component (0-30 points) - decreasing = absorption.

    Decreasing volume on support tests indicates smart money absorbing supply
    (Wyckoff accumulation signature). Increasing volume indicates distribution.

    Args:
        creek_touches: List of creek touches

    Returns:
        Tuple[int, str]: (score 0-30, trend "DECREASING"/"FLAT"/"INCREASING")
    """
    # Sort by index (chronological order)
    sorted_touches = sorted(creek_touches, key=lambda t: t.index)

    # Split into first half and second half
    mid = len(sorted_touches) // 2
    if mid == 0:
        mid = 1  # Handle 2-touch minimum case

    first_half = sorted_touches[:mid]
    second_half = sorted_touches[mid:]

    # Calculate average volume_ratio for each half
    first_half_vol = mean([float(t.volume_ratio) for t in first_half])
    second_half_vol = mean([float(t.volume_ratio) for t in second_half])

    # Analyze trend
    if second_half_vol < first_half_vol * 0.85:
        # Decreasing volume = absorption (bullish)
        return 30, "DECREASING"
    elif second_half_vol < first_half_vol * 1.15:
        # Flat volume = neutral
        return 15, "FLAT"
    else:
        # Increasing volume = distribution (bearish)
        return 0, "INCREASING"


def _score_rejection_wicks(creek_touches: List[TouchDetail]) -> int:
    """
    Score rejection wick component (0-20 points) - large wicks = strong rejection.

    Rejection wicks measure where the close is relative to the bar range.
    High rejection wicks (close near high) show buyers stepping in at support.

    Args:
        creek_touches: List of creek touches

    Returns:
        int: Score 0-20
    """
    # Calculate average rejection_wick
    avg_rejection = mean([float(touch.rejection_wick) for touch in creek_touches])

    if avg_rejection >= 0.7:
        return 20  # Strong rejection, close in upper 30%
    elif avg_rejection >= 0.5:
        return 15  # Good rejection, close in upper half
    elif avg_rejection >= 0.3:
        return 10  # Moderate rejection
    else:
        return 5  # Weak rejection, close near low


def _score_hold_duration(hold_duration: int) -> int:
    """
    Score hold duration component (0-10 points) - longer = stronger.

    Longer accumulation periods build larger cause, indicating stronger
    potential for markup (Wyckoff Law of Cause and Effect).

    Args:
        hold_duration: Bars between first and last test

    Returns:
        int: Score 0-10
    """
    if hold_duration >= 30:
        return 10  # Very strong, long accumulation
    elif hold_duration >= 20:
        return 8  # Strong
    elif hold_duration >= 10:
        return 5  # Good
    else:
        return 2  # Weak, short accumulation


def _determine_strength_rating(strength_score: int) -> str:
    """
    Determine strength rating from score.

    Args:
        strength_score: Total strength score 0-100

    Returns:
        str: "EXCELLENT", "STRONG", "MODERATE", or "WEAK"
    """
    if strength_score >= 85:
        return "EXCELLENT"
    elif strength_score >= 70:
        return "STRONG"
    elif strength_score >= 60:
        return "MODERATE"  # Minimum threshold per FR9
    else:
        return "WEAK"  # Reject, do not use


def _validate_creek_deviation(creek_price: Decimal, cluster_avg: Decimal, symbol: str) -> None:
    """
    Validate creek level within tolerance of cluster average.

    Volume weighting shouldn't drastically change the price. If deviation > 0.5%,
    one high-volume outlier may be skewing the average.

    Args:
        creek_price: Volume-weighted creek price
        cluster_avg: Cluster average price
        symbol: Symbol for logging
    """
    deviation_pct = abs(creek_price - cluster_avg) / cluster_avg

    if deviation_pct > VALIDATION_TOLERANCE_PCT:
        logger.warning(
            "creek_validation_warning",
            symbol=symbol,
            creek_price=str(creek_price),
            cluster_avg=str(cluster_avg),
            deviation_pct=str(deviation_pct),
            message=f"Creek level deviated {float(deviation_pct)*100:.2f}% from cluster average, exceeds 0.5% tolerance"
        )
    else:
        logger.info(
            "creek_validation_passed",
            symbol=symbol,
            deviation_pct=str(deviation_pct)
        )


# ============================================================================
# ICE LEVEL CALCULATION (Story 3.5)
# ============================================================================


def calculate_ice_level(
    trading_range: TradingRange,
    bars: List[OHLCVBar],
    volume_analysis: List[VolumeAnalysis]
) -> IceLevel:
    """
    Calculate Ice level (volume-weighted resistance) for a trading range.

    The Ice represents the ceiling of Wyckoff accumulation where smart money
    absorbs supply. High-volume tests are weighted more heavily than low-volume
    tests, reflecting their greater significance. Ice is broken on Sign of
    Strength (SOS) with high volume.

    Args:
        trading_range: TradingRange with quality_score >= 70 (quality ranges only)
        bars: List of OHLCV bars in chronological order
        volume_analysis: List of VolumeAnalysis matching bars (same length)

    Returns:
        IceLevel: Volume-weighted resistance level with strength metrics

    Raises:
        ValueError: If quality_score < 70, resistance_cluster invalid, or strength < 60

    Algorithm:
        1. Validate inputs (quality >= 70, resistance cluster exists)
        2. Collect pivot highs within 1.5% tolerance of cluster average
        3. Calculate volume-weighted average price
        4. Score strength (touch count, volume trend, rejection wicks, duration)
        5. Validate strength >= 60 (AC 5) and deviation <= 0.5%
        6. Return IceLevel with all metadata

    Note:
        - Ice > Creek validation deferred to Story 3.8 (TradingRangeDetector)
        - Range width >= 3% validation deferred to Story 3.8
        - Rejection wick is INVERTED from Creek: (high - close) / spread

    Example:
        >>> ice = calculate_ice_level(trading_range, bars, volume_analysis)
        >>> print(f"Ice: ${ice.price:.2f}, Absolute High: ${ice.absolute_high:.2f}")
        >>> print(f"Strength: {ice.strength_score} ({ice.strength_rating})")
        >>> print(f"Volume Trend: {ice.volume_trend}")
        >>> # SOS breakout detection
        >>> sos = bar.close > ice.price and bar.volume_ratio >= 1.5
    """
    # Validate inputs
    _validate_ice_inputs(trading_range, bars, volume_analysis)

    symbol = bars[trading_range.start_index].symbol if trading_range.start_index < len(bars) else "UNKNOWN"
    resistance_cluster = trading_range.resistance_cluster
    cluster_avg = resistance_cluster.average_price

    logger.info(
        "ice_calculation_start",
        symbol=symbol,
        range_id=str(trading_range.id),
        cluster_avg=str(cluster_avg),
        cluster_touches=resistance_cluster.touch_count
    )

    # Task 4: Collect pivot highs within tolerance
    ice_touches = _collect_ice_touches(
        resistance_cluster=resistance_cluster,
        bars=bars,
        volume_analysis=volume_analysis,
        cluster_avg=cluster_avg
    )

    logger.info(
        "ice_touches_collected",
        symbol=symbol,
        total_pivots=resistance_cluster.touch_count,
        ice_touches=len(ice_touches)
    )

    # Task 5: Calculate volume-weighted average
    ice_price = _calculate_weighted_price(ice_touches)

    # Task 6: Identify absolute high (UTAD reference)
    absolute_high = max(touch.price for touch in ice_touches)

    # Task 7: Calculate touch count and timestamps
    touch_count = len(ice_touches)
    first_test_timestamp = min(touch.timestamp for touch in ice_touches)
    last_test_timestamp = max(touch.timestamp for touch in ice_touches)
    first_test_index = min(touch.index for touch in ice_touches)
    last_test_index = max(touch.index for touch in ice_touches)
    hold_duration = last_test_index - first_test_index

    # Task 8: Assess confidence level
    confidence = _assess_confidence(touch_count)

    # Tasks 9-13: Calculate strength score
    touch_score = _score_touch_count(ice_touches)
    volume_score, volume_trend = _score_volume_trend(ice_touches)
    wick_score = _score_rejection_wicks_ice(ice_touches)  # INVERTED from Creek
    duration_score = _score_hold_duration(hold_duration)

    strength_score = min(touch_score + volume_score + wick_score + duration_score, 100)
    strength_rating = _determine_strength_rating(strength_score)

    logger.info(
        "ice_strength_calculated",
        symbol=symbol,
        touch_score=touch_score,
        volume_score=volume_score,
        volume_trend=volume_trend,
        wick_score=wick_score,
        duration_score=duration_score,
        total_strength=strength_score,
        strength_rating=strength_rating
    )

    # Task 16: Validate ice level within tolerance
    _validate_ice_deviation(ice_price, cluster_avg, symbol)

    # Task 13: Validate minimum strength (AC 5)
    if strength_score < MIN_ICE_STRENGTH:
        logger.error(
            "ice_strength_too_low",
            symbol=symbol,
            strength_score=strength_score,
            minimum_required=MIN_ICE_STRENGTH,
            message=f"Ice level strength {strength_score} below minimum {MIN_ICE_STRENGTH} (AC 5)"
        )
        raise ValueError(f"Ice level strength {strength_score} below minimum {MIN_ICE_STRENGTH} (AC 5)")

    # Task 17: Create IceLevel object and return
    ice_level = IceLevel(
        price=ice_price,
        absolute_high=absolute_high,
        touch_count=touch_count,
        touch_details=ice_touches,
        strength_score=strength_score,
        strength_rating=strength_rating,
        last_test_timestamp=last_test_timestamp,
        first_test_timestamp=first_test_timestamp,
        hold_duration=hold_duration,
        confidence=confidence,
        volume_trend=volume_trend
    )

    logger.info(
        "ice_calculation_complete",
        symbol=symbol,
        ice_price=str(ice_price),
        absolute_high=str(absolute_high),
        touch_count=touch_count,
        strength_score=strength_score,
        strength_rating=strength_rating,
        volume_trend=volume_trend,
        confidence=confidence,
        hold_duration=hold_duration
    )

    return ice_level


def _validate_ice_inputs(
    trading_range: TradingRange,
    bars: List[OHLCVBar],
    volume_analysis: List[VolumeAnalysis]
) -> None:
    """
    Validate inputs for ice calculation.

    Raises:
        ValueError: If validation fails
    """
    # Validate trading_range exists
    if trading_range is None:
        raise ValueError("trading_range cannot be None")

    # Validate quality score >= 70 (Story 3.3 requirement)
    if trading_range.quality_score is None or trading_range.quality_score < 70:
        logger.error(
            "low_quality_range",
            range_id=str(trading_range.id),
            quality_score=trading_range.quality_score,
            message="Ice calculation requires quality score >= 70"
        )
        raise ValueError(f"Cannot calculate ice for range with quality score {trading_range.quality_score} (minimum 70)")

    # Validate resistance cluster exists
    if not trading_range.resistance_cluster or trading_range.resistance_cluster.touch_count < 2:
        logger.error(
            "invalid_resistance_cluster",
            range_id=str(trading_range.id),
            message="Resistance cluster missing or insufficient touches"
        )
        raise ValueError("Invalid resistance cluster for ice calculation (minimum 2 touches required)")

    # Validate bars not empty
    if not bars:
        raise ValueError("Bars list cannot be empty")

    # Validate volume_analysis matches bars
    if len(volume_analysis) != len(bars):
        logger.error(
            "bars_volume_mismatch",
            bars_count=len(bars),
            volume_count=len(volume_analysis)
        )
        raise ValueError(f"Bars and volume_analysis length mismatch ({len(bars)} vs {len(volume_analysis)})")


def _collect_ice_touches(
    resistance_cluster,
    bars: List[OHLCVBar],
    volume_analysis: List[VolumeAnalysis],
    cluster_avg: Decimal
) -> List[TouchDetail]:
    """
    Collect pivot highs within tolerance of cluster average.

    Args:
        resistance_cluster: PriceCluster with pivot highs
        bars: OHLCV bars
        volume_analysis: Volume analysis matching bars
        cluster_avg: Cluster average price

    Returns:
        List[TouchDetail]: Ice touches within tolerance
    """
    tolerance_band = cluster_avg * PIVOT_TOLERANCE_PCT
    ice_touches = []

    for pivot in resistance_cluster.pivots:
        # Check if pivot within tolerance (1.5%)
        if abs(pivot.price - cluster_avg) <= tolerance_band:
            # Get bar and volume analysis for this pivot
            bar = bars[pivot.index]
            vol_analysis = volume_analysis[pivot.index]

            # Calculate rejection wick: (high - close) / spread (INVERTED from Creek)
            # High value = close near low = strong downward rejection from resistance
            spread = bar.high - bar.low
            if spread > 0:
                rejection_wick = (bar.high - bar.close) / spread
            else:
                rejection_wick = Decimal("0")  # Doji bar

            # Create TouchDetail
            touch = TouchDetail(
                index=pivot.index,
                price=pivot.price,  # Pivot high
                volume=bar.volume,
                volume_ratio=vol_analysis.volume_ratio,
                close_position=vol_analysis.close_position,
                rejection_wick=rejection_wick,  # UPPER wick for Ice
                timestamp=bar.timestamp
            )
            ice_touches.append(touch)

    return ice_touches


def _score_rejection_wicks_ice(ice_touches: List[TouchDetail]) -> int:
    """
    Score rejection wick component for Ice (0-20 points) - large upper wicks = strong rejection.

    CRITICAL DIFFERENCE FROM CREEK:
    Ice rejection wicks measure UPPER wicks: (high - close) / spread
    Large upper wicks show sellers stepping in at resistance (supply).

    Args:
        ice_touches: List of ice touches

    Returns:
        int: Score 0-20
    """
    # Calculate average rejection_wick
    avg_rejection = mean([float(touch.rejection_wick) for touch in ice_touches])

    if avg_rejection >= 0.7:
        return 20  # Strong rejection, close in lower 30% (sellers in control)
    elif avg_rejection >= 0.5:
        return 15  # Good rejection, close in lower half
    elif avg_rejection >= 0.3:
        return 10  # Moderate rejection
    else:
        return 5  # Weak rejection, close near high


def _validate_ice_deviation(ice_price: Decimal, cluster_avg: Decimal, symbol: str) -> None:
    """
    Validate ice level within tolerance of cluster average.

    Volume weighting shouldn't drastically change the price. If deviation > 0.5%,
    one high-volume outlier may be skewing the average.

    Args:
        ice_price: Volume-weighted ice price
        cluster_avg: Cluster average price
        symbol: Symbol for logging
    """
    deviation_pct = abs(ice_price - cluster_avg) / cluster_avg

    if deviation_pct > VALIDATION_TOLERANCE_PCT:
        logger.warning(
            "ice_validation_warning",
            symbol=symbol,
            ice_price=str(ice_price),
            cluster_avg=str(cluster_avg),
            deviation_pct=str(deviation_pct),
            message=f"Ice level deviated {float(deviation_pct)*100:.2f}% from cluster average, exceeds 0.5% tolerance"
        )
    else:
        logger.info(
            "ice_validation_passed",
            symbol=symbol,
            deviation_pct=str(deviation_pct)
        )
