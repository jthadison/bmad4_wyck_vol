"""
Campaign Event Publisher (Story 15.6)

Purpose:
--------
Provides async (non-blocking) event publishing for campaign lifecycle events.
Uses a background thread to dispatch events to subscribers without impacting
pattern processing performance.

Features:
---------
1. Non-blocking publish: Events queued instantly (< 1ms overhead)
2. Async delivery: Background thread dispatches to subscribers
3. Subscription management: Subscribe/unsubscribe by event type
4. Wildcard support: Subscribe to all events with "*"
5. Error isolation: Callback failures don't break other callbacks
6. Rate limiting: Optional max events per minute

Architecture:
-------------
- In-memory event queue (queue.Queue)
- Background dispatcher thread (daemon)
- Type-safe subscriptions with callback error handling
- Structured logging for observability

Author: Developer Agent (Story 15.6 Implementation)
"""

import logging
import queue
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any

import structlog

from src.models.campaign_event import CampaignEvent, CampaignEventType

logger = structlog.get_logger(__name__)

# Type alias for event callbacks
EventCallback = Callable[[CampaignEvent], None]


class EventFilter:
    """
    Filter for event subscriptions.

    Allows subscribers to filter events based on campaign attributes
    like minimum strength score or specific pattern types.

    Attributes:
        min_strength_score: Minimum campaign strength score (0.0-1.0)
        pattern_types: Only receive events for these pattern types (None = all)

    Example:
        >>> filter = EventFilter(min_strength_score=0.7, pattern_types=["Spring", "SOSBreakout"])
        >>> filter.matches(event)
        True
    """

    def __init__(
        self,
        min_strength_score: float | None = None,
        pattern_types: list[str] | None = None,
    ) -> None:
        """Initialize event filter with optional criteria."""
        self.min_strength_score = min_strength_score
        self.pattern_types = pattern_types

    def matches(self, event: CampaignEvent) -> bool:
        """
        Check if event matches filter criteria.

        Args:
            event: Event to check

        Returns:
            True if event matches all filter criteria
        """
        # Check strength score filter
        if self.min_strength_score is not None:
            strength_score = event.metadata.get("strength_score")
            if strength_score is None or strength_score < self.min_strength_score:
                return False

        # Check pattern type filter
        if self.pattern_types is not None:
            if event.pattern_type and event.pattern_type not in self.pattern_types:
                return False

        return True


