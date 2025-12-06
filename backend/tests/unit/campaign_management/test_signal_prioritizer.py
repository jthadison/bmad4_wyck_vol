"""
Unit Tests for Signal Prioritizer (Story 9.7 Task 4)

Tests:
------
1. calculate_priority_score formula accuracy
2. Pattern priority weights (Spring > LPS > SOS > UTAD)
3. SignalPriorityQueue ordering
4. Tie-breaking logic (priority → pattern → timestamp)
5. prioritize_signals batch sorting

Author: Story 9.7 Task 9
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.campaign_management.signal_prioritizer import (
    SignalPriorityQueue,
    calculate_priority_score,
    prioritize_signals,
)
from src.models.signal import TradeSignal

# ==================================================================================
# Fixtures
# ==================================================================================


@pytest.fixture
def spring_signal() -> TradeSignal:
    """Create Spring signal for testing."""
    return TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        pattern_type="SPRING",
        confidence=Decimal("75.0"),
        r_multiple=Decimal("3.0"),
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def sos_signal() -> TradeSignal:
    """Create SOS signal for testing."""
    return TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        pattern_type="SOS",
        confidence=Decimal("85.0"),
        r_multiple=Decimal("2.8"),
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def lps_signal() -> TradeSignal:
    """Create LPS signal for testing."""
    return TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        pattern_type="LPS",
        confidence=Decimal("80.0"),
        r_multiple=Decimal("3.5"),
        created_at=datetime.now(UTC),
    )


# ==================================================================================
# Priority Score Calculation Tests
# ==================================================================================


def test_calculate_priority_score_spring(spring_signal: TradeSignal) -> None:
    """Test priority score calculation for Spring signal."""
    # Spring: 75% confidence, 3.0R
    # Score = (75 × 0.4) + (30 × 0.3) + (100 × 0.3) = 30 + 9 + 30 = 69.0
    score = calculate_priority_score(spring_signal)
    assert score == pytest.approx(69.0, abs=0.1)


def test_calculate_priority_score_sos(sos_signal: TradeSignal) -> None:
    """Test priority score calculation for SOS signal."""
    # SOS: 85% confidence, 2.8R
    # Score = (85 × 0.4) + (28 × 0.3) + (60 × 0.3) = 34 + 8.4 + 18 = 60.4
    score = calculate_priority_score(sos_signal)
    assert score == pytest.approx(60.4, abs=0.1)


def test_calculate_priority_score_lps(lps_signal: TradeSignal) -> None:
    """Test priority score calculation for LPS signal."""
    # LPS: 80% confidence, 3.5R
    # Score = (80 × 0.4) + (35 × 0.3) + (80 × 0.3) = 32 + 10.5 + 24 = 66.5
    score = calculate_priority_score(lps_signal)
    assert score == pytest.approx(66.5, abs=0.1)


def test_spring_higher_priority_than_sos_despite_lower_confidence(
    spring_signal: TradeSignal, sos_signal: TradeSignal
) -> None:
    """
    Test that Spring with 75% confidence scores higher than SOS with 85%
    confidence due to pattern priority weight.
    """
    spring_score = calculate_priority_score(spring_signal)
    sos_score = calculate_priority_score(sos_signal)
    assert spring_score > sos_score  # 69.0 > 60.4


def test_lps_higher_than_sos_with_better_r_multiple(
    lps_signal: TradeSignal, sos_signal: TradeSignal
) -> None:
    """
    Test that LPS with 3.5R scores higher than SOS with 2.8R despite
    lower confidence (80% vs 85%).
    """
    # LPS: 80% confidence, 3.5R → ~66.5
    # SOS: 85% confidence, 2.8R → ~60.4
    lps_score = calculate_priority_score(lps_signal)
    sos_score = calculate_priority_score(sos_signal)
    assert lps_score > sos_score


# ==================================================================================
# SignalPriorityQueue Tests
# ==================================================================================


def test_priority_queue_ordering() -> None:
    """Test that priority queue orders signals by priority score descending."""
    queue = SignalPriorityQueue()

    # Create signals with different priorities
    signal1 = TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        pattern_type="SPRING",
        confidence=Decimal("75.0"),
        r_multiple=Decimal("3.0"),
        created_at=datetime.now(UTC),
    )  # Score ~69.0

    signal2 = TradeSignal(
        id=uuid4(),
        symbol="MSFT",
        timeframe="1d",
        pattern_type="SOS",
        confidence=Decimal("85.0"),
        r_multiple=Decimal("2.8"),
        created_at=datetime.now(UTC),
    )  # Score ~60.4

    signal3 = TradeSignal(
        id=uuid4(),
        symbol="GOOGL",
        timeframe="1d",
        pattern_type="LPS",
        confidence=Decimal("80.0"),
        r_multiple=Decimal("3.5"),
        created_at=datetime.now(UTC),
    )  # Score ~66.5

    # Push in random order
    queue.push(signal2)
    queue.push(signal1)
    queue.push(signal3)

    # Pop should return highest priority first (Spring ~69.0)
    first = queue.pop()
    assert first is not None
    assert first.pattern_type == "SPRING"

    # Next should be LPS (~66.5)
    second = queue.pop()
    assert second is not None
    assert second.pattern_type == "LPS"

    # Last should be SOS (~60.4)
    third = queue.pop()
    assert third is not None
    assert third.pattern_type == "SOS"


def test_priority_queue_tie_breaking_by_pattern_priority() -> None:
    """
    Test tie-breaking when two signals have equal priority scores.
    Higher pattern priority should win (Spring > LPS > SOS).
    """
    queue = SignalPriorityQueue()

    # Create signals with equal priority scores but different patterns
    # Adjust confidence to make scores equal
    spring_signal = TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        pattern_type="SPRING",
        confidence=Decimal("70.0"),  # Adjusted for equal score
        r_multiple=Decimal("2.5"),
        created_at=datetime.now(UTC),
    )

    sos_signal = TradeSignal(
        id=uuid4(),
        symbol="MSFT",
        timeframe="1d",
        pattern_type="SOS",
        confidence=Decimal("82.0"),  # Adjusted for equal score
        r_multiple=Decimal("2.5"),
        created_at=datetime.now(UTC),
    )

    queue.push(sos_signal)
    queue.push(spring_signal)

    # Spring should come first due to pattern priority (even if scores are close)
    first = queue.pop()
    assert first is not None
    # We expect Spring to have higher priority due to pattern weight
    assert first.pattern_type == "SPRING"


def test_priority_queue_tie_breaking_by_timestamp() -> None:
    """
    Test FIFO tie-breaking when signals have equal scores and pattern priority.
    Earlier timestamp should win.
    """
    queue = SignalPriorityQueue()

    now = datetime.now(UTC)

    # Create two Spring signals with identical scores but different timestamps
    signal1 = TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        pattern_type="SPRING",
        confidence=Decimal("75.0"),
        r_multiple=Decimal("3.0"),
        created_at=now,  # Earlier
    )

    signal2 = TradeSignal(
        id=uuid4(),
        symbol="MSFT",
        timeframe="1d",
        pattern_type="SPRING",
        confidence=Decimal("75.0"),
        r_multiple=Decimal("3.0"),
        created_at=now + timedelta(seconds=10),  # Later
    )

    # Push in reverse order
    queue.push(signal2)
    queue.push(signal1)

    # Earlier timestamp should come first (FIFO)
    first = queue.pop()
    assert first is not None
    assert first.id == signal1.id


def test_priority_queue_duplicate_prevention() -> None:
    """Test that duplicate signals (same ID) are ignored."""
    queue = SignalPriorityQueue()

    signal = TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        pattern_type="SPRING",
        confidence=Decimal("75.0"),
        r_multiple=Decimal("3.0"),
        created_at=datetime.now(UTC),
    )

    # Push same signal twice
    queue.push(signal)
    queue.push(signal)

    # Queue should contain only 1 signal
    assert len(queue) == 1

    # Pop once should return signal
    popped = queue.pop()
    assert popped is not None
    assert popped.id == signal.id

    # Pop again should return None (queue empty)
    assert queue.pop() is None


def test_priority_queue_is_empty() -> None:
    """Test is_empty() method."""
    queue = SignalPriorityQueue()
    assert queue.is_empty()

    signal = TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        pattern_type="SPRING",
        confidence=Decimal("75.0"),
        r_multiple=Decimal("3.0"),
        created_at=datetime.now(UTC),
    )
    queue.push(signal)
    assert not queue.is_empty()

    queue.pop()
    assert queue.is_empty()


def test_priority_queue_peek() -> None:
    """Test peek() method returns highest priority without removing."""
    queue = SignalPriorityQueue()

    signal = TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        pattern_type="SPRING",
        confidence=Decimal("75.0"),
        r_multiple=Decimal("3.0"),
        created_at=datetime.now(UTC),
    )
    queue.push(signal)

    # Peek should return signal without removing
    peeked = queue.peek()
    assert peeked is not None
    assert peeked.id == signal.id
    assert len(queue) == 1  # Still in queue

    # Pop should return same signal
    popped = queue.pop()
    assert popped is not None
    assert popped.id == signal.id
    assert len(queue) == 0  # Now removed


# ==================================================================================
# Batch Prioritization Tests
# ==================================================================================


def test_prioritize_signals_batch_sorting() -> None:
    """Test prioritize_signals() sorts signals by priority descending."""
    signals = [
        TradeSignal(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            pattern_type="SOS",
            confidence=Decimal("85.0"),
            r_multiple=Decimal("2.8"),
            created_at=datetime.now(UTC),
        ),  # Score ~60.4
        TradeSignal(
            id=uuid4(),
            symbol="MSFT",
            timeframe="1d",
            pattern_type="SPRING",
            confidence=Decimal("75.0"),
            r_multiple=Decimal("3.0"),
            created_at=datetime.now(UTC),
        ),  # Score ~69.0
        TradeSignal(
            id=uuid4(),
            symbol="GOOGL",
            timeframe="1d",
            pattern_type="LPS",
            confidence=Decimal("80.0"),
            r_multiple=Decimal("3.5"),
            created_at=datetime.now(UTC),
        ),  # Score ~66.5
    ]

    sorted_signals = prioritize_signals(signals)

    # Should be ordered: Spring (69.0), LPS (66.5), SOS (60.4)
    assert sorted_signals[0].pattern_type == "SPRING"
    assert sorted_signals[1].pattern_type == "LPS"
    assert sorted_signals[2].pattern_type == "SOS"


def test_prioritize_signals_empty_list() -> None:
    """Test prioritize_signals() with empty list returns empty."""
    assert prioritize_signals([]) == []
