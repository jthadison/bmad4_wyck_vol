"""
Campaign Event Notification System (Story 9.7, Task 2)

Purpose:
--------
Provides event-driven architecture for campaign state change notifications.
Enables loose coupling between CampaignManager and dependent services
(NotificationService, PerformanceTracker, WebSocketService).

Event Types:
------------
- CampaignCreatedEvent: Campaign initialized with first signal
- CampaignUpdatedEvent: Campaign status/phase/metrics changed
- CampaignInvalidatedEvent: Campaign stopped (Spring low breached)
- CampaignCompletedEvent: All positions closed, campaign finished

Architecture:
-------------
- EventBus: Publish/subscribe pattern with asyncio.Queue
- Subscribers: Services register callbacks for specific event types
- Background task: Processes event queue and dispatches to subscribers
- Audit trail: All events logged to database with correlation_id

Integration:
------------
- Story 9.7: Used by CampaignManager to emit state change events
- Story 9.6: PerformanceTracker subscribes to CampaignCompleted events
- Epic 8: NotificationService subscribes to CampaignInvalidated events
- Frontend: WebSocketService subscribes to all campaign events

Author: Story 9.7 Task 2
"""

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel, ConfigDict, Field, model_serializer

logger = structlog.get_logger(__name__)


# ==================================================================================
# Event Models
# ==================================================================================


class CampaignEvent(BaseModel):
    """
    Base class for all campaign events.

    Fields
    ------
    event_id : UUID
        Unique event identifier
    campaign_id : UUID
        Campaign this event relates to
    timestamp : datetime
        When event occurred (UTC)
    correlation_id : UUID
        Correlation ID for tracing related events
    """

    event_id: UUID = Field(default_factory=uuid4, description="Unique event identifier")
    campaign_id: UUID = Field(..., description="Campaign this event relates to")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="When event occurred (UTC)"
    )
    correlation_id: UUID = Field(
        default_factory=uuid4, description="Correlation ID for tracing related events"
    )

    model_config = ConfigDict(json_encoders={Decimal: str, UUID: str, datetime: str})

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize model with UUID and datetime as strings."""
        return {
            "event_id": str(self.event_id),
            "campaign_id": str(self.campaign_id),
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": str(self.correlation_id),
        }


class CampaignCreatedEvent(CampaignEvent):
    """
    Event emitted when a new campaign is created.

    Triggered when first signal (typically Spring) initiates a campaign
    within a trading range.

    Fields
    ------
    symbol : str
        Trading symbol (e.g., "AAPL")
    trading_range_id : UUID
        Trading range this campaign belongs to
    initial_pattern_type : str
        First pattern type (SPRING, SOS, or LPS)
    campaign_id_str : str
        Human-readable campaign ID (e.g., "AAPL-2024-10-15")
    """

    symbol: str = Field(..., max_length=20, description="Trading symbol")
    trading_range_id: UUID = Field(..., description="Trading range this campaign belongs to")
    initial_pattern_type: str = Field(
        ..., max_length=10, description="First pattern type (SPRING, SOS, LPS)"
    )
    campaign_id_str: str = Field(..., max_length=50, description="Human-readable campaign ID")

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize model with UUID and datetime as strings."""
        base = super().serialize_model()
        base.update(
            {
                "symbol": self.symbol,
                "trading_range_id": str(self.trading_range_id),
                "initial_pattern_type": self.initial_pattern_type,
                "campaign_id_str": self.campaign_id_str,
            }
        )
        return base


