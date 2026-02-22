"""
Unit tests for WebSocket missed message recovery endpoint (Story 25.13).

Tests the ring buffer, TTL enforcement, and GET /websocket/messages endpoint.
"""

import time
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.websocket import ConnectionManager


@pytest.fixture
def manager():
    """Provide a fresh ConnectionManager instance for each test."""
    return ConnectionManager()


@pytest.fixture
def mock_websocket():
    """Provide a mock WebSocket connection."""
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


class TestRingBuffer:
    """Test ring buffer behavior in ConnectionManager."""

    @pytest.mark.asyncio
    async def test_buffer_initialization(self, manager):
        """Test that buffer initializes empty with correct maxlen."""
        assert len(manager._message_buffer) == 0
        assert manager._message_buffer.maxlen == 500
        assert manager._global_sequence == 0

    @pytest.mark.asyncio
    async def test_message_buffering_after_send(self, manager, mock_websocket):
        """Test that messages are buffered after successful send."""
        # Connect a client
        connection_id = await manager.connect(mock_websocket, already_accepted=True)

        # Send a message
        message = {"type": "test", "data": {"value": 42}}
        await manager.send_message(connection_id, message)

        # Verify buffer contains the message
        assert len(manager._message_buffer) == 1
        seq, timestamp, buffered_msg = manager._message_buffer[0]

        assert seq == 1  # First global sequence
        assert isinstance(timestamp, float)
        assert buffered_msg["type"] == "test"
        assert buffered_msg["data"]["value"] == 42
        assert buffered_msg["sequence_number"] == 1  # Global seq

    @pytest.mark.asyncio
    async def test_global_sequence_increments(self, manager, mock_websocket):
        """Test that global sequence increments across all connections."""
        # Connect two clients
        conn1 = await manager.connect(mock_websocket, already_accepted=True)
        ws2 = AsyncMock()
        ws2.send_json = AsyncMock()
        conn2 = await manager.connect(ws2, already_accepted=True)

        # Send messages from both connections
        await manager.send_message(conn1, {"type": "test1"})
        await manager.send_message(conn2, {"type": "test2"})
        await manager.send_message(conn1, {"type": "test3"})

        # Verify global sequence is monotonic
        assert len(manager._message_buffer) == 3
        assert manager._message_buffer[0][0] == 1
        assert manager._message_buffer[1][0] == 2
        assert manager._message_buffer[2][0] == 3

    @pytest.mark.asyncio
    async def test_buffer_overflow_maxlen_500(self, manager, mock_websocket):
        """AC4: Test that buffer only retains last 500 messages."""
        connection_id = await manager.connect(mock_websocket, already_accepted=True)

        # Send 501 messages
        for i in range(501):
            await manager.send_message(connection_id, {"type": "test", "data": {"index": i}})

        # Verify buffer contains only 500 messages
        assert len(manager._message_buffer) == 500

        # Verify oldest (index 0) was dropped, starts with index 1
        first_msg = manager._message_buffer[0][2]
        assert first_msg["data"]["index"] == 1  # Index 0 dropped

        # Verify last message is index 500
        last_msg = manager._message_buffer[-1][2]
        assert last_msg["data"]["index"] == 500

    @pytest.mark.asyncio
    async def test_failed_send_not_buffered(self, manager, mock_websocket):
        """Test that failed sends do not populate the buffer."""
        # Make send_json raise an exception
        mock_websocket.send_json.side_effect = Exception("Connection lost")

        connection_id = await manager.connect(mock_websocket, already_accepted=True)
        mock_websocket.send_json.side_effect = Exception("Connection lost")

        # Attempt to send a message (will fail)
        await manager.send_message(connection_id, {"type": "test"})

        # Verify buffer is still empty
        assert len(manager._message_buffer) == 0
        assert manager._global_sequence == 0


