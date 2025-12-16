"""
VSA (Volume Spread Analysis) Detector Service (Task 6)

Purpose:
--------
Detects and counts VSA events (No Demand, No Supply, Stopping Volume) for pattern
performance analytics. These events indicate supply/demand imbalances critical for
Wyckoff methodology.

VSA Events Detected:
--------------------
1. No Demand:
   - High volume (>1.5x 20-bar SMA)
   - Narrow spread (<0.5x average)
   - Down close (close < open)
   - Context: Uptrend resistance (sellers absorbing demand)

2. No Supply:
   - High volume (>1.5x 20-bar SMA)
   - Narrow spread (<0.5x average)
   - Up close (close > open)
   - Context: Downtrend support (buyers absorbing supply)

3. Stopping Volume:
   - Climactic volume (>2.5x 20-bar SMA)
   - Wide spread initially → narrow on next bar
   - Reversal signal (down bar → up bar, or vice versa)
   - Context: Support/resistance level

Integration:
------------
- Story 11.9 Task 6: VSA metrics detection
- Stores event counts in patterns.vsa_events JSONB column
- Used by AnalyticsRepository.get_vsa_metrics()

Author: Story 11.9 Task 6
"""

from typing import Optional

import numpy as np

from src.analysis.vsa_helpers import VSA_THRESHOLDS
from src.models.ohlcv import OHLCVBar


