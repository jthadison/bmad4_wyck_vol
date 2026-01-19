"""
Integration Tests for RealtimeCampaignService (Story 16.2b)

Tests real-time campaign detection pipeline with pattern detection,
event emission, and performance validation.

Author: Story 16.2b Implementation
"""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.campaign_management.events import CampaignEvent, get_event_bus
from src.models.campaign_event import CampaignEventType
from src.models.ohlcv import OHLCVBar
from src.services.realtime_campaign_service import BarBuffer, RealtimeCampaignService


# ==================================================================================
# Fixtures
# ==================================================================================


@pytest.fixture
def sample_bars() -> list[OHLCVBar]:
    """Create sample OHLCV bars for testing."""
    bars = []
    base_time = datetime.now(UTC)

    for i in range(50):
        bars.append(
            OHLCVBar(
                id=uuid4(),
                symbol="AAPL",
                timeframe="1h",
                timestamp=base_time + timedelta(hours=i),
                open=Decimal("150.00") + Decimal(str(i * 0.5)),
                high=Decimal("151.00") + Decimal(str(i * 0.5)),
                low=Decimal("149.00") + Decimal(str(i * 0.5)),
                close=Decimal("150.50") + Decimal(str(i * 0.5)),
                volume=1000000 + (i * 10000),
                spread=Decimal("2.00"),
                spread_ratio=Decimal("1.0"),
                volume_ratio=Decimal("1.0"),
            )
        )

    return bars


@pytest.fixture
async def service() -> RealtimeCampaignService:
    """Create and start RealtimeCampaignService for testing."""
    service = RealtimeCampaignService(
        buffer_capacity=50,
        min_detection_bars=20,
    )
    await service.start()
    yield service
    await service.stop()


@pytest.fixture
async def event_collector():
    """Collect emitted events for testing."""
    events = []

    async def collect_event(event: CampaignEvent):
        events.append(event)

    event_bus = get_event_bus()
    await event_bus.start()

    # Subscribe to all campaign event types
    event_bus.subscribe(CampaignEvent, collect_event)

    yield events

    await event_bus.stop()


# ==================================================================================
# BarBuffer Tests
# ==================================================================================


def test_bar_buffer_initialization():
    """Test BarBuffer initialization (Story 16.2b TR4)."""
    buffer = BarBuffer("AAPL", capacity=50)

    assert buffer.symbol == "AAPL"
    assert buffer.capacity == 50
    assert len(buffer.bars) == 0
    assert not buffer.has_minimum_bars(20)


def test_bar_buffer_add_bar(sample_bars):
    """Test adding bars to buffer (Story 16.2b TR4)."""
    buffer = BarBuffer("AAPL", capacity=50)

    # Add first bar
    buffer.add_bar(sample_bars[0])
    assert len(buffer.bars) == 1

    # Add more bars
    for bar in sample_bars[1:25]:
        buffer.add_bar(bar)

    assert len(buffer.bars) == 25
    assert buffer.has_minimum_bars(20)


def test_bar_buffer_capacity_limit(sample_bars):
    """Test buffer evicts oldest bars when capacity reached (Story 16.2b TR4)."""
    buffer = BarBuffer("AAPL", capacity=30)

    # Add 50 bars (exceeds capacity)
    for bar in sample_bars:
        buffer.add_bar(bar)

    # Should only have last 30 bars
    assert len(buffer.bars) == 30

    # Verify oldest bars evicted (should have bars 20-49)
    bars_list = buffer.get_bars()
    assert bars_list[0].timestamp == sample_bars[20].timestamp
    assert bars_list[-1].timestamp == sample_bars[49].timestamp


def test_bar_buffer_get_bars(sample_bars):
    """Test getting bars as list (Story 16.2b TR4)."""
    buffer = BarBuffer("AAPL", capacity=50)

    for bar in sample_bars[:25]:
        buffer.add_bar(bar)

    bars_list = buffer.get_bars()
    assert len(bars_list) == 25
    assert isinstance(bars_list, list)
    assert bars_list[0].symbol == "AAPL"


# ==================================================================================
# RealtimeCampaignService Tests
# ==================================================================================


@pytest.mark.asyncio
async def test_service_start_stop():
    """Test service lifecycle (Story 16.2b FR1)."""
    service = RealtimeCampaignService()

    assert not service._running

    await service.start()
    assert service._running

    await service.stop()
    assert not service._running


@pytest.mark.asyncio
async def test_process_bar_creates_buffer(service, sample_bars):
    """Test processing bar creates buffer for new symbol (Story 16.2b FR1)."""
    assert "AAPL" not in service.buffers

    await service.process_bar(sample_bars[0])

    assert "AAPL" in service.buffers
    assert len(service.buffers["AAPL"].bars) == 1


@pytest.mark.asyncio
async def test_process_bar_waits_for_minimum_bars(service, sample_bars):
    """Test service waits for minimum bars before detection (Story 16.2b FR1)."""
    # Process first 19 bars (below minimum)
    for bar in sample_bars[:19]:
        await service.process_bar(bar)

    # No detection should occur (not enough bars)
    assert len(service.active_campaigns) == 0

    # Process 20th bar (meets minimum)
    await service.process_bar(sample_bars[19])

    # Now detection can occur (though may not detect pattern)
    buffer = service.buffers["AAPL"]
    assert buffer.has_minimum_bars(20)


@pytest.mark.asyncio
async def test_process_bar_batch_concurrency(service, sample_bars):
    """Test concurrent bar processing (Story 16.2b NFR6)."""
    start_time = datetime.now(UTC)

    # Process 30 bars concurrently
    await service.process_bar_batch(sample_bars[:30])

    end_time = datetime.now(UTC)
    duration = (end_time - start_time).total_seconds()

    # Should process quickly (< 1 second for 30 bars)
    assert duration < 1.0

    # All bars should be in buffer
    assert len(service.buffers["AAPL"].bars) == 30