class TestGetMessagesSince:
    """Test get_messages_since() recovery method."""

    @pytest.mark.asyncio
    async def test_empty_buffer_returns_empty_list(self, manager):
        """AC3: Test that empty buffer returns empty list."""
        messages = manager.get_messages_since(0)
        assert messages == []

    @pytest.mark.asyncio
    async def test_returns_messages_after_since_seq(self, manager, mock_websocket):
        """AC2: Test that only messages with seq > since are returned."""
        connection_id = await manager.connect(mock_websocket, already_accepted=True)

        # Send 5 messages (global seq 1-5)
        for i in range(5):
            await manager.send_message(connection_id, {"type": "test", "data": {"index": i}})

        # Request messages since seq 2
        messages = manager.get_messages_since(2)

        # Should get messages 3, 4, 5
        assert len(messages) == 3
        assert messages[0]["sequence_number"] == 3
        assert messages[1]["sequence_number"] == 4
        assert messages[2]["sequence_number"] == 5

    @pytest.mark.asyncio
    async def test_since_equals_max_returns_empty(self, manager, mock_websocket):
        """AC3: Test that since == max sequence returns empty list."""
        connection_id = await manager.connect(mock_websocket, already_accepted=True)

        # Send 3 messages
        for i in range(3):
            await manager.send_message(connection_id, {"type": "test"})

        # Request messages since seq 3 (current max)
        messages = manager.get_messages_since(3)

        # Should get empty list
        assert messages == []

    @pytest.mark.asyncio
    async def test_since_zero_returns_all(self, manager, mock_websocket):
        """Test that since=0 returns all buffered messages."""
        connection_id = await manager.connect(mock_websocket, already_accepted=True)

        # Send 3 messages
        for i in range(3):
            await manager.send_message(connection_id, {"type": "test", "data": {"index": i}})

        # Request all messages
        messages = manager.get_messages_since(0)

        # Should get all 3 messages
        assert len(messages) == 3

    @pytest.mark.asyncio
    async def test_ttl_enforcement_excludes_old_messages(self, manager, mock_websocket):
        """AC5: Test that messages older than 15 minutes are excluded."""
        connection_id = await manager.connect(mock_websocket, already_accepted=True)

        # Send message at t=1000 (old)
        with patch("time.time", return_value=1000.0):
            await manager.send_message(connection_id, {"type": "old"})

        # Send message at t=1800 (within TTL if queried at t=1850)
        with patch("time.time", return_value=1800.0):
            await manager.send_message(connection_id, {"type": "recent"})

        # Query at t=1850 (850 seconds after first message, 50 after second)
        with patch("time.time", return_value=1850.0):
            messages = manager.get_messages_since(0)

        # Should only get recent message (old is > 900s ago)
        assert len(messages) == 1
        assert messages[0]["type"] == "recent"

    @pytest.mark.asyncio
    async def test_ttl_edge_case_exactly_900_seconds(self, manager, mock_websocket):
        """Test TTL edge case: message at exactly 900 seconds is excluded."""
        connection_id = await manager.connect(mock_websocket, already_accepted=True)

        # Send message at t=1000
        with patch("time.time", return_value=1000.0):
            await manager.send_message(connection_id, {"type": "edge"})

        # Query at exactly t=1900 (900 seconds later)
        with patch("time.time", return_value=1900.0):
            messages = manager.get_messages_since(0)

        # Should be excluded (timestamp > ttl_cutoff requires strict >)
        assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_combined_sequence_and_ttl_filtering(self, manager, mock_websocket):
        """Test that both sequence and TTL filters are applied."""
        connection_id = await manager.connect(mock_websocket, already_accepted=True)

        # Send old message (seq 1, t=1000)
        with patch("time.time", return_value=1000.0):
            await manager.send_message(connection_id, {"type": "old", "data": {"seq": 1}})

        # Send recent messages (seq 2-3, t=2000)
        with patch("time.time", return_value=2000.0):
            await manager.send_message(connection_id, {"type": "recent1", "data": {"seq": 2}})
            await manager.send_message(connection_id, {"type": "recent2", "data": {"seq": 3}})

        # Query at t=2100 with since=1
        with patch("time.time", return_value=2100.0):
            messages = manager.get_messages_since(1)

        # Should get messages 2 and 3 (seq > 1 AND within TTL)
        # Message 1 is excluded by both filters (seq <= 1 OR too old)
        assert len(messages) == 2
        assert messages[0]["data"]["seq"] == 2
        assert messages[1]["data"]["seq"] == 3


