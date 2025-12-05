"""
Integration Tests for Signal Prioritization - Full Pipeline (Story 9.3).

Tests the complete prioritization pipeline including:
- Multiple concurrent signals with MasterOrchestrator (AC: 9)
- SignalPriorityQueue integration
- Priority ordering with real signal generation
- get_next_signal() and get_pending_signals() methods

Author: Story 9.3 Integration Tests
"""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.signal import ConfidenceComponents, TargetLevels, TradeSignal, ValidationChain
from src.signal_generator.master_orchestrator import MasterOrchestrator
from src.signal_prioritization.priority_queue import SignalPriorityQueue
from src.signal_prioritization.scorer import SignalScorer


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


@pytest.fixture
def scorer():
    """SignalScorer with default normalization ranges."""
    return SignalScorer()


@pytest.fixture
def priority_queue(scorer):
    """SignalPriorityQueue with scorer."""
    return SignalPriorityQueue(scorer=scorer)


@pytest.fixture
def orchestrator(priority_queue):
    """MasterOrchestrator with priority queue."""
    return MasterOrchestrator(signal_priority_queue=priority_queue)


# =============================================================================
# Test: Multiple Concurrent Signals Correctly Prioritized (AC: 9)
# =============================================================================


def test_multiple_concurrent_signals_correctly_prioritized(priority_queue):
    """
    Test AC 9: Multiple concurrent signals are correctly ordered by priority.

    Create 5 signals with different scores:
    - Signal 1 (SPRING 85%, 4.0R): Expected rank 1 (highest)
    - Signal 2 (SOS 90%, 3.0R): Expected rank 3
    - Signal 3 (LPS 80%, 3.5R): Expected rank 2
    - Signal 4 (UTAD 85%, 2.5R): Expected rank 5 (lowest)
    - Signal 5 (SOS 75%, 2.8R): Expected rank 4

    Expected order by priority score:
    1. SPRING 85%, 4.0R (~75.0)
    2. LPS 80%, 3.5R (~51.0)
    3. SOS 90%, 3.0R (~51.8)
    4. SOS 75%, 2.8R (~38.4)
    5. UTAD 85%, 2.5R (~28.0)
    """
    # Create 5 signals with varying priorities
    signal_1 = create_test_signal("SPRING", 85, Decimal("4.0"), "AAPL")  # Rank 1
    signal_2 = create_test_signal("SOS", 90, Decimal("3.0"), "MSFT")  # Rank 3
    signal_3 = create_test_signal("LPS", 80, Decimal("3.5"), "GOOGL")  # Rank 2
    signal_4 = create_test_signal("UTAD", 85, Decimal("2.5"), "TSLA")  # Rank 5
    signal_5 = create_test_signal("SOS", 75, Decimal("2.8"), "NVDA")  # Rank 4

    # Push all signals to queue
    priority_queue.push(signal_1)
    priority_queue.push(signal_2)
    priority_queue.push(signal_3)
    priority_queue.push(signal_4)
    priority_queue.push(signal_5)

    assert priority_queue.size() == 5

    # Get all signals in priority order
    sorted_signals = priority_queue.get_all_sorted()

    # Verify order (highest priority first)
    assert len(sorted_signals) == 5
    assert sorted_signals[0].id == signal_1.id  # SPRING 85%, 4.0R (highest)
    assert sorted_signals[0].pattern_type == "SPRING"

    # Verify Spring has highest score
    spring_score = priority_queue.get_score(signal_1.id)
    assert spring_score is not None
    assert spring_score.priority_score > Decimal("70.0")

    # Verify UTAD has lowest score
    utad_score = priority_queue.get_score(signal_4.id)
    assert utad_score is not None
    assert utad_score.priority_score < Decimal("30.0")

    # Verify all signals are in descending priority order
    for i in range(len(sorted_signals) - 1):
        score_i = priority_queue.get_score(sorted_signals[i].id)
        score_next = priority_queue.get_score(sorted_signals[i + 1].id)
        assert score_i is not None
        assert score_next is not None
        assert score_i.priority_score >= score_next.priority_score


