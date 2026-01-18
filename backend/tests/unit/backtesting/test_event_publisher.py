"""
Unit tests for Campaign Event Publisher (Story 15.6).

Tests cover:
1. Event publishing and delivery
2. Subscription management
3. Wildcard subscriptions
4. Event filtering
5. Error handling
6. Rate limiting
7. Queue handling

Author: Developer Agent (Story 15.6 Implementation)
"""

import time
from datetime import datetime

import pytest

from src.backtesting.event_publisher import EventFilter, EventPublisher
from src.models.campaign_event import CampaignEvent, CampaignEventType


class TestCampaignEvent:
    """Test CampaignEvent dataclass."""

    def test_event_creation_basic(self):
        """Test basic event creation."""
        event = CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test-campaign-123",
            timestamp=datetime(2024, 1, 15, 10, 30),
            pattern_type="Spring",
        )

        assert event.event_type == CampaignEventType.PATTERN_DETECTED
        assert event.campaign_id == "test-campaign-123"
        assert event.pattern_type == "Spring"
        assert event.metadata == {}

    def test_event_creation_with_metadata(self):
        """Test event creation with metadata."""
        metadata = {
            "campaign_state": "ACTIVE",
            "strength_score": 0.85,
            "pattern_count": 3,
        }

        event = CampaignEvent(
            event_type=CampaignEventType.CAMPAIGN_ACTIVATED,
            campaign_id="test-123",
            timestamp=datetime.now(),
            metadata=metadata,
        )

        assert event.metadata == metadata
        assert event.metadata["strength_score"] == 0.85

    def test_event_to_dict(self):
        """Test event serialization to dictionary."""
        event = CampaignEvent(
            event_type=CampaignEventType.CAMPAIGN_FORMED,
            campaign_id="abc-123",
            timestamp=datetime(2024, 1, 15, 10, 30),
            pattern_type="Spring",
            metadata={"phase": "C"},
        )

        result = event.to_dict()

        assert result["event_type"] == "CAMPAIGN_FORMED"
        assert result["campaign_id"] == "abc-123"
        assert result["pattern_type"] == "Spring"
        assert result["metadata"] == {"phase": "C"}
        assert "2024-01-15" in result["timestamp"]

    def test_event_metadata_defaults_to_empty_dict(self):
        """Test that metadata defaults to empty dict."""
        event = CampaignEvent(
            event_type=CampaignEventType.CAMPAIGN_COMPLETED,
            campaign_id="test",
            timestamp=datetime.now(),
        )

        assert event.metadata == {}
        assert isinstance(event.metadata, dict)

    def test_all_event_types(self):
        """Test all event types can be created."""
        event_types = [
            CampaignEventType.CAMPAIGN_FORMED,
            CampaignEventType.CAMPAIGN_ACTIVATED,
            CampaignEventType.PATTERN_DETECTED,
            CampaignEventType.CAMPAIGN_COMPLETED,
            CampaignEventType.CAMPAIGN_FAILED,
        ]

        for event_type in event_types:
            event = CampaignEvent(
                event_type=event_type,
                campaign_id="test",
                timestamp=datetime.now(),
            )
            assert event.event_type == event_type


