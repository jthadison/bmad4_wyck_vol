"""
Pivot point detection module.

This module provides functionality to identify swing highs and swing lows (pivot points)
in price action. Pivots are used in Wyckoff analysis to discover potential support and
resistance levels that define trading range boundaries.

A pivot high is a bar whose high exceeds all highs in N bars before and after.
A pivot low is a bar whose low is below all lows in N bars before and after.
The parameter N is called the "lookback" and determines pivot sensitivity:
- Smaller lookback (e.g., 3) = more sensitive, finds more pivots
- Larger lookback (e.g., 10) = less sensitive, finds fewer, stronger pivots

Example:
    >>> from backend.src.pattern_engine.pivot_detector import detect_pivots
    >>> from backend.src.repositories.ohlcv_repository import OHLCVRepository
    >>>
    >>> repo = OHLCVRepository()
    >>> bars = repo.get_bars("AAPL", "1d", limit=252)
    >>> pivots = detect_pivots(bars, lookback=5)
    >>> print(f"Found {len(pivots)} pivots")
"""

from __future__ import annotations

from typing import List

import numpy as np
import structlog

from src.models.ohlcv import OHLCVBar
from src.models.pivot import Pivot, PivotType

logger = structlog.get_logger(__name__)


def detect_pivots(bars: List[OHLCVBar], lookback: int = 5) -> List[Pivot]:
    """
    Detect swing highs and swing lows (pivot points) in price action.

    Identifies potential support and resistance levels by finding local extrema
    in the price sequence. A pivot high is a bar whose high exceeds all highs
    in N bars before and after. A pivot low is a bar whose low is below all lows
    in N bars before and after.

    Algorithm:
        1. Validate inputs (bars not empty, sufficient data, valid lookback)
        2. Extract highs and lows into NumPy arrays for vectorized operations
        3. For each candidate bar from index lookback to len(bars)-lookback-1:
           - Check if bar.high > all highs in [i-lookback:i] and [i+1:i+lookback+1]
           - Check if bar.low < all lows in [i-lookback:i] and [i+1:i+lookback+1]
           - Create Pivot object if conditions met
        4. Return list of detected pivots

    Edge Cases:
        - First lookback bars cannot be pivots (no prior context)
        - Last lookback bars cannot be pivots (no future context)
        - Insufficient bars (< 2*lookback + 1) returns empty list
        - Flat price action (all highs/lows equal) returns empty list

    Performance:
        Optimized with NumPy vectorization to process 1000 bars in <50ms.
        Uses pre-extracted arrays and efficient array slicing.

    Args:
        bars: Sequence of OHLCV bars to analyze (must have ≥ 2*lookback+1 bars)
        lookback: Number of bars on each side to compare (default 5, range 1-100)
                  Higher values find fewer, stronger pivots

    Returns:
        List of Pivot objects, ordered by bar index (chronological)

    Raises:
        ValueError: If lookback < 1 or lookback > 100

    Example:
        >>> # Detect pivots with default 5-bar lookback
        >>> bars = ohlcv_repo.get_bars("AAPL", "1d", limit=252)
        >>> pivots = detect_pivots(bars, lookback=5)
        >>> print(f"Found {len(pivots)} pivots")
        Found 32 pivots
        >>>
        >>> # Filter for highs and lows
        >>> pivot_highs = get_pivot_highs(pivots)
        >>> pivot_lows = get_pivot_lows(pivots)
        >>> print(f"Highs: {len(pivot_highs)}, Lows: {len(pivot_lows)}")
        Highs: 16, Lows: 16
    """
    import time

    start_time = time.perf_counter()

    # Input validation
    if not bars:
        logger.warning(
            "empty_bars_list", message="Cannot detect pivots on empty bar list"
        )
        return []

    if lookback < 1:
        raise ValueError(f"lookback must be >= 1, got {lookback}")

    if lookback > 100:
        raise ValueError(f"lookback must be <= 100, got {lookback}")

    if len(bars) <= 2 * lookback:
        logger.warning(
            "insufficient_bars",
            bars_count=len(bars),
            required=2 * lookback + 1,
            message="Insufficient bars for pivot detection",
        )
        return []

    # Extract symbol for logging
    symbol = bars[0].symbol if bars else "UNKNOWN"

    logger.info(
        "pivot_detection_start",
        symbol=symbol,
        bar_count=len(bars),
        lookback=lookback,
        first_timestamp=bars[0].timestamp.isoformat(),
        last_timestamp=bars[-1].timestamp.isoformat(),
    )

    # Pre-extract highs and lows into NumPy arrays for vectorized operations
    # Convert Decimal to float for NumPy performance
    highs = np.array([float(bar.high) for bar in bars])
    lows = np.array([float(bar.low) for bar in bars])

    pivots: List[Pivot] = []

    # Loop through candidate bars (skip first and last lookback bars)
    for i in range(lookback, len(bars) - lookback):
        current_high = highs[i]
        current_low = lows[i]

        # Extract comparison windows
        highs_before = highs[i - lookback : i]
        highs_after = highs[i + 1 : i + lookback + 1]
        lows_before = lows[i - lookback : i]
        lows_after = lows[i + 1 : i + lookback + 1]

        # Check for pivot high
        if current_high > np.max(highs_before) and current_high > np.max(highs_after):
            pivot = Pivot(
                bar=bars[i],
                price=bars[i].high,  # Use original Decimal, not float
                type=PivotType.HIGH,
                strength=lookback,
                timestamp=bars[i].timestamp,
                index=i,
            )
            pivots.append(pivot)

        # Check for pivot low
        if current_low < np.min(lows_before) and current_low < np.min(lows_after):
            pivot = Pivot(
                bar=bars[i],
                price=bars[i].low,  # Use original Decimal, not float
                type=PivotType.LOW,
                strength=lookback,
                timestamp=bars[i].timestamp,
                index=i,
            )
            pivots.append(pivot)

    # Calculate execution time
    duration_ms = (time.perf_counter() - start_time) * 1000

    # Count pivot types
    pivot_highs = [p for p in pivots if p.type == PivotType.HIGH]
    pivot_lows = [p for p in pivots if p.type == PivotType.LOW]

    # Log results
    logger.info(
        "pivot_detection_complete",
        symbol=symbol,
        total_pivots=len(pivots),
        pivot_highs=len(pivot_highs),
        pivot_lows=len(pivot_lows),
        duration_ms=round(duration_ms, 2),
        bars_per_second=round(len(bars) / (duration_ms / 1000)) if duration_ms > 0 else 0,
        first_pivot_index=pivots[0].index if pivots else None,
        last_pivot_index=pivots[-1].index if pivots else None,
    )

    # Warn if no pivots found
    if not pivots:
        logger.warning(
            "no_pivots_found",
            symbol=symbol,
            bar_count=len(bars),
            lookback=lookback,
            message="No pivots detected - may indicate flat price action or insufficient volatility",
        )

    return pivots


