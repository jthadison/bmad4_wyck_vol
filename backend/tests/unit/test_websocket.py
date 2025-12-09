"""
Unit Tests for WebSocket API (Story 10.9)

Tests ConnectionManager functionality:
- Connection establishment and tracking
- Message sending with sequence numbers
- Broadcast to all connections
- Event emission methods
- Graceful disconnect handling
"""

from unittest.mock import AsyncMock

import pytest

from src.api.websocket import ConnectionManager


@pytest.fixture
def manager():
    """Fixture providing fresh ConnectionManager for each test."""
    return ConnectionManager()


@pytest.fixture
def mock_websocket():
    """Fixture providing mock WebSocket connection."""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.mark.asyncio
async def test_connect_assigns_uuid_and_sends_connected_message(manager, mock_websocket):
    """Test that connect() assigns UUID and sends connected message."""
    # Act
    connection_id = await manager.connect(mock_websocket)

    # Assert
    assert connection_id is not None
    assert len(connection_id) == 36  # UUID string length
    assert connection_id in manager.active_connections

    # Verify WebSocket was accepted
    mock_websocket.accept.assert_called_once()

    # Verify connected message was sent
    mock_websocket.send_json.assert_called_once()
    sent_message = mock_websocket.send_json.call_args[0][0]

    assert sent_message["type"] == "connected"
    assert sent_message["connection_id"] == connection_id
    assert sent_message["sequence_number"] == 0
    assert "timestamp" in sent_message


@pytest.mark.asyncio
async def test_disconnect_removes_connection(manager, mock_websocket):
    """Test that disconnect() removes connection from tracking."""
    # Arrange
    connection_id = await manager.connect(mock_websocket)
    assert connection_id in manager.active_connections

    # Act
    await manager.disconnect(connection_id)

    # Assert
    assert connection_id not in manager.active_connections


@pytest.mark.asyncio
async def test_send_message_increments_sequence_number(manager, mock_websocket):
    """Test that send_message() increments sequence number per message."""
    # Arrange
    connection_id = await manager.connect(mock_websocket)
    mock_websocket.send_json.reset_mock()  # Clear connected message call

    # Act
    await manager.send_message(connection_id, {"type": "test1", "data": "foo"})
    await manager.send_message(connection_id, {"type": "test2", "data": "bar"})

    # Assert
    assert mock_websocket.send_json.call_count == 2

    # Verify first message has sequence_number = 1
    first_call = mock_websocket.send_json.call_args_list[0][0][0]
    assert first_call["sequence_number"] == 1
    assert first_call["type"] == "test1"

    # Verify second message has sequence_number = 2
    second_call = mock_websocket.send_json.call_args_list[1][0][0]
    assert second_call["sequence_number"] == 2
    assert second_call["type"] == "test2"


@pytest.mark.asyncio
async def test_send_message_adds_timestamp_if_missing(manager, mock_websocket):
    """Test that send_message() adds timestamp if not present."""
    # Arrange
    connection_id = await manager.connect(mock_websocket)
    mock_websocket.send_json.reset_mock()

    # Act
    await manager.send_message(connection_id, {"type": "test", "data": "foo"})

    # Assert
    sent_message = mock_websocket.send_json.call_args[0][0]
    assert "timestamp" in sent_message


@pytest.mark.asyncio
async def test_broadcast_sends_to_all_connections(manager):
    """Test that broadcast() sends message to all connected clients."""
    # Arrange
    ws1 = AsyncMock()
    ws1.accept = AsyncMock()
    ws1.send_json = AsyncMock()

    ws2 = AsyncMock()
    ws2.accept = AsyncMock()
    ws2.send_json = AsyncMock()

    conn_id1 = await manager.connect(ws1)
    conn_id2 = await manager.connect(ws2)

    ws1.send_json.reset_mock()
    ws2.send_json.reset_mock()

    # Act
    await manager.broadcast({"type": "broadcast_test", "data": "hello"})

    # Assert
    ws1.send_json.assert_called_once()
    ws2.send_json.assert_called_once()

    # Verify both received message with different sequence numbers
    msg1 = ws1.send_json.call_args[0][0]
    msg2 = ws2.send_json.call_args[0][0]

    assert msg1["type"] == "broadcast_test"
    assert msg2["type"] == "broadcast_test"
    assert msg1["sequence_number"] == 1  # First message after connected
    assert msg2["sequence_number"] == 1  # First message after connected


