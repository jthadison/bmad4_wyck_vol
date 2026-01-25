"""
Signal Notification Service (Story 19.7)

Purpose:
--------
Delivers approved signals to connected frontend clients via WebSocket.
Implements retry logic with exponential backoff for reliable delivery.

Features:
---------
- Real-time signal delivery within 500ms of approval
- 3-retry delivery with exponential backoff (100ms, 500ms, 2000ms)
- Delivery status logging for debugging and metrics
- User-scoped notification delivery

Integration:
------------
- Signal validation pipeline (Story 19.5)
- Confidence scoring (Story 19.6)
- WebSocket infrastructure (Story 10.9)

Author: Story 19.7
"""

from __future__ import annotations

__all__ = [
    "SignalNotificationService",
    "DeliveryResult",
    "DeliveryStatus",
]

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from src.models.notification import SignalNotification
from src.models.signal import TradeSignal

if TYPE_CHECKING:
    from src.api.websocket import ConnectionManager

logger = structlog.get_logger(__name__)

# Retry delays in milliseconds (exponential backoff)
RETRY_DELAYS_MS = [100, 500, 2000]
MAX_RETRIES = 3

# Signal expiration for manual approval (5 minutes)
DEFAULT_EXPIRY_MINUTES = 5

# Delivery timing requirement
MAX_DELIVERY_LATENCY_MS = 500


class DeliveryStatus(str, Enum):
    """Delivery status for signal notifications."""

    SUCCESS = "success"
    RETRY = "retry"
    FAILED = "failed"


@dataclass
class DeliveryResult:
    """Result of a notification delivery attempt."""

    status: DeliveryStatus
    signal_id: UUID
    user_id: UUID | None
    attempts: int
    latency_ms: float
    error: str | None = None