class CampaignUpdatedEvent(CampaignEvent):
    """
    Event emitted when campaign state changes.

    Triggered when:
    - New position added (SOS or LPS entry)
    - Campaign status transitions (ACTIVE → MARKUP → COMPLETED)
    - Campaign phase transitions (ACCUMULATION → MARKUP)
    - Position exits (partial or full)

    Fields
    ------
    status : str
        Campaign status (ACTIVE, MARKUP, COMPLETED, INVALIDATED)
    phase : str
        Campaign phase (ACCUMULATION, MARKUP)
    total_risk : Decimal
        Current total campaign risk percentage
    total_pnl : Decimal
        Current total P&L (unrealized + realized)
    change_description : str
        Human-readable description of change
    """

    status: str = Field(..., max_length=20, description="Campaign status")
    phase: str = Field(..., max_length=20, description="Campaign phase")
    total_risk: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Current total campaign risk"
    )
    total_pnl: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Current total P&L"
    )
    change_description: str = Field(..., description="Human-readable description of change")

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize model with UUID and datetime as strings."""
        base = super().serialize_model()
        base.update(
            {
                "status": self.status,
                "phase": self.phase,
                "total_risk": str(self.total_risk),
                "total_pnl": str(self.total_pnl),
                "change_description": self.change_description,
            }
        )
        return base


class CampaignInvalidatedEvent(CampaignEvent):
    """
    Event emitted when campaign is invalidated (FR21).

    Triggered when:
    - Spring low breached (exit ALL positions immediately)
    - Ice level breached after SOS
    - Creek level breached after Jump achieved
    - Manual invalidation requested

    Fields
    ------
    reason : str
        Invalidation reason (e.g., "Spring low breached at $147.50")
    invalidation_price : Decimal
        Price at which invalidation occurred
    positions_closed : int
        Number of positions force-closed
    final_pnl : Decimal
        Final P&L after all exits
    """

    reason: str = Field(..., description="Invalidation reason")
    invalidation_price: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Price at which invalidation occurred"
    )
    positions_closed: int = Field(..., ge=0, description="Number of positions force-closed")
    final_pnl: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Final P&L after all exits"
    )

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize model with UUID and datetime as strings."""
        base = super().serialize_model()
        base.update(
            {
                "reason": self.reason,
                "invalidation_price": str(self.invalidation_price),
                "positions_closed": self.positions_closed,
                "final_pnl": str(self.final_pnl),
            }
        )
        return base