@pytest.mark.asyncio
async def test_emit_pattern_detected_broadcasts_correct_format(manager, mock_websocket):
    """Test emit_pattern_detected() sends correctly formatted message."""
    # Arrange
    connection_id = await manager.connect(mock_websocket)
    mock_websocket.send_json.reset_mock()

    # Act
    await manager.emit_pattern_detected(
        pattern_id="pattern-123",
        symbol="AAPL",
        pattern_type="SPRING",
        confidence_score=85,
        phase="C",
        test_confirmed=True,
    )

    # Assert
    mock_websocket.send_json.assert_called_once()
    sent_message = mock_websocket.send_json.call_args[0][0]

    assert sent_message["type"] == "pattern_detected"
    assert sent_message["sequence_number"] == 1
    assert "timestamp" in sent_message
    assert sent_message["data"]["id"] == "pattern-123"
    assert sent_message["data"]["symbol"] == "AAPL"
    assert sent_message["data"]["pattern_type"] == "SPRING"
    assert sent_message["data"]["confidence_score"] == 85
    assert sent_message["data"]["phase"] == "C"
    assert sent_message["data"]["test_confirmed"] is True
    assert sent_message["full_details_url"] == "/api/v1/patterns/pattern-123"


@pytest.mark.asyncio
async def test_emit_signal_generated_broadcasts_correct_format(manager, mock_websocket):
    """Test emit_signal_generated() sends correctly formatted message."""
    # Arrange
    connection_id = await manager.connect(mock_websocket)
    mock_websocket.send_json.reset_mock()

    signal_data = {
        "id": "signal-456",
        "symbol": "TSLA",
        "pattern_type": "SOS",
        "status": "APPROVED",
    }

    # Act
    await manager.emit_signal_generated(signal_data)

    # Assert
    mock_websocket.send_json.assert_called_once()
    sent_message = mock_websocket.send_json.call_args[0][0]

    assert sent_message["type"] == "signal:new"
    assert sent_message["data"] == signal_data


@pytest.mark.asyncio
async def test_emit_portfolio_updated_broadcasts_correct_format(manager, mock_websocket):
    """Test emit_portfolio_updated() sends correctly formatted message."""
    # Arrange
    connection_id = await manager.connect(mock_websocket)
    mock_websocket.send_json.reset_mock()

    # Act
    await manager.emit_portfolio_updated(total_heat="0.75", available_capacity="0.25")

    # Assert
    mock_websocket.send_json.assert_called_once()
    sent_message = mock_websocket.send_json.call_args[0][0]

    assert sent_message["type"] == "portfolio:updated"
    assert sent_message["data"]["total_heat"] == "0.75"
    assert sent_message["data"]["available_capacity"] == "0.25"
    assert "timestamp" in sent_message["data"]


@pytest.mark.asyncio
async def test_emit_campaign_updated_broadcasts_correct_format(manager, mock_websocket):
    """Test emit_campaign_updated() sends correctly formatted message."""
    # Arrange
    connection_id = await manager.connect(mock_websocket)
    mock_websocket.send_json.reset_mock()

    # Act
    await manager.emit_campaign_updated(
        campaign_id="campaign-789", risk_allocated="0.35", positions_count=5
    )

    # Assert
    mock_websocket.send_json.assert_called_once()
    sent_message = mock_websocket.send_json.call_args[0][0]

    assert sent_message["type"] == "campaign:updated"
    assert sent_message["data"]["campaign_id"] == "campaign-789"
    assert sent_message["data"]["risk_allocated"] == "0.35"
    assert sent_message["data"]["positions_count"] == 5


@pytest.mark.asyncio
async def test_send_message_handles_failed_connection_gracefully(manager, mock_websocket):
    """Test that send_message() handles send failures gracefully."""
    # Arrange
    connection_id = await manager.connect(mock_websocket)
    mock_websocket.send_json.reset_mock()

    # Make send_json raise an exception
    mock_websocket.send_json.side_effect = Exception("Connection lost")

    # Act
    await manager.send_message(connection_id, {"type": "test"})

    # Assert: Connection should be removed after failure
    assert connection_id not in manager.active_connections


@pytest.mark.asyncio
async def test_multiple_connections_tracked_independently(manager):
    """Test that multiple connections are tracked with independent sequence numbers."""
    # Arrange
    ws1 = AsyncMock()
    ws1.accept = AsyncMock()
    ws1.send_json = AsyncMock()

    ws2 = AsyncMock()
    ws2.accept = AsyncMock()
    ws2.send_json = AsyncMock()

    # Act
    conn_id1 = await manager.connect(ws1)
    conn_id2 = await manager.connect(ws2)

    # Assert
    assert len(manager.active_connections) == 2
    assert conn_id1 != conn_id2

    # Send messages to first connection
    ws1.send_json.reset_mock()
    await manager.send_message(conn_id1, {"type": "test1"})
    await manager.send_message(conn_id1, {"type": "test2"})

    # Verify sequence numbers for first connection
    assert ws1.send_json.call_count == 2
    assert ws1.send_json.call_args_list[0][0][0]["sequence_number"] == 1
    assert ws1.send_json.call_args_list[1][0][0]["sequence_number"] == 2

    # Send message to second connection
    ws2.send_json.reset_mock()
    await manager.send_message(conn_id2, {"type": "test1"})

    # Verify sequence number for second connection starts at 1
    assert ws2.send_json.call_count == 1
    assert ws2.send_json.call_args[0][0]["sequence_number"] == 1
