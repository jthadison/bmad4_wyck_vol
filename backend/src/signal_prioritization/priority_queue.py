"""
Signal Priority Queue - Priority Queue for Signal Ranking (Story 9.3).

Purpose:
--------
Maintains concurrent signals in priority order using Python heapq (binary heap).
Signals are ranked by priority_score (highest first) with pattern-based tie-breaking.

Features:
---------
- O(log n) push/pop operations (AC: 6)
- O(1) peek operation
- O(n log n) sorted retrieval
- Automatic priority score calculation on push
- FIFO tie-breaking for equal scores
- Pattern priority tie-breaking (Spring > LPS > SOS > UTAD) (AC: 5)

Heap Structure:
---------------
Python heapq is min-heap (smallest value at top).
To get max-priority (highest score), negate priority_score:
  (-priority_score, rank_counter, signal)

rank_counter ensures FIFO tie-breaking when scores equal.

Author: Story 9.3 (Signal Prioritization Logic)
"""

import heapq
from uuid import UUID

import structlog

from src.models.priority import PriorityScore
from src.models.signal import TradeSignal
from src.signal_prioritization.scorer import SignalScorer

logger = structlog.get_logger()


class SignalPriorityQueue:
    """
    Priority queue for signal ranking using FR28 scoring (AC: 6).

    Uses Python heapq (binary heap) for efficient O(log n) operations.
    Signals automatically scored and ranked on push.
    """

    def __init__(self, scorer: SignalScorer):
        """
        Initialize priority queue with scorer.

        Parameters:
        -----------
        scorer : SignalScorer
            Signal scorer for calculating priority scores
        """
        self.scorer = scorer
        self.heap: list[tuple] = []  # [(neg_priority_score, rank_counter, signal), ...]
        self.rank_counter = 0  # Auto-increment for FIFO tie-breaking
        self.signal_scores: dict[UUID, PriorityScore] = {}  # signal_id → PriorityScore
        self.logger = logger.bind(component="signal_priority_queue")

    def push(self, signal: TradeSignal) -> None:
        """
        Add signal to priority queue (AC: 6).

        Calculates priority score and inserts into heap with negated score
        for max-heap behavior (highest priority at top).

        Parameters:
        -----------
        signal : TradeSignal
            Signal to add to queue
        """
        # Calculate priority score using FR28 algorithm
        score = self.scorer.calculate_priority_score(signal)

        # Add to heap with negated score (max-heap behavior)
        # Tuple: (neg_score, rank_counter, signal)
        # heapq pops smallest first, so negating score gives us max-priority
        heapq.heappush(self.heap, (-float(score.priority_score), self.rank_counter, signal))

        # Store score mapping for retrieval
        self.signal_scores[signal.id] = score

        # Increment rank counter for next signal (FIFO tie-breaking)
        self.rank_counter += 1

        self.logger.info(
            "signal_added_to_queue",
            signal_id=str(signal.id),
            pattern_type=signal.pattern_type,
            priority_score=str(score.priority_score),
            queue_size=len(self.heap),
        )

    def pop(self) -> TradeSignal | None:
        """
        Remove and return highest priority signal (AC: 6).

        Returns None if queue is empty.

        Returns:
        --------
        TradeSignal | None
            Highest priority signal, or None if empty
        """
        if not self.heap:
            self.logger.debug("pop_called_on_empty_queue")
            return None

        # Pop highest priority signal
        # heappop returns smallest tuple, which has largest priority_score (due to negation)
        neg_score, rank, signal = heapq.heappop(self.heap)

        # Update rank in stored PriorityScore (was highest in queue)
        if signal.id in self.signal_scores:
            self.signal_scores[signal.id].rank = 1

        self.logger.info(
            "signal_popped_from_queue",
            signal_id=str(signal.id),
            pattern_type=signal.pattern_type,
            priority_score=str(-neg_score),  # Un-negate for logging
            remaining_size=len(self.heap),
        )

        return signal

    def peek(self) -> TradeSignal | None:
        """
        Return highest priority signal without removing.

        Returns None if queue is empty.

        Returns:
        --------
        TradeSignal | None
            Highest priority signal, or None if empty
        """
        if not self.heap:
            return None

        # Return signal from top of heap (index 2 in tuple)
        return self.heap[0][2]

    def get_all_sorted(self) -> list[TradeSignal]:
        """
        Return copy of all signals in priority order (AC: 10).

        Does not modify the queue. Signals returned in descending priority order
        (highest priority first).

        Returns:
        --------
        list[TradeSignal]
            All signals sorted by priority (highest first)
        """
        # heapq.nsmallest returns largest priority_score first (due to negation)
        # Extract all tuples in priority order
        sorted_tuples = heapq.nsmallest(len(self.heap), self.heap)

        # Extract signals from tuples
        signals = [tup[2] for tup in sorted_tuples]

        self.logger.debug(
            "get_all_sorted_called",
            signal_count=len(signals),
        )

        return signals

    def get_score(self, signal_id: UUID) -> PriorityScore | None:
        """
        Get stored PriorityScore for signal.

        Parameters:
        -----------
        signal_id : UUID
            Signal identifier

        Returns:
        --------
        PriorityScore | None
            Stored priority score, or None if not found
        """
        return self.signal_scores.get(signal_id)

    def size(self) -> int:
        """
        Get current queue size.

        Returns:
        --------
        int
            Number of signals in queue
        """
        return len(self.heap)

    def clear(self) -> None:
        """
        Clear all signals from queue.

        Resets heap, scores, and rank counter to initial state.
        """
        self.heap.clear()
        self.signal_scores.clear()
        self.rank_counter = 0

        self.logger.info("queue_cleared")
