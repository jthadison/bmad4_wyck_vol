"""
Unit tests for WebSocket JWT authentication (Story 25.17)

Tests the /ws endpoint authentication flow:
- AC1: Valid token → connection accepted, client added to pool
- AC2: Missing token → close 1008 "Authentication required", not in pool
- AC3: Invalid/expired token → close 1008 "Invalid or expired token", not in pool
- AC5: Authenticated client receives signals normally
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.websocket import manager


@pytest.fixture(autouse=True)
def clear_connections():
    """Clear active connections before each test."""
    manager.active_connections.clear()
    yield
    manager.active_connections.clear()


@pytest.fixture
def mock_valid_token():
    """Mock a valid JWT token payload."""
    return {"sub": "12345678-1234-5678-1234-567812345678", "exp": 9999999999}


@pytest.fixture
def mock_invalid_token():
    """Mock an invalid token that returns None."""
    return None


def test_valid_token_connects_successfully(mock_valid_token):
    """
    AC1: Valid token → connection accepted, client added to pool.

    Given a client sends a WebSocket upgrade request to /ws?token=<valid_jwt>
    When the server validates the token
    Then the connection is accepted (HTTP 101 Switching Protocols)
    And the client is added to the ConnectionManager pool
    And the client begins receiving broadcast events
    """
    with patch("src.api.websocket.decode_access_token", return_value=mock_valid_token):
        client = TestClient(app)

        with client.websocket_connect("/ws?token=valid_jwt_token") as websocket:
            # Should receive connected message
            data = websocket.receive_json()
            assert data["type"] == "connected"
            assert "connection_id" in data
            assert data["sequence_number"] == 0

            # Verify client is in the pool
            assert len(manager.active_connections) == 1

        # After disconnect, should be removed from pool
        assert len(manager.active_connections) == 0


def test_missing_token_closes_connection():
    """
    AC2: Missing token → connection rejected with close code 1008.

    Given a client sends a WebSocket upgrade request to /ws with no token parameter
    When the server processes the upgrade
    Then the connection is accepted at the protocol level (WebSocket upgrade completes)
    Then immediately closed with WebSocket close code 1008 (Policy Violation)
    And a close reason message "Authentication required" is sent before closing
    And the client is NOT added to the ConnectionManager pool
    """
    from starlette.websockets import WebSocketDisconnect

    client = TestClient(app)

    # Connect without token - should close immediately
    with client.websocket_connect("/ws") as websocket:
        # Try to receive - should get WebSocketDisconnect
        with pytest.raises(WebSocketDisconnect) as exc_info:
            websocket.receive_json()

        # Check close code is 1008 (Policy Violation)
        assert exc_info.value.code == 1008

    # Verify client was NOT added to pool
    assert len(manager.active_connections) == 0


def test_invalid_token_closes_connection(mock_invalid_token):
    """
    AC3: Invalid or expired token → connection rejected with close code 1008.

    Given a client sends a WebSocket upgrade request to /ws?token=<expired_or_invalid_jwt>
    When the server validates the token
    Then the connection is closed with WebSocket close code 1008
    And a close reason message "Invalid or expired token" is sent
    And the client is NOT added to the ConnectionManager pool
    """
    from starlette.websockets import WebSocketDisconnect

    with patch("src.api.websocket.decode_access_token", return_value=mock_invalid_token):
        client = TestClient(app)

        with client.websocket_connect("/ws?token=invalid_jwt_token") as websocket:
            # Try to receive - should get WebSocketDisconnect
            with pytest.raises(WebSocketDisconnect) as exc_info:
                websocket.receive_json()

            # Check close code is 1008
            assert exc_info.value.code == 1008

        # Verify client was NOT added to pool
        assert len(manager.active_connections) == 0


def test_expired_token_closes_connection():
    """
    AC3 variant: Expired token → connection rejected.

    Tests that an expired token (payload with exp in the past) is rejected.
    """
    from starlette.websockets import WebSocketDisconnect

    expired_payload = None  # decode_access_token returns None for expired tokens

    with patch("src.api.websocket.decode_access_token", return_value=expired_payload):
        client = TestClient(app)

        with client.websocket_connect("/ws?token=expired_jwt_token") as websocket:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                websocket.receive_json()

            assert exc_info.value.code == 1008

        assert len(manager.active_connections) == 0


@pytest.mark.asyncio
async def test_signal_broadcast_to_authenticated_client_only(mock_valid_token):
    """
    AC4 & AC5: Signal broadcast only reaches authenticated clients.

    Given an authenticated client connected via /ws?token=<valid_jwt>
    When a signal is broadcast
    Then the authenticated client receives the signal:new event
    And unauthenticated clients do not receive it (not in pool)
    """
    with patch("src.api.websocket.decode_access_token", return_value=mock_valid_token):
        client = TestClient(app)

        with client.websocket_connect("/ws?token=valid_jwt_token") as websocket:
            # Receive connected message
            data = websocket.receive_json()
            assert data["type"] == "connected"

            # Simulate signal broadcast
            test_signal = {
                "signal_id": "test-123",
                "symbol": "AAPL",
                "pattern_type": "SPRING",
            }

            await manager.emit_signal_generated(test_signal)

            # Authenticated client should receive the signal
            signal_message = websocket.receive_json()
            assert signal_message["type"] == "signal:new"
            assert signal_message["data"]["signal_id"] == "test-123"
            assert signal_message["sequence_number"] == 1  # sequence starts at 1 after connected


def test_no_signal_data_sent_to_unauthenticated():
    """
    AC4: No signal data sent to unauthenticated clients.

    Given an unauthenticated client attempts to connect (invalid token)
    When a signal is broadcast via emit_signal_generated()
    Then the unauthenticated client is not in the active connection pool
    And receives no signal data
    """
    from starlette.websockets import WebSocketDisconnect

    # Unauthenticated client should not be in pool after rejection
    with patch("src.api.websocket.decode_access_token", return_value=None):
        client = TestClient(app)

        with client.websocket_connect("/ws?token=invalid_token") as websocket:
            # Connection closes immediately on auth failure
            with pytest.raises(WebSocketDisconnect):
                websocket.receive_json()

    # Verify pool is empty
    assert len(manager.active_connections) == 0

    # Broadcast should not fail (no connections to broadcast to)
    import asyncio

    test_signal = {"signal_id": "test-456", "symbol": "TSLA"}
    asyncio.run(manager.emit_signal_generated(test_signal))

    # Still no connections
    assert len(manager.active_connections) == 0


def test_token_passed_as_query_parameter():
    """
    AC6: Token passed as query parameter (not header).

    Verifies that the token is accepted as a query parameter.
    This is the standard approach for WebSocket auth because browser
    WebSocket clients cannot set custom headers on the initial handshake.
    """
    with patch("src.api.websocket.decode_access_token", return_value={"sub": "user-123"}):
        client = TestClient(app)

        # Token in query parameter should work
        with client.websocket_connect("/ws?token=test_token_123") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "connected"
            assert len(manager.active_connections) == 1
