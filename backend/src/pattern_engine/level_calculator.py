"""
Level Calculator module for Wyckoff Creek, Ice, and Jump level calculation.

This module calculates volume-weighted support (Creek), resistance (Ice), and
price targets (Jump) for Wyckoff accumulation and distribution zones. The Creek
is the foundation of accumulation where smart money absorbs supply with decreasing
volume. The Ice is the ceiling of accumulation, broken on Sign of Strength (SOS)
with high volume. The Jump is the upside target calculated using Wyckoff Point &
Figure cause-effect methodology.

Wyckoff Context:
    - Creek (support): Tested multiple times in Phase B, volume decreases each test
    - Ice (resistance): Upper boundary of range, breaks out in Phase D (SOS)
    - Jump (target): Upside projection after SOS, proportional to accumulation duration
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

Algorithm (Jump):
    1. Extract range duration from TradingRange (minimum 15 bars)
    2. Determine cause factor: 40+ bars = 3.0x, 25-39 bars = 2.5x, 15-24 bars = 2.0x
    3. Calculate range width: range_width = ice - creek
    4. Aggressive jump: jump = ice + (cause_factor × range_width)
    5. Conservative jump: conservative = ice + (1.0 × range_width)
    6. Risk-reward ratio: RR = (jump - ice) / (ice - creek) = cause_factor

Example:
    >>> from src.pattern_engine.level_calculator import (
    ...     calculate_creek_level, calculate_ice_level, calculate_jump_level
    ... )
    >>> from src.pattern_engine.volume_analyzer import VolumeAnalyzer
    >>>
    >>> # Analyze volume
    >>> volume_analyzer = VolumeAnalyzer()
    >>> volume_analysis = volume_analyzer.analyze(bars)
    >>>
    >>> # Calculate all three levels (only for quality ranges)
    >>> if trading_range.quality_score >= 70:
    ...     creek = calculate_creek_level(trading_range, bars, volume_analysis)
    ...     ice = calculate_ice_level(trading_range, bars, volume_analysis)
    ...     jump = calculate_jump_level(trading_range, creek, ice)
    ...     print(f"Creek: ${creek.price:.2f}, Ice: ${ice.price:.2f}")
    ...     print(f"Jump (Aggressive): ${jump.price:.2f} ({jump.cause_factor}x)")
    ...     print(f"Jump (Conservative): ${jump.conservative_price:.2f} (1.0x)")
    ...     print(f"Risk-Reward: {jump.risk_reward_ratio}:1")
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from statistics import mean

import structlog

from src.models.creek_level import CreekLevel
from src.models.ice_level import IceLevel
from src.models.jump_level import JumpLevel
from src.models.ohlcv import OHLCVBar
from src.models.touch_detail import TouchDetail
from src.models.trading_range import TradingRange
from src.models.volume_analysis import VolumeAnalysis
from src.shared.validation_helpers import validate_level_calculator_inputs

logger = structlog.get_logger(__name__)

# Constants - Creek and Ice
PIVOT_TOLERANCE_PCT = Decimal("0.015")  # 1.5% tolerance from cluster average (AC 2)
MIN_CREEK_STRENGTH = 60  # Minimum strength score for FR9 requirement (Creek AC 6)
MIN_ICE_STRENGTH = 60  # Minimum strength score for Ice (Story 3.5 AC 5)
VALIDATION_TOLERANCE_PCT = Decimal("0.005")  # 0.5% max deviation (AC 10)

# Constants - Jump (Story 3.6)
CAUSE_FACTOR_LONG = Decimal("3.0")  # 40+ bars, strong cause
CAUSE_FACTOR_MEDIUM = Decimal("2.5")  # 25-39 bars, good cause
CAUSE_FACTOR_SHORT = Decimal("2.0")  # 15-24 bars, adequate cause
CONSERVATIVE_FACTOR = Decimal("1.0")  # Conservative projection (measured move)
MIN_RANGE_DURATION = 15  # Minimum bars for Jump calculation (AC 2)


def calculate_creek_level(
    trading_range: TradingRange, bars: list[OHLCVBar], volume_analysis: list[VolumeAnalysis]
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
    # Validate inputs (Story 18.1: uses shared validation helper)
    validate_level_calculator_inputs(
        trading_range,
        bars,
        volume_analysis,
        level_type="Creek",
        cluster_attr="support_cluster",
    )

    symbol = (
        bars[trading_range.start_index].symbol
        if trading_range.start_index < len(bars)
        else "UNKNOWN"
    )
    support_cluster = trading_range.support_cluster
    cluster_avg = support_cluster.average_price

    logger.info(
        "creek_calculation_start",
        symbol=symbol,
        range_id=str(trading_range.id),
        cluster_avg=str(cluster_avg),
        cluster_touches=support_cluster.touch_count,
    )

    # Task 4: Collect pivot lows within tolerance
    creek_touches = _collect_creek_touches(
        support_cluster=support_cluster,
        bars=bars,
        volume_analysis=volume_analysis,
        cluster_avg=cluster_avg,
    )

    logger.info(
        "creek_touches_collected",
        symbol=symbol,
        total_pivots=support_cluster.touch_count,
        creek_touches=len(creek_touches),
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
        strength_rating=strength_rating,
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
            message=f"Creek level strength {strength_score} below minimum {MIN_CREEK_STRENGTH} (FR9)",
        )
        raise ValueError(
            f"Creek level strength {strength_score} below minimum {MIN_CREEK_STRENGTH} (FR9)"
        )

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
        volume_trend=volume_trend,
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
        hold_duration=hold_duration,
    )

    return creek_level


def _collect_creek_touches(
    support_cluster,
    bars: list[OHLCVBar],
    volume_analysis: list[VolumeAnalysis],
    cluster_avg: Decimal,
) -> list[TouchDetail]:
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
                timestamp=bar.timestamp,
            )
            creek_touches.append(touch)

    return creek_touches


def _calculate_weighted_price(creek_touches: list[TouchDetail]) -> Decimal:
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


def _score_touch_count(creek_touches: list[TouchDetail]) -> int:
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


def _score_volume_trend(creek_touches: list[TouchDetail]) -> tuple[int, str]:
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


def _score_rejection_wicks(creek_touches: list[TouchDetail]) -> int:
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
            message=f"Creek level deviated {float(deviation_pct)*100:.2f}% from cluster average, exceeds 0.5% tolerance",
        )
    else:
        logger.info("creek_validation_passed", symbol=symbol, deviation_pct=str(deviation_pct))


# ============================================================================
# ICE LEVEL CALCULATION (Story 3.5)
# ============================================================================


def calculate_ice_level(
    trading_range: TradingRange, bars: list[OHLCVBar], volume_analysis: list[VolumeAnalysis]
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
    # Validate inputs (Story 18.1: uses shared validation helper)
    validate_level_calculator_inputs(
        trading_range,
        bars,
        volume_analysis,
        level_type="Ice",
        cluster_attr="resistance_cluster",
    )

    symbol = (
        bars[trading_range.start_index].symbol
        if trading_range.start_index < len(bars)
        else "UNKNOWN"
    )
    resistance_cluster = trading_range.resistance_cluster
    cluster_avg = resistance_cluster.average_price

    logger.info(
        "ice_calculation_start",
        symbol=symbol,
        range_id=str(trading_range.id),
        cluster_avg=str(cluster_avg),
        cluster_touches=resistance_cluster.touch_count,
    )

    # Task 4: Collect pivot highs within tolerance
    ice_touches = _collect_ice_touches(
        resistance_cluster=resistance_cluster,
        bars=bars,
        volume_analysis=volume_analysis,
        cluster_avg=cluster_avg,
    )

    logger.info(
        "ice_touches_collected",
        symbol=symbol,
        total_pivots=resistance_cluster.touch_count,
        ice_touches=len(ice_touches),
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
        strength_rating=strength_rating,
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
            message=f"Ice level strength {strength_score} below minimum {MIN_ICE_STRENGTH} (AC 5)",
        )
        raise ValueError(
            f"Ice level strength {strength_score} below minimum {MIN_ICE_STRENGTH} (AC 5)"
        )

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
        volume_trend=volume_trend,
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
        hold_duration=hold_duration,
    )

    return ice_level


def _collect_ice_touches(
    resistance_cluster,
    bars: list[OHLCVBar],
    volume_analysis: list[VolumeAnalysis],
    cluster_avg: Decimal,
) -> list[TouchDetail]:
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
                timestamp=bar.timestamp,
            )
            ice_touches.append(touch)

    return ice_touches


def _score_rejection_wicks_ice(ice_touches: list[TouchDetail]) -> int:
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
            message=f"Ice level deviated {float(deviation_pct)*100:.2f}% from cluster average, exceeds 0.5% tolerance",
        )
    else:
        logger.info("ice_validation_passed", symbol=symbol, deviation_pct=str(deviation_pct))


# ============================================================================
# JUMP LEVEL CALCULATION (Story 3.6)
# ============================================================================


def calculate_jump_level(
    trading_range: TradingRange, creek: CreekLevel, ice: IceLevel
) -> JumpLevel:
    """
    Calculate Jump level (price target) using Wyckoff Point & Figure cause-effect method.

    The Jump represents the upside profit objective after successful SOS breakout,
    calculated using Wyckoff's cause-effect principle: longer accumulation (cause)
    produces larger price move (effect). The cause factor amplifies based on
    accumulation duration: 40+ bars = 3.0x, 25-39 bars = 2.5x, 15-24 bars = 2.0x.

    Args:
        trading_range: TradingRange with duration >= 15 bars
        creek: CreekLevel (support reference)
        ice: IceLevel (resistance reference)

    Returns:
        JumpLevel: Price target with aggressive and conservative projections

    Raises:
        ValueError: If range_duration < 15 bars (insufficient cause)
        ValueError: If ice.price <= creek.price (invalid range)

    Algorithm:
        1. Validate inputs (duration >= 15, ice > creek)
        2. Calculate range width: range_width = ice - creek
        3. Determine cause factor based on duration:
           - 40+ bars: 3.0x (HIGH confidence)
           - 25-39 bars: 2.5x (MEDIUM confidence)
           - 15-24 bars: 2.0x (LOW confidence)
        4. Calculate aggressive jump: jump = ice + (cause_factor × range_width)
        5. Calculate conservative jump: conservative = ice + (1.0 × range_width)
        6. Calculate risk-reward ratios
        7. Validate jump > ice (defensive check)

    Wyckoff Context:
        The effect (price move) is proportional to the cause (accumulation duration).
        A large cause (extended accumulation) produces a large effect (significant
        price advance). A small cause produces a small effect. The Jump is the
        measured objective derived from the cause built during accumulation.

    Example:
        >>> # 40-bar range: Creek $100, Ice $110, Width $10
        >>> jump = calculate_jump_level(trading_range, creek, ice)
        >>> print(f"Aggressive: ${jump.price:.2f} ({jump.cause_factor}x)")
        >>> # Output: Aggressive: $140.00 (3.0x)
        >>> print(f"Conservative: ${jump.conservative_price:.2f}")
        >>> # Output: Conservative: $120.00
        >>> print(f"Risk-Reward: {jump.risk_reward_ratio}:1")
        >>> # Output: Risk-Reward: 3.0:1
    """
    # Validate inputs
    if trading_range is None:
        raise ValueError("trading_range cannot be None")
    if creek is None:
        raise ValueError("creek cannot be None")
    if ice is None:
        raise ValueError("ice cannot be None")

    # Get range duration
    range_duration = trading_range.duration

    # Validate minimum duration (AC 2)
    if range_duration < MIN_RANGE_DURATION:
        logger.error(
            "insufficient_cause",
            range_id=str(trading_range.id),
            duration=range_duration,
            minimum=MIN_RANGE_DURATION,
            message=f"Range duration {range_duration} < {MIN_RANGE_DURATION} bars minimum",
        )
        raise ValueError(
            f"Insufficient cause: {range_duration} bars < {MIN_RANGE_DURATION} minimum"
        )

    # Defensive validation: ice > creek (should be validated by Story 3.8)
    if ice.price <= creek.price:
        logger.error(
            "invalid_range",
            ice_price=str(ice.price),
            creek_price=str(creek.price),
            message="Ice must be above Creek",
        )
        raise ValueError(f"Invalid range: Ice {ice.price} <= Creek {creek.price}")

    symbol = trading_range.symbol if hasattr(trading_range, "symbol") else "UNKNOWN"

    logger.info(
        "jump_calculation_start",
        symbol=symbol,
        range_id=str(trading_range.id),
        range_duration=range_duration,
        creek_price=str(creek.price),
        ice_price=str(ice.price),
    )

    # Calculate range width (AC 4)
    range_width = ice.price - creek.price

    # Defensive validation: range_width > 0
    if range_width <= 0:
        logger.error(
            "invalid_range_width",
            range_width=str(range_width),
            message="Range width must be positive",
        )
        raise ValueError(f"Invalid range width: {range_width}")

    # Determine cause factor based on duration (AC 2)
    if range_duration >= 40:
        cause_factor = CAUSE_FACTOR_LONG  # 3.0x
        confidence = "HIGH"
    elif range_duration >= 25:
        cause_factor = CAUSE_FACTOR_MEDIUM  # 2.5x
        confidence = "MEDIUM"
    elif range_duration >= 15:
        cause_factor = CAUSE_FACTOR_SHORT  # 2.0x
        confidence = "LOW"
    else:
        # Should never reach here due to earlier validation
        raise ValueError(f"Insufficient range duration: {range_duration} bars")

    logger.info(
        "cause_factor_determined",
        symbol=symbol,
        duration=range_duration,
        cause_factor=str(cause_factor),
        confidence=confidence,
    )

    # Calculate aggressive jump target (AC 3)
    effect = cause_factor * range_width
    jump_price = ice.price + effect

    # Calculate conservative jump target (AC 6)
    conservative_effect = CONSERVATIVE_FACTOR * range_width
    conservative_price = ice.price + conservative_effect

    # Calculate risk-reward ratios (AC all)
    aggressive_reward = jump_price - ice.price
    risk = ice.price - creek.price  # Same as range_width
    risk_reward_ratio = aggressive_reward / risk  # Simplifies to cause_factor

    conservative_reward = conservative_price - ice.price
    conservative_risk_reward = conservative_reward / risk  # Always 1.0

    logger.info(
        "jump_targets_calculated",
        symbol=symbol,
        range_width=str(range_width),
        aggressive_jump=str(jump_price),
        conservative_jump=str(conservative_price),
        aggressive_rr=str(risk_reward_ratio),
        conservative_rr=str(conservative_risk_reward),
    )

    # Validate jump > ice (AC 10) - defensive check
    if jump_price <= ice.price:
        logger.error(
            "invalid_jump_calculation",
            jump_price=str(jump_price),
            ice_price=str(ice.price),
            message="Jump must be above Ice",
        )
        raise ValueError(f"Invalid jump calculation: {jump_price} <= {ice.price}")

    if conservative_price <= ice.price:
        logger.error(
            "invalid_conservative_jump",
            conservative_price=str(conservative_price),
            ice_price=str(ice.price),
            message="Conservative jump must be above Ice",
        )
        raise ValueError(f"Invalid conservative jump: {conservative_price} <= {ice.price}")

    # Create JumpLevel object (AC 5)
    jump_level = JumpLevel(
        price=jump_price,
        conservative_price=conservative_price,
        range_width=range_width,
        cause_factor=cause_factor,
        range_duration=range_duration,
        confidence=confidence,
        risk_reward_ratio=risk_reward_ratio,
        conservative_risk_reward=conservative_risk_reward,
        ice_price=ice.price,
        creek_price=creek.price,
        calculated_at=datetime.now(UTC),
    )

    logger.info(
        "jump_calculation_complete",
        symbol=symbol,
        aggressive_target=str(jump_price),
        conservative_target=str(conservative_price),
        cause_factor=str(cause_factor),
        confidence=confidence,
        range_duration=range_duration,
        aggressive_rr=str(risk_reward_ratio),
        conservative_rr=str(conservative_risk_reward),
    )

    return jump_level


# Story 11.9c: LevelCalculator class
class LevelCalculator:
    """
    Class-based level calculator for Story 11.9c implementation.

    Provides an object-oriented interface for calculating Creek, Ice, and Jump levels.
    This class wraps the functional calculate_*_level() APIs to match Story 11.9
    requirements while maintaining backward compatibility.

    The Story 11.9 requirements specify plural methods (calculate_creek_levels, etc.)
    that return lists, but the existing implementation works with single ranges.
    This class bridges that gap by providing both interfaces.

    Example:
        >>> calculator = LevelCalculator()
        >>> # Single level calculation
        >>> creek_levels = calculator.calculate_creek_levels(trading_range, bars, volume_analysis)
        >>> ice_levels = calculator.calculate_ice_levels(trading_range, bars, volume_analysis)
        >>> jump_levels = calculator.calculate_jump_levels(trading_range, "bullish")
    """

    def __init__(self) -> None:
        """Initialize level calculator."""
        logger.debug("level_calculator_initialized")

    def calculate_creek_levels(
        self,
        trading_range: TradingRange,
        bars: list[OHLCVBar],
        volume_analysis: list[VolumeAnalysis],
    ) -> list[CreekLevel]:
        """
        Calculate Creek levels (minor S/R) for a trading range.

        In the current implementation, each trading range has one Creek level
        (the primary support). This method returns it as a single-element list
        to match the Story 11.9 interface specification.

        Args:
            trading_range: TradingRange to analyze
            bars: OHLCV bars for the range period
            volume_analysis: VolumeAnalysis results matching bars

        Returns:
            List containing the Creek level for this range

        Example:
            >>> creek_levels = calculator.calculate_creek_levels(range, bars, vol_analysis)
            >>> if creek_levels:
            ...     print(f"Creek support at ${creek_levels[0].price}")
        """
        creek_level = calculate_creek_level(trading_range, bars, volume_analysis)
        return [creek_level] if creek_level else []

    def calculate_ice_levels(
        self,
        trading_range: TradingRange,
        bars: list[OHLCVBar],
        volume_analysis: list[VolumeAnalysis],
    ) -> list[IceLevel]:
        """
        Calculate Ice levels (major S/R) for a trading range.

        In the current implementation, each trading range has one Ice level
        (the primary resistance). This method returns it as a single-element list
        to match the Story 11.9 interface specification.

        Args:
            trading_range: TradingRange to analyze
            bars: OHLCV bars for the range period
            volume_analysis: VolumeAnalysis results matching bars

        Returns:
            List containing the Ice level for this range

        Example:
            >>> ice_levels = calculator.calculate_ice_levels(range, bars, vol_analysis)
            >>> if ice_levels:
            ...     print(f"Ice resistance at ${ice_levels[0].price}")
        """
        ice_level = calculate_ice_level(trading_range, bars, volume_analysis)
        return [ice_level] if ice_level else []

    def calculate_jump_levels(
        self,
        trading_range: TradingRange,
        direction: str,  # "bullish" or "bearish"
        creek: CreekLevel | None = None,
        ice: IceLevel | None = None,
        bars: list[OHLCVBar] | None = None,
        volume_analysis: list[VolumeAnalysis] | None = None,
    ) -> list[JumpLevel]:
        """
        Calculate Jump levels (breakout targets) for a trading range.

        Args:
            trading_range: TradingRange to analyze
            direction: "bullish" for upside targets, "bearish" for downside targets
            creek: Optional pre-calculated Creek level (calculated if not provided)
            ice: Optional pre-calculated Ice level (calculated if not provided)
            bars: OHLCV bars (required if creek/ice not provided)
            volume_analysis: Volume analysis (required if creek/ice not provided)

        Returns:
            List containing the Jump level for this range

        Example:
            >>> # With pre-calculated levels
            >>> jump_levels = calculator.calculate_jump_levels(
            ...     range, "bullish", creek=creek, ice=ice
            ... )
            >>>
            >>> # Calculate levels automatically
            >>> jump_levels = calculator.calculate_jump_levels(
            ...     range, "bullish", bars=bars, volume_analysis=vol_analysis
            ... )
        """
        # Calculate Creek and Ice if not provided
        if creek is None:
            if bars is None or volume_analysis is None:
                logger.error(
                    "missing_parameters",
                    message="bars and volume_analysis required if creek not provided",
                )
                return []
            creek = calculate_creek_level(trading_range, bars, volume_analysis)
            if creek is None:
                return []

        if ice is None:
            if bars is None or volume_analysis is None:
                logger.error(
                    "missing_parameters",
                    message="bars and volume_analysis required if ice not provided",
                )
                return []
            ice = calculate_ice_level(trading_range, bars, volume_analysis)
            if ice is None:
                return []

        # Calculate Jump level
        # Note: Current implementation only supports bullish (upside) jumps
        # Bearish (downside) jumps would require implementing the inverse calculation
        if direction == "bullish":
            jump_level = calculate_jump_level(trading_range, creek, ice)
            return [jump_level] if jump_level else []
        else:
            logger.warning(
                "bearish_jump_not_implemented",
                message="Bearish jump calculation not yet implemented",
            )
            return []
