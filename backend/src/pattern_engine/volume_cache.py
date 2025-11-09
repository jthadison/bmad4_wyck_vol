"""
VolumeCache - Pre-calculated volume ratios for performance optimization.

This module provides O(n) pre-calculation with O(1) lookups for volume ratios,
achieving ~10x speedup for multi-spring detection scenarios.

Purpose:
--------
Pre-calculate volume ratios during initial bar processing to avoid
redundant calculations during pattern detection.

Performance Impact:
-------------------
WITHOUT cache: O(n × m) complexity
- 100 bars × 50 spring candidates = 5,000 volume ratio calculations

WITH cache: O(n) + O(1) lookups
- 100 pre-calculations + 50 lookups = ~10x speedup

Target: <100ms for 100-bar sequence with 50 spring candidates

Algorithm:
----------
1. __init__: Build cache with O(n) single pass
2. get_ratio: O(1) lookup by timestamp
3. invalidate: O(1) removal for live data updates

Usage:
------
>>> from backend.src.pattern_engine.volume_cache import VolumeCache
>>> from backend.src.models.ohlcv import OHLCVBar
>>> from datetime import datetime, timezone
>>> from decimal import Decimal
>>>
>>> # Create bars
>>> bars = [
...     OHLCVBar(symbol="AAPL", timestamp=datetime(2024, 1, i, tzinfo=timezone.utc),
...              open=Decimal("100"), high=Decimal("101"), low=Decimal("99"),
...              close=Decimal("100"), volume=1000000, spread=Decimal("2"))
...     for i in range(1, 101)
... ]
>>>
>>> # Build cache (O(n) single pass)
>>> cache = VolumeCache(bars, window=20)
>>>
>>> # Lookup ratios (O(1) each)
>>> ratio = cache.get_ratio(bars[50].timestamp)  # Instant lookup
>>> if ratio:
...     print(f"Volume ratio: {ratio:.2f}x")

Thread Safety:
--------------
Current implementation is NOT thread-safe. If concurrent access is needed,
wrap get_ratio() and invalidate() calls with threading.Lock.

Author: Story 5.6 - SpringDetector Module Integration
"""

from __future__ import annotations

import time
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

import structlog

from src.models.ohlcv import OHLCVBar

logger = structlog.get_logger(__name__)