class CampaignCompletedEvent(CampaignEvent):
    """
    Event emitted when campaign completes successfully.

    Triggered when all positions are closed at target levels (T1, T2, T3).

    Fields
    ------
    final_metrics : dict[str, Any]
        Campaign metrics (total_return_pct, total_r_achieved, win_rate, etc.)
    duration_days : int
        Campaign duration in days
    total_positions : int
        Total number of positions taken
    """

    final_metrics: dict[str, Any] = Field(..., description="Campaign final metrics")
    duration_days: int = Field(..., ge=0, description="Campaign duration in days")
    total_positions: int = Field(..., ge=0, description="Total number of positions")

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize model with UUID and datetime as strings."""
        base = super().serialize_model()
        base.update(
            {
                "final_metrics": self.final_metrics,
                "duration_days": self.duration_days,
                "total_positions": self.total_positions,
            }
        )
        return base


# ==================================================================================
# Event Bus
# ==================================================================================

# Type alias for event handlers
EventHandler = Callable[[CampaignEvent], Awaitable[None]]


class EventBus:
    """
    Publish/subscribe event bus for campaign events.

    Provides async event delivery with multiple subscribers per event type.
    Background task processes event queue and dispatches to registered handlers.

    Attributes
    ----------
    _queue : asyncio.Queue[CampaignEvent]
        Event queue for async processing
    _subscribers : dict[type, list[EventHandler]]
        Registered event handlers by event type
    _running : bool
        Whether background processor is running
    _processor_task : asyncio.Task | None
        Background task processing event queue
    """

    def __init__(self) -> None:
        """Initialize event bus with empty queue and subscribers."""
        self._queue: asyncio.Queue[CampaignEvent] = asyncio.Queue()
        self._subscribers: dict[type, list[EventHandler]] = defaultdict(list)
        self._running = False
        self._processor_task: asyncio.Task[None] | None = None
        self.logger = logger.bind(component="EventBus")

    async def start(self) -> None:
        """
        Start background event processor.

        Creates async task that processes events from queue and dispatches
        to registered subscribers.
        """
        if self._running:
            self.logger.warning("EventBus already running")
            return

        self._running = True
        self._processor_task = asyncio.create_task(self._process_events())
        self.logger.info("EventBus started")

    async def stop(self) -> None:
        """
        Stop background event processor.

        Waits for queue to drain and cancels processor task.
        """
        if not self._running:
            return

        self._running = False

        # Wait for queue to drain (max 5 seconds)
        try:
            await asyncio.wait_for(self._queue.join(), timeout=5.0)
        except asyncio.TimeoutError:
            self.logger.warning("EventBus queue did not drain within timeout")

        # Cancel processor task
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass

        self.logger.info("EventBus stopped")

    def subscribe(self, event_type: type[CampaignEvent], handler: EventHandler) -> None:
        """
        Subscribe to specific event type.

        Parameters
        ----------
        event_type : type[CampaignEvent]
            Event class to subscribe to (e.g., CampaignCreatedEvent)
        handler : EventHandler
            Async callback function to invoke when event occurs

        Example
        -------
        >>> async def on_campaign_created(event: CampaignCreatedEvent):
        ...     print(f"Campaign {event.campaign_id} created")
        >>> event_bus.subscribe(CampaignCreatedEvent, on_campaign_created)
        """
        self._subscribers[event_type].append(handler)
        self.logger.debug(
            "Subscriber registered",
            event_type=event_type.__name__,
            handler_count=len(self._subscribers[event_type]),
        )

    async def publish(self, event: CampaignEvent) -> None:
        """
        Publish event to queue for async processing.

        Event will be dispatched to all registered subscribers for its type.

        Parameters
        ----------
        event : CampaignEvent
            Event to publish

        Example
        -------
        >>> event = CampaignCreatedEvent(
        ...     campaign_id=uuid4(),
        ...     symbol="AAPL",
        ...     trading_range_id=uuid4(),
        ...     initial_pattern_type="SPRING",
        ...     campaign_id_str="AAPL-2024-10-15"
        ... )
        >>> await event_bus.publish(event)
        """
        await self._queue.put(event)
        self.logger.debug(
            "Event published",
            event_type=type(event).__name__,
            event_id=str(event.event_id),
            campaign_id=str(event.campaign_id),
            queue_size=self._queue.qsize(),
        )

    async def _process_events(self) -> None:
        """
        Background task that processes events from queue.

        Runs continuously while _running is True, dispatching events to
        registered subscribers.
        """
        self.logger.info("Event processor started")

        while self._running:
            try:
                # Get event from queue (wait up to 1 second)
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)

                # Get subscribers for this event type
                handlers = self._subscribers.get(type(event), [])

                if not handlers:
                    self.logger.debug(
                        "No subscribers for event type",
                        event_type=type(event).__name__,
                        event_id=str(event.event_id),
                    )
                else:
                    # Dispatch to all subscribers
                    await self._dispatch_to_handlers(event, handlers)

                # Mark task as done
                self._queue.task_done()

            except asyncio.TimeoutError:
                # No events in queue, continue
                continue
            except Exception as e:
                self.logger.error(
                    "Error processing event",
                    error=str(e),
                    error_type=type(e).__name__,
                )

        self.logger.info("Event processor stopped")

    async def _dispatch_to_handlers(
        self, event: CampaignEvent, handlers: list[EventHandler]
    ) -> None:
        """
        Dispatch event to all registered handlers.

        Handlers are invoked concurrently using asyncio.gather. If a handler
        raises an exception, it is logged but does not prevent other handlers
        from executing.

        Parameters
        ----------
        event : CampaignEvent
            Event to dispatch
        handlers : list[EventHandler]
            Registered handlers for this event type
        """
        # Invoke all handlers concurrently
        tasks = [handler(event) for handler in handlers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any handler errors
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(
                    "Event handler raised exception",
                    event_type=type(event).__name__,
                    event_id=str(event.event_id),
                    handler_index=i,
                    error=str(result),
                    error_type=type(result).__name__,
                )

        self.logger.debug(
            "Event dispatched to handlers",
            event_type=type(event).__name__,
            event_id=str(event.event_id),
            handler_count=len(handlers),
            successful_handlers=sum(1 for r in results if not isinstance(r, Exception)),
        )


# ==================================================================================
# Global Event Bus Instance
# ==================================================================================

# Global event bus instance (singleton)
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """
    Get global EventBus singleton instance.

    Returns
    -------
    EventBus
        Global event bus instance

    Example
    -------
    >>> event_bus = get_event_bus()
    >>> await event_bus.publish(event)
    """
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


async def start_event_bus() -> None:
    """Start global event bus background processor."""
    event_bus = get_event_bus()
    await event_bus.start()


async def stop_event_bus() -> None:
    """Stop global event bus background processor."""
    event_bus = get_event_bus()
    await event_bus.stop()