class TestEventPublisher:
    """Test EventPublisher class."""

    @pytest.fixture
    def publisher(self):
        """Create EventPublisher instance."""
        pub = EventPublisher(max_queue_size=100)
        yield pub
        pub.shutdown(timeout=2.0)

    @pytest.fixture
    def sample_event(self):
        """Create sample event for testing."""
        return CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test-campaign-123",
            timestamp=datetime.now(),
            pattern_type="Spring",
            metadata={"strength_score": 0.75, "campaign_state": "ACTIVE"},
        )

    def test_publish_returns_true(self, publisher, sample_event):
        """Test that publish returns True on success."""
        result = publisher.publish(sample_event)
        assert result is True

    def test_subscribe_and_receive_event(self, publisher, sample_event):
        """Test subscribing and receiving events."""
        received_events: list[CampaignEvent] = []

        def callback(event: CampaignEvent):
            received_events.append(event)

        publisher.subscribe("PATTERN_DETECTED", callback)
        publisher.publish(sample_event)

        # Wait for event delivery
        time.sleep(0.1)

        assert len(received_events) == 1
        assert received_events[0].campaign_id == "test-campaign-123"

    def test_subscribe_specific_event_type(self, publisher):
        """Test subscribing to specific event types only."""
        pattern_events: list[CampaignEvent] = []
        formed_events: list[CampaignEvent] = []

        def on_pattern(event: CampaignEvent):
            pattern_events.append(event)

        def on_formed(event: CampaignEvent):
            formed_events.append(event)

        publisher.subscribe("PATTERN_DETECTED", on_pattern)
        publisher.subscribe("CAMPAIGN_FORMED", on_formed)

        # Publish pattern event
        publisher.publish(
            CampaignEvent(
                event_type=CampaignEventType.PATTERN_DETECTED,
                campaign_id="c1",
                timestamp=datetime.now(),
            )
        )

        # Publish formed event
        publisher.publish(
            CampaignEvent(
                event_type=CampaignEventType.CAMPAIGN_FORMED,
                campaign_id="c2",
                timestamp=datetime.now(),
            )
        )

        time.sleep(0.1)

        assert len(pattern_events) == 1
        assert len(formed_events) == 1
        assert pattern_events[0].campaign_id == "c1"
        assert formed_events[0].campaign_id == "c2"

    def test_wildcard_subscription(self, publisher):
        """Test wildcard subscription receives all events."""
        all_events: list[CampaignEvent] = []

        def on_all(event: CampaignEvent):
            all_events.append(event)

        publisher.subscribe("*", on_all)

        # Publish different event types
        for event_type in [
            CampaignEventType.CAMPAIGN_FORMED,
            CampaignEventType.PATTERN_DETECTED,
            CampaignEventType.CAMPAIGN_ACTIVATED,
        ]:
            publisher.publish(
                CampaignEvent(
                    event_type=event_type,
                    campaign_id="test",
                    timestamp=datetime.now(),
                )
            )

        time.sleep(0.2)

        assert len(all_events) == 3

    def test_unsubscribe(self, publisher, sample_event):
        """Test unsubscribing from events."""
        received_events: list[CampaignEvent] = []

        def callback(event: CampaignEvent):
            received_events.append(event)

        publisher.subscribe("PATTERN_DETECTED", callback)
        publisher.publish(sample_event)
        time.sleep(0.1)

        assert len(received_events) == 1

        # Unsubscribe
        result = publisher.unsubscribe("PATTERN_DETECTED", callback)
        assert result is True

        # Publish again - should not be received
        publisher.publish(sample_event)
        time.sleep(0.1)

        assert len(received_events) == 1  # Still 1, not 2

    def test_unsubscribe_wildcard(self, publisher, sample_event):
        """Test unsubscribing from wildcard subscription."""
        received_events: list[CampaignEvent] = []

        def callback(event: CampaignEvent):
            received_events.append(event)

        publisher.subscribe("*", callback)
        publisher.publish(sample_event)
        time.sleep(0.1)

        assert len(received_events) == 1

        # Unsubscribe wildcard
        result = publisher.unsubscribe("*", callback)
        assert result is True

        publisher.publish(sample_event)
        time.sleep(0.1)

        assert len(received_events) == 1

    def test_unsubscribe_not_found(self, publisher):
        """Test unsubscribing non-existent subscription."""

        def callback(event: CampaignEvent):
            pass

        result = publisher.unsubscribe("PATTERN_DETECTED", callback)
        assert result is False

    def test_callback_error_does_not_break_other_callbacks(self, publisher, sample_event):
        """Test that callback errors don't break other callbacks."""
        successful_events: list[CampaignEvent] = []

        def broken_callback(event: CampaignEvent):
            raise ValueError("Intentional test error")

        def working_callback(event: CampaignEvent):
            successful_events.append(event)

        publisher.subscribe("PATTERN_DETECTED", broken_callback)
        publisher.subscribe("PATTERN_DETECTED", working_callback)

        publisher.publish(sample_event)
        time.sleep(0.1)

        # Working callback should still receive event
        assert len(successful_events) == 1
        # Error count should be tracked
        metrics = publisher.get_metrics()
        assert metrics["callback_errors"] >= 1

    def test_get_metrics(self, publisher, sample_event):
        """Test metrics tracking."""
        publisher.publish(sample_event)
        time.sleep(0.1)

        metrics = publisher.get_metrics()

        assert "events_published" in metrics
        assert "events_delivered" in metrics
        assert "events_dropped" in metrics
        assert "callback_errors" in metrics
        assert "queue_size" in metrics
        assert "subscriber_count" in metrics

        assert metrics["events_published"] >= 1

    def test_multiple_subscribers_same_event(self, publisher, sample_event):
        """Test multiple subscribers for same event type."""
        results: list[str] = []

        def callback_a(event: CampaignEvent):
            results.append("A")

        def callback_b(event: CampaignEvent):
            results.append("B")

        def callback_c(event: CampaignEvent):
            results.append("C")

        publisher.subscribe("PATTERN_DETECTED", callback_a)
        publisher.subscribe("PATTERN_DETECTED", callback_b)
        publisher.subscribe("PATTERN_DETECTED", callback_c)

        publisher.publish(sample_event)
        time.sleep(0.1)

        assert len(results) == 3
        assert set(results) == {"A", "B", "C"}


