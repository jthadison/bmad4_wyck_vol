"""
TradingRangeDetector module - Epic 3.8 Integration Layer.

This module orchestrates all Epic 3 components (Stories 3.1-3.7) into a unified
TradingRangeDetector that provides a single, performant interface for pattern
detectors (Epics 4-6) to access complete trading range analysis with all levels
and zones.

Pipeline:
    1. Pivot Detection (Story 3.1) - detect swing highs and lows
    2. Clustering & Formation (Story 3.2) - cluster pivots into ranges
    3. Quality Scoring (Story 3.3) - score ranges 0-100, filter >= 70
    4. Level Calculation (Stories 3.4-3.6) - Creek, Ice, Jump levels
    5. Zone Mapping (Story 3.7) - Supply and Demand zones
    6. Overlap Resolution (Story 3.8) - Newer ranges take precedence
    7. Status Assignment (Story 3.8) - FORMING → ACTIVE lifecycle

Performance Target:
    1000 bars in <200ms (AC 10)

Example:
    >>> from backend.src.pattern_engine.trading_range_detector import TradingRangeDetector
    >>> from backend.src.pattern_engine.volume_analyzer import VolumeAnalyzer
    >>> from backend.src.repositories.ohlcv_repository import OHLCVRepository
    >>>
    >>> # Load data
    >>> repo = OHLCVRepository()
    >>> bars = repo.get_bars("AAPL", "1d", limit=252)
    >>>
    >>> # Analyze volume
    >>> volume_analyzer = VolumeAnalyzer()
    >>> volume_analysis = volume_analyzer.analyze_bars(bars)
    >>>
    >>> # Detect ranges
    >>> detector = TradingRangeDetector(lookback=5, min_quality_threshold=70)
    >>> ranges = detector.detect_ranges(bars, volume_analysis)
    >>>
    >>> # Access most recent range
    >>> current_range = get_most_recent_range(ranges)
    >>> if current_range and current_range.is_active:
    ...     print(f"Creek: {current_range.creek.price}")
    ...     print(f"Ice: {current_range.ice.price}")
    ...     print(f"Jump: {current_range.jump.price}")
"""

from __future__ import annotations

import time
from datetime import datetime
from decimal import Decimal

import structlog

from src.models.ohlcv import OHLCVBar
from src.models.trading_range import RangeStatus, TradingRange
from src.models.volume_analysis import VolumeAnalysis
from src.models.zone import ZoneStrength, ZoneType
from src.pattern_engine.level_calculator import (
    calculate_creek_level,
    calculate_ice_level,
    calculate_jump_level,
)
from src.pattern_engine.pivot_detector import detect_pivots, get_pivot_highs, get_pivot_lows
from src.pattern_engine.range_cluster import cluster_pivots, form_trading_range
from src.pattern_engine.range_quality import calculate_range_quality
from src.pattern_engine.zone_mapper import map_supply_demand_zones

logger = structlog.get_logger(__name__)