class EventPublisher:
    """
    Async event publisher for campaign events.

    Uses background thread for non-blocking delivery. Subscribers register
    callbacks that are invoked when matching events occur.

    Args:
        max_queue_size: Maximum events in queue before dropping (default: 1000)
        max_events_per_minute: Rate limit for events (default: None = unlimited)

    Example:
        >>> publisher = EventPublisher()
        >>> def on_pattern(event):
        ...     print(f"Pattern detected: {event.pattern_type}")
        >>> publisher.subscribe("PATTERN_DETECTED", on_pattern)
        >>> publisher.publish(event)  # Non-blocking
        >>> publisher.shutdown()
    """

    def __init__(
        self,
        max_queue_size: int = 1000,
        max_events_per_minute: int | None = None,
    ) -> None:
        """Initialize event publisher with background dispatcher."""
        # Validate max_queue_size bounds
        if max_queue_size < 1:
            raise ValueError("max_queue_size must be at least 1")
        if max_queue_size > 100000:
            raise ValueError("max_queue_size cannot exceed 100000")

        self._event_queue: queue.Queue[CampaignEvent] = queue.Queue(maxsize=max_queue_size)
        self._subscribers: dict[
            CampaignEventType, list[tuple[EventCallback, EventFilter | None]]
        ] = defaultdict(list)
        self._wildcard_subscribers: list[tuple[EventCallback, EventFilter | None]] = []
        self._max_events_per_minute = max_events_per_minute

        # Rate limiting state - use deque for O(1) append/popleft operations
        self._event_timestamps: deque[float] = deque()
        self._rate_limit_lock = threading.Lock()

        # Background dispatcher
        self._running = True
        self._dispatcher_ready = threading.Event()
        self._dispatcher_thread = threading.Thread(
            target=self._dispatch_events,
            daemon=True,
            name="CampaignEventDispatcher",
        )
        self._dispatcher_thread.start()
        # Wait for dispatcher to be ready (max 2 seconds)
        ready = self._dispatcher_ready.wait(timeout=2.0)
        if not ready:
            # Use standard logging as fallback
            logging.warning(
                "Dispatcher thread failed to start in time - thread alive: %s",
                self._dispatcher_thread.is_alive(),
            )

        # Metrics
        self._events_published = 0
        self._events_delivered = 0
        self._events_dropped = 0
        self._callback_errors = 0

        self.logger = logger.bind(component="EventPublisher")
        self.logger.info(
            "EventPublisher started",
            max_queue_size=max_queue_size,
            max_events_per_minute=max_events_per_minute,
        )

    def publish(self, event: CampaignEvent) -> bool:
        """
        Publish event to queue (non-blocking).

        Event is queued instantly and delivered asynchronously by background
        thread. Overhead is < 1ms.

        Args:
            event: Campaign event to publish

        Returns:
            True if event was queued, False if dropped (queue full or rate limited)
        """
        # Check rate limit
        if self._max_events_per_minute is not None:
            if not self._check_rate_limit():
                self.logger.warning(
                    "Event rate limited",
                    event_type=event.event_type.value,
                    campaign_id=event.campaign_id,
                    max_per_minute=self._max_events_per_minute,
                )
                self._events_dropped += 1
                return False

        try:
            self._event_queue.put_nowait(event)
            self._events_published += 1

            self.logger.debug(
                "Event published",
                event_type=event.event_type.value,
                campaign_id=event.campaign_id,
                pattern_type=event.pattern_type,
                queue_size=self._event_queue.qsize(),
            )
            return True

        except queue.Full:
            self.logger.warning(
                "Event queue full, dropping event",
                event_type=event.event_type.value,
                campaign_id=event.campaign_id,
            )
            self._events_dropped += 1
            return False

    def subscribe(
        self,
        event_type: str,
        callback: EventCallback,
        event_filter: EventFilter | None = None,
    ) -> None:
        """
        Subscribe to events.

        Args:
            event_type: Event type or "*" for all events
            callback: Function to call on event (receives CampaignEvent)
            event_filter: Optional filter for event attributes

        Example:
            >>> def on_spring(event):
            ...     print(f"Spring detected in campaign {event.campaign_id}")
            >>> publisher.subscribe("PATTERN_DETECTED", on_spring, EventFilter(pattern_types=["Spring"]))
        """
        if event_type == "*":
            self._wildcard_subscribers.append((callback, event_filter))
            self.logger.debug(
                "Wildcard subscriber registered",
                callback=callback.__name__,
                has_filter=event_filter is not None,
            )
        else:
            event_enum = CampaignEventType(event_type)
            self._subscribers[event_enum].append((callback, event_filter))
            self.logger.debug(
                "Subscriber registered",
                event_type=event_type,
                callback=callback.__name__,
                has_filter=event_filter is not None,
            )

    def unsubscribe(
        self,
        event_type: str,
        callback: EventCallback,
    ) -> bool:
        """
        Unsubscribe from events.

        Args:
            event_type: Event type or "*"
            callback: Callback to remove

        Returns:
            True if callback was found and removed
        """
        if event_type == "*":
            for i, (cb, _) in enumerate(self._wildcard_subscribers):
                if cb == callback:
                    self._wildcard_subscribers.pop(i)
                    self.logger.debug("Wildcard subscriber removed", callback=callback.__name__)
                    return True
        else:
            event_enum = CampaignEventType(event_type)
            for i, (cb, _) in enumerate(self._subscribers[event_enum]):
                if cb == callback:
                    self._subscribers[event_enum].pop(i)
                    self.logger.debug(
                        "Subscriber removed",
                        event_type=event_type,
                        callback=callback.__name__,
                    )
                    return True
        return False

    def _check_rate_limit(self) -> bool:
        """
        Check if event can be published (rate limit).

        Returns:
            True if event can be published, False if rate limited
        """
        if self._max_events_per_minute is None:
            return True

        current_time = time.time()
        one_minute_ago = current_time - 60.0

        with self._rate_limit_lock:
            # Remove old timestamps from front of deque (O(1) per removal)
            while self._event_timestamps and self._event_timestamps[0] <= one_minute_ago:
                self._event_timestamps.popleft()

            # Check limit
            if len(self._event_timestamps) >= self._max_events_per_minute:
                return False

            # Add current timestamp (O(1) append)
            self._event_timestamps.append(current_time)
            return True

    def _dispatch_events(self) -> None:
        """Background thread that dispatches events to subscribers."""
        try:
            logging.info("Event dispatcher started")
            # Signal that dispatcher is ready
            self._dispatcher_ready.set()

            while self._running:
                try:
                    # Wait for event (100ms timeout for responsive shutdown)
                    event = self._event_queue.get(timeout=0.1)

                    # Deliver to subscribers
                    self._deliver_event(event)

                    self._event_queue.task_done()

                except queue.Empty:
                    continue
                except Exception as e:
                    logging.error("Event dispatcher error: %s - %s", type(e).__name__, str(e))

            logging.info("Event dispatcher stopped")
        except Exception:
            logging.exception("FATAL: Dispatcher thread crashed")

    def _deliver_event(self, event: CampaignEvent) -> None:
        """
        Deliver event to all matching subscribers.

        Args:
            event: Event to deliver
        """
        delivered_count = 0

        # Specific subscribers
        for callback, event_filter in self._subscribers[event.event_type]:
            if event_filter is None or event_filter.matches(event):
                if self._invoke_callback(callback, event):
                    delivered_count += 1

        # Wildcard subscribers
        for callback, event_filter in self._wildcard_subscribers:
            if event_filter is None or event_filter.matches(event):
                if self._invoke_callback(callback, event):
                    delivered_count += 1

        self._events_delivered += delivered_count

        # Log structured event (Story 15.6: Logging channel)
        self.logger.info(
            "Campaign event",
            event_type=event.event_type.value,
            campaign_id=event.campaign_id,
            pattern_type=event.pattern_type,
            metadata=event.metadata,
            subscribers_notified=delivered_count,
        )

    def _invoke_callback(self, callback: EventCallback, event: CampaignEvent) -> bool:
        """
        Safely invoke callback with error handling.

        Args:
            callback: Callback to invoke
            event: Event to pass

        Returns:
            True if callback succeeded
        """
        try:
            callback(event)
            return True
        except Exception as e:
            self._callback_errors += 1
            self.logger.error(
                "Event callback failed",
                event_type=event.event_type.value,
                campaign_id=event.campaign_id,
                callback=callback.__name__,
                error=str(e),
                error_type=type(e).__name__,
            )
            return False

    def get_metrics(self) -> dict[str, Any]:
        """
        Get publisher metrics.

        Returns:
            Dictionary with events_published, events_delivered, events_dropped, callback_errors
        """
        return {
            "events_published": self._events_published,
            "events_delivered": self._events_delivered,
            "events_dropped": self._events_dropped,
            "callback_errors": self._callback_errors,
            "queue_size": self._event_queue.qsize(),
            "subscriber_count": sum(len(subs) for subs in self._subscribers.values())
            + len(self._wildcard_subscribers),
        }

    def shutdown(self, timeout: float = 5.0) -> None:
        """
        Shutdown event publisher.

        Waits for queue to drain and stops dispatcher thread.

        Args:
            timeout: Maximum seconds to wait for shutdown
        """
        self.logger.info("Shutting down EventPublisher", queue_size=self._event_queue.qsize())

        # Wait for queue to drain BEFORE stopping dispatcher
        # The dispatcher thread needs to keep running to process remaining events
        start_time = time.time()
        while not self._event_queue.empty() and (time.time() - start_time) < timeout:
            time.sleep(0.05)

        # Now stop the dispatcher thread
        self._running = False

        # Wait for dispatcher thread to finish (with remaining timeout)
        remaining_timeout = max(0.1, timeout - (time.time() - start_time))
        self._dispatcher_thread.join(timeout=remaining_timeout)

        metrics = self.get_metrics()
        self.logger.info(
            "EventPublisher shutdown complete",
            **metrics,
        )
