"""
Unit tests for Priority Queue implementation.

Story 19.23: Symbol Priority Tiers
Tests cover:
- Priority enum values
- PrioritizedBar ordering
- PriorityBarQueue operations (put, get, clear)
- Priority ordering during congestion
- FIFO ordering within same priority
- SymbolPriorityManager functionality
"""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.models.ohlcv import OHLCVBar
from src.pattern_engine.priority_queue import (
    PrioritizedBar,
    Priority,
    PriorityBarQueue,
    QueueEmpty,
    SymbolPriorityManager,
)

# =============================
# Fixtures
# =============================


@pytest.fixture
def sample_bar() -> OHLCVBar:
    """Create a sample OHLCVBar for testing."""
    return OHLCVBar(
        symbol="AAPL",
        timeframe="1m",
        timestamp=datetime.now(UTC),
        open=Decimal("150.00"),
        high=Decimal("151.00"),
        low=Decimal("149.50"),
        close=Decimal("150.50"),
        volume=100000,
        spread=Decimal("1.50"),
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("1.0"),
    )


def make_bar(symbol: str) -> OHLCVBar:
    """Helper to create bars with specific symbols."""
    return OHLCVBar(
        symbol=symbol,
        timeframe="1m",
        timestamp=datetime.now(UTC),
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("99.00"),
        close=Decimal("100.50"),
        volume=10000,
        spread=Decimal("2.00"),
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("1.0"),
    )


# =============================
# Priority Enum Tests
# =============================


class TestPriorityEnum:
    """Tests for Priority enum."""

    def test_priority_values(self):
        """Priority values are ordered correctly for heap."""
        assert Priority.HIGH == 1
        assert Priority.MEDIUM == 2
        assert Priority.LOW == 3

    def test_priority_ordering(self):
        """Priority comparison works for heap ordering."""
        assert Priority.HIGH < Priority.MEDIUM < Priority.LOW

    def test_priority_from_name(self):
        """Priority can be created from string name."""
        assert Priority["HIGH"] == Priority.HIGH
        assert Priority["MEDIUM"] == Priority.MEDIUM
        assert Priority["LOW"] == Priority.LOW


# =============================
# PrioritizedBar Tests
# =============================


class TestPrioritizedBar:
    """Tests for PrioritizedBar dataclass."""

    def test_ordering_by_priority(self, sample_bar):
        """PrioritizedBars are ordered by priority first."""
        high = PrioritizedBar(
            priority=Priority.HIGH.value,
            timestamp=2.0,
            symbol="A",
            bar=sample_bar,
        )
        low = PrioritizedBar(
            priority=Priority.LOW.value,
            timestamp=1.0,
            symbol="B",
            bar=sample_bar,
        )

        assert high < low  # HIGH (1) < LOW (3)

    def test_ordering_by_timestamp_within_priority(self, sample_bar):
        """Within same priority, ordered by timestamp (FIFO)."""
        first = PrioritizedBar(
            priority=Priority.MEDIUM.value,
            timestamp=1.0,
            symbol="A",
            bar=sample_bar,
        )
        second = PrioritizedBar(
            priority=Priority.MEDIUM.value,
            timestamp=2.0,
            symbol="B",
            bar=sample_bar,
        )

        assert first < second


# =============================
# PriorityBarQueue Tests
# =============================


class TestPriorityBarQueue:
    """Tests for PriorityBarQueue."""

    @pytest.mark.asyncio
    async def test_put_and_get(self, sample_bar):
        """Basic put and get operations."""
        queue = PriorityBarQueue()

        result = await queue.put("AAPL", sample_bar, Priority.MEDIUM)
        assert result is True
        assert queue.qsize() == 1

        item = await queue.get(timeout=1.0)
        assert item.symbol == "AAPL"
        assert item.bar == sample_bar
        assert queue.qsize() == 0

    @pytest.mark.asyncio
    async def test_put_nowait(self, sample_bar):
        """Synchronous put_nowait operation."""
        queue = PriorityBarQueue()

        result = queue.put_nowait("AAPL", sample_bar, Priority.HIGH)
        assert result is True
        assert queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_get_empty_raises(self):
        """Get on empty queue raises QueueEmpty."""
        queue = PriorityBarQueue()

        with pytest.raises(QueueEmpty):
            await queue.get()

    @pytest.mark.asyncio
    async def test_get_nowait_empty_raises(self):
        """get_nowait on empty queue raises QueueEmpty."""
        queue = PriorityBarQueue()

        with pytest.raises(QueueEmpty):
            await queue.get_nowait()

    @pytest.mark.asyncio
    async def test_get_with_timeout_expires(self):
        """Get with timeout raises QueueEmpty when expired."""
        queue = PriorityBarQueue()

        with pytest.raises(QueueEmpty):
            await queue.get(timeout=0.1)

    @pytest.mark.asyncio
    async def test_maxsize_enforcement(self, sample_bar):
        """Queue respects maxsize limit."""
        queue = PriorityBarQueue(maxsize=2)

        assert await queue.put("A", sample_bar, Priority.MEDIUM) is True
        assert await queue.put("B", sample_bar, Priority.MEDIUM) is True
        assert await queue.put("C", sample_bar, Priority.MEDIUM) is False

        assert queue.qsize() == 2

    def test_put_nowait_maxsize(self, sample_bar):
        """put_nowait respects maxsize limit."""
        queue = PriorityBarQueue(maxsize=1)

        assert queue.put_nowait("A", sample_bar, Priority.MEDIUM) is True
        assert queue.put_nowait("B", sample_bar, Priority.MEDIUM) is False

    @pytest.mark.asyncio
    async def test_clear(self, sample_bar):
        """Clear removes all items and returns count."""
        queue = PriorityBarQueue()
        await queue.put("A", sample_bar, Priority.HIGH)
        await queue.put("B", sample_bar, Priority.LOW)

        count = await queue.clear()

        assert count == 2
        assert queue.qsize() == 0
        assert queue.empty()

    def test_empty(self):
        """empty() returns True for empty queue."""
        queue = PriorityBarQueue()
        assert queue.empty() is True