class VSADetector:
    """
    Detects VSA events in price/volume data.

    Methods:
    --------
    - detect_no_demand: Identify No Demand bars
    - detect_no_supply: Identify No Supply bars
    - detect_stopping_volume: Identify Stopping Volume bars
    - analyze_bars: Run all detectors on bar sequence
    """

    def __init__(self, lookback_period: int = 20):
        """
        Initialize VSA detector.

        Args:
            lookback_period: Period for calculating moving averages (default 20 bars)
        """
        self.lookback_period = lookback_period

    def _calculate_averages(self, bars: list[OHLCVBar]) -> tuple[float, float]:
        """
        Calculate average volume and spread over lookback period.

        Args:
            bars: List of OHLCV bars (must have >= lookback_period bars)

        Returns:
            Tuple of (avg_volume, avg_spread)
        """
        if len(bars) < self.lookback_period:
            raise ValueError(f"Need at least {self.lookback_period} bars, got {len(bars)}")

        recent_bars = bars[-self.lookback_period :]

        volumes = [float(bar.volume) for bar in recent_bars]
        spreads = [float(bar.high - bar.low) for bar in recent_bars]

        avg_volume = np.mean(volumes)
        avg_spread = np.mean(spreads)

        return avg_volume, avg_spread

    def detect_no_demand(
        self,
        bar: OHLCVBar,
        avg_volume: float,
        avg_spread: float,
        in_uptrend: bool = True,
    ) -> bool:
        """
        Detect No Demand bar.

        No Demand indicates sellers are absorbing buying pressure at resistance.
        Typically seen in uptrends near resistance levels.

        Criteria:
        ---------
        1. Volume > 1.5x average (high effort)
        2. Spread < 0.5x average (low result - narrow spread)
        3. Close < Open (down close)
        4. Context: Uptrend or at resistance

        Args:
            bar: Bar to analyze
            avg_volume: Average volume over lookback period
            avg_spread: Average spread over lookback period
            in_uptrend: True if in uptrend context (default True)

        Returns:
            True if No Demand detected

        Example:
            >>> detector = VSADetector()
            >>> is_no_demand = detector.detect_no_demand(bar, avg_vol, avg_spread)
        """
        volume_ratio = float(bar.volume) / avg_volume
        spread = float(bar.high - bar.low)
        spread_ratio = spread / avg_spread if avg_spread > 0 else 0

        # Check criteria
        high_volume = volume_ratio > VSA_THRESHOLDS["high_volume"]
        narrow_spread = spread_ratio < 0.5
        down_close = bar.close < bar.open

        # No Demand requires all criteria + uptrend context
        return high_volume and narrow_spread and down_close and in_uptrend

    def detect_no_supply(
        self,
        bar: OHLCVBar,
        avg_volume: float,
        avg_spread: float,
        in_downtrend: bool = True,
    ) -> bool:
        """
        Detect No Supply bar.

        No Supply indicates buyers are absorbing selling pressure at support.
        Typically seen in downtrends near support levels.

        Criteria:
        ---------
        1. Volume > 1.5x average (high effort)
        2. Spread < 0.5x average (low result - narrow spread)
        3. Close > Open (up close)
        4. Context: Downtrend or at support

        Args:
            bar: Bar to analyze
            avg_volume: Average volume
            avg_spread: Average spread
            in_downtrend: True if in downtrend context (default True)

        Returns:
            True if No Supply detected

        Example:
            >>> is_no_supply = detector.detect_no_supply(bar, avg_vol, avg_spread)
        """
        volume_ratio = float(bar.volume) / avg_volume
        spread = float(bar.high - bar.low)
        spread_ratio = spread / avg_spread if avg_spread > 0 else 0

        # Check criteria
        high_volume = volume_ratio > VSA_THRESHOLDS["high_volume"]
        narrow_spread = spread_ratio < 0.5
        up_close = bar.close > bar.open

        # No Supply requires all criteria + downtrend context
        return high_volume and narrow_spread and up_close and in_downtrend

    def detect_stopping_volume(
        self,
        current_bar: OHLCVBar,
        previous_bar: Optional[OHLCVBar],
        avg_volume: float,
        avg_spread: float,
    ) -> bool:
        """
        Detect Stopping Volume.

        Stopping Volume indicates a reversal - professionals stepping in to stop
        the current move. Characterized by climactic volume followed by reversal.

        Criteria:
        ---------
        1. Previous bar: Climactic volume (>2.5x average) + wide spread
        2. Current bar: Reversal in direction (down→up or up→down)
        3. Current bar: Narrower spread than previous
        4. Context: Support or resistance level

        Args:
            current_bar: Current bar
            previous_bar: Previous bar (None if first bar)
            avg_volume: Average volume
            avg_spread: Average spread

        Returns:
            True if Stopping Volume detected

        Example:
            >>> is_stopping = detector.detect_stopping_volume(
            ...     bar, prev_bar, avg_vol, avg_spread
            ... )
        """
        if previous_bar is None:
            return False

        # Check previous bar for climactic volume
        prev_volume_ratio = float(previous_bar.volume) / avg_volume
        prev_spread = float(previous_bar.high - previous_bar.low)
        curr_spread = float(current_bar.high - current_bar.low)

        climactic_volume = prev_volume_ratio > 2.5  # Ultra-high volume

        # Wide spread on previous bar
        wide_spread = prev_spread > avg_spread

        # Narrowing spread on current bar
        narrowing = curr_spread < prev_spread

        # Reversal in direction
        prev_down = previous_bar.close < previous_bar.open
        curr_up = current_bar.close > current_bar.open
        prev_up = previous_bar.close > previous_bar.open
        curr_down = current_bar.close < current_bar.open

        reversal = (prev_down and curr_up) or (prev_up and curr_down)

        # Stopping Volume requires all criteria
        return climactic_volume and wide_spread and narrowing and reversal

    def analyze_bars(
        self,
        bars: list[OHLCVBar],
        in_uptrend: bool = True,
    ) -> dict[str, int]:
        """
        Analyze a sequence of bars for all VSA events.

        Runs all detectors and counts occurrences of each event type.
        This is the main entry point for VSA analysis.

        Args:
            bars: List of OHLCV bars (minimum lookback_period + 1 bars)
            in_uptrend: True if in uptrend, False if downtrend

        Returns:
            Dictionary with event counts:
            {
                "no_demand": int,
                "no_supply": int,
                "stopping_volume": int
            }

        Example:
            >>> detector = VSADetector(lookback_period=20)
            >>> bars = [...] # List of OHLCVBar objects
            >>> events = detector.analyze_bars(bars, in_uptrend=True)
            >>> print(f"No Demand events: {events['no_demand']}")

        Raises:
            ValueError: If bars list is too short (< lookback_period + 1)
        """
        if len(bars) < self.lookback_period + 1:
            raise ValueError(
                f"Need at least {self.lookback_period + 1} bars for VSA analysis, "
                f"got {len(bars)}"
            )

        event_counts = {
            "no_demand": 0,
            "no_supply": 0,
            "stopping_volume": 0,
        }

        # Analyze each bar after lookback period
        for i in range(self.lookback_period, len(bars)):
            # Calculate averages from previous bars
            avg_volume, avg_spread = self._calculate_averages(bars[:i])

            current_bar = bars[i]
            previous_bar = bars[i - 1] if i > 0 else None

            # Detect No Demand (uptrend context)
            if in_uptrend and self.detect_no_demand(
                current_bar, avg_volume, avg_spread, in_uptrend=True
            ):
                event_counts["no_demand"] += 1

            # Detect No Supply (downtrend context)
            if not in_uptrend and self.detect_no_supply(
                current_bar, avg_volume, avg_spread, in_downtrend=True
            ):
                event_counts["no_supply"] += 1

            # Detect Stopping Volume (any trend)
            if self.detect_stopping_volume(current_bar, previous_bar, avg_volume, avg_spread):
                event_counts["stopping_volume"] += 1

        return event_counts

    @staticmethod
    def format_vsa_events_for_db(event_counts: dict[str, int]) -> dict:
        """
        Format VSA event counts for storage in patterns.vsa_events JSONB column.

        Args:
            event_counts: Dictionary from analyze_bars()

        Returns:
            JSONB-compatible dictionary

        Example:
            >>> events = detector.analyze_bars(bars)
            >>> db_format = VSADetector.format_vsa_events_for_db(events)
            >>> # Store in patterns.vsa_events column
            >>> pattern.vsa_events = db_format
        """
        return {
            "no_demand": event_counts.get("no_demand", 0),
            "no_supply": event_counts.get("no_supply", 0),
            "stopping_volume": event_counts.get("stopping_volume", 0),
        }