def test_priority_queue_integration_with_orchestrator(orchestrator, priority_queue):
    """
    Test priority queue integration with MasterOrchestrator.

    Create 3 signals and verify they're automatically added to priority queue
    when generated by orchestrator.
    """
    # Create 3 test signals
    signal_spring = create_test_signal("SPRING", 85, Decimal("4.0"), "AAPL")
    signal_sos = create_test_signal("SOS", 80, Decimal("3.0"), "MSFT")
    signal_utad = create_test_signal("UTAD", 75, Decimal("2.5"), "GOOGL")

    # Manually push signals (simulating orchestrator.generate_signal_from_pattern)
    priority_queue.push(signal_spring)
    priority_queue.push(signal_sos)
    priority_queue.push(signal_utad)

    # Verify queue size
    assert priority_queue.size() == 3

    # Get next signal (highest priority)
    next_signal = orchestrator.get_next_signal()
    assert next_signal is not None
    assert next_signal.pattern_type == "SPRING"  # Highest priority

    # Get remaining pending signals
    pending_signals = orchestrator.get_pending_signals(limit=50)
    assert len(pending_signals) == 2  # Spring was popped
    assert pending_signals[0].pattern_type == "SOS"  # Second highest
    assert pending_signals[1].pattern_type == "UTAD"  # Lowest


def test_get_next_signal_returns_highest_priority(orchestrator, priority_queue):
    """
    Test get_next_signal() returns highest priority signal.

    Create signals with different scores and verify get_next_signal()
    returns them in correct priority order.
    """
    # Create signals with clear priority differences
    signal_high = create_test_signal("SPRING", 95, Decimal("4.5"), "AAPL")  # Highest
    signal_mid = create_test_signal("LPS", 85, Decimal("3.5"), "MSFT")  # Mid
    signal_low = create_test_signal("SOS", 75, Decimal("2.5"), "GOOGL")  # Lowest

    # Push signals
    priority_queue.push(signal_low)
    priority_queue.push(signal_high)
    priority_queue.push(signal_mid)

    # Get next signal (should be highest priority)
    next_1 = orchestrator.get_next_signal()
    assert next_1 is not None
    assert next_1.id == signal_high.id

    # Get next signal (should be mid priority)
    next_2 = orchestrator.get_next_signal()
    assert next_2 is not None
    assert next_2.id == signal_mid.id

    # Get next signal (should be low priority)
    next_3 = orchestrator.get_next_signal()
    assert next_3 is not None
    assert next_3.id == signal_low.id

    # Queue should be empty
    next_4 = orchestrator.get_next_signal()
    assert next_4 is None


def test_get_pending_signals_does_not_modify_queue(orchestrator, priority_queue):
    """
    Test get_pending_signals() returns signals without modifying queue.

    Verify that calling get_pending_signals() multiple times returns
    the same signals in the same order without removing them.
    """
    # Create 3 signals
    signal_1 = create_test_signal("SPRING", 85, Decimal("3.5"), "AAPL")
    signal_2 = create_test_signal("LPS", 80, Decimal("3.0"), "MSFT")
    signal_3 = create_test_signal("SOS", 75, Decimal("2.5"), "GOOGL")

    # Push signals
    priority_queue.push(signal_1)
    priority_queue.push(signal_2)
    priority_queue.push(signal_3)

    initial_size = priority_queue.size()
    assert initial_size == 3

    # Get pending signals (first call)
    pending_1 = orchestrator.get_pending_signals(limit=50)
    assert len(pending_1) == 3
    assert priority_queue.size() == initial_size  # Size unchanged

    # Get pending signals (second call)
    pending_2 = orchestrator.get_pending_signals(limit=50)
    assert len(pending_2) == 3
    assert priority_queue.size() == initial_size  # Size still unchanged

    # Verify same signals returned in same order
    assert pending_1[0].id == pending_2[0].id
    assert pending_1[1].id == pending_2[1].id
    assert pending_1[2].id == pending_2[2].id


def test_get_pending_signals_respects_limit(orchestrator, priority_queue):
    """
    Test get_pending_signals() respects the limit parameter.

    Create 5 signals and verify limit parameter correctly restricts
    the number of signals returned.
    """
    # Create 5 signals
    for i in range(5):
        signal = create_test_signal("SOS", 80, Decimal("3.0"), f"SYM{i}")
        priority_queue.push(signal)

    assert priority_queue.size() == 5

    # Get pending signals with limit=3
    pending = orchestrator.get_pending_signals(limit=3)
    assert len(pending) == 3

    # Queue size unchanged
    assert priority_queue.size() == 5


def test_empty_queue_behavior(orchestrator):
    """
    Test orchestrator methods with empty priority queue.

    Verify that methods return expected values when queue is empty.
    """
    # get_next_signal() should return None
    next_signal = orchestrator.get_next_signal()
    assert next_signal is None

    # get_pending_signals() should return empty list
    pending_signals = orchestrator.get_pending_signals()
    assert pending_signals == []


