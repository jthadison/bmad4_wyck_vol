"""
Trading range clustering module for identifying support and resistance zones.

This module implements proximity-based clustering of pivot points to identify
trading range boundaries (support and resistance levels) for Wyckoff analysis.

The clustering algorithm groups pivot points within a configurable price tolerance
to form PriceCluster objects, which are then combined into TradingRange objects
representing accumulation or distribution zones.

Example:
    >>> from backend.src.pattern_engine.pivot_detector import detect_pivots
    >>> from backend.src.pattern_engine.range_cluster import find_potential_ranges
    >>>
    >>> # Detect pivots from OHLCV bars
    >>> pivots = detect_pivots(bars, lookback=5)
    >>>
    >>> # Find trading ranges
    >>> ranges = find_potential_ranges(pivots, bars, tolerance_pct=0.02)
    >>>
    >>> # Filter for high-quality ranges
    >>> quality_ranges = [r for r in ranges if r.quality_score and r.quality_score >= 70]
"""

from __future__ import annotations

import statistics
from decimal import ROUND_HALF_UP, Decimal

import structlog

from src.models.ohlcv import OHLCVBar
from src.models.pivot import Pivot, PivotType
from src.models.price_cluster import PriceCluster
from src.models.trading_range import TradingRange
from src.pattern_engine.pivot_detector import get_pivot_highs, get_pivot_lows

logger = structlog.get_logger(__name__)


def _quantize_decimal(value: Decimal, decimal_places: int = 8) -> Decimal:
    """
    Quantize a Decimal to a specific number of decimal places.

    Args:
        value: Decimal value to quantize
        decimal_places: Number of decimal places (default: 8)

    Returns:
        Quantized Decimal value
    """
    if decimal_places == 4:
        quantizer = Decimal("0.0001")
    elif decimal_places == 8:
        quantizer = Decimal("0.00000001")
    else:
        quantizer = Decimal(10) ** -decimal_places
    return value.quantize(quantizer, rounding=ROUND_HALF_UP)


def cluster_pivots(pivots: list[Pivot], tolerance_pct: float = 0.02) -> list[PriceCluster]:
    """
    Cluster pivot points within price tolerance to identify support/resistance zones.

    Groups pivot points that are within a specified price tolerance of each other,
    creating distinct clusters that represent potential support (pivot lows) or
    resistance (pivot highs) levels.

    Algorithm:
        1. Separate pivots by type (HIGH vs LOW)
        2. Sort each type by price (ascending)
        3. Group pivots within tolerance_pct of cluster average
        4. Calculate cluster statistics (average, std deviation, etc.)
        5. Filter out clusters with < 2 pivots
        6. Sort by quality (touch count descending, std deviation ascending)

    Args:
        pivots: List of Pivot objects (can contain mix of HIGH and LOW types)
        tolerance_pct: Price tolerance as decimal (default 0.02 = 2%)
                      Pivots within this percentage are grouped together

    Returns:
        List[PriceCluster]: List of valid clusters (2+ pivots each),
                           sorted by quality (most touches, tightest first)

    Raises:
        ValueError: If tolerance_pct <= 0

    Example:
        >>> pivots = detect_pivots(bars, lookback=5)
        >>> clusters = cluster_pivots(pivots, tolerance_pct=0.02)
        >>> support_clusters = [c for c in clusters if c.cluster_type == PivotType.LOW]
        >>> resistance_clusters = [c for c in clusters if c.cluster_type == PivotType.HIGH]
    """
    # Validate inputs
    if not pivots:
        logger.warning("empty_pivots_list", message="Cannot cluster empty pivot list")
        return []

    if tolerance_pct <= 0:
        raise ValueError(f"tolerance_pct must be > 0, got {tolerance_pct}")

    if tolerance_pct > 0.5:
        logger.warning(
            "large_tolerance",
            tolerance_pct=tolerance_pct,
            message="Tolerance > 50% may cluster unrelated pivots",
        )

    # Extract symbol for logging (if available)
    symbol = pivots[0].bar.symbol if pivots and hasattr(pivots[0].bar, "symbol") else "UNKNOWN"

    logger.info(
        "pivot_clustering_start",
        symbol=symbol,
        pivot_count=len(pivots),
        tolerance_pct=tolerance_pct,
    )

    # Separate pivots by type
    pivot_highs = get_pivot_highs(pivots)
    pivot_lows = get_pivot_lows(pivots)

    # Cluster each type separately
    high_clusters = _cluster_by_proximity(pivot_highs, tolerance_pct)
    low_clusters = _cluster_by_proximity(pivot_lows, tolerance_pct)

    # Combine results
    all_clusters = high_clusters + low_clusters

    logger.info(
        "pivot_clustering_complete",
        symbol=symbol,
        cluster_count=len(all_clusters),
        high_clusters=len(high_clusters),
        low_clusters=len(low_clusters),
    )

    return all_clusters