# =============================
# Priority Ordering Tests
# =============================


class TestPriorityOrdering:
    """Tests for priority-based ordering."""

    @pytest.mark.asyncio
    async def test_high_priority_processed_first(self):
        """High priority bars are processed before medium and low."""
        queue = PriorityBarQueue()

        # Add bars in reverse priority order
        queue.put_nowait("LOW", make_bar("LOW"), Priority.LOW)
        queue.put_nowait("MEDIUM", make_bar("MEDIUM"), Priority.MEDIUM)
        queue.put_nowait("HIGH", make_bar("HIGH"), Priority.HIGH)

        # Should get HIGH first, then MEDIUM, then LOW
        item1 = await queue.get_nowait()
        assert item1.symbol == "HIGH"

        item2 = await queue.get_nowait()
        assert item2.symbol == "MEDIUM"

        item3 = await queue.get_nowait()
        assert item3.symbol == "LOW"

    @pytest.mark.asyncio
    async def test_fifo_within_same_priority(self):
        """FIFO order maintained within same priority level."""
        queue = PriorityBarQueue()

        # Add multiple HIGH priority bars
        queue.put_nowait("AAPL", make_bar("AAPL"), Priority.HIGH)
        queue.put_nowait("SPY", make_bar("SPY"), Priority.HIGH)
        queue.put_nowait("TSLA", make_bar("TSLA"), Priority.HIGH)

        # Should get in FIFO order: AAPL, SPY, TSLA
        item1 = await queue.get_nowait()
        assert item1.symbol == "AAPL"

        item2 = await queue.get_nowait()
        assert item2.symbol == "SPY"

        item3 = await queue.get_nowait()
        assert item3.symbol == "TSLA"

    @pytest.mark.asyncio
    async def test_mixed_priority_ordering(self):
        """Mixed priority bars are ordered correctly."""
        queue = PriorityBarQueue()

        # Add bars in interleaved order
        queue.put_nowait("TSLA", make_bar("TSLA"), Priority.LOW)
        queue.put_nowait("MSFT", make_bar("MSFT"), Priority.MEDIUM)
        queue.put_nowait("AAPL", make_bar("AAPL"), Priority.HIGH)
        queue.put_nowait("SPY", make_bar("SPY"), Priority.HIGH)

        # Process all bars
        processed = []
        while not queue.empty():
            item = await queue.get_nowait()
            processed.append(item.symbol)

        # Expected: AAPL, SPY (HIGH), MSFT (MEDIUM), TSLA (LOW)
        assert processed == ["AAPL", "SPY", "MSFT", "TSLA"]

    @pytest.mark.asyncio
    async def test_scenario_congestion_processing(self):
        """Test scenario from story: congestion processing order."""
        queue = PriorityBarQueue()

        # Setup from Story 19.23 Test Scenario 3
        queue.put_nowait("TSLA", make_bar("TSLA"), Priority.LOW)
        queue.put_nowait("MSFT", make_bar("MSFT"), Priority.MEDIUM)
        queue.put_nowait("AAPL", make_bar("AAPL"), Priority.HIGH)
        queue.put_nowait("SPY", make_bar("SPY"), Priority.HIGH)

        # Process and verify order
        order = []
        while not queue.empty():
            item = await queue.get_nowait()
            order.append(item.symbol)

        # Expected: AAPL, SPY, MSFT, TSLA
        assert order == ["AAPL", "SPY", "MSFT", "TSLA"]


# =============================
# SymbolPriorityManager Tests
# =============================


