"""
Unit tests for AuditLogger - Story 23.13

Tests:
  - Event logging and retrieval
  - Event filtering by type and symbol
  - Ring buffer max size enforcement
  - Thread safety under concurrent access
"""

from __future__ import annotations

import asyncio

import pytest

from src.monitoring.audit_logger import AuditEvent, AuditEventType, AuditLogger


@pytest.fixture
def audit_logger() -> AuditLogger:
    """Fresh AuditLogger for each test."""
    return AuditLogger(max_size=100)


# ---------------------------------------------------------------------------
# Basic logging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_event_returns_audit_event(audit_logger: AuditLogger) -> None:
    event = await audit_logger.log_event(
        AuditEventType.SIGNAL_GENERATED,
        symbol="AAPL",
        confidence=92,
    )
    assert isinstance(event, AuditEvent)
    assert event.event_type == AuditEventType.SIGNAL_GENERATED
    assert event.symbol == "AAPL"
    assert event.details == {"confidence": 92}


@pytest.mark.asyncio
async def test_log_event_increments_count(audit_logger: AuditLogger) -> None:
    assert audit_logger.event_count == 0
    await audit_logger.log_event(AuditEventType.ORDER_PLACED, symbol="TSLA")
    assert audit_logger.event_count == 1
    await audit_logger.log_event(AuditEventType.ORDER_FILLED, symbol="TSLA")
    assert audit_logger.event_count == 2


@pytest.mark.asyncio
async def test_log_event_optional_fields(audit_logger: AuditLogger) -> None:
    event = await audit_logger.log_event(AuditEventType.KILL_SWITCH_ACTIVATED)
    assert event.symbol is None
    assert event.campaign_id is None
    assert event.details == {}


# ---------------------------------------------------------------------------
# Querying / filtering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_events_returns_newest_first(audit_logger: AuditLogger) -> None:
    await audit_logger.log_event(AuditEventType.ORDER_PLACED, symbol="A")
    await audit_logger.log_event(AuditEventType.ORDER_PLACED, symbol="B")
    await audit_logger.log_event(AuditEventType.ORDER_PLACED, symbol="C")

    events = await audit_logger.get_events()
    assert [e.symbol for e in events] == ["C", "B", "A"]


@pytest.mark.asyncio
async def test_get_events_filter_by_type(audit_logger: AuditLogger) -> None:
    await audit_logger.log_event(AuditEventType.SIGNAL_GENERATED, symbol="AAPL")
    await audit_logger.log_event(AuditEventType.ORDER_PLACED, symbol="AAPL")
    await audit_logger.log_event(AuditEventType.SIGNAL_GENERATED, symbol="TSLA")

    events = await audit_logger.get_events(event_type=AuditEventType.SIGNAL_GENERATED)
    assert len(events) == 2
    assert all(e.event_type == AuditEventType.SIGNAL_GENERATED for e in events)


@pytest.mark.asyncio
async def test_get_events_filter_by_symbol(audit_logger: AuditLogger) -> None:
    await audit_logger.log_event(AuditEventType.ORDER_PLACED, symbol="AAPL")
    await audit_logger.log_event(AuditEventType.ORDER_PLACED, symbol="TSLA")

    events = await audit_logger.get_events(symbol="TSLA")
    assert len(events) == 1
    assert events[0].symbol == "TSLA"


@pytest.mark.asyncio
async def test_get_events_respects_limit(audit_logger: AuditLogger) -> None:
    for i in range(10):
        await audit_logger.log_event(AuditEventType.ORDER_PLACED, symbol=f"S{i}")

    events = await audit_logger.get_events(limit=3)
    assert len(events) == 3


# ---------------------------------------------------------------------------
# Ring buffer max size
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ring_buffer_caps_at_max_size() -> None:
    small_logger = AuditLogger(max_size=5)
    for i in range(10):
        await small_logger.log_event(AuditEventType.ORDER_PLACED, symbol=f"S{i}")

    assert small_logger.event_count == 5

    events = await small_logger.get_events()
    # Should only have the last 5 (S5..S9), newest first
    symbols = [e.symbol for e in events]
    assert symbols == ["S9", "S8", "S7", "S6", "S5"]


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_event_to_dict(audit_logger: AuditLogger) -> None:
    event = await audit_logger.log_event(
        AuditEventType.POSITION_OPENED, symbol="MSFT", campaign_id="C-123"
    )
    d = event.to_dict()
    assert d["event_type"] == "POSITION_OPENED"
    assert d["symbol"] == "MSFT"
    assert isinstance(d["timestamp"], str)  # ISO format string


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_logging() -> None:
    """Concurrent tasks should not corrupt the buffer."""
    audit = AuditLogger(max_size=10_000)

    async def writer(n: int) -> None:
        for _ in range(100):
            await audit.log_event(AuditEventType.ORDER_PLACED, symbol=f"W{n}")

    await asyncio.gather(*(writer(i) for i in range(10)))
    assert audit.event_count == 1000


@pytest.mark.asyncio
async def test_concurrent_read_write() -> None:
    """Reads during writes should not raise."""
    audit = AuditLogger(max_size=500)

    async def writer() -> None:
        for _ in range(200):
            await audit.log_event(AuditEventType.SIGNAL_GENERATED, symbol="X")

    async def reader() -> None:
        for _ in range(50):
            await audit.get_events(limit=10)

    await asyncio.gather(writer(), reader())
    # If we get here without an exception, the test passes
    assert audit.event_count <= 500