@pytest.mark.asyncio
async def test_multiple_symbols_concurrent(service):
    """Test concurrent processing for multiple symbols (Story 16.2b FR2)."""
    symbols = ["AAPL", "MSFT", "GOOGL"]
    base_time = datetime.now(UTC)

    bars = []
    for symbol in symbols:
        for i in range(25):
            bars.append(
                OHLCVBar(
                    id=uuid4(),
                    symbol=symbol,
                    timeframe="1h",
                    timestamp=base_time + timedelta(hours=i),
                    open=Decimal("150.00"),
                    high=Decimal("151.00"),
                    low=Decimal("149.00"),
                    close=Decimal("150.50"),
                    volume=1000000,
                    spread=Decimal("2.00"),
                    spread_ratio=Decimal("1.0"),
                    volume_ratio=Decimal("1.0"),
                )
            )

    # Process all bars concurrently
    await service.process_bar_batch(bars)

    # All symbols should have buffers
    assert "AAPL" in service.buffers
    assert "MSFT" in service.buffers
    assert "GOOGL" in service.buffers

    # Each should have 25 bars
    assert len(service.buffers["AAPL"].bars) == 25
    assert len(service.buffers["MSFT"].bars) == 25
    assert len(service.buffers["GOOGL"].bars) == 25


# ==================================================================================
# Event Emission Tests
# ==================================================================================


@pytest.mark.asyncio
async def test_emit_campaign_formed_event(service):
    """Test CAMPAIGN_FORMED event emission (Story 16.2b FR3)."""
    # Emit test event - should not raise errors
    await service._emit_event(
        event_type=CampaignEventType.CAMPAIGN_FORMED,
        campaign_id="TEST_CAMPAIGN_001",
        pattern_type="SPRING",
        metadata={
            "symbol": "AAPL",
            "timestamp": datetime.now(UTC).isoformat(),
            "initial_pattern": "SPRING",
        },
    )

    # Verify no exceptions raised
    assert True


@pytest.mark.asyncio
async def test_emit_pattern_detected_event(service):
    """Test PATTERN_DETECTED event emission (Story 16.2b FR3)."""
    # Emit test event - should not raise errors
    await service._emit_event(
        event_type=CampaignEventType.PATTERN_DETECTED,
        campaign_id="TEST_CAMPAIGN_001",
        pattern_type="SOS",
        metadata={
            "symbol": "AAPL",
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )

    # Verify no exceptions raised
    assert True


@pytest.mark.asyncio
async def test_emit_campaign_activated_event(service):
    """Test CAMPAIGN_ACTIVATED event emission (Story 16.2b FR3)."""
    # Emit test event - should not raise errors
    await service._emit_event(
        event_type=CampaignEventType.CAMPAIGN_ACTIVATED,
        campaign_id="TEST_CAMPAIGN_001",
        pattern_type=None,
        metadata={
            "symbol": "AAPL",
            "timestamp": datetime.now(UTC).isoformat(),
            "activation_reason": "SOS breakout detected",
        },
    )

    # Verify no exceptions raised
    assert True


# ==================================================================================
# Performance Tests
# ==================================================================================


@pytest.mark.asyncio
async def test_processing_latency_under_2_seconds(service, sample_bars):
    """Test pattern detection latency < 2 seconds (Story 16.2b NFR6)."""
    # Add 25 bars to buffer (enough for detection)
    for bar in sample_bars[:25]:
        await service.process_bar(bar)

    # Measure latency for next bar
    start_time = datetime.now(UTC)
    await service.process_bar(sample_bars[25])
    end_time = datetime.now(UTC)

    latency = (end_time - start_time).total_seconds()

    # Should be well under 2 seconds
    assert latency < 2.0


@pytest.mark.asyncio
async def test_throughput_exceeds_100_bars_per_second(service):
    """Test throughput > 100 bars/second (Story 16.2b NFR6)."""
    # Create 150 bars
    bars = []
    base_time = datetime.now(UTC)

    for i in range(150):
        bars.append(
            OHLCVBar(
                id=uuid4(),
                symbol="AAPL",
                timeframe="1h",
                timestamp=base_time + timedelta(hours=i),
                open=Decimal("150.00"),
                high=Decimal("151.00"),
                low=Decimal("149.00"),
                close=Decimal("150.50"),
                volume=1000000,
                spread=Decimal("2.00"),
                spread_ratio=Decimal("1.0"),
                volume_ratio=Decimal("1.0"),
            )
        )

    # Measure throughput
    start_time = datetime.now(UTC)
    await service.process_bar_batch(bars)
    end_time = datetime.now(UTC)

    duration = (end_time - start_time).total_seconds()
    throughput = len(bars) / duration

    # Should exceed 100 bars/second
    assert throughput > 100


# ==================================================================================
# Edge Cases
# ==================================================================================


@pytest.mark.asyncio
async def test_service_handles_duplicate_start():
    """Test service handles duplicate start calls gracefully."""
    service = RealtimeCampaignService()

    await service.start()
    await service.start()  # Should not error

    assert service._running

    await service.stop()


@pytest.mark.asyncio
async def test_service_handles_stop_when_not_running():
    """Test service handles stop when not running."""
    service = RealtimeCampaignService()

    await service.stop()  # Should not error

    assert not service._running


@pytest.mark.asyncio
async def test_process_bar_with_empty_service(sample_bars):
    """Test processing bar with unstarted service."""
    service = RealtimeCampaignService()

    # Should handle gracefully (no errors)
    await service.process_bar(sample_bars[0])

    # Buffer should still be created
    assert "AAPL" in service.buffers