def _cluster_by_proximity(pivots: list[Pivot], tolerance_pct: float) -> list[PriceCluster]:
    """
    Internal helper: cluster pivots of same type by price proximity.

    Args:
        pivots: List of Pivot objects (all same type: HIGH or LOW)
        tolerance_pct: Price tolerance as decimal (e.g., 0.02 = 2%)

    Returns:
        List[PriceCluster]: Clusters with 2+ pivots, sorted by quality
    """
    if not pivots:
        return []

    # Sort by price (ascending)
    sorted_pivots = sorted(pivots, key=lambda p: p.price)

    clusters = []
    current_cluster = [sorted_pivots[0]]
    cluster_avg = float(sorted_pivots[0].price)

    # Iterate through remaining pivots
    for pivot in sorted_pivots[1:]:
        price_diff_pct = abs(float(pivot.price) - cluster_avg) / cluster_avg

        if price_diff_pct <= tolerance_pct:
            # Add to current cluster
            current_cluster.append(pivot)
            # Recalculate cluster average (incremental mean)
            prices = [float(p.price) for p in current_cluster]
            cluster_avg = sum(prices) / len(prices)
        else:
            # Start new cluster (save current if valid)
            if len(current_cluster) >= 2:
                clusters.append(_create_price_cluster(current_cluster))
            current_cluster = [pivot]
            cluster_avg = float(pivot.price)

    # Don't forget last cluster
    if len(current_cluster) >= 2:
        clusters.append(_create_price_cluster(current_cluster))

    # Sort by quality: touch count (descending), then std_deviation (ascending)
    clusters.sort(key=lambda c: (-c.touch_count, c.std_deviation))

    return clusters


def _create_price_cluster(pivots: list[Pivot]) -> PriceCluster:
    """
    Internal helper: create PriceCluster object from list of pivots.

    Args:
        pivots: List of Pivot objects (all same type)

    Returns:
        PriceCluster: Cluster object with calculated statistics
    """
    prices = [float(p.price) for p in pivots]

    # Calculate statistics
    avg_price = _quantize_decimal(Decimal(str(statistics.mean(prices))), decimal_places=8)
    min_price = min(p.price for p in pivots)
    max_price = max(p.price for p in pivots)
    price_range = max_price - min_price

    # Standard deviation (need at least 2 values)
    if len(prices) >= 2:
        std_dev = _quantize_decimal(Decimal(str(statistics.stdev(prices))), decimal_places=8)
    else:
        std_dev = Decimal("0")

    # Timestamp range
    timestamps = [p.timestamp for p in pivots]
    timestamp_range = (min(timestamps), max(timestamps))

    return PriceCluster(
        pivots=pivots,
        average_price=avg_price,
        min_price=min_price,
        max_price=max_price,
        price_range=price_range,
        touch_count=len(pivots),
        cluster_type=pivots[0].type,  # All same type
        std_deviation=std_dev,
        timestamp_range=timestamp_range,
    )