def get_pivot_highs(pivots: List[Pivot]) -> List[Pivot]:
    """
    Filter pivots to return only HIGH pivots (resistance candidates).

    Args:
        pivots: List of Pivot objects (mixed HIGH and LOW)

    Returns:
        List of Pivot objects where type == PivotType.HIGH

    Example:
        >>> pivots = detect_pivots(bars, lookback=5)
        >>> highs = get_pivot_highs(pivots)
        >>> print(f"Found {len(highs)} resistance levels")
    """
    return [p for p in pivots if p.type == PivotType.HIGH]


def get_pivot_lows(pivots: List[Pivot]) -> List[Pivot]:
    """
    Filter pivots to return only LOW pivots (support candidates).

    Args:
        pivots: List of Pivot objects (mixed HIGH and LOW)

    Returns:
        List of Pivot objects where type == PivotType.LOW

    Example:
        >>> pivots = detect_pivots(bars, lookback=5)
        >>> lows = get_pivot_lows(pivots)
        >>> print(f"Found {len(lows)} support levels")
    """
    return [p for p in pivots if p.type == PivotType.LOW]


def get_pivot_prices(pivots: List[Pivot]) -> List[float]:
    """
    Extract pivot prices as a list of floats.

    Useful for statistical analysis, clustering, or plotting.

    Args:
        pivots: List of Pivot objects

    Returns:
        List of pivot prices as floats (converted from Decimal)

    Example:
        >>> pivots = detect_pivots(bars, lookback=5)
        >>> prices = get_pivot_prices(pivots)
        >>> avg_price = sum(prices) / len(prices)
    """
    return [float(p.price) for p in pivots]
