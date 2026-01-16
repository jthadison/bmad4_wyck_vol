"""
Consolidation Detector - Story 18.11.2

Purpose:
--------
Detects consolidation zones in price data for exit strategy refinement.
Identifies periods where price trades in a narrow range with declining volume.

This is Part 2 of refactoring exit_logic_refinements.py (CF-008).
Extracts consolidation detection into independently testable module.

Classes:
--------
- ConsolidationConfig: Configuration for consolidation detection thresholds
- ConsolidationZone: Detected consolidation zone with metrics
- ConsolidationDetector: Consolidation detection engine

Author: Story 18.11.2
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from src.models.ohlcv import OHLCVBar


@dataclass
class ConsolidationConfig:
    """
    Configuration for consolidation detection.

    Attributes:
    -----------
    min_bars : int
        Minimum number of bars required to form consolidation (default: 5)
    max_range_pct : Decimal
        Maximum price range as percentage of price to qualify as consolidation
        (default: 0.02 = 2%)
    volume_decline_threshold : Decimal
        Ratio below which average volume indicates declining volume
        (default: 0.7 = 30% below overall average)
    """

    min_bars: int = 5
    max_range_pct: Decimal = Decimal("0.02")
    volume_decline_threshold: Decimal = Decimal("0.7")


@dataclass
class ConsolidationZone:
    """
    Detected consolidation zone with boundaries and metrics.

    Attributes:
    -----------
    start_index : int
        Starting index of consolidation in bar list
    end_index : int
        Ending index of consolidation in bar list
    high : Decimal
        Highest price in consolidation zone
    low : Decimal
        Lowest price in consolidation zone
    avg_volume : Decimal
        Average volume during consolidation
    """

    start_index: int
    end_index: int
    high: Decimal
    low: Decimal
    avg_volume: Decimal


class ConsolidationDetector:
    """
    Detect consolidation zones in price data.

    Consolidation is identified by:
    1. Sufficient number of bars (min_bars)
    2. Narrow price range (max_range_pct)
    3. Declining volume (volume_decline_threshold)

    Example:
    --------
    >>> config = ConsolidationConfig(min_bars=5, max_range_pct=Decimal("0.02"))
    >>> detector = ConsolidationDetector(config)
    >>> zone = detector.detect_consolidation(bars, start_index=10)
    >>> if zone:
    ...     print(f"Consolidation from {zone.start_index} to {zone.end_index}")
    """

    def __init__(self, config: Optional[ConsolidationConfig] = None):
        """
        Initialize consolidation detector.

        Parameters:
        -----------
        config : ConsolidationConfig | None
            Configuration settings (uses defaults if None)
        """
        self._config = config or ConsolidationConfig()

    def detect_consolidation(
        self,
        bars: list[OHLCVBar],
        start_index: int,
    ) -> Optional[ConsolidationZone]:
        """
        Detect consolidation zone starting at specified index.

        Evaluates bars from start_index onwards to identify if they form
        a consolidation pattern based on configured thresholds.

        Parameters:
        -----------
        bars : List[OHLCVBar]
            List of price bars to analyze
        start_index : int
            Index to begin consolidation detection

        Returns:
        --------
        ConsolidationZone | None
            Detected consolidation zone if found, None otherwise

        Example:
        --------
        >>> zone = detector.detect_consolidation(bars, 10)
        >>> if zone:
        ...     range_pct = (zone.high - zone.low) / zone.low
        ...     print(f"Range: {range_pct:.2%}")
        """
        if not self._has_sufficient_bars(bars, start_index):
            return None

        window = bars[start_index:]

        if not self._is_range_narrow(window):
            return None

        if not self._is_volume_declining(window):
            return None

        return self._build_zone(window, start_index)

    def _has_sufficient_bars(self, bars: list[OHLCVBar], start_index: int) -> bool:
        """
        Check if sufficient bars exist from start_index.

        Parameters:
        -----------
        bars : List[OHLCVBar]
            Full bar list
        start_index : int
            Starting index

        Returns:
        --------
        bool
            True if enough bars available
        """
        available_bars = len(bars) - start_index
        return available_bars >= self._config.min_bars

    def _is_range_narrow(self, window: list[OHLCVBar]) -> bool:
        """
        Check if price range is narrow enough for consolidation.

        Calculates the percentage range (high - low) / low and compares
        against configured threshold.

        Parameters:
        -----------
        window : List[OHLCVBar]
            Bars to analyze (from start_index onwards)

        Returns:
        --------
        bool
            True if range is narrow enough
        """
        if not window:
            return False

        # Get min_bars window for analysis
        analysis_window = window[: self._config.min_bars]

        high = max(bar.high for bar in analysis_window)
        low = min(bar.low for bar in analysis_window)

        if low == Decimal("0"):
            return False

        range_pct = (high - low) / low
        return range_pct <= self._config.max_range_pct

    def _is_volume_declining(self, window: list[OHLCVBar]) -> bool:
        """
        Check if volume is declining during consolidation.

        Uses volume_ratio field from OHLCV bars (current volume / 20-bar avg).
        Volume is considered declining if average volume_ratio is below threshold.

        Parameters:
        -----------
        window : List[OHLCVBar]
            Bars to analyze

        Returns:
        --------
        bool
            True if volume is declining
        """
        if not window or len(window) < self._config.min_bars:
            return False

        # Get min_bars window for analysis
        analysis_window = window[: self._config.min_bars]

        # Use volume_ratio field if available, otherwise calculate manually
        if hasattr(analysis_window[0], "volume_ratio"):
            # Average volume_ratio across consolidation window
            avg_volume_ratio = sum(bar.volume_ratio for bar in analysis_window) / Decimal(
                len(analysis_window)
            )
            return avg_volume_ratio <= self._config.volume_decline_threshold

        # Fallback: Manual calculation if volume_ratio not available
        # Compare recent bars (last half) vs earlier bars (first half)
        mid_point = len(analysis_window) // 2
        if mid_point == 0:
            mid_point = 1

        first_half = analysis_window[:mid_point]
        second_half = analysis_window[mid_point:]

        first_half_avg = sum(bar.volume for bar in first_half) / len(first_half)
        second_half_avg = sum(bar.volume for bar in second_half) / len(second_half)

        if first_half_avg == 0:
            return False

        decline_ratio = Decimal(second_half_avg) / Decimal(first_half_avg)
        return decline_ratio <= self._config.volume_decline_threshold

    def _build_zone(self, window: list[OHLCVBar], start_index: int) -> ConsolidationZone:
        """
        Build ConsolidationZone from detected consolidation.

        Parameters:
        -----------
        window : List[OHLCVBar]
            Consolidation bars
        start_index : int
            Starting index in original bar list

        Returns:
        --------
        ConsolidationZone
            Zone with boundaries and metrics
        """
        analysis_window = window[: self._config.min_bars]

        high = max(bar.high for bar in analysis_window)
        low = min(bar.low for bar in analysis_window)
        avg_volume = Decimal(sum(bar.volume for bar in analysis_window)) / Decimal(
            len(analysis_window)
        )

        return ConsolidationZone(
            start_index=start_index,
            end_index=start_index + len(analysis_window) - 1,
            high=high,
            low=low,
            avg_volume=avg_volume,
        )