class TradingRangeDetector:
    """
    Unified detector that orchestrates complete trading range analysis.

    Integrates all Epic 3 components into single interface for Epic 4-6 pattern
    detectors. Provides caching, overlap resolution, and lifecycle management.

    Attributes:
        lookback: Pivot detection sensitivity (default 5)
        pivot_tolerance_pct: Clustering tolerance 2% (default Decimal("0.02"))
        min_quality_threshold: Minimum quality score 70 (default 70)
        cache_enabled: Enable range caching (default True)

    Example:
        >>> detector = TradingRangeDetector(
        ...     lookback=5,
        ...     pivot_tolerance_pct=Decimal("0.02"),
        ...     min_quality_threshold=70,
        ...     cache_enabled=True
        ... )
        >>> ranges = detector.detect_ranges(bars, volume_analysis)
        >>> active_ranges = [r for r in ranges if r.is_active]
    """

    def __init__(
        self,
        lookback: int = 5,
        pivot_tolerance_pct: Decimal = Decimal("0.02"),
        min_quality_threshold: int = 70,
        cache_enabled: bool = True,
    ):
        """
        Initialize TradingRangeDetector with configuration.

        Args:
            lookback: Pivot detection sensitivity (1-100, default 5)
            pivot_tolerance_pct: Price clustering tolerance (default 0.02 = 2%)
            min_quality_threshold: Minimum quality score (0-100, default 70)
            cache_enabled: Enable result caching (default True)
        """
        self.lookback = lookback
        self.pivot_tolerance_pct = pivot_tolerance_pct
        self.min_quality_threshold = min_quality_threshold
        self.cache_enabled = cache_enabled

        # Cache storage
        self._range_cache: dict[str, list[TradingRange]] = {}
        self._cache_hits = 0
        self._cache_misses = 0

        logger.info(
            "trading_range_detector_initialized",
            lookback=lookback,
            pivot_tolerance_pct=str(pivot_tolerance_pct),
            min_quality_threshold=min_quality_threshold,
            cache_enabled=cache_enabled,
        )

    def detect_ranges(
        self, bars: list[OHLCVBar], volume_analysis: list[VolumeAnalysis]
    ) -> list[TradingRange]:
        """
        Detect trading ranges with complete levels and zones.

        Orchestrates full pipeline: pivots → clustering → quality → levels → zones
        → overlap resolution → status assignment. Returns only valid, non-overlapping
        ranges ready for pattern detection.

        Algorithm:
            1. Check cache for existing results
            2. Detect pivots (Story 3.1)
            3. Cluster pivots into ranges (Story 3.2)
            4. Score quality, filter >= 70 (Story 3.3)
            5. Calculate Creek, Ice, Jump levels (Stories 3.4-3.6)
            6. Map supply/demand zones (Story 3.7)
            7. Resolve overlapping ranges (Story 3.8)
            8. Assign lifecycle status (Story 3.8)
            9. Cache results

        Args:
            bars: OHLCV bars to analyze (500-1000 typical, minimum 20)
            volume_analysis: Volume analysis results from Epic 2 (same length as bars)

        Returns:
            List[TradingRange]: Detected ranges with all fields populated

        Raises:
            ValueError: If bars/volume_analysis length mismatch or bars not sequential

        Performance:
            1000 bars in <200ms (AC 10)

        Example:
            >>> bars = repo.get_bars("AAPL", "1d", limit=252)
            >>> volume_analysis = volume_analyzer.analyze_bars(bars)
            >>> ranges = detector.detect_ranges(bars, volume_analysis)
            >>> print(f"Found {len(ranges)} ranges")
            >>> for r in ranges:
            ...     if r.is_active:
            ...         print(f"Range {r.id}: Creek={r.creek.price}, Ice={r.ice.price}")
        """
        start_time = time.perf_counter()

        # Input validation
        if not bars:
            logger.warning("empty_bars_list", message="Cannot detect ranges on empty bar list")
            return []

        if len(bars) < 20:
            logger.warning(
                "insufficient_bars",
                bars_count=len(bars),
                required=20,
                message="Insufficient bars for range detection",
            )
            return []

        if len(volume_analysis) != len(bars):
            logger.error(
                "bars_volume_mismatch",
                bars_count=len(bars),
                volume_count=len(volume_analysis),
                message="Bars and volume_analysis length mismatch",
            )
            raise ValueError("Bars and volume_analysis must have same length")

        # Validate sequential timestamps
        for i in range(1, len(bars)):
            if bars[i].timestamp <= bars[i - 1].timestamp:
                logger.error(
                    "non_sequential_bars",
                    index=i,
                    message="Bars must be in chronological order",
                )
                raise ValueError("Bars must have sequential timestamps")

        symbol = bars[0].symbol
        timeframe = bars[0].timeframe

        # Check cache
        cache_key = self._create_cache_key(bars)
        if self.cache_enabled and cache_key in self._range_cache:
            self._cache_hits += 1
            logger.info(
                "range_detection_cache_hit",
                cache_key=cache_key,
                cache_hits=self._cache_hits,
                cache_misses=self._cache_misses,
            )
            return self._range_cache[cache_key]

        self._cache_misses += 1

        logger.info(
            "range_detection_start",
            symbol=symbol,
            timeframe=timeframe,
            bar_count=len(bars),
            date_range=f"{bars[0].timestamp} to {bars[-1].timestamp}",
            cache_enabled=self.cache_enabled,
        )

        # Step 1: Pivot Detection (~50ms)
        pivot_start = time.perf_counter()
        pivots = detect_pivots(bars, lookback=self.lookback)
        pivot_duration = (time.perf_counter() - pivot_start) * 1000

        if len(pivots) < 4:
            logger.warning(
                "insufficient_pivots",
                pivot_count=len(pivots),
                required=4,
                message="Need at least 4 pivots (2 highs, 2 lows) for range detection",
            )
            return []

        pivot_highs = get_pivot_highs(pivots)
        pivot_lows = get_pivot_lows(pivots)

        logger.info(
            "pivot_detection_complete",
            total_pivots=len(pivots),
            pivot_highs=len(pivot_highs),
            pivot_lows=len(pivot_lows),
            duration_ms=f"{pivot_duration:.2f}",
        )

        # Step 2: Clustering & Formation (~30ms)
        cluster_start = time.perf_counter()
        resistance_clusters = cluster_pivots(pivot_highs, tolerance_pct=self.pivot_tolerance_pct)
        support_clusters = cluster_pivots(pivot_lows, tolerance_pct=self.pivot_tolerance_pct)

        candidate_ranges = []
        for support_cluster in support_clusters:
            for resistance_cluster in resistance_clusters:
                # Basic validation: resistance > support, min 3% width, min 10 bars
                if resistance_cluster.average_price > support_cluster.average_price:
                    range_width_pct = (
                        resistance_cluster.average_price - support_cluster.average_price
                    ) / support_cluster.average_price

                    if range_width_pct >= Decimal("0.03"):
                        # Calculate duration from pivot indices
                        support_indices = [p.index for p in support_cluster.pivots]
                        resistance_indices = [p.index for p in resistance_cluster.pivots]
                        min_index = min(min(support_indices), min(resistance_indices))
                        max_index = max(max(support_indices), max(resistance_indices))
                        duration = max_index - min_index + 1

                        if duration >= 10:
                            try:
                                trading_range = form_trading_range(
                                    support_cluster, resistance_cluster, bars
                                )
                                candidate_ranges.append(trading_range)
                            except Exception as e:
                                logger.warning(
                                    "range_formation_failed",
                                    error=str(e),
                                    support_avg=str(support_cluster.average_price),
                                    resistance_avg=str(resistance_cluster.average_price),
                                )

        cluster_duration = (time.perf_counter() - cluster_start) * 1000

        logger.info(
            "clustering_complete",
            resistance_clusters=len(resistance_clusters),
            support_clusters=len(support_clusters),
            candidate_ranges=len(candidate_ranges),
            duration_ms=f"{cluster_duration:.2f}",
        )

        # Step 3: Quality Scoring (~20ms)
        quality_start = time.perf_counter()
        quality_ranges = []
        rejected_count = 0

        for candidate_range in candidate_ranges:
            try:
                quality_score = calculate_range_quality(candidate_range, bars, volume_analysis)
                candidate_range.quality_score = quality_score

                if quality_score >= self.min_quality_threshold:
                    quality_ranges.append(candidate_range)
                else:
                    rejected_count += 1
            except Exception as e:
                logger.warning(
                    "quality_scoring_failed",
                    error=str(e),
                    range_id=str(candidate_range.id),
                )
                rejected_count += 1

        quality_duration = (time.perf_counter() - quality_start) * 1000

        logger.info(
            "quality_scoring_complete",
            quality_ranges=len(quality_ranges),
            rejected_ranges=rejected_count,
            threshold=self.min_quality_threshold,
            duration_ms=f"{quality_duration:.2f}",
        )

        # Step 4: Level Calculation (~30ms)
        level_start = time.perf_counter()
        ranges_with_levels = []

        for trading_range in quality_ranges:
            try:
                # Calculate levels
                creek = calculate_creek_level(trading_range, bars, volume_analysis)
                ice = calculate_ice_level(trading_range, bars, volume_analysis)

                # Validate level strengths
                if creek.strength_score < 60 or ice.strength_score < 60:
                    logger.warning(
                        "low_level_strength",
                        range_id=str(trading_range.id),
                        creek_strength=creek.strength_score,
                        ice_strength=ice.strength_score,
                        message="Skipping range due to low level strength (<60)",
                    )
                    continue

                # Validate creek < ice
                if creek.price >= ice.price:
                    logger.warning(
                        "invalid_level_order",
                        range_id=str(trading_range.id),
                        creek_price=str(creek.price),
                        ice_price=str(ice.price),
                        message="Creek price must be < Ice price",
                    )
                    continue

                jump = calculate_jump_level(trading_range, creek, ice)

                # Validate jump > ice
                if jump.price <= ice.price:
                    logger.warning(
                        "invalid_jump_target",
                        range_id=str(trading_range.id),
                        ice_price=str(ice.price),
                        jump_price=str(jump.price),
                        message="Jump price must be > Ice price",
                    )
                    continue

                # Update range with levels
                trading_range.creek = creek
                trading_range.ice = ice
                trading_range.jump = jump

                # Calculate midpoint (should match existing midpoint closely)
                calculated_midpoint = (creek.price + ice.price) / Decimal("2.0")
                trading_range.midpoint = calculated_midpoint

                ranges_with_levels.append(trading_range)

                logger.debug(
                    "levels_calculated",
                    range_id=str(trading_range.id),
                    creek_price=str(creek.price),
                    ice_price=str(ice.price),
                    jump_price=str(jump.price),
                    midpoint=str(calculated_midpoint),
                )

            except Exception as e:
                logger.warning(
                    "level_calculation_failed",
                    error=str(e),
                    range_id=str(trading_range.id),
                )

        level_duration = (time.perf_counter() - level_start) * 1000

        logger.info(
            "level_calculation_complete",
            ranges_with_levels=len(ranges_with_levels),
            duration_ms=f"{level_duration:.2f}",
        )

        # Step 5: Zone Mapping (~20ms)
        zone_start = time.perf_counter()

        for trading_range in ranges_with_levels:
            try:
                zones = map_supply_demand_zones(trading_range, bars, volume_analysis)
                trading_range.supply_zones = [z for z in zones if z.zone_type == ZoneType.SUPPLY]
                trading_range.demand_zones = [z for z in zones if z.zone_type == ZoneType.DEMAND]

                fresh_zones = [z for z in zones if z.strength == ZoneStrength.FRESH]

                logger.debug(
                    "zones_mapped",
                    range_id=str(trading_range.id),
                    total_zones=len(zones),
                    supply_zones=len(trading_range.supply_zones),
                    demand_zones=len(trading_range.demand_zones),
                    fresh_zones=len(fresh_zones),
                )

            except Exception as e:
                logger.warning(
                    "zone_mapping_failed",
                    error=str(e),
                    range_id=str(trading_range.id),
                    message="Continuing with empty zones",
                )
                trading_range.supply_zones = []
                trading_range.demand_zones = []

        zone_duration = (time.perf_counter() - zone_start) * 1000

        logger.info(
            "zone_mapping_complete",
            duration_ms=f"{zone_duration:.2f}",
        )

        # Step 6: Overlap Resolution (~10ms)
        overlap_start = time.perf_counter()
        non_overlapping_ranges = self._resolve_overlapping_ranges(ranges_with_levels)
        overlap_duration = (time.perf_counter() - overlap_start) * 1000

        logger.info(
            "overlap_resolution_complete",
            input_ranges=len(ranges_with_levels),
            output_ranges=len(non_overlapping_ranges),
            archived_ranges=len(ranges_with_levels) - len(non_overlapping_ranges),
            duration_ms=f"{overlap_duration:.2f}",
        )

        # Step 7: Status Assignment (~10ms)
        status_start = time.perf_counter()

        for trading_range in non_overlapping_ranges:
            # FORMING → ACTIVE based on duration and quality
            if trading_range.duration >= 15 and trading_range.quality_score >= 70:
                trading_range.status = RangeStatus.ACTIVE
            else:
                trading_range.status = RangeStatus.FORMING

            # Add timestamps if not already set
            if not trading_range.start_timestamp:
                trading_range.start_timestamp = bars[trading_range.start_index].timestamp
            if not trading_range.end_timestamp:
                trading_range.end_timestamp = bars[trading_range.end_index].timestamp

        status_duration = (time.perf_counter() - status_start) * 1000

        logger.info(
            "status_assignment_complete",
            duration_ms=f"{status_duration:.2f}",
        )

        # Cache results
        if self.cache_enabled:
            self._range_cache[cache_key] = non_overlapping_ranges
            logger.info(
                "ranges_cached",
                cache_key=cache_key,
                range_count=len(non_overlapping_ranges),
            )

        # Final summary
        total_duration = (time.perf_counter() - start_time) * 1000
        active_ranges = [r for r in non_overlapping_ranges if r.is_active]
        forming_ranges = [r for r in non_overlapping_ranges if r.status == RangeStatus.FORMING]
        avg_quality = (
            sum(r.quality_score for r in non_overlapping_ranges) / len(non_overlapping_ranges)
            if non_overlapping_ranges
            else 0
        )

        logger.info(
            "range_detection_complete",
            symbol=symbol,
            timeframe=timeframe,
            total_ranges=len(non_overlapping_ranges),
            active_ranges=len(active_ranges),
            forming_ranges=len(forming_ranges),
            avg_quality=f"{avg_quality:.1f}",
            total_duration_ms=f"{total_duration:.2f}",
            performance_breakdown={
                "pivot_detection_ms": f"{pivot_duration:.2f}",
                "clustering_ms": f"{cluster_duration:.2f}",
                "quality_scoring_ms": f"{quality_duration:.2f}",
                "level_calculation_ms": f"{level_duration:.2f}",
                "zone_mapping_ms": f"{zone_duration:.2f}",
                "overlap_resolution_ms": f"{overlap_duration:.2f}",
                "status_assignment_ms": f"{status_duration:.2f}",
            },
        )

        return non_overlapping_ranges

    def _create_cache_key(self, bars: list[OHLCVBar]) -> str:
        """
        Create cache key from bar sequence.

        Format: {symbol}:{timeframe}:{start_timestamp}:{end_timestamp}:{bar_count}

        Args:
            bars: OHLCV bars to create key from

        Returns:
            str: Cache key

        Example:
            >>> key = detector._create_cache_key(bars)
            >>> print(key)
            AAPL:1d:2024-01-01T00:00:00Z:2024-12-31T23:59:59Z:252
        """
        symbol = bars[0].symbol
        timeframe = bars[0].timeframe
        start_timestamp = bars[0].timestamp.isoformat()
        end_timestamp = bars[-1].timestamp.isoformat()
        bar_count = len(bars)

        return f"{symbol}:{timeframe}:{start_timestamp}:{end_timestamp}:{bar_count}"

    def _resolve_overlapping_ranges(self, ranges: list[TradingRange]) -> list[TradingRange]:
        """
        Resolve overlapping ranges by archiving older ones.

        Strategy: Newer ranges take precedence (higher end_index wins).
        Two ranges overlap if their bar indices AND price levels overlap.

        Args:
            ranges: List of ranges to check for overlaps

        Returns:
            List[TradingRange]: Non-overlapping ranges (archived ranges excluded)

        Example:
            >>> ranges = [range1, range2_overlapping]
            >>> resolved = detector._resolve_overlapping_ranges(ranges)
            >>> # Only newer range remains active
        """
        if len(ranges) <= 1:
            return ranges

        # Sort by end_index (chronological order)
        sorted_ranges = sorted(ranges, key=lambda r: r.end_index)

        active_ranges = []

        for candidate in sorted_ranges:
            overlaps_with_active = False

            for active in active_ranges:
                if self._ranges_overlap(candidate, active):
                    # Newer range takes precedence
                    if candidate.end_index > active.end_index:
                        # Archive the older range
                        active.status = RangeStatus.ARCHIVED
                        logger.info(
                            "range_archived_due_to_overlap",
                            archived_range_id=str(active.id),
                            kept_range_id=str(candidate.id),
                            reason="newer range overlaps",
                        )
                        # Remove archived range from active list
                        active_ranges.remove(active)
                    else:
                        # Current candidate is older, skip it
                        candidate.status = RangeStatus.ARCHIVED
                        logger.info(
                            "range_archived_due_to_overlap",
                            archived_range_id=str(candidate.id),
                            kept_range_id=str(active.id),
                            reason="older than existing range",
                        )
                        overlaps_with_active = True
                        break

            if not overlaps_with_active and candidate.status != RangeStatus.ARCHIVED:
                active_ranges.append(candidate)

        return active_ranges

    def _ranges_overlap(self, range1: TradingRange, range2: TradingRange) -> bool:
        """
        Check if two ranges overlap in both bar indices and price levels.

        Args:
            range1: First trading range
            range2: Second trading range

        Returns:
            bool: True if ranges overlap, False otherwise

        Example:
            >>> overlap = detector._ranges_overlap(range1, range2)
            >>> if overlap:
            ...     print("Ranges overlap!")
        """
        # Check bar index overlap
        bar_overlap = (
            range1.end_index >= range2.start_index and range2.end_index >= range1.start_index
        )

        # Check price level overlap (using support/resistance)
        price_overlap = range1.support <= range2.resistance and range1.resistance >= range2.support

        return bar_overlap and price_overlap

    def clear_cache(self) -> None:
        """
        Clear all cached ranges.

        Example:
            >>> detector.clear_cache()
            >>> # All cached results removed
        """
        self._range_cache.clear()
        logger.info(
            "cache_cleared",
            cache_hits=self._cache_hits,
            cache_misses=self._cache_misses,
        )
        self._cache_hits = 0
        self._cache_misses = 0

    def invalidate_symbol(self, symbol: str) -> None:
        """
        Clear cached ranges for specific symbol.

        Args:
            symbol: Ticker symbol to invalidate

        Example:
            >>> detector.invalidate_symbol("AAPL")
            >>> # Only AAPL cached results removed
        """
        keys_to_remove = [key for key in self._range_cache.keys() if key.startswith(f"{symbol}:")]
        for key in keys_to_remove:
            del self._range_cache[key]

        logger.info(
            "symbol_cache_invalidated",
            symbol=symbol,
            keys_removed=len(keys_to_remove),
        )


