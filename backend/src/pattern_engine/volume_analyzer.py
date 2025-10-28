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


def calculate_spread_ratio(bars: List[OHLCVBar], index: int) -> Optional[float]:
    """
    Calculate spread ratio: current bar spread / 20-bar average spread.

    Computes the ratio of the current bar's spread (high - low) to the simple moving
    average of the previous 20 bars' spreads (excluding the current bar). This metric
    helps identify volatility changes:
    - >2.0x = Wide spread (climactic action, breakout)
    - <0.5x = Narrow spread (absorption, consolidation)
    - 0.6x-1.5x = Normal spread

    Args:
        bars: List of OHLCVBar objects in chronological order
        index: Index of the bar to calculate spread ratio for

    Returns:
        Spread ratio as float, or None if:
        - Index < 20 (insufficient historical data)
        - Invalid index (out of bounds)
        Returns 0.0 if:
        - Average spread is zero (all bars have same high/low)
        - Current bar has zero spread (high == low)

    Performance:
        Uses NumPy for vectorized operations. Processes 1000 bars in <10ms.

    Example:
        >>> bars = [OHLCVBar(high=110, low=100, ...) for _ in range(20)]  # spread=10
        >>> bars.append(OHLCVBar(high=120, low=100, ...))  # spread=20
        >>> calculate_spread_ratio(bars, 20)
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

    # Calculate current bar spread
    current_bar = bars[index]
    current_spread = float(current_bar.high - current_bar.low)

    # Handle edge case: current bar has zero spread (high == low)
    if current_spread == 0:
        return 0.0

    # Extract spreads from previous 20 bars (excluding current bar)
    # Using list comprehension for small arrays (20 elements)
    spreads = [float(bars[i].high - bars[i].low) for i in range(index - 20, index)]

    # Convert to NumPy array for vectorized operations
    spreads_array = np.array(spreads, dtype=np.float64)

    # Calculate simple moving average
    avg_spread_20 = np.mean(spreads_array)

    # Handle edge case: zero spread average (all bars have same high/low)
    if avg_spread_20 == 0:
        logger.warning(
            "zero_spread_average_detected",
            symbol=bars[index].symbol,
            index=index,
            timeframe=bars[index].timeframe,
        )
        return 0.0

    # Calculate and return spread ratio
    spread_ratio = current_spread / avg_spread_20

    # Log warning for abnormally wide spreads (>3.0x average)
    if spread_ratio > 3.0:
        logger.warning(
            "abnormal_spread_detected",
            symbol=bars[index].symbol,
            index=index,
            spread_ratio=round(spread_ratio, 4),
            current_spread=round(current_spread, 8),
            avg_spread=round(avg_spread_20, 8),
            timeframe=bars[index].timeframe,
            timestamp=bars[index].timestamp.isoformat(),
        )

    return spread_ratio


def calculate_spread_ratios_batch(bars: List[OHLCVBar]) -> List[Optional[float]]:
    """
    Calculate spread ratios for all bars in a sequence using vectorized operations.

    This is a fully optimized batch processing function that processes all bars
    at once using NumPy's rolling window operations. Significantly faster than
    calling calculate_spread_ratio() in a loop.

    Performance: Processes 10,000 bars in <100ms using NumPy convolution.

    Args:
        bars: List of OHLCVBar objects in chronological order

    Returns:
        List of spread ratios (float or None) for each bar.
        First 20 elements are None (insufficient data).
        Returns 0.0 for bars with zero spread or zero spread average.

    Example:
        >>> bars = [OHLCVBar(high=110, low=100, ...) for _ in range(25)]  # spread=10
        >>> bars[-1].high = 120  # Last bar has spread=20
        >>> ratios = calculate_spread_ratios_batch(bars)
        >>> ratios[24]  # Last bar's ratio
        2.0
    """
    if not bars or len(bars) == 0:
        return []

    # Log debug info for batch processing
    if len(bars) <= 25:
        logger.debug(
            "batch_spread_calculation_starting",
            num_bars=len(bars),
            symbol=bars[0].symbol if bars else None,
            timeframe=bars[0].timeframe if bars else None,
        )

    # Extract all highs and lows into NumPy arrays (single pass, vectorized)
    highs = np.array([float(bar.high) for bar in bars], dtype=np.float64)
    lows = np.array([float(bar.low) for bar in bars], dtype=np.float64)

    # Calculate spreads vectorized: spreads = highs - lows
    spreads = np.subtract(highs, lows)

    # Initialize result array with None for first 20 bars
    results: List[Optional[float]] = [None] * len(bars)

    # Calculate 20-bar rolling average using NumPy convolution
    window_size = 20

    # Use uniform filter (moving average kernel) for rolling computation
    ones = np.ones(window_size)
    rolling_sums = np.convolve(spreads, ones, mode='valid')
    rolling_avgs = rolling_sums / window_size

    # Calculate ratios for bars with sufficient history (index >= 20)
    abnormal_count = 0
    zero_spread_count = 0

    for i in range(window_size, len(bars)):
        current_spread = spreads[i]

        # Handle zero current spread
        if current_spread == 0:
            results[i] = 0.0
            zero_spread_count += 1
            continue

        # rolling_avgs[i - window_size] is the average of bars[i-20:i]
        avg_spread = rolling_avgs[i - window_size]

        if avg_spread == 0:
            results[i] = 0.0
            zero_spread_count += 1
        else:
            ratio = float(current_spread / avg_spread)
            results[i] = ratio

            # Track abnormally wide spreads
            if ratio > 3.0:
                abnormal_count += 1
                # Log only first few abnormal spreads to avoid log spam
                if abnormal_count <= 3:
                    logger.warning(
                        "abnormal_spread_in_batch",
                        symbol=bars[i].symbol,
                        index=i,
                        spread_ratio=round(ratio, 4),
                        timestamp=bars[i].timestamp.isoformat(),
                    )

    # Log batch completion summary
    if len(bars) <= 25 or abnormal_count > 0 or zero_spread_count > 0:
        logger.debug(
            "batch_spread_calculation_completed",
            num_bars=len(bars),
            num_calculated=len([r for r in results if r is not None]),
            abnormal_spreads=abnormal_count,
            zero_spreads=zero_spread_count,
        )

    return results


def calculate_close_position(bar: OHLCVBar) -> float:
    """
    Calculate close position: where the bar closed within its range.

    Computes the position of the close within the bar's range (high to low).
    This metric indicates buying vs. selling pressure:
    - 0.0 = Closed at low (maximum selling pressure)
    - 1.0 = Closed at high (maximum buying pressure)
    - 0.5 = Closed at midpoint (neutral/balanced pressure)

    Wyckoff Interpretation:
    - >= 0.7: Strong buying pressure (bullish)
    - <= 0.3: Strong selling pressure (bearish)
    - 0.4-0.6: Neutral/balanced pressure

    Pattern Applications:
    - Springs should close high (>= 0.7) to be valid
    - UTAD should close low (<= 0.3) to be valid
    - High volume + narrow spread + close >= 0.7 = Bullish absorption
    - High volume + narrow spread + close <= 0.3 = Bearish distribution

    Args:
        bar: OHLCVBar object to analyze

    Returns:
        Close position as float in range [0.0, 1.0]
        Returns 0.5 (neutral) if high == low (zero spread/doji bar)

    Performance:
        Simple arithmetic operation, executes in <1µs per bar.

    Example:
        >>> bar = OHLCVBar(high=Decimal('100'), low=Decimal('90'), close=Decimal('95'), ...)
        >>> calculate_close_position(bar)
        0.5
        >>> bar = OHLCVBar(high=Decimal('100'), low=Decimal('90'), close=Decimal('100'), ...)
        >>> calculate_close_position(bar)
        1.0
    """
    # Validate input
    if bar is None:
        raise ValueError("Bar parameter cannot be None")

    # Extract values and convert to float for calculation
    close = float(bar.close)
    high = float(bar.high)
    low = float(bar.low)

    # Calculate spread
    spread = high - low

    # Handle edge case: zero spread (doji bar, high == low)
    if spread == 0:
        logger.debug(
            "zero_spread_bar",
            symbol=bar.symbol,
            timestamp=bar.timestamp.isoformat(),
            price=close,
            message="Doji bar detected (high == low), returning neutral position 0.5"
        )
        return 0.5

    # Validate data integrity: close should be within [low, high]
    if not (low <= close <= high):
        logger.warning(
            "invalid_close_position_data",
            symbol=bar.symbol,
            timestamp=bar.timestamp.isoformat(),
            close=close,
            low=low,
            high=high,
            message="Close is outside [low, high] range, data quality issue. Clamping value."
        )
        # Clamp close to [low, high] range
        close = max(low, min(close, high))

    # Calculate close position
    close_position = (close - low) / spread

    # Ensure result is in valid range [0.0, 1.0]
    # This should always be true after clamping, but we validate to be safe
    close_position = max(0.0, min(1.0, close_position))

    return close_position


def calculate_close_positions_batch(bars: List[OHLCVBar]) -> List[float]:
    """
    Calculate close positions for all bars in a sequence using vectorized operations.

    This is an optimized batch processing function that processes all bars
    at once using NumPy's vectorized operations. Much faster than calling
    calculate_close_position() in a loop.

    Performance: Processes 10,000 bars in <5ms using NumPy vectorization.

    Args:
        bars: List of OHLCVBar objects in chronological order

    Returns:
        List of close positions (float) for each bar, all in range [0.0, 1.0].
        Zero spread bars return 0.5 (neutral).

    Example:
        >>> bars = [
        ...     OHLCVBar(high=Decimal('100'), low=Decimal('90'), close=Decimal('95'), ...),
        ...     OHLCVBar(high=Decimal('110'), low=Decimal('100'), close=Decimal('110'), ...)
        ... ]
        >>> positions = calculate_close_positions_batch(bars)
        >>> positions
        [0.5, 1.0]
    """
    if not bars or len(bars) == 0:
        return []

    # Log debug info for batch processing
    if len(bars) <= 25:
        logger.debug(
            "batch_close_position_calculation_starting",
            num_bars=len(bars),
            symbol=bars[0].symbol if bars else None,
            timeframe=bars[0].timeframe if bars else None,
        )

    # Extract all highs, lows, and closes into NumPy arrays (vectorized)
    highs = np.array([float(bar.high) for bar in bars], dtype=np.float64)
    lows = np.array([float(bar.low) for bar in bars], dtype=np.float64)
    closes = np.array([float(bar.close) for bar in bars], dtype=np.float64)

    # Calculate spreads vectorized: spreads = highs - lows
    spreads = np.subtract(highs, lows)

    # Initialize results array with neutral values (0.5)
    results = np.full(len(bars), 0.5, dtype=np.float64)

    # Find bars with non-zero spread
    non_zero_mask = spreads != 0

    # Calculate close positions only for non-zero spread bars (vectorized)
    # close_position = (close - low) / spread
    results[non_zero_mask] = (closes[non_zero_mask] - lows[non_zero_mask]) / spreads[non_zero_mask]

    # Clamp all values to [0.0, 1.0] range (handles any data integrity issues)
    results = np.clip(results, 0.0, 1.0)

    # Count zero spread bars for logging
    zero_spread_count = np.sum(~non_zero_mask)

    # Count bars with data integrity issues (close outside [low, high])
    # This check is done BEFORE clamping, so we need to recalculate
    invalid_data_mask = (closes < lows) | (closes > highs)
    invalid_data_count = np.sum(invalid_data_mask)

    if invalid_data_count > 0:
        logger.warning(
            "invalid_close_position_data_in_batch",
            num_bars=len(bars),
            invalid_count=int(invalid_data_count),
            message=f"Found {invalid_data_count} bars with close outside [low, high] range. Values clamped."
        )

    # Log batch completion summary
    if len(bars) <= 25 or zero_spread_count > 0 or invalid_data_count > 0:
        logger.debug(
            "batch_close_position_calculation_completed",
            num_bars=len(bars),
            zero_spreads=int(zero_spread_count),
            invalid_data=int(invalid_data_count),
        )

    return results.tolist()
