"""
BarSequence Interface (Story 12.1 Task 10).

Provides abstraction for accessing historical bars to prevent look-ahead bias
in pattern detection. Ensures pattern detectors only see historical data up to
the current bar index.

Author: Story 12.1 Task 10
"""

from abc import ABC, abstractmethod
from typing import Optional

from src.models.ohlcv import OHLCVBar


class BarSequence(ABC):
    """
    Abstract interface for accessing OHLCV bars sequentially.

    Prevents look-ahead bias by controlling which bars pattern detectors can access.
    Two implementations:
    - LiveBarSequence: Real-time bars from market data service
    - BacktestBarSequence: Historical bars with chronological access enforcement

    AC6: Pattern detectors receive ONLY historical bars up to current bar index.

    Example:
        # In backtest
        sequence = BacktestBarSequence(bars, current_index=50)
        historical_bars = sequence.get_bars(0, 50)  # Only bars[0:51]
        current_bar = sequence.get_bar(50)

        # Attempting to access future data raises error
        future_bar = sequence.get_bar(51)  # Raises IndexError
    """

    @abstractmethod
    def get_bars(self, start_index: int, end_index: int) -> list[OHLCVBar]:
        """
        Get a slice of bars from start_index to end_index (inclusive).

        Args:
            start_index: Starting index (0-based)
            end_index: Ending index (inclusive)

        Returns:
            List of OHLCV bars

        Raises:
            IndexError: If indices are out of bounds or access future data
        """
        pass

    @abstractmethod
    def get_bar(self, index: int) -> Optional[OHLCVBar]:
        """
        Get a single bar at the specified index.

        Args:
            index: Bar index (0-based)

        Returns:
            OHLCVBar if exists, None otherwise

        Raises:
            IndexError: If index accesses future data (in backtest mode)
        """
        pass

    @abstractmethod
    def length(self) -> int:
        """
        Get the number of accessible bars.

        Returns:
            Number of bars available
        """
        pass

    @abstractmethod
    def current_index(self) -> int:
        """
        Get the current bar index (0-based).

        In backtest mode, this is the current bar being processed.
        In live mode, this is the most recent bar received.

        Returns:
            Current bar index
        """
        pass


class BacktestBarSequence(BarSequence):
    """
    Backtest implementation of BarSequence.

    Enforces chronological access - only returns bars up to current_index.
    Prevents look-ahead bias by raising IndexError on future data access.

    AC6 Subtask 10.5: BacktestBarSequence only returns bars[0:current_index+1].

    Example:
        bars = [bar0, bar1, bar2, bar3, bar4]
        sequence = BacktestBarSequence(bars, current_index=2)

        # Valid access (historical data)
        sequence.get_bar(0)  # bar0
        sequence.get_bar(2)  # bar2 (current)
        sequence.get_bars(0, 2)  # [bar0, bar1, bar2]

        # Invalid access (future data) - raises IndexError
        sequence.get_bar(3)  # IndexError!
        sequence.get_bars(0, 4)  # IndexError!
    """

    def __init__(self, bars: list[OHLCVBar], current_index: int):
        """
        Initialize backtest bar sequence.

        Args:
            bars: Complete list of historical bars
            current_index: Current bar index being processed (0-based)

        Raises:
            ValueError: If current_index is out of bounds
        """
        if not bars:
            raise ValueError("Cannot create BarSequence with empty bar list")

        if current_index < 0 or current_index >= len(bars):
            raise ValueError(f"current_index {current_index} out of bounds (0-{len(bars)-1})")

        self._bars = bars
        self._current_index = current_index

    def get_bars(self, start_index: int, end_index: int) -> list[OHLCVBar]:
        """
        Get bars from start to end (inclusive).

        AC6: Only returns bars up to current_index (no future data).

        Args:
            start_index: Starting index (0-based)
            end_index: Ending index (inclusive)

        Returns:
            List of OHLCV bars

        Raises:
            IndexError: If end_index > current_index (future data access)
            ValueError: If start_index > end_index

        Example:
            sequence = BacktestBarSequence(bars, current_index=10)
            historical = sequence.get_bars(0, 10)  # Valid
            future = sequence.get_bars(0, 11)  # IndexError!
        """
        if start_index > end_index:
            raise ValueError(f"start_index ({start_index}) must be <= end_index ({end_index})")

        if end_index > self._current_index:
            raise IndexError(
                f"Cannot access bar at index {end_index} (future data). "
                f"Current index is {self._current_index}. "
                f"This would cause look-ahead bias!"
            )

        if start_index < 0:
            raise IndexError(f"start_index ({start_index}) cannot be negative")

        # Return slice (end_index+1 because slicing is exclusive on end)
        return self._bars[start_index : end_index + 1]

    def get_bar(self, index: int) -> Optional[OHLCVBar]:
        """
        Get a single bar at index.

        AC6: Only returns bars up to current_index.

        Args:
            index: Bar index (0-based)

        Returns:
            OHLCVBar if exists, None otherwise

        Raises:
            IndexError: If index > current_index (future data access)

        Example:
            sequence = BacktestBarSequence(bars, current_index=5)
            bar = sequence.get_bar(3)  # Valid
            future_bar = sequence.get_bar(6)  # IndexError!
        """
        if index > self._current_index:
            raise IndexError(
                f"Cannot access bar at index {index} (future data). "
                f"Current index is {self._current_index}. "
                f"This would cause look-ahead bias!"
            )

        if index < 0 or index >= len(self._bars):
            return None

        return self._bars[index]

    def length(self) -> int:
        """
        Get number of accessible bars (up to current_index).

        Returns:
            Number of bars accessible (current_index + 1)

        Example:
            sequence = BacktestBarSequence(bars, current_index=10)
            sequence.length()  # Returns 11 (bars 0-10)
        """
        return self._current_index + 1

    def current_index(self) -> int:
        """
        Get current bar index.

        Returns:
            Current bar index (0-based)
        """
        return self._current_index


