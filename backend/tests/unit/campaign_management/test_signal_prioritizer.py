"""
Unit Tests for Signal Prioritizer (Story 9.7 Task 4)

Tests:
------
1. calculate_priority_score formula accuracy
2. Pattern priority weights (Spring > LPS > SOS > UTAD)
3. SignalPriorityQueue ordering
4. Tie-breaking logic (priority -> pattern -> timestamp)
5. prioritize_signals batch sorting

Author: Story 9.7 Task 9
Updated: Issue #232 - Fixed to use complete TradeSignal model
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.campaign_management.signal_prioritizer import (
    SignalPriorityQueue,
    calculate_priority_score,
    prioritize_signals,
)

# ==================================================================================
# Priority Score Calculation Tests
# ==================================================================================


def test_calculate_priority_score_spring(create_test_trade_signal) -> None:
    """Test priority score calculation for Spring signal."""
    signal = create_test_trade_signal(
        pattern_type="SPRING",
        confidence_score=75,
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("148.00"),
        primary_target=Decimal("156.00"),  # R-multiple = 3.0
    )
    # Spring: 75% confidence, 3.0R
    # Score = (75 * 0.4) + (30 * 0.3) + (100 * 0.3) = 30 + 9 + 30 = 69.0
    score = calculate_priority_score(signal)
    assert score == pytest.approx(69.0, abs=1.0)


def test_calculate_priority_score_sos(create_test_trade_signal) -> None:
    """Test priority score calculation for SOS signal."""
    signal = create_test_trade_signal(
        pattern_type="SOS",
        phase="D",
        confidence_score=85,
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("147.00"),
        primary_target=Decimal("158.40"),  # R-multiple ~= 2.8
    )
    # SOS: 85% confidence, ~2.8R
    # Score = (85 * 0.4) + (28 * 0.3) + (60 * 0.3) = 34 + 8.4 + 18 = 60.4
    score = calculate_priority_score(signal)
    assert score == pytest.approx(60.4, abs=2.0)


def test_calculate_priority_score_lps(create_test_trade_signal) -> None:
    """Test priority score calculation for LPS signal."""
    signal = create_test_trade_signal(
        pattern_type="LPS",
        phase="D",
        confidence_score=80,
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("147.00"),
        primary_target=Decimal("160.50"),  # R-multiple ~= 3.5
    )
    # LPS: 80% confidence, ~3.5R
    # Score = (80 * 0.4) + (35 * 0.3) + (80 * 0.3) = 32 + 10.5 + 24 = 66.5
    score = calculate_priority_score(signal)
    assert score == pytest.approx(66.5, abs=2.0)


def test_spring_higher_priority_than_sos_despite_lower_confidence(
    create_test_trade_signal,
) -> None:
    """
    Test that Spring with 75% confidence scores higher than SOS with 85%
    confidence due to pattern priority weight.
    """
    spring_signal = create_test_trade_signal(
        pattern_type="SPRING",
        confidence_score=75,
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("148.00"),
        primary_target=Decimal("156.00"),  # R = 3.0
    )
    sos_signal = create_test_trade_signal(
        pattern_type="SOS",
        phase="D",
        confidence_score=85,
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("147.00"),
        primary_target=Decimal("158.40"),  # R ~= 2.8
    )

    spring_score = calculate_priority_score(spring_signal)
    sos_score = calculate_priority_score(sos_signal)
    assert spring_score > sos_score


def test_lps_higher_than_sos_with_better_r_multiple(
    create_test_trade_signal,
) -> None:
    """
    Test that LPS with 3.5R scores higher than SOS with 2.8R despite
    lower confidence (80% vs 85%).
    """
    lps_signal = create_test_trade_signal(
        pattern_type="LPS",
        phase="D",
        confidence_score=80,
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("147.00"),
        primary_target=Decimal("160.50"),  # R ~= 3.5
    )
    sos_signal = create_test_trade_signal(
        pattern_type="SOS",
        phase="D",
        confidence_score=85,
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("147.00"),
        primary_target=Decimal("158.40"),  # R ~= 2.8
    )

    lps_score = calculate_priority_score(lps_signal)
    sos_score = calculate_priority_score(sos_signal)
    assert lps_score > sos_score


# ==================================================================================
# SignalPriorityQueue Tests
# ==================================================================================


def test_priority_queue_ordering(create_test_trade_signal) -> None:
    """Test that priority queue orders signals by priority score descending."""
    queue = SignalPriorityQueue()

    # Create signals with different priorities
    signal1 = create_test_trade_signal(
        symbol="AAPL",
        pattern_type="SPRING",
        confidence_score=75,
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("148.00"),
        primary_target=Decimal("156.00"),  # Score ~69.0
    )

    signal2 = create_test_trade_signal(
        symbol="MSFT",
        pattern_type="SOS",
        phase="D",
        confidence_score=85,
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("147.00"),
        primary_target=Decimal("158.40"),  # Score ~60.4
    )

    signal3 = create_test_trade_signal(
        symbol="GOOGL",
        pattern_type="LPS",
        phase="D",
        confidence_score=80,
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("147.00"),
        primary_target=Decimal("160.50"),  # Score ~66.5
    )

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


def test_priority_queue_tie_breaking_by_pattern_priority(
    create_test_trade_signal,
) -> None:
    """
    Test tie-breaking when two signals have similar priority scores.
    Higher pattern priority should win (Spring > LPS > SOS).
    """
    queue = SignalPriorityQueue()

    spring_signal = create_test_trade_signal(
        symbol="AAPL",
        pattern_type="SPRING",
        confidence_score=70,
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("148.00"),
        primary_target=Decimal("155.00"),  # R = 2.5
    )

    sos_signal = create_test_trade_signal(
        symbol="MSFT",
        pattern_type="SOS",
        phase="D",
        confidence_score=82,
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("148.00"),
        primary_target=Decimal("155.00"),  # R = 2.5
    )

    queue.push(sos_signal)
    queue.push(spring_signal)

    # Spring should come first due to pattern priority
    first = queue.pop()
    assert first is not None
    assert first.pattern_type == "SPRING"


def test_priority_queue_tie_breaking_by_timestamp(create_test_trade_signal) -> None:
    """
    Test FIFO tie-breaking when signals have equal scores and pattern priority.
    Earlier timestamp should win.
    """
    queue = SignalPriorityQueue()

    now = datetime.now(UTC)

    # Create two Spring signals with identical parameters but different timestamps
    signal1 = create_test_trade_signal(
        symbol="AAPL",
        pattern_type="SPRING",
        confidence_score=75,
        timestamp=now,  # Earlier
    )

    signal2 = create_test_trade_signal(
        symbol="MSFT",
        pattern_type="SPRING",
        confidence_score=75,
        timestamp=now + timedelta(seconds=10),  # Later
    )

    # Push in reverse order
    queue.push(signal2)
    queue.push(signal1)

    # Earlier timestamp should come first (FIFO)
    first = queue.pop()
    assert first is not None
    assert first.id == signal1.id


def test_priority_queue_duplicate_prevention(create_test_trade_signal) -> None:
    """Test that duplicate signals (same ID) are ignored."""
    queue = SignalPriorityQueue()

    signal = create_test_trade_signal(pattern_type="SPRING", confidence_score=75)

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


def test_priority_queue_is_empty(create_test_trade_signal) -> None:
    """Test is_empty() method."""
    queue = SignalPriorityQueue()
    assert queue.is_empty()

    signal = create_test_trade_signal(pattern_type="SPRING", confidence_score=75)
    queue.push(signal)
    assert not queue.is_empty()

    queue.pop()
    assert queue.is_empty()


def test_priority_queue_peek(create_test_trade_signal) -> None:
    """Test peek() method returns highest priority without removing."""
    queue = SignalPriorityQueue()

    signal = create_test_trade_signal(pattern_type="SPRING", confidence_score=75)
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


def test_prioritize_signals_batch_sorting(create_test_trade_signal) -> None:
    """Test prioritize_signals() sorts signals by priority descending."""
    signals = [
        create_test_trade_signal(
            symbol="AAPL",
            pattern_type="SOS",
            phase="D",
            confidence_score=85,
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("147.00"),
            primary_target=Decimal("158.40"),  # Score ~60.4
        ),
        create_test_trade_signal(
            symbol="MSFT",
            pattern_type="SPRING",
            confidence_score=75,
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("148.00"),
            primary_target=Decimal("156.00"),  # Score ~69.0
        ),
        create_test_trade_signal(
            symbol="GOOGL",
            pattern_type="LPS",
            phase="D",
            confidence_score=80,
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("147.00"),
            primary_target=Decimal("160.50"),  # Score ~66.5
        ),
    ]

    sorted_signals = prioritize_signals(signals)

    # Should be ordered: Spring (69.0), LPS (66.5), SOS (60.4)
    assert sorted_signals[0].pattern_type == "SPRING"
    assert sorted_signals[1].pattern_type == "LPS"
    assert sorted_signals[2].pattern_type == "SOS"


def test_prioritize_signals_empty_list() -> None:
    """Test prioritize_signals() with empty list returns empty."""
    assert prioritize_signals([]) == []
