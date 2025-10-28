"""
Volume Analyzer module.

This module provides functions to calculate volume-related metrics for OHLCV bars.
Primary function is calculate_volume_ratio which computes current volume / 20-bar average.
"""

from typing import List, Optional

import numpy as np
import structlog
from decimal import Decimal

from src.models.ohlcv import OHLCVBar

logger = structlog.get_logger(__name__)


def calculate_volume_ratio(bars: List[OHLCVBar], index: int) -> Optional[float]:
    """
    Calculate volume ratio: current bar volume / 20-bar average volume.

    Computes the ratio of the current bar's volume to the simple moving average
    of the previous 20 bars (excluding the current bar). This metric helps identify
    abnormal volume conditions:
    - >1.5x = Climactic volume
    - <0.6x = Low volume
    - 0.6x-1.5x = Normal volume

    Args:
        bars: List of OHLCVBar objects in chronological order
        index: Index of the bar to calculate volume ratio for

    Returns:
        Volume ratio as float, or None if:
        - Index < 20 (insufficient historical data)
        - Average volume is zero (division by zero)
        - Invalid index (out of bounds)

    Performance:
        Uses NumPy for vectorized operations. Processes 1000 bars in <10ms.

    Example:
        >>> bars = [OHLCVBar(volume=100, ...) for _ in range(20)]
        >>> bars.append(OHLCVBar(volume=200, ...))
        >>> calculate_volume_ratio(bars, 20)
        2.0
    """
    # Validate input parameters
    if not bars:
        return None
    if index < 0 or index >= len(bars):
        return None
    if index < 20:
        # Insufficient historical data for 20-bar average
        return None

    # Extract volumes from previous 20 bars (excluding current bar)
    # Using list comprehension is fast for small arrays (20 elements)
    volumes = [bars[i].volume for i in range(index - 20, index)]

    # Convert to NumPy array for vectorized operations
    volumes_array = np.array(volumes, dtype=np.float64)

    # Calculate simple moving average
    avg_volume_20 = np.mean(volumes_array)

    # Handle edge case: zero volume average (prevent division by zero)
    if avg_volume_20 == 0:
        logger.warning(
            "zero_volume_average_detected",
            symbol=bars[index].symbol,
            index=index,
            timeframe=bars[index].timeframe,
        )
        return None

    # Calculate and return volume ratio
    current_volume = float(bars[index].volume)
    volume_ratio = current_volume / avg_volume_20

    # Log warning for abnormal volume spikes (>5.0x average)
    if volume_ratio > 5.0:
        logger.warning(
            "abnormal_volume_spike_detected",
            symbol=bars[index].symbol,
            index=index,
            volume_ratio=round(volume_ratio, 4),
            current_volume=current_volume,
            avg_volume=round(avg_volume_20, 2),
            timeframe=bars[index].timeframe,
            timestamp=bars[index].timestamp.isoformat(),
        )

    return volume_ratio


def calculate_volume_ratios_batch(bars: List[OHLCVBar]) -> List[Optional[float]]:
    """
    Calculate volume ratios for all bars in a sequence using vectorized operations.

    This is a fully optimized batch processing function that processes all bars
    at once using NumPy's rolling window operations. Significantly faster than
    calling calculate_volume_ratio() in a loop.

    Performance: Processes 10,000 bars in <100ms using NumPy convolution.

    Args:
        bars: List of OHLCVBar objects in chronological order

    Returns:
        List of volume ratios (float or None) for each bar.
        First 20 elements are None (insufficient data).

    Example:
        >>> bars = [OHLCVBar(volume=100, ...) for _ in range(25)]
        >>> bars[-1].volume = 200  # Last bar has 2x volume
        >>> ratios = calculate_volume_ratios_batch(bars)
        >>> ratios[24]  # Last bar's ratio
        2.0
    """
    if not bars or len(bars) == 0:
        return []

    # Log debug info for batch processing (for first 25 bars or when explicitly enabled)
    if len(bars) <= 25:
        logger.debug(
            "batch_volume_calculation_starting",
            num_bars=len(bars),
            symbol=bars[0].symbol if bars else None,
            timeframe=bars[0].timeframe if bars else None,
        )

    # Extract all volumes into NumPy array (single pass, vectorized)
    volumes = np.array([bar.volume for bar in bars], dtype=np.float64)

    # Initialize result array with None for first 20 bars
    results: List[Optional[float]] = [None] * len(bars)

    # Calculate 20-bar rolling average using NumPy convolution
    # This is the key optimization: vectorized rolling window computation
    window_size = 20

    # Use uniform filter (moving average kernel) for rolling computation
    # np.convolve with 'valid' mode computes sum for each 20-bar window
    ones = np.ones(window_size)
    rolling_sums = np.convolve(volumes, ones, mode='valid')
    rolling_avgs = rolling_sums / window_size

    # Calculate ratios for bars with sufficient history (index >= 20)
    abnormal_count = 0
    for i in range(window_size, len(bars)):
        # rolling_avgs[i - window_size] is the average of bars[i-20:i]
        avg_volume = rolling_avgs[i - window_size]

        if avg_volume == 0:
            results[i] = None
        else:
            ratio = float(volumes[i] / avg_volume)
            results[i] = ratio

            # Track abnormal volume spikes
            if ratio > 5.0:
                abnormal_count += 1
                # Log only first few abnormal spikes to avoid log spam
                if abnormal_count <= 3:
                    logger.warning(
                        "abnormal_volume_spike_in_batch",
                        symbol=bars[i].symbol,
                        index=i,
                        volume_ratio=round(ratio, 4),
                        timestamp=bars[i].timestamp.isoformat(),
                    )

    # Log batch completion summary
    if len(bars) <= 25 or abnormal_count > 0:
        logger.debug(
            "batch_volume_calculation_completed",
            num_bars=len(bars),
            num_calculated=len([r for r in results if r is not None]),
            abnormal_spikes=abnormal_count,
        )

    return results