class LiveBarSequence(BarSequence):
    """
    Live trading implementation of BarSequence.

    Returns all bars received from market data service up to the current moment.
    No look-ahead bias possible since future bars don't exist yet.

    AC6 Subtask 10.3: LiveBarSequence for real-time bars from market data service.

    Example:
        # Market data service provides bars as they arrive
        bars = [bar0, bar1, bar2]  # Received so far
        sequence = LiveBarSequence(bars)

        # Can access all received bars
        all_bars = sequence.get_bars(0, 2)  # [bar0, bar1, bar2]
        latest = sequence.get_bar(2)  # bar2

        # Future bars don't exist yet
        future = sequence.get_bar(3)  # Returns None (not received yet)
    """

    def __init__(self, bars: list[OHLCVBar]):
        """
        Initialize live bar sequence.

        Args:
            bars: List of bars received so far from market data
        """
        self._bars = bars

    def get_bars(self, start_index: int, end_index: int) -> list[OHLCVBar]:
        """
        Get bars from start to end (inclusive).

        Args:
            start_index: Starting index (0-based)
            end_index: Ending index (inclusive)

        Returns:
            List of OHLCV bars

        Raises:
            ValueError: If start_index > end_index
            IndexError: If indices are out of bounds
        """
        if start_index > end_index:
            raise ValueError(f"start_index ({start_index}) must be <= end_index ({end_index})")

        if start_index < 0 or end_index >= len(self._bars):
            raise IndexError(
                f"Index out of bounds: start={start_index}, end={end_index}, length={len(self._bars)}"
            )

        return self._bars[start_index : end_index + 1]

    def get_bar(self, index: int) -> Optional[OHLCVBar]:
        """
        Get a single bar at index.

        Args:
            index: Bar index (0-based)

        Returns:
            OHLCVBar if exists, None if not yet received
        """
        if index < 0 or index >= len(self._bars):
            return None

        return self._bars[index]

    def length(self) -> int:
        """
        Get number of bars received so far.

        Returns:
            Number of bars available
        """
        return len(self._bars)

    def current_index(self) -> int:
        """
        Get index of most recent bar.

        Returns:
            Index of latest bar (length - 1)
        """
        return len(self._bars) - 1 if self._bars else -1