class TestRecoveryEndpoint:
    """Test GET /websocket/messages endpoint."""

    def test_endpoint_requires_authentication(self):
        """AC7: Test that endpoint returns 401 without auth token."""
        client = TestClient(app)

        # Request without auth
        response = client.get("/websocket/messages?since=0")

        # Should return 401
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_endpoint_returns_200_with_auth(self, mock_websocket):
        """AC1: Test that endpoint returns 200 with valid auth."""
        client = TestClient(app)

        # Create a mock user and generate a token
        from src.api.dependencies import create_access_token

        token = create_access_token(data={"sub": "test-user-id"})

        # Request with auth
        response = client.get("/websocket/messages?since=0", headers={"Authorization": f"Bearer {token}"})

        # Should return 200
        assert response.status_code == status.HTTP_200_OK
        assert "messages" in response.json()

    def test_endpoint_response_format(self, mock_websocket):
        """Test that endpoint returns correct response format."""
        client = TestClient(app)

        from src.api.dependencies import create_access_token
        from src.api.websocket import manager

        token = create_access_token(data={"sub": "test-user-id"})

        # Pre-populate buffer manually (bypass WebSocket connection)
        manager._global_sequence = 2
        manager._message_buffer.append((1, time.time(), {"type": "test1", "sequence_number": 1}))
        manager._message_buffer.append((2, time.time(), {"type": "test2", "sequence_number": 2}))

        # Request messages
        response = client.get("/websocket/messages?since=0", headers={"Authorization": f"Bearer {token}"})

        # Verify response format
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "messages" in data
        assert isinstance(data["messages"], list)
        assert len(data["messages"]) == 2

        # Clean up buffer for other tests
        manager._message_buffer.clear()
        manager._global_sequence = 0

    def test_endpoint_since_parameter(self, mock_websocket):
        """Test that since parameter correctly filters messages."""
        client = TestClient(app)

        from src.api.dependencies import create_access_token
        from src.api.websocket import manager

        token = create_access_token(data={"sub": "test-user-id"})

        # Pre-populate buffer
        manager._global_sequence = 3
        manager._message_buffer.append((1, time.time(), {"type": "test1", "sequence_number": 1}))
        manager._message_buffer.append((2, time.time(), {"type": "test2", "sequence_number": 2}))
        manager._message_buffer.append((3, time.time(), {"type": "test3", "sequence_number": 3}))

        # Request messages since seq 1
        response = client.get("/websocket/messages?since=1", headers={"Authorization": f"Bearer {token}"})

        # Should get messages 2 and 3
        data = response.json()
        assert len(data["messages"]) == 2
        assert data["messages"][0]["sequence_number"] == 2
        assert data["messages"][1]["sequence_number"] == 3

        # Clean up
        manager._message_buffer.clear()
        manager._global_sequence = 0

    def test_endpoint_default_since_zero(self, mock_websocket):
        """Test that since defaults to 0 (returns all messages)."""
        client = TestClient(app)

        from src.api.dependencies import create_access_token
        from src.api.websocket import manager

        token = create_access_token(data={"sub": "test-user-id"})

        # Pre-populate buffer
        manager._global_sequence = 2
        manager._message_buffer.append((1, time.time(), {"type": "test1", "sequence_number": 1}))
        manager._message_buffer.append((2, time.time(), {"type": "test2", "sequence_number": 2}))

        # Request without since parameter (defaults to 0)
        response = client.get("/websocket/messages", headers={"Authorization": f"Bearer {token}"})

        # Should get all messages
        data = response.json()
        assert len(data["messages"]) == 2

        # Clean up
        manager._message_buffer.clear()
        manager._global_sequence = 0