def form_trading_range(
    support_cluster: PriceCluster,
    resistance_cluster: PriceCluster,
    bars: list[OHLCVBar],
    symbol: str | None = None,
    timeframe: str | None = None,
) -> TradingRange | None:
    """
    Form a TradingRange from support and resistance clusters.

    Validates that the clusters form a valid trading range meeting minimum
    requirements for support < resistance, range width >= 3%, and duration >= 10 bars.

    Args:
        support_cluster: PriceCluster of pivot lows (support level)
        resistance_cluster: PriceCluster of pivot highs (resistance level)
        bars: List of OHLCVBar objects (for duration calculation)
        symbol: Optional ticker symbol (extracted from bars if not provided)
        timeframe: Optional timeframe (extracted from bars if not provided)

    Returns:
        TradingRange: Valid trading range object, or None if validation fails

    Validation criteria:
        - support < resistance
        - range_width_pct >= 0.03 (3% minimum per FR1)
        - duration >= 10 bars
        - Both clusters have >= 2 touches

    Example:
        >>> support = find_best_support_cluster(clusters)
        >>> resistance = find_best_resistance_cluster(clusters)
        >>> trading_range = form_trading_range(support, resistance, bars)
        >>> if trading_range:
        ...     print(f"Range: {trading_range.support} - {trading_range.resistance}")
    """
    # Extract support and resistance prices
    support = support_cluster.average_price
    resistance = resistance_cluster.average_price

    # Extract symbol and timeframe
    if symbol is None:
        symbol = bars[0].symbol if bars and hasattr(bars[0], "symbol") else "UNKNOWN"
    if timeframe is None:
        timeframe = bars[0].timeframe if bars and hasattr(bars[0], "timeframe") else "UNKNOWN"

    # Validate: support < resistance
    if resistance <= support:
        logger.warning(
            "invalid_range_order",
            symbol=symbol,
            support=float(support),
            resistance=float(resistance),
            message="Resistance must be > support",
        )
        return None

    # Calculate range metrics
    midpoint = _quantize_decimal((support + resistance) / Decimal("2"), decimal_places=8)
    range_width = resistance - support
    range_width_pct = _quantize_decimal(range_width / support, decimal_places=4)

    # Validate: minimum 3% range size
    if range_width_pct < Decimal("0.03"):
        logger.warning(
            "range_too_narrow",
            symbol=symbol,
            range_width_pct=float(range_width_pct),
            min_required=0.03,
            message="Range below 3% minimum (FR1)",
        )
        return None

    # Calculate duration (number of bars from first to last pivot)
    all_pivots = support_cluster.pivots + resistance_cluster.pivots
    pivot_indices = [p.index for p in all_pivots]
    start_index = min(pivot_indices)
    end_index = max(pivot_indices)
    duration = end_index - start_index + 1

    # Validate: minimum 10 bars duration
    if duration < 10:
        logger.warning(
            "insufficient_duration",
            symbol=symbol,
            duration=duration,
            min_required=10,
            message="Duration below 10 bars minimum",
        )
        return None

    # Calculate preliminary quality score
    quality_score = calculate_preliminary_quality_score(
        support_cluster=support_cluster, resistance_cluster=resistance_cluster, duration=duration
    )

    # Create TradingRange object
    trading_range = TradingRange(
        symbol=symbol,
        timeframe=timeframe,
        support_cluster=support_cluster,
        resistance_cluster=resistance_cluster,
        support=support,
        resistance=resistance,
        midpoint=midpoint,
        range_width=range_width,
        range_width_pct=range_width_pct,
        start_index=start_index,
        end_index=end_index,
        duration=duration,
        quality_score=quality_score,
    )

    logger.info(
        "trading_range_formed",
        symbol=symbol,
        support=float(support),
        resistance=float(resistance),
        range_width_pct=float(range_width_pct),
        duration=duration,
        quality_score=quality_score,
        total_touches=trading_range.total_touches,
    )

    return trading_range


def calculate_preliminary_quality_score(
    support_cluster: PriceCluster, resistance_cluster: PriceCluster, duration: int
) -> int:
    """
    Calculate preliminary quality score for a trading range.

    This is a simplified quality score based on duration, touch count, and
    cluster tightness. Story 3.3 will implement full quality scoring with
    volume confirmation.

    Scoring components (total 100 points):
        - Duration (30 points):
            * >= 40 bars: 30 pts
            * >= 25 bars: 20 pts
            * >= 15 bars: 10 pts
            * < 15 bars: 5 pts
        - Touch count (30 points):
            * >= 8 total touches: 30 pts
            * >= 6 touches: 20 pts
            * >= 4 touches: 10 pts
            * < 4 touches: 5 pts
        - Cluster tightness (40 points):
            * avg std_dev < 1%: 40 pts
            * avg std_dev < 2%: 20 pts
            * avg std_dev >= 2%: 10 pts

    Args:
        support_cluster: Support level cluster
        resistance_cluster: Resistance level cluster
        duration: Range duration in bars

    Returns:
        int: Quality score 0-100 (capped at 100)

    Note:
        Story 3.3 will enhance this with volume confirmation component.
    """
    score = 0

    # Duration component (30 points)
    if duration >= 40:
        score += 30
    elif duration >= 25:
        score += 20
    elif duration >= 15:
        score += 10
    else:
        score += 5

    # Touch count component (30 points)
    total_touches = support_cluster.touch_count + resistance_cluster.touch_count
    if total_touches >= 8:
        score += 30
    elif total_touches >= 6:
        score += 20
    elif total_touches >= 4:
        score += 10
    else:
        score += 5

    # Tightness component (40 points)
    # Calculate average relative std deviation across both clusters
    support_std_pct = support_cluster.std_deviation / support_cluster.average_price
    resistance_std_pct = resistance_cluster.std_deviation / resistance_cluster.average_price
    avg_std_pct = (support_std_pct + resistance_std_pct) / Decimal("2")

    if avg_std_pct < Decimal("0.01"):  # < 1%
        score += 40
    elif avg_std_pct < Decimal("0.02"):  # < 2%
        score += 20
    else:
        score += 10

    # Cap at 100
    return min(score, 100)


