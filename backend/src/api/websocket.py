"""
WebSocket API for Real-Time Updates (Story 10.9)

Purpose:
--------
Provides WebSocket endpoint for real-time event streaming to frontend clients.
Implements ConnectionManager to track active connections with sequence numbers
for message ordering and deduplication.

Architecture:
-------------
- Native FastAPI WebSocket support (NOT Socket.IO)
- ConnectionManager: Tracks active connections with UUID + sequence numbers
- Event emission methods: Integrate with Pattern Engine, Signal Generator, Risk Management
- Heartbeat/ping every 30 seconds to keep connections alive
- Graceful disconnect handling with cleanup

Message Format:
---------------
All WebSocket messages include:
- type: Event type identifier (connected, pattern_detected, signal:new, etc.)
- sequence_number: Monotonic counter per connection (prevents duplicates)
- timestamp: ISO 8601 UTC timestamp
- data: Message-specific payload (optional)

Event Types:
------------
- connected: Connection established
- pattern_detected: New Wyckoff pattern detected
- signal:new: New trade signal generated
- signal:executed: Signal executed
- signal:rejected: Signal rejected
- signal_approved: Approved signal notification (Story 19.7)
- portfolio:updated: Portfolio heat changed
- campaign:updated: Campaign risk changed
- batch_update: Multiple events batched (high-volume scenarios)

Integration Points:
-------------------
- Pattern Detection Engine: emit_pattern_detected()
- Signal Generator: emit_signal_generated(), emit_signal_executed(), emit_signal_rejected()
- Risk Management Service: emit_portfolio_updated(), emit_campaign_updated()

Author: Story 10.9
"""

import time
from collections import deque
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import uuid4

from fastapi import Query, WebSocket, WebSocketDisconnect

from src.api.dependencies import decode_access_token

if TYPE_CHECKING:
    from src.orm.models import Notification