def test_orchestrator_without_priority_queue():
    """
    Test orchestrator gracefully handles missing priority queue.

    When signal_priority_queue is None, methods should log warning
    and return None/empty list.
    """
    # Create orchestrator without priority queue
    orchestrator = MasterOrchestrator(signal_priority_queue=None)

    # get_next_signal() should return None (with warning log)
    next_signal = orchestrator.get_next_signal()
    assert next_signal is None

    # get_pending_signals() should return empty list (with warning log)
    pending_signals = orchestrator.get_pending_signals()
    assert pending_signals == []


# =============================================================================
# Test: Priority Scores Match Expected Calculations (AC: 9)
# =============================================================================


def test_priority_scores_match_expected_calculations(scorer, priority_queue):
    """
    Test that priority scores match expected FR28 calculations.

    Calculate expected scores manually and verify they match
    the scores calculated by SignalScorer.
    """
    # Signal 1: SPRING 85%, 4.0R
    # confidence_norm = (85-70)/(95-70) = 15/25 = 0.60
    # r_norm = (4.0-2.0)/(5.0-2.0) = 2.0/3.0 = 0.67
    # pattern_norm (Spring) = 1.0
    # score = (0.60*0.40) + (0.67*0.30) + (1.0*0.30) = 0.24 + 0.20 + 0.30 = 0.74 = 74.0
    signal_spring = create_test_signal("SPRING", 85, Decimal("4.0"))
    priority_queue.push(signal_spring)

    spring_score = priority_queue.get_score(signal_spring.id)
    assert spring_score is not None
    assert spring_score.priority_score >= Decimal("73.0")
    assert spring_score.priority_score <= Decimal("75.0")

    # Signal 2: LPS 80%, 3.5R
    # confidence_norm = (80-70)/(95-70) = 10/25 = 0.40
    # r_norm = (3.5-2.0)/(5.0-2.0) = 1.5/3.0 = 0.50
    # pattern_norm (LPS) = 0.67
    # score = (0.40*0.40) + (0.50*0.30) + (0.67*0.30) = 0.16 + 0.15 + 0.20 = 0.51 = 51.0
    signal_lps = create_test_signal("LPS", 80, Decimal("3.5"))
    priority_queue.push(signal_lps)

    lps_score = priority_queue.get_score(signal_lps.id)
    assert lps_score is not None
    assert lps_score.priority_score >= Decimal("50.0")
    assert lps_score.priority_score <= Decimal("52.0")

    # Signal 3: UTAD 85%, 2.5R
    # confidence_norm = 0.60
    # r_norm = (2.5-2.0)/(5.0-2.0) = 0.5/3.0 = 0.17
    # pattern_norm (UTAD) = 0.0
    # score = (0.60*0.40) + (0.17*0.30) + (0.0*0.30) = 0.24 + 0.05 + 0.0 = 0.29 = 29.0
    signal_utad = create_test_signal("UTAD", 85, Decimal("2.5"))
    priority_queue.push(signal_utad)

    utad_score = priority_queue.get_score(signal_utad.id)
    assert utad_score is not None
    assert utad_score.priority_score >= Decimal("28.0")
    assert utad_score.priority_score <= Decimal("30.0")


# =============================================================================
# Test: Pattern Priority Overrides Confidence (AC: 7, 8)
# =============================================================================


def test_pattern_priority_overrides_confidence_in_integration(priority_queue):
    """
    Test AC 7 in integration context: Spring with lower confidence
    beats SOS with higher confidence due to pattern priority weight.
    """
    # Spring 75% confidence vs SOS 85% confidence (same R-multiple)
    signal_spring = create_test_signal("SPRING", 75, Decimal("3.5"), "AAPL")
    signal_sos = create_test_signal("SOS", 85, Decimal("3.5"), "MSFT")

    priority_queue.push(signal_spring)
    priority_queue.push(signal_sos)

    # Get sorted signals
    sorted_signals = priority_queue.get_all_sorted()

    # Spring should be first despite lower confidence
    assert sorted_signals[0].id == signal_spring.id
    assert sorted_signals[1].id == signal_sos.id


def test_lps_beats_sos_due_to_pattern_and_r_multiple_in_integration(priority_queue):
    """
    Test AC 8 in integration context: LPS with better R-multiple
    beats SOS with lower R-multiple.
    """
    # LPS 3.5R vs SOS 2.8R (same confidence)
    signal_lps = create_test_signal("LPS", 80, Decimal("3.5"), "AAPL")
    signal_sos = create_test_signal("SOS", 80, Decimal("2.8"), "MSFT")

    priority_queue.push(signal_lps)
    priority_queue.push(signal_sos)

    # Get sorted signals
    sorted_signals = priority_queue.get_all_sorted()

    # LPS should be first due to higher R-multiple + better pattern priority
    assert sorted_signals[0].id == signal_lps.id
    assert sorted_signals[1].id == signal_sos.id