class VolumeCache:
    """
    Pre-calculated volume ratios for performance optimization.

    Builds a cache of volume ratios during initialization using O(n) single pass.
    Provides O(1) lookups by timestamp for fast pattern detection.

    Attributes:
        ratios: Pre-calculated volume ratios keyed by timestamp
        window: Rolling window size for average calculation (default: 20)

    Performance:
        Target: <100ms for 100-bar sequence
        Speedup: ~10x vs per-candidate calculation

    Example:
        >>> cache = VolumeCache(bars, window=20)
        >>> ratio = cache.get_ratio(bars[50].timestamp)  # O(1) lookup
        >>> if ratio:
        ...     print(f"Volume: {ratio:.2f}x")
    """

    def __init__(self, bars: list[OHLCVBar], window: int = 20):
        """
        Initialize cache with pre-calculated volume ratios.

        Performs O(n) single pass to calculate all volume ratios.

        Args:
            bars: List of OHLCV bars (sorted by timestamp)
            window: Rolling window size for average (default: 20)

        Example:
            >>> cache = VolumeCache(bars, window=20)
            >>> len(cache.ratios)  # Number of ratios calculated
            80  # 100 bars - 20 window = 80 ratios
        """
        self.ratios: dict[datetime, Decimal] = {}
        self.window: int = window
        self.logger = logger.bind(component="VolumeCache")

        # Build cache with O(n) single pass
        self._build_cache(bars, window)

    def _build_cache(self, bars: list[OHLCVBar], window: int) -> None:
        """
        Build volume ratio cache with O(n) single pass.

        Algorithm:
        ----------
        For each bar starting at index `window`:
            1. Calculate average volume of previous `window` bars
            2. Calculate ratio: bar.volume / avg_volume
            3. Store in cache: ratios[bar.timestamp] = ratio

        Time Complexity: O(n) where n = len(bars)
        Space Complexity: O(n - window) for cached ratios

        Args:
            bars: List of OHLCV bars (sorted by timestamp)
            window: Rolling window size for average

        Side Effects:
            Populates self.ratios dictionary

        Example:
            >>> bars = [...]  # 100 bars
            >>> cache = VolumeCache(bars, window=20)
            >>> # Processes bars[20:] and calculates 80 ratios
        """
        start_time = time.perf_counter()
        calculated_count = 0

        # Insufficient bars for window calculation
        if len(bars) < window:
            self.logger.warning(
                "insufficient_bars_for_volume_cache",
                bar_count=len(bars),
                required_window=window,
                message=f"Need at least {window} bars for volume ratio calculation",
            )
            return

        # O(n) single pass starting at window index
        for i in range(window, len(bars)):
            current_bar = bars[i]

            # Calculate average volume of previous window bars
            window_volumes = [bars[j].volume for j in range(i - window, i)]
            avg_volume = sum(window_volumes) / window

            # Avoid division by zero
            if avg_volume == 0:
                self.logger.debug(
                    "zero_average_volume",
                    bar_timestamp=current_bar.timestamp.isoformat(),
                    message="Average volume is zero, skipping ratio calculation",
                )
                continue

            # Calculate volume ratio and quantize to 4 decimal places
            # to match Spring model constraint (max_digits=10, decimal_places=4)
            volume_ratio = Decimal(str(current_bar.volume / avg_volume)).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )

            # Store in cache (O(1) insertion)
            self.ratios[current_bar.timestamp] = volume_ratio
            calculated_count += 1

        # Log cache build completion
        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000

        self.logger.info(
            "volume_cache_built",
            total_bars=len(bars),
            ratios_calculated=calculated_count,
            window_size=window,
            elapsed_ms=f"{elapsed_ms:.2f}",
            cache_size_bytes=self._estimate_cache_size(),
        )

    def get_ratio(self, timestamp: datetime) -> Optional[Decimal]:
        """
        Retrieve pre-calculated volume ratio by timestamp.

        Time Complexity: O(1) dictionary lookup
        Space Complexity: O(1)

        Args:
            timestamp: Bar timestamp to lookup

        Returns:
            Decimal volume ratio if found, None otherwise

        Example:
            >>> cache = VolumeCache(bars)
            >>> ratio = cache.get_ratio(bars[50].timestamp)
            >>> if ratio:
            ...     print(f"Volume: {ratio:.2f}x average")
            ...     if ratio < Decimal("0.7"):
            ...         print("Low volume spring candidate ✅")
        """
        return self.ratios.get(timestamp)

    def invalidate(self, timestamp: datetime) -> None:
        """
        Remove cached ratio for given timestamp.

        Used for live data scenarios where bars are updated and ratios
        need recalculation.

        Time Complexity: O(1) dictionary removal
        Space Complexity: O(1)

        Args:
            timestamp: Bar timestamp to invalidate

        Example:
            >>> cache = VolumeCache(bars)
            >>> # Live data update received for bars[50]
            >>> cache.invalidate(bars[50].timestamp)
            >>> # Next get_ratio() will return None for this timestamp
        """
        removed = self.ratios.pop(timestamp, None)

        if removed is not None:
            self.logger.debug(
                "volume_ratio_invalidated",
                timestamp=timestamp.isoformat(),
                previous_ratio=float(removed),
                message="Cached ratio removed - recalculation needed",
            )
        else:
            self.logger.debug(
                "volume_ratio_not_found",
                timestamp=timestamp.isoformat(),
                message="No cached ratio found for timestamp",
            )

    def _estimate_cache_size(self) -> int:
        """
        Estimate cache memory usage in bytes.

        Rough estimation:
        - datetime key: ~56 bytes
        - Decimal value: ~48 bytes
        - dict overhead: ~24 bytes per entry
        - Total: ~128 bytes per entry

        Returns:
            Estimated cache size in bytes

        Example:
            >>> cache = VolumeCache(bars)  # 80 ratios
            >>> size = cache._estimate_cache_size()
            >>> print(f"Cache size: {size / 1024:.2f} KB")
            Cache size: 10.00 KB
        """
        bytes_per_entry = 128  # datetime + Decimal + dict overhead
        return len(self.ratios) * bytes_per_entry

    def __len__(self) -> int:
        """
        Return number of cached ratios.

        Returns:
            Number of cached volume ratios

        Example:
            >>> cache = VolumeCache(bars)
            >>> len(cache)
            80
        """
        return len(self.ratios)

    def __repr__(self) -> str:
        """
        Return string representation of cache.

        Returns:
            String with cache stats

        Example:
            >>> cache = VolumeCache(bars)
            >>> print(cache)
            VolumeCache(ratios=80, window=20, size=10.24KB)
        """
        size_kb = self._estimate_cache_size() / 1024
        return f"VolumeCache(ratios={len(self.ratios)}, window={self.window}, size={size_kb:.2f}KB)"