# Helper functions for range access


def get_active_ranges(ranges: list[TradingRange]) -> list[TradingRange]:
    """
    Filter for only ACTIVE ranges.

    Args:
        ranges: List of trading ranges

    Returns:
        List[TradingRange]: Only ranges with status=ACTIVE

    Example:
        >>> ranges = detector.detect_ranges(bars, volume_analysis)
        >>> active = get_active_ranges(ranges)
        >>> print(f"Found {len(active)} active ranges")
    """
    return [r for r in ranges if r.is_active]


def get_ranges_by_symbol(ranges: list[TradingRange], symbol: str) -> list[TradingRange]:
    """
    Filter ranges by symbol.

    Args:
        ranges: List of trading ranges
        symbol: Ticker symbol to filter

    Returns:
        List[TradingRange]: Ranges matching symbol

    Example:
        >>> ranges = detector.detect_ranges(bars, volume_analysis)
        >>> aapl_ranges = get_ranges_by_symbol(ranges, "AAPL")
    """
    return [r for r in ranges if r.symbol == symbol]


def get_most_recent_range(ranges: list[TradingRange]) -> TradingRange | None:
    """
    Get most recent range (highest end_index).

    Args:
        ranges: List of trading ranges

    Returns:
        TradingRange | None: Most recent range or None if empty

    Example:
        >>> ranges = detector.detect_ranges(bars, volume_analysis)
        >>> current = get_most_recent_range(ranges)
        >>> if current:
        ...     print(f"Current range: Creek={current.creek.price}")
    """
    if not ranges:
        return None
    return max(ranges, key=lambda r: r.end_index)


def get_range_at_timestamp(ranges: list[TradingRange], timestamp: datetime) -> TradingRange | None:
    """
    Find range containing specific timestamp.

    Args:
        ranges: List of trading ranges
        timestamp: Target timestamp

    Returns:
        TradingRange | None: Range containing timestamp or None

    Example:
        >>> from datetime import datetime
        >>> ranges = detector.detect_ranges(bars, volume_analysis)
        >>> target_time = datetime(2024, 6, 15)
        >>> range_at_time = get_range_at_timestamp(ranges, target_time)
    """
    for trading_range in ranges:
        if (
            trading_range.start_timestamp
            and trading_range.end_timestamp
            and trading_range.start_timestamp <= timestamp <= trading_range.end_timestamp
        ):
            return trading_range
    return None
