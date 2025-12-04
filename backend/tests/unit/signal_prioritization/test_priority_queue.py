"""
Unit Tests for SignalPriorityQueue - Priority Queue Implementation (Story 9.3).

Tests the priority queue including:
- Push/pop operations maintain priority order (AC: 6)
- Peek returns highest priority without removing
- get_all_sorted returns signals in priority order
- FIFO tie-breaking for equal scores
- get_score returns PriorityScore for signal

Author: Story 9.3 Unit Tests
"""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.signal import ConfidenceComponents, TargetLevels, TradeSignal, ValidationChain
from src.signal_prioritization.priority_queue import SignalPriorityQueue
from src.signal_prioritization.scorer import SignalScorer


@pytest.fixture
def scorer():
    """SignalScorer with default normalization ranges."""
    return SignalScorer()


@pytest.fixture
def priority_queue(scorer):
    """SignalPriorityQueue with scorer."""
    return SignalPriorityQueue(scorer=scorer)


def create_test_signal(
    pattern_type: str,
    confidence: int,
    r_multiple: Decimal,
    symbol: str = "AAPL",
    entry_price: Decimal = Decimal("150.00"),
    stop_loss: Decimal = Decimal("148.00"),
) -> TradeSignal:
    """
    Helper to create valid test signal with correct R-multiple calculation.

    Parameters:
    -----------
    pattern_type : str
        Pattern type (SPRING, LPS, SOS, UTAD)
    confidence : int
        Confidence score (70-95)
    r_multiple : Decimal
        Desired R-multiple (target will be calculated)
    symbol : str
        Stock symbol (default: AAPL)
    entry_price : Decimal
        Entry price (default: 150.00)
    stop_loss : Decimal
        Stop loss (default: 148.00)

    Returns:
    --------
    TradeSignal
        Valid test signal
    """
    # Calculate target from entry/stop/r_multiple
    risk_per_share = entry_price - stop_loss
    target_price = entry_price + (r_multiple * risk_per_share)

    return TradeSignal(
        id=uuid4(),
        symbol=symbol,
        pattern_type=pattern_type,  # type: ignore
        phase="C" if pattern_type == "SPRING" else "D",
        timeframe="1d",
        entry_price=entry_price,
        stop_loss=stop_loss,
        target_levels=TargetLevels(primary_target=target_price),
        position_size=Decimal("100"),
        position_size_unit="SHARES",
        risk_amount=Decimal("200.00"),
        notional_value=Decimal("15000.00"),
        r_multiple=r_multiple,
        confidence_score=confidence,
        confidence_components=ConfidenceComponents(
            pattern_confidence=confidence,
            phase_confidence=confidence,
            volume_confidence=confidence,
            overall_confidence=confidence,
        ),
        validation_chain=ValidationChain(pattern_id=uuid4()),
        timestamp=datetime.now(),
    )


# =============================================================================
# Test: Push and Pop Maintain Priority Order (AC: 6)
# =============================================================================


def test_push_and_pop_maintains_priority_order(priority_queue):
    """
    Test push/pop maintains priority order (AC: 6).

    Create 5 signals with different scores:
    - Signal A: score ~80 (Spring, 85 conf, 3.5R)
    - Signal B: score ~65 (SOS, 85 conf, 3.5R)
    - Signal C: score ~90 (Spring, 95 conf, 4.5R) - HIGHEST
    - Signal D: score ~50 (SOS, 75 conf, 2.5R) - LOWEST
    - Signal E: score ~75 (LPS, 90 conf, 3.5R)

    Expected pop order: C (90), A (80), E (75), B (65), D (50)
    """
    # Create signals with varying priority scores
    signal_a = create_test_signal("SPRING", 85, Decimal("3.5"))  # ~80
    signal_b = create_test_signal("SOS", 85, Decimal("3.5"))  # ~65
    signal_c = create_test_signal("SPRING", 95, Decimal("4.5"))  # ~90
    signal_d = create_test_signal("SOS", 75, Decimal("2.5"))  # ~50
    signal_e = create_test_signal("LPS", 90, Decimal("3.5"))  # ~75

    # Push all signals
    priority_queue.push(signal_a)
    priority_queue.push(signal_b)
    priority_queue.push(signal_c)
    priority_queue.push(signal_d)
    priority_queue.push(signal_e)

    assert priority_queue.size() == 5

    # Pop signals one by one
    popped_1 = priority_queue.pop()
    popped_2 = priority_queue.pop()
    popped_3 = priority_queue.pop()
    popped_4 = priority_queue.pop()
    popped_5 = priority_queue.pop()

    # Verify order (highest priority first)
    assert popped_1 == signal_c  # Spring 95%, 4.5R (highest)
    assert popped_2 == signal_a  # Spring 85%, 3.5R
    assert popped_3 == signal_e  # LPS 90%, 3.5R
    assert popped_4 == signal_b  # SOS 85%, 3.5R
    assert popped_5 == signal_d  # SOS 75%, 2.5R (lowest)

    # Queue should be empty
    assert priority_queue.size() == 0


def test_pop_on_empty_queue_returns_none(priority_queue):
    """Test pop on empty queue returns None."""
    assert priority_queue.size() == 0
    popped = priority_queue.pop()
    assert popped is None


# =============================================================================
# Test: Peek Returns Highest Priority Without Removing
# =============================================================================


