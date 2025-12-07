"""
Signal Prioritization Logic - Priority Score Calculation (Story 9.7, Task 4)

Purpose:
--------
Implements FR28 signal prioritization logic to determine execution order when
multiple trade signals trigger simultaneously. Priority score combines:
- Confidence (40% weight): Pattern quality/reliability
- R-multiple (30% weight): Reward potential
- Pattern priority (30% weight): Pattern rarity and strategic value

Formula:
--------
priority_score = (confidence × 0.4) + (r_multiple × 10 × 0.3) + (pattern_priority × 0.3)

Pattern Priority Weights:
-------------------------
- Spring: 100 (rarest pattern, highest R-multiple, best risk/reward)
- LPS: 80 (late accumulation, better entry than SOS)
- SOS: 60 (markup confirmation, direct entry)
- UTAD: 40 (distribution pattern, lower priority for long trades)

Tie-Breaking Logic:
-------------------
If two signals have equal priority scores:
1. Use pattern priority weight (Spring > LPS > SOS > UTAD)
2. If still tied, use timestamp (FIFO, earlier signal first)

Integration:
------------
- Story 8.8: Uses TradeSignal model
- Story 9.7: Used by CampaignManager to determine signal execution order
- Epic 8: MasterOrchestrator uses SignalPriorityQueue for concurrent signals

Author: Story 9.7 Task 4
"""

import heapq
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID

import structlog

from src.models.signal import TradeSignal

logger = structlog.get_logger(__name__)

# Pattern priority weights (Story 9.7 AC #10, FR28)
PATTERN_PRIORITY_WEIGHTS = {
    "SPRING": 100,  # Rarest, highest strategic value, best R-multiple
    "LPS": 80,  # Late accumulation, better entry than SOS
    "SOS": 60,  # Markup confirmation, direct entry
    "UTAD": 40,  # Distribution pattern, lower priority for longs
}

# Priority score weights (Story 9.7 AC #10)
CONFIDENCE_WEIGHT = Decimal("0.4")  # 40% - Most important (pattern quality)
R_MULTIPLE_WEIGHT = Decimal("0.3")  # 30% - Reward potential
PATTERN_PRIORITY_WEIGHT = Decimal("0.3")  # 30% - Pattern rarity and strategic value


def calculate_priority_score(signal: TradeSignal) -> float:
    """
    Calculate priority score for a trade signal (AC #10, FR28).

    Formula:
    priority_score = (confidence × 0.4) + (r_multiple × 10 × 0.3) + (pattern_priority × 0.3)

    The R-multiple is multiplied by 10 to normalize its scale (typical R-multiples
    are 2.0-5.0, so ×10 brings them to 20-50 to match confidence scale of 0-100).

    Parameters
    ----------
    signal : TradeSignal
        Trade signal with confidence, r_multiple, and pattern_type

    Returns
    -------
    float
        Priority score in range 0-100 (higher = more important)

    Example
    -------
    >>> signal = TradeSignal(
    ...     confidence=Decimal("75.0"),
    ...     r_multiple=Decimal("3.0"),
    ...     pattern_type="SPRING"
    ... )
    >>> score = calculate_priority_score(signal)
    >>> # score = (75 × 0.4) + (30 × 0.3) + (100 × 0.3) = 30 + 9 + 30 = 69.0
    """
    # Get pattern priority weight (default to 0 for unknown patterns)
    pattern_priority = PATTERN_PRIORITY_WEIGHTS.get(signal.pattern_type, 0)

    # Calculate components
    confidence_component = float(signal.confidence) * float(CONFIDENCE_WEIGHT)
    r_multiple_component = float(signal.r_multiple * 10) * float(R_MULTIPLE_WEIGHT)
    pattern_component = pattern_priority * float(PATTERN_PRIORITY_WEIGHT)

    # Calculate total priority score
    priority_score = confidence_component + r_multiple_component + pattern_component

    # Log calculation for debugging
    logger.debug(
        "Calculated priority score",
        signal_id=str(signal.id),
        pattern_type=signal.pattern_type,
        confidence=str(signal.confidence),
        r_multiple=str(signal.r_multiple),
        pattern_priority=pattern_priority,
        confidence_component=f"{confidence_component:.2f}",
        r_multiple_component=f"{r_multiple_component:.2f}",
        pattern_component=f"{pattern_component:.2f}",
        priority_score=f"{priority_score:.2f}",
    )

    return priority_score


@dataclass(order=True)
class PrioritizedSignal:
    """
    Wrapper for TradeSignal with priority score for heapq ordering.

    The @dataclass(order=True) decorator enables comparison operators based
    on field order. Since heapq is a min-heap, we negate priority_score to
    achieve max-heap behavior (highest priority first).

    Fields
    ------
    priority_score : float
        Negative priority score for max-heap ordering (field is compared first)
    pattern_priority : int
        Pattern priority weight for tie-breaking (field is compared second)
    timestamp : datetime
        Signal creation timestamp for FIFO tie-breaking (field is compared third)
    signal : TradeSignal
        Original trade signal (field is NOT used for comparison)
    """

    priority_score: float = field(compare=True)  # Negated for max-heap
    pattern_priority: int = field(compare=True)  # Tie-breaker: higher pattern priority first
    timestamp: datetime = field(compare=True)  # Tie-breaker: earlier timestamp first
    signal: TradeSignal = field(compare=False)  # Do not use in comparison

    def __post_init__(self) -> None:
        """Negate priority_score and pattern_priority for max-heap behavior."""
        # heapq is min-heap, so negate to get max-heap (highest priority first)
        self.priority_score = -abs(self.priority_score)
        # Negate pattern_priority so higher pattern priority comes first
        self.pattern_priority = -abs(self.pattern_priority)