class TestEventFilter:
    """Test EventFilter class."""

    def test_filter_matches_all_by_default(self):
        """Test that empty filter matches all events."""
        event_filter = EventFilter()

        event = CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test",
            timestamp=datetime.now(),
            pattern_type="Spring",
            metadata={"strength_score": 0.5},
        )

        assert event_filter.matches(event) is True

    def test_filter_by_min_strength_score(self):
        """Test filtering by minimum strength score."""
        event_filter = EventFilter(min_strength_score=0.7)

        low_score_event = CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test",
            timestamp=datetime.now(),
            metadata={"strength_score": 0.5},
        )

        high_score_event = CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test",
            timestamp=datetime.now(),
            metadata={"strength_score": 0.8},
        )

        assert event_filter.matches(low_score_event) is False
        assert event_filter.matches(high_score_event) is True

    def test_filter_by_pattern_types(self):
        """Test filtering by pattern types."""
        event_filter = EventFilter(pattern_types=["Spring", "SOSBreakout"])

        spring_event = CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test",
            timestamp=datetime.now(),
            pattern_type="Spring",
        )

        lps_event = CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test",
            timestamp=datetime.now(),
            pattern_type="LPS",
        )

        assert event_filter.matches(spring_event) is True
        assert event_filter.matches(lps_event) is False

    def test_filter_combined_criteria(self):
        """Test filter with combined criteria."""
        event_filter = EventFilter(
            min_strength_score=0.6,
            pattern_types=["Spring", "SOSBreakout"],
        )

        # Matches both criteria
        good_event = CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test",
            timestamp=datetime.now(),
            pattern_type="Spring",
            metadata={"strength_score": 0.8},
        )

        # Wrong pattern type
        wrong_pattern = CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test",
            timestamp=datetime.now(),
            pattern_type="LPS",
            metadata={"strength_score": 0.8},
        )

        # Low score
        low_score = CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test",
            timestamp=datetime.now(),
            pattern_type="Spring",
            metadata={"strength_score": 0.4},
        )

        assert event_filter.matches(good_event) is True
        assert event_filter.matches(wrong_pattern) is False
        assert event_filter.matches(low_score) is False


class TestEventPublisherWithFilter:
    """Test EventPublisher with EventFilter."""

    @pytest.fixture
    def publisher(self):
        """Create EventPublisher instance."""
        pub = EventPublisher(max_queue_size=100)
        yield pub
        pub.shutdown(timeout=2.0)

    def test_filtered_subscription(self, publisher):
        """Test subscription with filter."""
        received_events: list[CampaignEvent] = []

        def callback(event: CampaignEvent):
            received_events.append(event)

        # Only receive events with strength_score >= 0.7
        event_filter = EventFilter(min_strength_score=0.7)
        publisher.subscribe("PATTERN_DETECTED", callback, event_filter)

        # Publish low score event
        publisher.publish(
            CampaignEvent(
                event_type=CampaignEventType.PATTERN_DETECTED,
                campaign_id="low",
                timestamp=datetime.now(),
                metadata={"strength_score": 0.5},
            )
        )

        # Publish high score event
        publisher.publish(
            CampaignEvent(
                event_type=CampaignEventType.PATTERN_DETECTED,
                campaign_id="high",
                timestamp=datetime.now(),
                metadata={"strength_score": 0.9},
            )
        )

        time.sleep(0.1)

        # Should only receive high score event
        assert len(received_events) == 1
        assert received_events[0].campaign_id == "high"