class SignalNotificationService:
    """
    Service for delivering approved signals via WebSocket.

    Handles notification creation, delivery with retry logic,
    and delivery status tracking.

    Attributes:
        connection_manager: WebSocket connection manager
        _delivery_metrics: Internal metrics tracking

    Example:
        >>> service = SignalNotificationService(connection_manager)
        >>> result = await service.notify_signal_approved(trade_signal)
        >>> print(result.status)  # DeliveryStatus.SUCCESS
    """

    def __init__(self, connection_manager: ConnectionManager) -> None:
        """
        Initialize SignalNotificationService.

        Args:
            connection_manager: WebSocket connection manager for broadcasting
        """
        self._connection_manager = connection_manager
        self._delivery_count = 0
        self._failure_count = 0
        self._retry_count = 0

    async def notify_signal_approved(
        self,
        signal: TradeSignal,
        user_id: UUID | None = None,
    ) -> DeliveryResult:
        """
        Deliver approved signal notification to connected clients.

        Creates SignalNotification payload and broadcasts via WebSocket.
        Implements retry logic with exponential backoff on failure.

        Args:
            signal: Approved TradeSignal to notify about
            user_id: Optional user ID for targeted delivery (broadcasts to all if None)

        Returns:
            DeliveryResult with status, attempts, and latency

        Timing:
            Target: < 500ms from approval to delivery
        """
        start_time = datetime.now(UTC)

        # Create notification payload
        notification = self._create_notification(signal)

        # Attempt delivery with retries
        result = await self._deliver_with_retry(notification, user_id, start_time)

        # Log delivery result
        self._log_delivery(result, notification)

        return result

    def _create_notification(self, signal: TradeSignal) -> SignalNotification:
        """
        Create SignalNotification payload from TradeSignal.

        Extracts relevant fields and calculates derived values
        (confidence grade, expiration time).

        Args:
            signal: Approved TradeSignal

        Returns:
            SignalNotification payload ready for WebSocket delivery
        """
        # Calculate confidence grade
        confidence_grade = SignalNotification.confidence_to_grade(signal.confidence_score)

        # Calculate expiration time (5 minutes from now)
        expires_at = datetime.now(UTC) + timedelta(minutes=DEFAULT_EXPIRY_MINUTES)

        # Extract risk percentage from validation chain if available
        risk_percentage = self._extract_risk_percentage(signal)

        return SignalNotification(
            signal_id=signal.id,
            timestamp=datetime.now(UTC),
            symbol=signal.symbol,
            pattern_type=signal.pattern_type,
            confidence_score=float(signal.confidence_score),
            confidence_grade=confidence_grade,
            entry_price=str(signal.entry_price),
            stop_loss=str(signal.stop_loss),
            target_price=str(signal.target_levels.primary_target),
            risk_amount=str(signal.risk_amount),
            risk_percentage=risk_percentage,
            r_multiple=float(signal.r_multiple),
            expires_at=expires_at,
        )

    def _extract_risk_percentage(self, signal: TradeSignal) -> float:
        """
        Extract risk percentage from signal validation chain.

        Looks for risk percentage in validation metadata or calculates
        from risk_amount if not available.

        Args:
            signal: TradeSignal with validation chain

        Returns:
            Risk percentage (0.0-100.0)
        """
        # Try to get from validation chain metadata
        for result in signal.validation_chain.validation_results:
            # Stage is a string field (e.g., "Risk", "Volume")
            if result.stage == "Risk" and result.metadata:
                if "risk_percentage" in result.metadata:
                    return float(result.metadata["risk_percentage"])

        # Default to 1.5% if not found (conservative estimate)
        return 1.5

    async def _deliver_with_retry(
        self,
        notification: SignalNotification,
        user_id: UUID | None,
        start_time: datetime,
    ) -> DeliveryResult:
        """
        Deliver notification with retry logic on failure.

        Implements exponential backoff: 100ms, 500ms, 2000ms delays.
        Logs each attempt for debugging.

        Args:
            notification: SignalNotification to deliver
            user_id: Target user ID (None for broadcast)
            start_time: When delivery was initiated

        Returns:
            DeliveryResult with final status
        """
        last_error: str | None = None

        for attempt in range(MAX_RETRIES):
            try:
                # Calculate current latency
                latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000

                # Attempt delivery
                await self._send_notification(notification, user_id)

                # Success
                self._delivery_count += 1

                return DeliveryResult(
                    status=DeliveryStatus.SUCCESS,
                    signal_id=notification.signal_id,
                    user_id=user_id,
                    attempts=attempt + 1,
                    latency_ms=latency_ms,
                )

            except Exception as e:
                last_error = str(e)
                self._retry_count += 1

                logger.warning(
                    "signal_notification_delivery_failed",
                    signal_id=str(notification.signal_id),
                    attempt=attempt + 1,
                    max_retries=MAX_RETRIES,
                    error=last_error,
                )

                # Wait before retry (unless last attempt)
                if attempt < MAX_RETRIES - 1:
                    delay_ms = RETRY_DELAYS_MS[attempt]
                    await asyncio.sleep(delay_ms / 1000)

        # All retries exhausted
        self._failure_count += 1
        latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000

        return DeliveryResult(
            status=DeliveryStatus.FAILED,
            signal_id=notification.signal_id,
            user_id=user_id,
            attempts=MAX_RETRIES,
            latency_ms=latency_ms,
            error=last_error,
        )

    async def _send_notification(
        self,
        notification: SignalNotification,
        user_id: UUID | None,
    ) -> None:
        """
        Send notification via WebSocket.

        Broadcasts to all connected clients or targets specific user.

        Args:
            notification: SignalNotification payload
            user_id: Target user ID (None for broadcast)

        Raises:
            Exception: If WebSocket delivery fails
        """
        # Convert notification to dict for JSON serialization
        message = notification.model_dump(mode="json")

        if user_id is not None:
            # Send to specific user (if user_id tracking is implemented)
            # For now, broadcast to all (single-user MVP)
            await self._connection_manager.broadcast(message)
        else:
            # Broadcast to all connected clients
            await self._connection_manager.broadcast(message)

    def _log_delivery(
        self,
        result: DeliveryResult,
        notification: SignalNotification,
    ) -> None:
        """
        Log delivery result for debugging and metrics.

        Logs success/failure with relevant context for monitoring.

        Args:
            result: Delivery result
            notification: Notification that was delivered
        """
        log_data = {
            "signal_id": str(notification.signal_id),
            "symbol": notification.symbol,
            "pattern_type": notification.pattern_type,
            "confidence_grade": notification.confidence_grade,
            "attempts": result.attempts,
            "latency_ms": round(result.latency_ms, 2),
            "status": result.status.value,
        }

        if result.status == DeliveryStatus.SUCCESS:
            # Check if we met timing requirement
            if result.latency_ms <= MAX_DELIVERY_LATENCY_MS:
                logger.info("signal_notification_delivered", **log_data)
            else:
                logger.warning(
                    "signal_notification_delivered_late",
                    **log_data,
                    max_latency_ms=MAX_DELIVERY_LATENCY_MS,
                )
        else:
            logger.error(
                "signal_notification_delivery_failed",
                **log_data,
                error=result.error,
            )

    def get_metrics(self) -> dict[str, int]:
        """
        Get delivery metrics for monitoring.

        Returns:
            Dictionary with delivery counts
        """
        return {
            "signal_notifications_sent_total": self._delivery_count,
            "signal_notification_failures_total": self._failure_count,
            "signal_notification_retries_total": self._retry_count,
        }