class TestSymbolPriorityManager:
    """Tests for SymbolPriorityManager."""

    @pytest.mark.asyncio
    async def test_default_priority_is_medium(self):
        """Default priority for unknown symbols is MEDIUM."""
        manager = SymbolPriorityManager()

        priority = await manager.get_priority("UNKNOWN")
        assert priority == Priority.MEDIUM

    @pytest.mark.asyncio
    async def test_set_and_get_priority(self):
        """Can set and get symbol priority."""
        manager = SymbolPriorityManager()

        await manager.set_priority("AAPL", Priority.HIGH)
        priority = await manager.get_priority("AAPL")

        assert priority == Priority.HIGH

    def test_get_priority_sync(self):
        """Synchronous priority getter works."""
        manager = SymbolPriorityManager()
        manager._priorities["AAPL"] = Priority.HIGH

        priority = manager.get_priority_sync("AAPL")
        assert priority == Priority.HIGH

        # Unknown symbol returns MEDIUM
        priority = manager.get_priority_sync("UNKNOWN")
        assert priority == Priority.MEDIUM

    @pytest.mark.asyncio
    async def test_set_priorities_bulk(self):
        """Can bulk set multiple priorities."""
        manager = SymbolPriorityManager()

        await manager.set_priorities(
            {
                "AAPL": Priority.HIGH,
                "TSLA": Priority.LOW,
                "SPY": Priority.HIGH,
            }
        )

        assert await manager.get_priority("AAPL") == Priority.HIGH
        assert await manager.get_priority("TSLA") == Priority.LOW
        assert await manager.get_priority("SPY") == Priority.HIGH

    @pytest.mark.asyncio
    async def test_remove_priority(self):
        """Removing priority reverts to MEDIUM."""
        manager = SymbolPriorityManager()

        await manager.set_priority("AAPL", Priority.HIGH)
        await manager.remove_priority("AAPL")

        priority = await manager.get_priority("AAPL")
        assert priority == Priority.MEDIUM

    @pytest.mark.asyncio
    async def test_remove_nonexistent_priority(self):
        """Removing non-existent priority doesn't raise."""
        manager = SymbolPriorityManager()

        await manager.remove_priority("NONEXISTENT")  # Should not raise

    @pytest.mark.asyncio
    async def test_get_all_priorities(self):
        """Can get all priority mappings."""
        manager = SymbolPriorityManager()

        await manager.set_priority("AAPL", Priority.HIGH)
        await manager.set_priority("TSLA", Priority.LOW)

        all_priorities = await manager.get_all_priorities()

        assert all_priorities == {
            "AAPL": Priority.HIGH,
            "TSLA": Priority.LOW,
        }

    @pytest.mark.asyncio
    async def test_clear_priorities(self):
        """Clear removes all priority mappings."""
        manager = SymbolPriorityManager()

        await manager.set_priorities(
            {
                "AAPL": Priority.HIGH,
                "TSLA": Priority.LOW,
            }
        )

        await manager.clear()

        all_priorities = await manager.get_all_priorities()
        assert all_priorities == {}

        # All symbols should revert to MEDIUM
        assert await manager.get_priority("AAPL") == Priority.MEDIUM


# =============================
# Integration Tests
# =============================


class TestPriorityQueueIntegration:
    """Integration tests for priority queue usage patterns."""

    @pytest.mark.asyncio
    async def test_producer_consumer_pattern(self):
        """Test async producer-consumer pattern with priority."""
        queue = PriorityBarQueue(maxsize=100)
        processed = []

        async def producer():
            """Add bars with different priorities."""
            for symbol, priority in [
                ("LOW1", Priority.LOW),
                ("MED1", Priority.MEDIUM),
                ("HIGH1", Priority.HIGH),
                ("LOW2", Priority.LOW),
                ("HIGH2", Priority.HIGH),
            ]:
                await queue.put(symbol, make_bar(symbol), priority)
            # Signal done by adding sentinel
            await queue.put("DONE", make_bar("DONE"), Priority.LOW)

        async def consumer():
            """Process bars from queue."""
            while True:
                try:
                    item = await queue.get(timeout=1.0)
                    if item.symbol == "DONE":
                        break
                    processed.append(item.symbol)
                except QueueEmpty:
                    break

        # Run producer and consumer
        await asyncio.gather(producer(), consumer())

        # Should be processed in priority order
        # HIGH: HIGH1, HIGH2
        # MEDIUM: MED1
        # LOW: LOW1, LOW2
        assert processed == ["HIGH1", "HIGH2", "MED1", "LOW1", "LOW2"]

    @pytest.mark.asyncio
    async def test_load_scenario(self):
        """Test under simulated load with many bars."""
        queue = PriorityBarQueue(maxsize=1000)
        manager = SymbolPriorityManager()

        # Configure some high priority symbols
        await manager.set_priorities(
            {
                "AAPL": Priority.HIGH,
                "SPY": Priority.HIGH,
            }
        )

        # Add 100 bars with varying priorities
        symbols = ["AAPL", "TSLA", "MSFT", "SPY", "GOOGL"]
        for i in range(100):
            symbol = symbols[i % len(symbols)]
            priority = manager.get_priority_sync(symbol)
            queue.put_nowait(symbol, make_bar(symbol), priority)

        assert queue.qsize() == 100

        # Verify first several bars are high priority
        first_five = []
        for _ in range(5):
            item = await queue.get_nowait()
            first_five.append(item.symbol)

        # All first items should be high priority (AAPL or SPY)
        assert all(s in ["AAPL", "SPY"] for s in first_five)