class SignalPriorityQueue:
    """
    Priority queue for trade signals with tie-breaking logic.

    Uses Python's heapq for efficient priority queue implementation.
    Signals are ordered by:
    1. Priority score (descending)
    2. Pattern priority (descending) - tie-breaker
    3. Timestamp (ascending, FIFO) - final tie-breaker

    Attributes
    ----------
    _heap : list[PrioritizedSignal]
        Internal heap data structure
    _signal_ids : set[UUID]
        Set of signal IDs in queue (for duplicate detection)
    """

    def __init__(self) -> None:
        """Initialize empty priority queue."""
        self._heap: list[PrioritizedSignal] = []
        self._signal_ids: set[UUID] = set()
        self.logger = logger.bind(component="SignalPriorityQueue")

    def push(self, signal: TradeSignal) -> None:
        """
        Add signal to priority queue.

        Calculates priority score and adds signal with proper ordering.
        Duplicates are ignored (same signal_id).

        Parameters
        ----------
        signal : TradeSignal
            Trade signal to add to queue

        Example
        -------
        >>> queue = SignalPriorityQueue()
        >>> queue.push(signal1)
        >>> queue.push(signal2)
        """
        # Check for duplicate
        if signal.id in self._signal_ids:
            self.logger.warning("Duplicate signal ignored", signal_id=str(signal.id))
            return

        # Calculate priority score
        priority_score = calculate_priority_score(signal)

        # Get pattern priority for tie-breaking
        pattern_priority = PATTERN_PRIORITY_WEIGHTS.get(signal.pattern_type, 0)

        # Create prioritized wrapper
        prioritized = PrioritizedSignal(
            priority_score=priority_score,
            pattern_priority=pattern_priority,
            timestamp=signal.created_at,
            signal=signal,
        )

        # Push to heap
        heapq.heappush(self._heap, prioritized)
        self._signal_ids.add(signal.id)

        self.logger.debug(
            "Signal added to priority queue",
            signal_id=str(signal.id),
            pattern_type=signal.pattern_type,
            priority_score=f"{priority_score:.2f}",
            queue_size=len(self._heap),
        )

    def pop(self) -> TradeSignal | None:
        """
        Remove and return highest priority signal.

        Returns
        -------
        TradeSignal | None
            Highest priority signal, or None if queue is empty

        Example
        -------
        >>> queue = SignalPriorityQueue()
        >>> queue.push(signal1)
        >>> highest_priority = queue.pop()
        """
        if not self._heap:
            return None

        prioritized = heapq.heappop(self._heap)
        self._signal_ids.remove(prioritized.signal.id)

        self.logger.debug(
            "Signal removed from priority queue",
            signal_id=str(prioritized.signal.id),
            pattern_type=prioritized.signal.pattern_type,
            priority_score=f"{-prioritized.priority_score:.2f}",  # Un-negate for logging
            queue_size=len(self._heap),
        )

        return prioritized.signal

    def peek(self) -> TradeSignal | None:
        """
        View highest priority signal without removing.

        Returns
        -------
        TradeSignal | None
            Highest priority signal, or None if queue is empty
        """
        if not self._heap:
            return None
        return self._heap[0].signal

    def __len__(self) -> int:
        """Return number of signals in queue."""
        return len(self._heap)

    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return len(self._heap) == 0


def prioritize_signals(signals: list[TradeSignal]) -> list[TradeSignal]:
    """
    Sort signals by priority score descending.

    Convenience function for batch prioritization without using queue.

    Parameters
    ----------
    signals : list[TradeSignal]
        List of trade signals to prioritize

    Returns
    -------
    list[TradeSignal]
        Signals sorted by priority score (highest first)

    Example
    -------
    >>> signals = [signal1, signal2, signal3]
    >>> sorted_signals = prioritize_signals(signals)
    >>> # sorted_signals[0] has highest priority
    """
    if not signals:
        return []

    # Calculate priority score for each signal
    scored_signals: list[tuple[float, int, datetime, TradeSignal]] = []
    for signal in signals:
        priority_score = calculate_priority_score(signal)
        pattern_priority = PATTERN_PRIORITY_WEIGHTS.get(signal.pattern_type, 0)
        scored_signals.append((priority_score, pattern_priority, signal.created_at, signal))

    # Sort by priority_score desc, pattern_priority desc, timestamp asc (FIFO)
    sorted_signals = sorted(
        scored_signals,
        key=lambda x: (-x[0], -x[1], x[2]),  # Negate for descending, timestamp asc
    )

    # Extract signals
    result = [item[3] for item in sorted_signals]

    logger.debug(
        "Signals prioritized",
        signal_count=len(signals),
        top_priority_pattern=result[0].pattern_type if result else None,
        top_priority_score=f"{scored_signals[0][0]:.2f}" if scored_signals else None,
    )

    return result