def test_peek_returns_highest_priority_without_removing(priority_queue):
    """Test peek returns highest priority signal without removing."""
    signal_low = create_test_signal("SOS", 75, Decimal("2.5"))  # Lower priority
    signal_high = create_test_signal("SPRING", 95, Decimal("4.5"))  # Higher priority
    signal_mid = create_test_signal("LPS", 85, Decimal("3.5"))  # Mid priority

    # Push signals
    priority_queue.push(signal_low)
    priority_queue.push(signal_high)
    priority_queue.push(signal_mid)

    assert priority_queue.size() == 3

    # Peek should return highest priority (signal_high)
    peeked = priority_queue.peek()
    assert peeked == signal_high

    # Queue size should be unchanged
    assert priority_queue.size() == 3

    # Peek again should return same signal
    peeked_again = priority_queue.peek()
    assert peeked_again == signal_high


def test_peek_on_empty_queue_returns_none(priority_queue):
    """Test peek on empty queue returns None."""
    assert priority_queue.size() == 0
    peeked = priority_queue.peek()
    assert peeked is None


# =============================================================================
# Test: get_all_sorted Returns Priority Order (AC: 10)
# =============================================================================


def test_get_all_sorted_does_not_modify_queue(priority_queue):
    """Test get_all_sorted returns signals in priority order without modifying queue."""
    signal_1 = create_test_signal("SPRING", 85, Decimal("3.5"), "AAPL")
    signal_2 = create_test_signal("SOS", 90, Decimal("3.0"), "MSFT")
    signal_3 = create_test_signal("LPS", 80, Decimal("3.5"), "GOOGL")

    # Push signals
    priority_queue.push(signal_1)
    priority_queue.push(signal_2)
    priority_queue.push(signal_3)

    initial_size = priority_queue.size()
    assert initial_size == 3

    # Get sorted signals
    sorted_signals = priority_queue.get_all_sorted()

    # Queue size should be unchanged
    assert priority_queue.size() == initial_size

    # Signals should be in priority order
    assert len(sorted_signals) == 3
    # Spring 85%, 3.5R should be first (highest priority ~69)
    assert sorted_signals[0] == signal_1
    # SOS 90%, 3.0R should be second (~52)
    assert sorted_signals[1] == signal_2
    # LPS 80%, 3.5R should be third (~51)
    assert sorted_signals[2] == signal_3


# =============================================================================
# Test: FIFO Tie-Breaking for Equal Scores
# =============================================================================


def test_tie_breaking_fifo_for_equal_scores(priority_queue):
    """
    Test FIFO tie-breaking when signals have equal scores.

    Create 3 SOS signals with same confidence and R-multiple (equal scores).
    Should be returned in insertion order (FIFO).
    """
    # All SOS with same confidence and R-multiple = same priority score
    signal_1 = create_test_signal("SOS", 80, Decimal("3.0"), "AAPL")
    signal_2 = create_test_signal("SOS", 80, Decimal("3.0"), "MSFT")
    signal_3 = create_test_signal("SOS", 80, Decimal("3.0"), "GOOGL")

    # Push in order: 1, 2, 3
    priority_queue.push(signal_1)
    priority_queue.push(signal_2)
    priority_queue.push(signal_3)

    # Pop all signals
    popped_1 = priority_queue.pop()
    popped_2 = priority_queue.pop()
    popped_3 = priority_queue.pop()

    # Should be returned in FIFO order (insertion order)
    assert popped_1 == signal_1
    assert popped_2 == signal_2
    assert popped_3 == signal_3


# =============================================================================
# Test: get_score Returns PriorityScore for Signal
# =============================================================================


def test_get_score_returns_priority_score_for_signal(priority_queue):
    """Test get_score returns stored PriorityScore for signal."""
    signal = create_test_signal("SPRING", 85, Decimal("3.5"))

    # Push signal (calculates and stores priority score)
    priority_queue.push(signal)

    # Get score for signal
    priority_score = priority_queue.get_score(signal.id)

    assert priority_score is not None
    assert priority_score.signal_id == signal.id
    assert priority_score.priority_score > Decimal("0.0")
    assert priority_score.components.confidence_score == 85
    assert priority_score.components.r_multiple == Decimal("3.5")
    assert priority_score.components.pattern_type == "SPRING"


def test_get_score_returns_none_for_unknown_signal(priority_queue):
    """Test get_score returns None for signal not in queue."""
    unknown_id = uuid4()
    priority_score = priority_queue.get_score(unknown_id)
    assert priority_score is None


# =============================================================================
# Test: Queue Size and Clear
# =============================================================================


def test_size_returns_correct_count(priority_queue):
    """Test size() returns correct number of signals in queue."""
    assert priority_queue.size() == 0

    signal_1 = create_test_signal("SPRING", 85, Decimal("3.5"))
    signal_2 = create_test_signal("SOS", 80, Decimal("3.0"))

    priority_queue.push(signal_1)
    assert priority_queue.size() == 1

    priority_queue.push(signal_2)
    assert priority_queue.size() == 2

    priority_queue.pop()
    assert priority_queue.size() == 1

    priority_queue.pop()
    assert priority_queue.size() == 0


def test_clear_removes_all_signals(priority_queue):
    """Test clear() removes all signals from queue."""
    signal_1 = create_test_signal("SPRING", 85, Decimal("3.5"))
    signal_2 = create_test_signal("SOS", 80, Decimal("3.0"))
    signal_3 = create_test_signal("LPS", 90, Decimal("4.0"))

    # Push signals
    priority_queue.push(signal_1)
    priority_queue.push(signal_2)
    priority_queue.push(signal_3)

    assert priority_queue.size() == 3

    # Clear queue
    priority_queue.clear()

    # Queue should be empty
    assert priority_queue.size() == 0
    assert priority_queue.pop() is None
    assert priority_queue.peek() is None

    # Scores should be cleared
    assert priority_queue.get_score(signal_1.id) is None
    assert priority_queue.get_score(signal_2.id) is None
    assert priority_queue.get_score(signal_3.id) is None