def find_best_support_cluster(clusters: list[PriceCluster]) -> PriceCluster | None:
    """
    Find the best support cluster from a list of clusters.

    Selects the highest quality support (LOW) cluster based on touch count
    and tightness.

    Args:
        clusters: List of PriceCluster objects

    Returns:
        PriceCluster: Best support cluster, or None if no LOW clusters found

    Selection criteria:
        1. Filter for LOW (support) clusters only
        2. Sort by touch_count (descending)
        3. Then by std_deviation (ascending - tighter is better)
        4. Return top cluster
    """
    support_clusters = [c for c in clusters if c.cluster_type == PivotType.LOW]
    if not support_clusters:
        return None

    # Sort by quality: most touches first, then tightest
    support_clusters.sort(key=lambda c: (-c.touch_count, c.std_deviation))
    return support_clusters[0]


def find_best_resistance_cluster(clusters: list[PriceCluster]) -> PriceCluster | None:
    """
    Find the best resistance cluster from a list of clusters.

    Selects the highest quality resistance (HIGH) cluster based on touch count
    and tightness.

    Args:
        clusters: List of PriceCluster objects

    Returns:
        PriceCluster: Best resistance cluster, or None if no HIGH clusters found

    Selection criteria:
        1. Filter for HIGH (resistance) clusters only
        2. Sort by touch_count (descending)
        3. Then by std_deviation (ascending - tighter is better)
        4. Return top cluster
    """
    resistance_clusters = [c for c in clusters if c.cluster_type == PivotType.HIGH]
    if not resistance_clusters:
        return None

    # Sort by quality: most touches first, then tightest
    resistance_clusters.sort(key=lambda c: (-c.touch_count, c.std_deviation))
    return resistance_clusters[0]


def find_potential_ranges(
    pivots: list[Pivot], bars: list[OHLCVBar], tolerance_pct: float = 0.02
) -> list[TradingRange]:
    """
    Find all potential trading ranges from pivot points.

    Clusters pivots and attempts to form valid trading ranges from all
    combinations of support and resistance clusters.

    Args:
        pivots: List of Pivot objects
        bars: List of OHLCVBar objects (for duration calculation)
        tolerance_pct: Price tolerance for clustering (default 0.02 = 2%)

    Returns:
        List[TradingRange]: Valid trading ranges, sorted by quality score (descending)

    Example:
        >>> pivots = detect_pivots(bars, lookback=5)
        >>> ranges = find_potential_ranges(pivots, bars)
        >>> best_range = ranges[0] if ranges else None
    """
    # Cluster pivots
    clusters = cluster_pivots(pivots, tolerance_pct=tolerance_pct)

    # Separate support and resistance clusters
    support_clusters = [c for c in clusters if c.cluster_type == PivotType.LOW]
    resistance_clusters = [c for c in clusters if c.cluster_type == PivotType.HIGH]

    # Extract symbol and timeframe for logging
    symbol = bars[0].symbol if bars and hasattr(bars[0], "symbol") else "UNKNOWN"
    timeframe = bars[0].timeframe if bars and hasattr(bars[0], "timeframe") else "UNKNOWN"

    # Try all combinations of support and resistance clusters
    valid_ranges = []
    for support in support_clusters:
        for resistance in resistance_clusters:
            trading_range = form_trading_range(
                support_cluster=support,
                resistance_cluster=resistance,
                bars=bars,
                symbol=symbol,
                timeframe=timeframe,
            )
            if trading_range and trading_range.is_valid:
                valid_ranges.append(trading_range)

    # Sort by quality score (descending - best first)
    valid_ranges.sort(key=lambda r: r.quality_score or 0, reverse=True)

    logger.info(
        "potential_ranges_found",
        symbol=symbol,
        timeframe=timeframe,
        range_count=len(valid_ranges),
        support_cluster_count=len(support_clusters),
        resistance_cluster_count=len(resistance_clusters),
    )

    return valid_ranges
