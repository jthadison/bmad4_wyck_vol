"""
In-Memory Event Bus for Orchestrator Coordination.

Provides publish/subscribe functionality for communication between pipeline
stages and detectors. Uses asyncio queues for async event processing.

Story 8.1: Master Orchestrator Architecture (AC: 3)
"""

import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import Any

import structlog

from src.orchestrator.events import Event

logger = structlog.get_logger(__name__)

# Type alias for event handlers
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """
    In-memory event bus for detector coordination.

    Provides async publish/subscribe functionality for loose coupling between
    pipeline stages. Handlers are invoked concurrently for performance.

    Features:
    - Async event processing with asyncio
    - Multiple handlers per event type
    - Structured logging for all operations
    - Error isolation (handler failures don't affect other handlers)
    - Metrics tracking for monitoring

    Example:
        >>> bus = EventBus()
        >>>
        >>> async def handle_volume(event: VolumeAnalyzedEvent):
        ...     print(f"Volume analyzed: {event.volume_ratio}")
        >>>
        >>> bus.subscribe("volume_analyzed", handle_volume)
        >>> await bus.publish(VolumeAnalyzedEvent(...))
    """

    def __init__(self) -> None:
        """Initialize event bus with empty handler registry."""
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._event_count: int = 0
        self._error_count: int = 0
        self._lock = asyncio.Lock()

        logger.info("event_bus_initialized")

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """
        Subscribe a handler to an event type.

        Handlers are async functions that receive the event as parameter.
        Multiple handlers can subscribe to the same event type.

        Args:
            event_type: Event type string (e.g., "volume_analyzed")
            handler: Async function to call when event is published

        Example:
            >>> async def my_handler(event: Event):
            ...     print(f"Received: {event.event_type}")
            >>> bus.subscribe("volume_analyzed", my_handler)
        """
        self._handlers[event_type].append(handler)
        logger.debug(
            "handler_subscribed",
            event_type=event_type,
            handler_name=handler.__name__,
            total_handlers=len(self._handlers[event_type]),
        )

    def unsubscribe(self, event_type: str, handler: EventHandler) -> bool:
        """
        Unsubscribe a handler from an event type.

        Args:
            event_type: Event type string
            handler: Handler to remove

        Returns:
            True if handler was found and removed, False otherwise
        """
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            logger.debug(
                "handler_unsubscribed",
                event_type=event_type,
                handler_name=handler.__name__,
                remaining_handlers=len(self._handlers[event_type]),
            )
            return True
        return False

    async def publish(self, event: Event) -> None:
        """
        Publish an event to all subscribed handlers.

        Handlers are invoked concurrently using asyncio.gather.
        Handler errors are logged but don't affect other handlers.

        Args:
            event: Event to publish

        Example:
            >>> await bus.publish(VolumeAnalyzedEvent(
            ...     correlation_id=uuid4(),
            ...     symbol="AAPL",
            ...     timeframe="1d",
            ...     volume_ratio=1.5,
            ...     spread_ratio=1.2,
            ...     close_position=0.75,
            ...     effort_result="NORMAL",
            ...     bars_analyzed=500
            ... ))
        """
        async with self._lock:
            self._event_count += 1

        handlers = self._handlers.get(event.event_type, [])

        if not handlers:
            logger.debug(
                "event_published_no_handlers",
                event_type=event.event_type,
                event_id=str(event.event_id),
                correlation_id=str(event.correlation_id),
            )
            return

        logger.debug(
            "event_publishing",
            event_type=event.event_type,
            event_id=str(event.event_id),
            correlation_id=str(event.correlation_id),
            symbol=event.symbol,
            handler_count=len(handlers),
        )

        # Create tasks for all handlers
        tasks = [self._invoke_handler(handler, event) for handler in handlers]

        # Execute all handlers concurrently
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _invoke_handler(self, handler: EventHandler, event: Event) -> None:
        """
        Invoke a single handler with error isolation.

        Args:
            handler: Handler function to invoke
            event: Event to pass to handler
        """
        try:
            await handler(event)
        except Exception as e:
            async with self._lock:
                self._error_count += 1

            logger.error(
                "handler_error",
                handler_name=handler.__name__,
                event_type=event.event_type,
                event_id=str(event.event_id),
                correlation_id=str(event.correlation_id),
                error=str(e),
                error_type=type(e).__name__,
            )

    def get_handler_count(self, event_type: str) -> int:
        """
        Get number of handlers subscribed to an event type.

        Args:
            event_type: Event type string

        Returns:
            Number of subscribed handlers
        """
        return len(self._handlers.get(event_type, []))

    def get_subscribed_event_types(self) -> list[str]:
        """
        Get all event types with at least one subscriber.

        Returns:
            List of event type strings
        """
        return [et for et, handlers in self._handlers.items() if handlers]

    @property
    def event_count(self) -> int:
        """Total number of events published."""
        return self._event_count

    @property
    def error_count(self) -> int:
        """Total number of handler errors."""
        return self._error_count

    def get_metrics(self) -> dict[str, Any]:
        """
        Get event bus metrics for monitoring.

        Returns:
            Dictionary with metrics:
            - event_count: Total events published
            - error_count: Total handler errors
            - handler_counts: Handlers per event type
            - subscribed_types: List of subscribed event types
        """
        return {
            "event_count": self._event_count,
            "error_count": self._error_count,
            "handler_counts": {et: len(handlers) for et, handlers in self._handlers.items()},
            "subscribed_types": self.get_subscribed_event_types(),
        }

    def clear(self) -> None:
        """
        Clear all subscriptions and reset metrics.

        Useful for testing.
        """
        self._handlers.clear()
        self._event_count = 0
        self._error_count = 0
        logger.info("event_bus_cleared")


# Singleton instance for application-wide event bus
_event_bus_instance: EventBus | None = None


def get_event_bus() -> EventBus:
    """
    Get the singleton event bus instance.

    Returns:
        EventBus: The application-wide event bus

    Example:
        >>> bus = get_event_bus()
        >>> bus.subscribe("volume_analyzed", my_handler)
    """
    global _event_bus_instance
    if _event_bus_instance is None:
        _event_bus_instance = EventBus()
    return _event_bus_instance


def reset_event_bus() -> None:
    """
    Reset the singleton event bus (for testing).

    Creates a new EventBus instance, clearing all subscriptions.
    """
    global _event_bus_instance
    _event_bus_instance = EventBus()
