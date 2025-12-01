"""
Unit tests for EventBus.

Tests publish/subscribe mechanism, error isolation, and metrics tracking.

Story 8.1: Master Orchestrator Architecture (AC: 3, 8)
"""

from uuid import uuid4

import pytest

from src.orchestrator.event_bus import EventBus, get_event_bus, reset_event_bus
from src.orchestrator.events import Event, VolumeAnalyzedEvent


@pytest.fixture
def event_bus() -> EventBus:
    """Create a fresh EventBus instance for each test."""
    return EventBus()


@pytest.fixture
def sample_event() -> VolumeAnalyzedEvent:
    """Create a sample VolumeAnalyzedEvent for testing."""
    return VolumeAnalyzedEvent(
        correlation_id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        volume_ratio=1.5,
        spread_ratio=1.2,
        close_position=0.75,
        effort_result="NORMAL",
        bars_analyzed=500,
    )


class TestEventBusSubscribe:
    """Tests for subscribe functionality."""

    @pytest.mark.asyncio
    async def test_subscribe_adds_handler(self, event_bus: EventBus):
        """Test that subscribe adds handler to registry."""

        async def handler(event: Event):
            pass

        event_bus.subscribe("test_event", handler)

        assert event_bus.get_handler_count("test_event") == 1

    @pytest.mark.asyncio
    async def test_subscribe_multiple_handlers(self, event_bus: EventBus):
        """Test that multiple handlers can subscribe to same event type."""

        async def handler1(event: Event):
            pass

        async def handler2(event: Event):
            pass

        event_bus.subscribe("test_event", handler1)
        event_bus.subscribe("test_event", handler2)

        assert event_bus.get_handler_count("test_event") == 2

    @pytest.mark.asyncio
    async def test_subscribe_different_event_types(self, event_bus: EventBus):
        """Test handlers can subscribe to different event types."""

        async def handler1(event: Event):
            pass

        async def handler2(event: Event):
            pass

        event_bus.subscribe("event_type_a", handler1)
        event_bus.subscribe("event_type_b", handler2)

        assert event_bus.get_handler_count("event_type_a") == 1
        assert event_bus.get_handler_count("event_type_b") == 1


class TestEventBusUnsubscribe:
    """Tests for unsubscribe functionality."""

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_handler(self, event_bus: EventBus):
        """Test that unsubscribe removes handler from registry."""

        async def handler(event: Event):
            pass

        event_bus.subscribe("test_event", handler)
        result = event_bus.unsubscribe("test_event", handler)

        assert result is True
        assert event_bus.get_handler_count("test_event") == 0

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent_handler(self, event_bus: EventBus):
        """Test that unsubscribing non-existent handler returns False."""

        async def handler(event: Event):
            pass

        result = event_bus.unsubscribe("test_event", handler)

        assert result is False


class TestEventBusPublish:
    """Tests for publish functionality."""

    @pytest.mark.asyncio
    async def test_publish_invokes_handler(
        self, event_bus: EventBus, sample_event: VolumeAnalyzedEvent
    ):
        """Test that publish invokes subscribed handler."""
        received_events = []

        async def handler(event: Event):
            received_events.append(event)

        event_bus.subscribe("volume_analyzed", handler)
        await event_bus.publish(sample_event)

        assert len(received_events) == 1
        assert received_events[0].event_id == sample_event.event_id

    @pytest.mark.asyncio
    async def test_publish_invokes_multiple_handlers(
        self, event_bus: EventBus, sample_event: VolumeAnalyzedEvent
    ):
        """Test that publish invokes all subscribed handlers."""
        handler1_called = []
        handler2_called = []

        async def handler1(event: Event):
            handler1_called.append(True)

        async def handler2(event: Event):
            handler2_called.append(True)

        event_bus.subscribe("volume_analyzed", handler1)
        event_bus.subscribe("volume_analyzed", handler2)
        await event_bus.publish(sample_event)

        assert len(handler1_called) == 1
        assert len(handler2_called) == 1

    @pytest.mark.asyncio
    async def test_publish_no_handlers(
        self, event_bus: EventBus, sample_event: VolumeAnalyzedEvent
    ):
        """Test that publish with no handlers doesn't raise error."""
        # Should not raise
        await event_bus.publish(sample_event)

        assert event_bus.event_count == 1

    @pytest.mark.asyncio
    async def test_publish_increments_event_count(
        self, event_bus: EventBus, sample_event: VolumeAnalyzedEvent
    ):
        """Test that publish increments event counter."""
        await event_bus.publish(sample_event)
        await event_bus.publish(sample_event)

        assert event_bus.event_count == 2


