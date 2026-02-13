"""
Structured Audit Logger - Story 23.13

Wraps structlog with standardized trading event fields and maintains
an in-memory ring buffer for recent event retrieval via API.

Thread Safety:
  Uses asyncio.Lock for safe concurrent access to the ring buffer.

Author: Story 23.13 Implementation
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional

import structlog
from structlog.stdlib import BoundLogger

logger: BoundLogger = structlog.get_logger(__name__)

__all__ = [
    "AuditEvent",
    "AuditEventType",
    "AuditLogger",
    "get_audit_logger",
]

MAX_BUFFER_SIZE = 10_000


class AuditEventType(str, Enum):
    """Types of auditable trading events."""

    SIGNAL_GENERATED = "SIGNAL_GENERATED"
    ORDER_PLACED = "ORDER_PLACED"
    ORDER_FILLED = "ORDER_FILLED"
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_CLOSED = "POSITION_CLOSED"
    KILL_SWITCH_ACTIVATED = "KILL_SWITCH_ACTIVATED"
    KILL_SWITCH_DEACTIVATED = "KILL_SWITCH_DEACTIVATED"
    RISK_LIMIT_BREACH = "RISK_LIMIT_BREACH"
    PNL_THRESHOLD_BREACH = "PNL_THRESHOLD_BREACH"


@dataclass
class AuditEvent:
    """Single audit event record stored in the ring buffer."""

    timestamp: datetime
    event_type: AuditEventType
    symbol: Optional[str] = None
    campaign_id: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-safe dictionary."""
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        d["event_type"] = self.event_type.value
        return d


class AuditLogger:
    """
    Structured audit logger for trading decisions.

    Logs events via structlog AND stores them in an in-memory ring buffer
    (max 10 000 events) so the monitoring API can query recent history.

    Example:
        >>> audit = AuditLogger()
        >>> await audit.log_event(
        ...     AuditEventType.SIGNAL_GENERATED,
        ...     symbol="AAPL",
        ...     confidence=92,
        ...     pattern="SPRING",
        ... )
        >>> events = await audit.get_events(symbol="AAPL", limit=10)
    """

    def __init__(self, max_size: int = MAX_BUFFER_SIZE) -> None:
        self._max_size = max_size
        self._buffer: deque[AuditEvent] = deque(maxlen=max_size)
        self._lock = asyncio.Lock()
        self._logger: BoundLogger = logger.bind(component="audit_logger")

    async def log_event(
        self,
        event_type: AuditEventType,
        symbol: Optional[str] = None,
        campaign_id: Optional[str] = None,
        **details: Any,
    ) -> AuditEvent:
        """
        Log a structured audit event.

        The event is written to structlog AND appended to the in-memory
        ring buffer for later retrieval via ``get_events``.

        Args:
            event_type: Category of the event.
            symbol: Trading symbol (e.g. "AAPL"), if applicable.
            campaign_id: Campaign identifier, if applicable.
            **details: Arbitrary key-value context.

        Returns:
            The created AuditEvent.
        """
        event = AuditEvent(
            timestamp=datetime.now(UTC),
            event_type=event_type,
            symbol=symbol,
            campaign_id=campaign_id,
            details=details,
        )

        # Structured log output
        self._logger.info(
            "audit_event",
            event_type=event_type.value,
            symbol=symbol,
            campaign_id=campaign_id,
            **details,
        )

        # Append to ring buffer (deque handles eviction automatically)
        async with self._lock:
            self._buffer.append(event)

        return event

    async def get_events(
        self,
        event_type: Optional[AuditEventType] = None,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """
        Query stored audit events with optional filters.

        Args:
            event_type: Filter by event type.
            symbol: Filter by trading symbol.
            limit: Maximum number of events to return (most recent first).

        Returns:
            Matching events, newest first.
        """
        async with self._lock:
            events = list(self._buffer)

        if event_type is not None:
            events = [e for e in events if e.event_type == event_type]
        if symbol is not None:
            events = [e for e in events if e.symbol == symbol]

        # Most recent first, limited
        events.reverse()
        return events[:limit]

    @property
    def event_count(self) -> int:
        """Number of events currently in the buffer."""
        return len(self._buffer)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get or create the singleton AuditLogger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