class TestEventPublisherQueueHandling:
    """Test EventPublisher queue edge cases."""

    def test_queue_full_drops_event(self):
        """Test that events are dropped when queue is full."""
        # Small queue size to test overflow
        publisher = EventPublisher(max_queue_size=5)

        # Don't subscribe anything so events stay in queue
        # Publish more events than queue can hold
        dropped_count = 0
        for i in range(10):
            event = CampaignEvent(
                event_type=CampaignEventType.PATTERN_DETECTED,
                campaign_id=f"test-{i}",
                timestamp=datetime.now(),
            )
            if not publisher.publish(event):
                dropped_count += 1

        # Some events should have been dropped
        metrics = publisher.get_metrics()
        assert metrics["events_dropped"] > 0

        publisher.shutdown(timeout=2.0)

    def test_shutdown_drains_queue(self):
        """Test that shutdown waits for queue to drain."""
        publisher = EventPublisher()
        received_events: list[CampaignEvent] = []

        def callback(event: CampaignEvent):
            time.sleep(0.05)  # Slow callback
            received_events.append(event)

        publisher.subscribe("PATTERN_DETECTED", callback)

        # Publish several events
        for i in range(5):
            publisher.publish(
                CampaignEvent(
                    event_type=CampaignEventType.PATTERN_DETECTED,
                    campaign_id=f"test-{i}",
                    timestamp=datetime.now(),
                )
            )

        # Shutdown should wait for all events
        publisher.shutdown(timeout=5.0)

        # All events should have been processed
        assert len(received_events) == 5


class TestEventPublisherRateLimiting:
    """Test EventPublisher rate limiting."""

    def test_rate_limiting(self):
        """Test rate limiting prevents too many events per minute."""
        publisher = EventPublisher(max_events_per_minute=5)
        received_events: list[CampaignEvent] = []

        def callback(event: CampaignEvent):
            received_events.append(event)

        publisher.subscribe("*", callback)

        # Publish 10 events quickly
        published_count = 0
        for i in range(10):
            event = CampaignEvent(
                event_type=CampaignEventType.PATTERN_DETECTED,
                campaign_id=f"test-{i}",
                timestamp=datetime.now(),
            )
            if publisher.publish(event):
                published_count += 1

        time.sleep(0.2)

        # Should have rate limited some events
        metrics = publisher.get_metrics()
        assert metrics["events_dropped"] > 0
        assert published_count <= 5

        publisher.shutdown(timeout=2.0)


class TestEventDeliveryLatency:
    """Test event delivery performance requirements."""

    def test_publish_overhead_under_1ms(self):
        """Test that publish has < 1ms overhead."""
        publisher = EventPublisher()

        event = CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test",
            timestamp=datetime.now(),
        )

        # Measure publish time
        start = time.perf_counter()
        for _ in range(100):
            publisher.publish(event)
        elapsed = time.perf_counter() - start

        avg_time_ms = (elapsed / 100) * 1000

        # Average should be well under 1ms
        assert avg_time_ms < 1.0, f"Publish overhead too high: {avg_time_ms:.3f}ms"

        publisher.shutdown(timeout=2.0)

    def test_event_delivery_under_500ms(self):
        """Test that event delivery is < 500ms."""
        publisher = EventPublisher()
        delivery_times: list[float] = []

        def callback(event: CampaignEvent):
            elapsed = time.perf_counter() - event.metadata["publish_time"]
            delivery_times.append(elapsed)

        publisher.subscribe("*", callback)

        # Publish events with timestamp
        for i in range(10):
            event = CampaignEvent(
                event_type=CampaignEventType.PATTERN_DETECTED,
                campaign_id=f"test-{i}",
                timestamp=datetime.now(),
                metadata={"publish_time": time.perf_counter()},
            )
            publisher.publish(event)

        # Wait for all deliveries
        time.sleep(0.5)

        # All delivery times should be < 500ms
        for dt in delivery_times:
            assert dt < 0.5, f"Delivery too slow: {dt * 1000:.1f}ms"

        publisher.shutdown(timeout=2.0)