class ConnectionManager:
    """
    Manages active WebSocket connections.

    Tracks connections with unique IDs and sequence numbers for message ordering.
    Provides methods to emit events to individual connections or broadcast to all.

    Attributes:
    -----------
    active_connections: Dict mapping connection_id to (WebSocket, sequence_number) tuple

    Methods:
    --------
    - connect(websocket): Accept connection, assign UUID, send connected message
    - disconnect(connection_id): Remove connection from tracking
    - send_message(connection_id, message): Send message to specific connection
    - broadcast(message): Send message to all connected clients
    - emit_pattern_detected(...): Emit pattern detection event
    - emit_signal_generated(...): Emit signal generation event
    - emit_signal_executed(...): Emit signal execution event
    - emit_signal_rejected(...): Emit signal rejection event
    - emit_signal_approved(...): Emit approved signal notification (Story 19.7)
    - emit_portfolio_updated(...): Emit portfolio update event
    - emit_campaign_updated(...): Emit campaign update event
    """

    def __init__(self) -> None:
        """Initialize ConnectionManager with empty connection tracking."""
        # Maps connection_id to (WebSocket, sequence_number) tuple
        self.active_connections: dict[str, tuple[WebSocket, int]] = {}

        # Story 25.13: Ring buffer for missed message recovery
        # Stores (global_seq, timestamp, message) tuples with 15-min TTL
        self._message_buffer: deque[tuple[int, float, dict[str, Any]]] = deque(maxlen=500)
        self._global_sequence: int = 0  # Global sequence counter for recovery

    async def connect(self, websocket: WebSocket, already_accepted: bool = False) -> str:
        """
        Accept WebSocket connection and send connected message.

        Args:
            websocket: FastAPI WebSocket instance
            already_accepted: If True, skip the accept() call (for pre-authenticated connections)

        Returns:
            connection_id: Unique UUID for this connection

        Side Effects:
            - Accepts WebSocket connection (unless already_accepted=True)
            - Assigns UUID and initializes sequence_number to 0
            - Sends connected message with connection_id
        """
        if not already_accepted:
            await websocket.accept()
        connection_id = str(uuid4())
        self.active_connections[connection_id] = (websocket, 0)

        # Send connected message (sequence_number = 0) directly without incrementing
        try:
            await websocket.send_json(
                {
                    "type": "connected",
                    "connection_id": connection_id,
                    "sequence_number": 0,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
        except Exception as e:
            print(f"[WebSocket] Failed to send connected message to {connection_id}: {e}")
            await self.disconnect(connection_id)

        return connection_id

    async def disconnect(self, connection_id: str) -> None:
        """
        Remove connection from tracking.

        Args:
            connection_id: UUID of connection to remove
        """
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]

    async def send_message(self, connection_id: str, message: dict[str, Any]) -> None:
        """
        Send message to specific connection with global sequence number.

        Story 25.13: Uses GLOBAL sequence numbers for both real-time delivery and recovery.
        This ensures clients can use the sequence number from real-time messages to query
        the recovery endpoint after reconnection.

        Args:
            connection_id: UUID of target connection
            message: Message dictionary (will be enriched with sequence_number)

        Side Effects:
            - Increments GLOBAL sequence number
            - Adds global sequence_number and timestamp to message
            - Sends JSON message via WebSocket
            - Buffers message for recovery after successful send
        """
        if connection_id not in self.active_connections:
            return

        ws, per_conn_seq = self.active_connections[connection_id]

        # Story 25.13 FIX: Increment GLOBAL sequence FIRST (before send)
        # This ensures real-time and recovery use the SAME sequence numbers
        self._global_sequence += 1
        global_seq = self._global_sequence

        # Increment per-connection sequence for internal tracking (optional)
        per_conn_seq += 1
        self.active_connections[connection_id] = (ws, per_conn_seq)

        # Add GLOBAL sequence number and timestamp
        message["sequence_number"] = global_seq  # Global seq for both real-time AND recovery
        if "timestamp" not in message:
            message["timestamp"] = datetime.now(UTC).isoformat()

        try:
            await ws.send_json(message)

            # Story 25.13: Buffer message after successful send for recovery
            # Use the SAME global sequence that was sent to the client
            self._message_buffer.append((global_seq, time.time(), message.copy()))

        except Exception as e:
            print(f"[WebSocket] Failed to send message to {connection_id}: {e}")
            # Remove dead connection
            await self.disconnect(connection_id)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """
        Send message to all connected clients.

        Args:
            message: Message dictionary (will be enriched with sequence_number per connection)

        Note:
            Each connection receives the message with its own sequence_number.
        """
        # Create list of connection IDs to avoid modification during iteration
        connection_ids = list(self.active_connections.keys())
        print(f"[WebSocket] Broadcasting to {len(connection_ids)} connections", flush=True)

        for connection_id in connection_ids:
            # Create copy of message for each connection (different sequence numbers)
            print(f"[WebSocket] Sending to connection {connection_id}", flush=True)
            await self.send_message(connection_id, message.copy())
            print(f"[WebSocket] Sent to connection {connection_id}", flush=True)

    def get_messages_since(self, since_seq: int) -> list[dict[str, Any]]:
        """
        Retrieve buffered messages for recovery after reconnection (Story 25.13).

        Returns messages with global sequence_number > since_seq and within 15-minute TTL.
        Used by GET /websocket/messages endpoint for missed message recovery.

        Args:
            since_seq: Last known global sequence number from client

        Returns:
            List of message dictionaries with global sequence_number field

        TTL: 900 seconds (15 minutes)

        Example:
            Client disconnects after receiving message with global seq 42.
            Server emits messages with global seq 43, 44, 45 while client is offline.
            Client reconnects and calls /websocket/messages?since=42
            Returns messages 43, 44, 45 (if within 15-min TTL)
        """
        now = time.time()
        ttl_cutoff = now - 900  # 15 minutes = 900 seconds

        result = []
        for seq, timestamp, message in self._message_buffer:
            # Filter: sequence > since AND within TTL
            if seq > since_seq and timestamp > ttl_cutoff:
                result.append(message)

        return result

    async def emit_pattern_detected(
        self,
        pattern_id: str,
        symbol: str,
        pattern_type: str,
        confidence_score: int,
        phase: str,
        test_confirmed: bool,
    ) -> None:
        """
        Emit pattern_detected event to all connected clients.

        Args:
            pattern_id: Pattern UUID
            symbol: Ticker symbol (e.g., "AAPL")
            pattern_type: Pattern name (SPRING, UTAD, SOS, etc.)
            confidence_score: Confidence score 70-95
            phase: Wyckoff phase (A, B, C, D, E)
            test_confirmed: Whether test confirmed (True/False)

        Message Format:
            {
                "type": "pattern_detected",
                "sequence_number": <seq>,
                "timestamp": "<ISO8601>",
                "data": {
                    "id": "<pattern_id>",
                    "symbol": "<symbol>",
                    "pattern_type": "<type>",
                    "confidence_score": <score>,
                    "phase": "<phase>",
                    "test_confirmed": <bool>
                },
                "full_details_url": "/api/v1/patterns/<pattern_id>"
            }
        """
        message = {
            "type": "pattern_detected",
            "data": {
                "id": pattern_id,
                "symbol": symbol,
                "pattern_type": pattern_type,
                "confidence_score": confidence_score,
                "phase": phase,
                "test_confirmed": test_confirmed,
            },
            "full_details_url": f"/api/v1/patterns/{pattern_id}",
        }

        await self.broadcast(message)

    async def emit_signal_generated(self, signal_data: dict[str, Any]) -> None:
        """
        Emit signal:new event to all connected clients.

        Args:
            signal_data: Complete Signal object as dictionary

        Message Format:
            {
                "type": "signal:new",
                "sequence_number": <seq>,
                "timestamp": "<ISO8601>",
                "data": <signal_data>
            }
        """
        message = {
            "type": "signal:new",
            "data": signal_data,
        }

        await self.broadcast(message)

    async def emit_signal_executed(self, signal_data: dict[str, Any]) -> None:
        """
        Emit signal:executed event to all connected clients.

        Args:
            signal_data: Complete Signal object as dictionary

        Message Format:
            {
                "type": "signal:executed",
                "sequence_number": <seq>,
                "timestamp": "<ISO8601>",
                "data": <signal_data>
            }
        """
        message = {
            "type": "signal:executed",
            "data": signal_data,
        }

        await self.broadcast(message)

    async def emit_signal_rejected(self, signal_data: dict[str, Any]) -> None:
        """
        Emit signal:rejected event to all connected clients.

        Args:
            signal_data: Complete Signal object as dictionary (includes rejection_reason)

        Message Format:
            {
                "type": "signal:rejected",
                "sequence_number": <seq>,
                "timestamp": "<ISO8601>",
                "data": <signal_data>
            }
        """
        message = {
            "type": "signal:rejected",
            "data": signal_data,
        }

        await self.broadcast(message)

    async def emit_signal_approved(self, notification_data: dict[str, Any]) -> None:
        """
        Emit signal_approved event to all connected clients (Story 19.7).

        Broadcasts approved signal notification for real-time trader alerts.
        Used by SignalNotificationService for delivery with retry logic.

        Args:
            notification_data: SignalNotification as dictionary with fields:
                - type: "signal_approved"
                - signal_id: UUID string
                - timestamp: ISO 8601 string
                - symbol: Trading symbol
                - pattern_type: SPRING, SOS, LPS, UTAD
                - confidence_score: Float 0-100
                - confidence_grade: A+, A, B, C
                - entry_price: Decimal string
                - stop_loss: Decimal string
                - target_price: Decimal string
                - risk_amount: Decimal string
                - risk_percentage: Float 0-100
                - r_multiple: Float
                - expires_at: ISO 8601 string

        Message Format:
            {
                "type": "signal_approved",
                "sequence_number": <seq>,
                "timestamp": "<ISO8601>",
                "signal_id": "<uuid>",
                "symbol": "<symbol>",
                "pattern_type": "<type>",
                "confidence_score": <float>,
                "confidence_grade": "<grade>",
                "entry_price": "<decimal>",
                "stop_loss": "<decimal>",
                "target_price": "<decimal>",
                "risk_amount": "<decimal>",
                "risk_percentage": <float>,
                "r_multiple": <float>,
                "expires_at": "<ISO8601>"
            }

        Timing:
            Target delivery within 500ms of signal approval.

        Integration:
            Called by SignalNotificationService.notify_signal_approved()
        """
        # Notification data already contains all fields from SignalNotification
        # Just broadcast directly - timestamp and sequence_number added by broadcast()
        await self.broadcast(notification_data)

    async def emit_portfolio_updated(
        self,
        total_heat: str,
        available_capacity: str,
    ) -> None:
        """
        Emit portfolio:updated event to all connected clients.

        Args:
            total_heat: Total portfolio heat as Decimal string
            available_capacity: Available capacity as Decimal string

        Message Format:
            {
                "type": "portfolio:updated",
                "sequence_number": <seq>,
                "timestamp": "<ISO8601>",
                "data": {
                    "total_heat": "<decimal_string>",
                    "available_capacity": "<decimal_string>",
                    "timestamp": "<ISO8601>"
                }
            }
        """
        timestamp = datetime.now(UTC).isoformat()

        message = {
            "type": "portfolio:updated",
            "data": {
                "total_heat": total_heat,
                "available_capacity": available_capacity,
                "timestamp": timestamp,
            },
        }

        await self.broadcast(message)

    async def emit_campaign_updated(
        self,
        campaign_id: str,
        risk_allocated: str,
        positions_count: int,
    ) -> None:
        """
        Emit campaign:updated event to all connected clients.

        Args:
            campaign_id: Campaign UUID
            risk_allocated: Risk allocated as Decimal string
            positions_count: Number of active positions

        Message Format:
            {
                "type": "campaign:updated",
                "sequence_number": <seq>,
                "timestamp": "<ISO8601>",
                "data": {
                    "campaign_id": "<campaign_id>",
                    "risk_allocated": "<decimal_string>",
                    "positions_count": <count>
                }
            }
        """
        message = {
            "type": "campaign:updated",
            "data": {
                "campaign_id": campaign_id,
                "risk_allocated": risk_allocated,
                "positions_count": positions_count,
            },
        }

        await self.broadcast(message)

    async def emit_campaign_tracker_update(
        self,
        campaign_updated_message: dict[str, Any],
    ) -> None:
        """
        Emit campaign_updated message for campaign tracker UI (Story 11.4 Task 4).

        Sends complete CampaignUpdatedMessage with full campaign data including
        progression, health status, entries, P&L, and exit plan.

        Args:
            campaign_updated_message: Serialized CampaignUpdatedMessage dict

        Message Format:
            {
                "type": "campaign_updated",
                "sequence_number": <seq>,
                "campaign_id": "<uuid>",
                "updated_fields": ["pnl", "progression", ...],
                "campaign": {<CampaignResponse>},
                "timestamp": "<ISO8601>"
            }

        Rate Limiting:
            Max 1 update per campaign per 5 seconds (enforced by caller)

        Integration:
            - Called when signal status changes (PENDING → FILLED, etc.)
            - Called when P&L changes > 1% of campaign allocation
            - Called when campaign health status changes
        """
        # Message already includes sequence_number from caller
        # Just broadcast as-is
        await self.broadcast(campaign_updated_message)

    async def emit_notification_toast(
        self,
        notification: "Notification",
    ) -> None:
        """
        Emit notification_toast event to all connected clients (Story 11.6).

        Sends real-time toast notification for display in frontend UI.
        Integrates with NotificationService for multi-channel notifications.

        Args:
            notification: Notification object to send as toast

        Message Format:
            {
                "type": "notification_toast",
                "sequence_number": <seq>,
                "timestamp": "<ISO8601>",
                "notification": {
                    "id": "<uuid>",
                    "notification_type": "<type>",
                    "priority": "<priority>",
                    "title": "<title>",
                    "message": "<message>",
                    "metadata": {...},
                    "user_id": "<uuid>",
                    "read": false,
                    "created_at": "<ISO8601>"
                }
            }

        Note:
            Toast notifications are sent to all connected clients.
            Frontend should filter by user_id if needed.
        """
        # Serialize Notification to dict for JSON transmission
        notification_dict = {
            "id": str(notification.id),
            "notification_type": notification.notification_type.value,
            "priority": notification.priority.value,
            "title": notification.title,
            "message": notification.message,
            "metadata": notification.metadata,
            "user_id": str(notification.user_id),
            "read": notification.read,
            "created_at": notification.created_at.isoformat(),
        }

        message = {
            "type": "notification_toast",
            "notification": notification_dict,
        }

        await self.broadcast(message)

    async def emit_order_event(
        self,
        event_type: str,
        order_data: dict[str, Any],
    ) -> None:
        """
        Emit order event to all connected clients (Story 23.7).

        Broadcasts order lifecycle events (submitted, filled, rejected, etc.)
        for real-time display in the frontend.

        Args:
            event_type: One of "order:submitted", "order:filled", "order:rejected"
            order_data: Order details as dictionary

        Message Format:
            {
                "type": "<event_type>",
                "sequence_number": <seq>,
                "timestamp": "<ISO8601>",
                "data": <order_data>
            }
        """
        message: dict[str, Any] = {
            "type": event_type,
            "data": order_data,
        }

        await self.broadcast(message)

    async def emit_signal_queue_added(self, pending_signal_data: dict[str, Any]) -> None:
        """
        Emit signal:queue_added event when a signal enters the approval queue (Story 23.10).

        Args:
            pending_signal_data: PendingSignalView as dictionary
        """
        message: dict[str, Any] = {
            "type": "signal:queue_added",
            "data": pending_signal_data,
        }
        await self.broadcast(message)

    async def emit_signal_queue_approved(self, queue_id: str, signal_id: str) -> None:
        """
        Emit signal:approved event when a signal is approved (Story 23.10).

        Args:
            queue_id: Queue entry UUID string
            signal_id: Signal UUID string
        """
        message: dict[str, Any] = {
            "type": "signal:approved",
            "data": {
                "queue_id": queue_id,
                "signal_id": signal_id,
                "approved_at": datetime.now(UTC).isoformat(),
            },
        }
        await self.broadcast(message)

    async def emit_signal_queue_rejected(self, queue_id: str, signal_id: str, reason: str) -> None:
        """
        Emit signal:queue_rejected event when a signal is rejected (Story 23.10).

        Args:
            queue_id: Queue entry UUID string
            signal_id: Signal UUID string
            reason: Rejection reason
        """
        message: dict[str, Any] = {
            "type": "signal:queue_rejected",
            "data": {
                "queue_id": queue_id,
                "signal_id": signal_id,
                "reason": reason,
                "rejected_at": datetime.now(UTC).isoformat(),
            },
        }
        await self.broadcast(message)

    async def emit_signal_queue_expired(self, queue_id: str, signal_id: str) -> None:
        """
        Emit signal:expired event when a signal expires (Story 23.10).

        Args:
            queue_id: Queue entry UUID string
            signal_id: Signal UUID string
        """
        message: dict[str, Any] = {
            "type": "signal:expired",
            "data": {
                "queue_id": queue_id,
                "signal_id": signal_id,
                "expired_at": datetime.now(UTC).isoformat(),
            },
        }
        await self.broadcast(message)

    async def emit_batch_update(
        self,
        patterns_detected: list[dict[str, Any]],
        signals_generated: list[dict[str, Any]],
    ) -> None:
        """
        Emit batch_update event for high-volume scenarios.

        Args:
            patterns_detected: List of pattern detection data
            signals_generated: List of signal generation data

        Message Format:
            {
                "type": "batch_update",
                "sequence_number": <seq>,
                "timestamp": "<ISO8601>",
                "batch_size": <total_count>,
                "patterns_detected": [...],
                "signals_generated": [...]
            }

        Note:
            Used when >10 events occur within 500ms to reduce message overhead.
        """
        message = {
            "type": "batch_update",
            "batch_size": len(patterns_detected) + len(signals_generated),
            "patterns_detected": patterns_detected,
            "signals_generated": signals_generated,
        }

        await self.broadcast(message)


# Global singleton instance
manager = ConnectionManager()


async def websocket_endpoint(
    websocket: WebSocket, token: Optional[str] = Query(default=None)
) -> None:
    """
    WebSocket endpoint handler with JWT authentication (Story 25.17).

    Endpoint: ws://localhost:8000/ws?token=<jwt>

    Authentication:
    ---------------
    - Requires valid JWT token passed as query parameter
    - Missing token → close code 1008 "Authentication required"
    - Invalid/expired token → close code 1008 "Invalid or expired token"
    - Connection closed before adding to pool to prevent signal leakage

    Connection Flow:
    ----------------
    1. Client connects: `new WebSocket('ws://localhost:8000/ws?token=<jwt>')`
    2. Server accepts connection (required by WebSocket protocol)
    3. Server validates JWT token
    4. If invalid: close connection immediately before pool add
    5. If valid: assign connection_id, add to pool, send connected message
    6. Server emits events as they occur (pattern detected, signal generated, etc.)
    7. Client processes messages, updates UI
    8. On disconnect: Server removes connection from tracking

    Heartbeat:
    ----------
    FastAPI WebSocket connections are kept alive by the ASGI server.
    No explicit ping/pong needed for MVP (single-user, local deployment).

    Error Handling:
    ---------------
    - WebSocketDisconnect: Normal disconnection, cleanup connection
    - Any Exception: Log error, cleanup connection
    """
    # Accept connection first (WebSocket protocol requirement)
    await websocket.accept()

    # Validate JWT token
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return

    # Decode and validate token
    try:
        payload = decode_access_token(token)
        if payload is None:
            await websocket.close(code=1008, reason="Invalid or expired token")
            return
    except Exception:
        # Catch any unexpected JWT decoding errors
        await websocket.close(code=1008, reason="Invalid or expired token")
        return

    # Token is valid - proceed with connection (pass already_accepted=True)
    connection_id = await manager.connect(websocket, already_accepted=True)
    print(f"[WebSocket] Client connected (authenticated): {connection_id}")

    try:
        # Keep connection alive, listen for client messages if needed
        while True:
            # Wait for messages from client (currently unused, but keeps connection alive)
            data = await websocket.receive_text()

            # Echo back for debugging (remove in production)
            if data:
                print(f"[WebSocket] Received from {connection_id}: {data}")

    except WebSocketDisconnect:
        print(f"[WebSocket] Client disconnected: {connection_id}")
        await manager.disconnect(connection_id)
    except Exception as e:
        print(f"[WebSocket] Error for {connection_id}: {e}")
        await manager.disconnect(connection_id)
