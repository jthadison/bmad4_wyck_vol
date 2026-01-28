"""
Priority queue for symbol bar processing (Story 19.23).

Implements a priority-based bar queue that processes high-priority symbols
before medium and low priority during periods of congestion.

Priority ordering:
- HIGH (1): Processed first during congestion
- MEDIUM (2): Default priority, standard processing
- LOW (3): Processed last during congestion
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import IntEnum
from heapq import heappop, heappush
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.ohlcv import OHLCVBar


class Priority(IntEnum):
    """Symbol processing priority levels."""

    HIGH = 1
    MEDIUM = 2
    LOW = 3


class QueueEmpty(Exception):
    """Raised when attempting to get from an empty queue."""

    pass


@dataclass(order=True)
class PrioritizedBar:
    """
    A bar with priority for heap-based ordering.

    Ordering is by (priority, timestamp) so that:
    - Higher priority bars (lower number) are processed first
    - Within same priority, FIFO order is maintained via timestamp
    """

    priority: int
    timestamp: float = field(compare=True)
    symbol: str = field(compare=False)
    bar: OHLCVBar = field(compare=False)


class PriorityBarQueue:
    """
    Thread-safe priority queue for OHLCV bars.

    Processes bars in priority order (HIGH > MEDIUM > LOW).
    Within the same priority level, maintains FIFO ordering.

    Usage:
        queue = PriorityBarQueue()
        await queue.put("AAPL", bar, Priority.HIGH)
        item = await queue.get()  # Returns PrioritizedBar
    """

    # Maximum counter value before wrapping (2^63 - 1)
    # Prevents unbounded growth in long-running processes
    _MAX_COUNTER = (2**63) - 1

    def __init__(self, maxsize: int = 0):
        """
        Initialize the priority queue.

        Args:
            maxsize: Maximum queue size (0 = unlimited)
        """
        self._queue: list[PrioritizedBar] = []
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Condition(self._lock)
        self._maxsize = maxsize
        self._counter = 0  # For tie-breaking within same priority

    async def put(
        self,
        symbol: str,
        bar: OHLCVBar,
        priority: Priority = Priority.MEDIUM,
    ) -> bool:
        """
        Add a bar to the priority queue.

        Args:
            symbol: Symbol identifier
            bar: OHLCV bar to queue
            priority: Processing priority (default: MEDIUM)

        Returns:
            True if bar was queued, False if queue is full
        """
        async with self._lock:
            if self._maxsize > 0 and len(self._queue) >= self._maxsize:
                return False

            # Use counter for FIFO ordering within same priority
            # Modular arithmetic prevents unbounded growth in long-running processes
            self._counter = (self._counter + 1) % self._MAX_COUNTER
            item = PrioritizedBar(
                priority=priority.value,
                timestamp=self._counter,  # Use counter instead of time for deterministic ordering
                symbol=symbol,
                bar=bar,
            )
            heappush(self._queue, item)

            # Notify waiters that queue is not empty
            self._not_empty.notify()
            return True

    async def get(self, timeout: float | None = None) -> PrioritizedBar:
        """
        Get the highest priority bar from the queue.

        Args:
            timeout: Maximum time to wait (None = wait forever)

        Returns:
            PrioritizedBar with highest priority

        Raises:
            QueueEmpty: If queue is empty and no timeout, or timeout expired
        """
        async with self._not_empty:
            if not self._queue:
                if timeout is None:
                    # Non-blocking mode
                    raise QueueEmpty()
                try:
                    await asyncio.wait_for(
                        self._not_empty.wait(),
                        timeout=timeout,
                    )
                except asyncio.TimeoutError:
                    raise QueueEmpty() from None

            if not self._queue:
                raise QueueEmpty()

            return heappop(self._queue)

    async def get_nowait(self) -> PrioritizedBar:
        """
        Get highest priority bar without waiting.

        Returns:
            PrioritizedBar with highest priority

        Raises:
            QueueEmpty: If queue is empty
        """
        async with self._lock:
            if not self._queue:
                raise QueueEmpty()
            return heappop(self._queue)

    def put_nowait(
        self,
        symbol: str,
        bar: OHLCVBar,
        priority: Priority = Priority.MEDIUM,
    ) -> bool:
        """
        Add a bar to the priority queue without waiting (synchronous).

        Warning - Concurrency Constraints:
            This method is intentionally synchronous for use in sync callbacks
            (e.g., WebSocket message handlers). It modifies shared state without
            locks, which means:

            1. NOT thread-safe: Do not call from multiple threads simultaneously
            2. NOT safe for concurrent coroutines: Even within the same event loop,
               concurrent coroutines calling this method may cause race conditions
            3. Safe usage: Call only from a single synchronous callback context
               where no other code can interleave (e.g., _on_bar_received)

            For async contexts with potential concurrency, use the async `put()`
            method instead, which uses proper locking.

        Args:
            symbol: Symbol identifier
            bar: OHLCV bar to queue
            priority: Processing priority (default: MEDIUM)

        Returns:
            True if bar was queued, False if queue is full
        """
        if self._maxsize > 0 and len(self._queue) >= self._maxsize:
            return False

        # Use modular arithmetic to prevent unbounded growth in long-running processes
        self._counter = (self._counter + 1) % self._MAX_COUNTER
        item = PrioritizedBar(
            priority=priority.value,
            timestamp=self._counter,
            symbol=symbol,
            bar=bar,
        )
        heappush(self._queue, item)
        return True

    def qsize(self) -> int:
        """Return the approximate size of the queue."""
        return len(self._queue)

    def empty(self) -> bool:
        """Return True if queue is empty."""
        return len(self._queue) == 0

    async def clear(self) -> int:
        """
        Clear all items from the queue.

        Returns:
            Number of items cleared
        """
        async with self._lock:
            count = len(self._queue)
            self._queue.clear()
            return count


class SymbolPriorityManager:
    """
    Manages symbol priority mappings.

    Provides priority lookup for symbols based on configuration.
    Default priority is MEDIUM if not explicitly set.
    """

    def __init__(self):
        """Initialize with empty priority mappings."""
        self._priorities: dict[str, Priority] = {}
        self._lock = asyncio.Lock()

    def get_priority_sync(self, symbol: str) -> Priority:
        """
        Get priority for a symbol (synchronous read).

        Thread Safety Note:
            This method reads from the dict without locking. This is safe in
            CPython due to the Global Interpreter Lock (GIL), which ensures
            atomic dict.get() operations. However, this is CPython-specific
            behavior and may not be safe in other Python implementations
            (e.g., PyPy, Jython).

            For guaranteed thread safety across implementations, use the
            async `get_priority()` method instead.

        Args:
            symbol: Symbol identifier

        Returns:
            Priority level (MEDIUM if not set)
        """
        return self._priorities.get(symbol, Priority.MEDIUM)

    async def set_priority(self, symbol: str, priority: Priority) -> None:
        """
        Set priority for a symbol.

        Args:
            symbol: Symbol identifier
            priority: Priority level to assign
        """
        async with self._lock:
            self._priorities[symbol] = priority

    async def get_priority(self, symbol: str) -> Priority:
        """
        Get priority for a symbol.

        Args:
            symbol: Symbol identifier

        Returns:
            Priority level (MEDIUM if not set)
        """
        async with self._lock:
            return self._priorities.get(symbol, Priority.MEDIUM)

    async def set_priorities(self, priorities: dict[str, Priority]) -> None:
        """
        Bulk set priorities for multiple symbols.

        Args:
            priorities: Mapping of symbol to priority
        """
        async with self._lock:
            self._priorities.update(priorities)

    async def remove_priority(self, symbol: str) -> None:
        """
        Remove priority setting for a symbol (reverts to MEDIUM).

        Args:
            symbol: Symbol identifier
        """
        async with self._lock:
            self._priorities.pop(symbol, None)

    async def get_all_priorities(self) -> dict[str, Priority]:
        """
        Get all symbol priority mappings.

        Returns:
            Copy of all priority mappings
        """
        async with self._lock:
            return dict(self._priorities)

    async def clear(self) -> None:
        """Clear all priority mappings."""
        async with self._lock:
            self._priorities.clear()