class TestEventBusErrorIsolation:
    """Tests for error isolation (handler errors don't affect others)."""

    @pytest.mark.asyncio
    async def test_handler_error_does_not_affect_others(
        self, event_bus: EventBus, sample_event: VolumeAnalyzedEvent
    ):
        """Test that handler errors don't prevent other handlers from running."""
        successful_calls = []

        async def failing_handler(event: Event):
            raise ValueError("Handler error")

        async def successful_handler(event: Event):
            successful_calls.append(True)

        event_bus.subscribe("volume_analyzed", failing_handler)
        event_bus.subscribe("volume_analyzed", successful_handler)

        await event_bus.publish(sample_event)

        assert len(successful_calls) == 1
        assert event_bus.error_count == 1

    @pytest.mark.asyncio
    async def test_handler_error_increments_error_count(
        self, event_bus: EventBus, sample_event: VolumeAnalyzedEvent
    ):
        """Test that handler errors increment error counter."""

        async def failing_handler(event: Event):
            raise ValueError("Handler error")

        event_bus.subscribe("volume_analyzed", failing_handler)
        await event_bus.publish(sample_event)

        assert event_bus.error_count == 1


class TestEventBusMetrics:
    """Tests for metrics and monitoring."""

    @pytest.mark.asyncio
    async def test_get_metrics(self, event_bus: EventBus, sample_event: VolumeAnalyzedEvent):
        """Test get_metrics returns accurate information."""

        async def handler(event: Event):
            pass

        event_bus.subscribe("volume_analyzed", handler)
        await event_bus.publish(sample_event)

        metrics = event_bus.get_metrics()

        assert metrics["event_count"] == 1
        assert metrics["error_count"] == 0
        assert "volume_analyzed" in metrics["subscribed_types"]
        assert metrics["handler_counts"]["volume_analyzed"] == 1

    @pytest.mark.asyncio
    async def test_get_subscribed_event_types(self, event_bus: EventBus):
        """Test get_subscribed_event_types returns correct types."""

        async def handler(event: Event):
            pass

        event_bus.subscribe("type_a", handler)
        event_bus.subscribe("type_b", handler)

        types = event_bus.get_subscribed_event_types()

        assert "type_a" in types
        assert "type_b" in types
        assert len(types) == 2


class TestEventBusClear:
    """Tests for clear functionality."""

    @pytest.mark.asyncio
    async def test_clear_removes_all_subscriptions(self, event_bus: EventBus):
        """Test that clear removes all handlers and resets metrics."""

        async def handler(event: Event):
            pass

        event_bus.subscribe("type_a", handler)
        event_bus.subscribe("type_b", handler)

        event_bus.clear()

        assert event_bus.get_handler_count("type_a") == 0
        assert event_bus.get_handler_count("type_b") == 0
        assert event_bus.event_count == 0
        assert event_bus.error_count == 0


class TestEventBusSingleton:
    """Tests for singleton behavior."""

    def test_get_event_bus_returns_singleton(self):
        """Test that get_event_bus returns the same instance."""
        reset_event_bus()
        bus1 = get_event_bus()
        bus2 = get_event_bus()

        assert bus1 is bus2

    def test_reset_event_bus_creates_new_instance(self):
        """Test that reset_event_bus creates a new instance."""
        bus1 = get_event_bus()
        reset_event_bus()
        bus2 = get_event_bus()

        assert bus1 is not bus2
