"""
Unit Tests for WebSocket Toast Notification Integration

Tests the integration between NotificationService and WebSocket manager
for real-time toast notification delivery.

Story: 11.6 - Notification & Alert System
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.models.notification import (
    Notification,
    NotificationPriority,
    NotificationType,
)
from src.notifications.service import NotificationService
from src.repositories.notification_repository import NotificationRepository


@pytest.fixture
def mock_repository():
    """Mock NotificationRepository."""
    repository = AsyncMock(spec=NotificationRepository)
    return repository


@pytest.fixture
def mock_websocket_manager():
    """Mock WebSocket manager."""
    manager = MagicMock()
    manager.emit_notification_toast = AsyncMock()
    return manager


@pytest.fixture
def notification_service_with_websocket(mock_repository, mock_websocket_manager):
    """NotificationService with WebSocket manager configured."""
    return NotificationService(
        repository=mock_repository,
        websocket_manager=mock_websocket_manager,
    )


@pytest.mark.asyncio
async def test_toast_sent_via_websocket(
    notification_service_with_websocket, mock_repository, mock_websocket_manager
):
    """Test that toast notifications are sent via WebSocket manager."""
    user_id = uuid4()

    # Mock preferences allowing toast notifications
    from src.models.notification import NotificationPreferences

    preferences = NotificationPreferences(
        user_id=user_id,
        updated_at=datetime.now(UTC),
    )
    mock_repository.get_preferences.return_value = preferences

    # Mock notification creation
    notification_id = uuid4()
    created_notification = Notification(
        id=notification_id,
        user_id=user_id,
        notification_type=NotificationType.SIGNAL_GENERATED,
        priority=NotificationPriority.INFO,
        title="Test Signal",
        message="New signal detected",
        metadata={"confidence": 90, "symbol": "AAPL"},
        read=False,
        created_at=datetime.now(UTC),
    )
    mock_repository.create_notification.return_value = created_notification

    # Send notification
    result = await notification_service_with_websocket.send_notification(
        user_id=user_id,
        notification_type=NotificationType.SIGNAL_GENERATED,
        priority=NotificationPriority.INFO,
        title="Test Signal",
        message="New signal detected",
        metadata={"confidence": 90, "symbol": "AAPL"},
    )

    # Verify notification was created
    assert result == created_notification

    # Verify toast was sent via WebSocket
    mock_websocket_manager.emit_notification_toast.assert_called_once()

    # Verify the notification passed to WebSocket matches
    call_args = mock_websocket_manager.emit_notification_toast.call_args[0]
    emitted_notification = call_args[0]

    assert emitted_notification.id == notification_id
    assert emitted_notification.notification_type == NotificationType.SIGNAL_GENERATED
    assert emitted_notification.title == "Test Signal"


@pytest.mark.asyncio
async def test_websocket_manager_not_configured(mock_repository):
    """Test that service handles missing WebSocket manager gracefully."""
    user_id = uuid4()

    # Create service without WebSocket manager
    service = NotificationService(
        repository=mock_repository,
        websocket_manager=None,  # No WebSocket manager
    )

    # Mock preferences
    from src.models.notification import NotificationPreferences

    preferences = NotificationPreferences(
        user_id=user_id,
        updated_at=datetime.now(UTC),
    )
    mock_repository.get_preferences.return_value = preferences

    # Mock notification creation
    created_notification = Notification(
        id=uuid4(),
        user_id=user_id,
        notification_type=NotificationType.SIGNAL_GENERATED,
        priority=NotificationPriority.INFO,
        title="Test Signal",
        message="New signal detected",
        metadata={"confidence": 90},
        read=False,
        created_at=datetime.now(UTC),
    )
    mock_repository.create_notification.return_value = created_notification

    # Should not raise error despite no WebSocket manager
    result = await service.send_notification(
        user_id=user_id,
        notification_type=NotificationType.SIGNAL_GENERATED,
        priority=NotificationPriority.INFO,
        title="Test Signal",
        message="New signal detected",
        metadata={"confidence": 90},
    )

    # Notification still created successfully
    assert result == created_notification


@pytest.mark.asyncio
async def test_toast_not_sent_if_filtered_by_confidence(
    notification_service_with_websocket, mock_repository, mock_websocket_manager
):
    """Test that toast is NOT sent if notification filtered by confidence threshold."""
    user_id = uuid4()

    # Mock preferences with high confidence threshold
    from src.models.notification import NotificationPreferences

    preferences = NotificationPreferences(
        user_id=user_id,
        min_confidence_threshold=90,  # High threshold
        updated_at=datetime.now(UTC),
    )
    mock_repository.get_preferences.return_value = preferences

    # Send low confidence signal (should be filtered)
    result = await notification_service_with_websocket.send_notification(
        user_id=user_id,
        notification_type=NotificationType.SIGNAL_GENERATED,
        priority=NotificationPriority.INFO,
        title="Low Confidence Signal",
        message="Signal at 75% confidence",
        metadata={"confidence": 75},  # Below threshold
    )

    # Notification should be filtered
    assert result is None

    # Toast should NOT be sent
    mock_websocket_manager.emit_notification_toast.assert_not_called()

    # Notification should NOT be created
    mock_repository.create_notification.assert_not_called()


@pytest.mark.asyncio
async def test_toast_not_sent_during_quiet_hours(
    notification_service_with_websocket, mock_repository, mock_websocket_manager
):
    """Test that toast is NOT sent during quiet hours (except CRITICAL)."""
    user_id = uuid4()

    # Mock preferences with quiet hours enabled
    from datetime import time

    from src.models.notification import NotificationPreferences, QuietHours

    preferences = NotificationPreferences(
        user_id=user_id,
        quiet_hours=QuietHours(
            enabled=True,
            start_time=time(0, 0),  # Midnight
            end_time=time(23, 59),  # End of day (covers all times)
            timezone="UTC",
        ),
        updated_at=datetime.now(UTC),
    )
    mock_repository.get_preferences.return_value = preferences

    # Send INFO notification during quiet hours
    result = await notification_service_with_websocket.send_notification(
        user_id=user_id,
        notification_type=NotificationType.SIGNAL_GENERATED,
        priority=NotificationPriority.INFO,  # Not CRITICAL
        title="Info Signal",
        message="Signal during quiet hours",
        metadata={"confidence": 90},
    )

    # Notification should be filtered
    assert result is None

    # Toast should NOT be sent
    mock_websocket_manager.emit_notification_toast.assert_not_called()


@pytest.mark.asyncio
async def test_critical_toast_sent_during_quiet_hours(
    notification_service_with_websocket, mock_repository, mock_websocket_manager
):
    """Test that CRITICAL toast is sent even during quiet hours."""
    user_id = uuid4()

    # Mock preferences with quiet hours enabled
    from datetime import time

    from src.models.notification import NotificationPreferences, QuietHours

    preferences = NotificationPreferences(
        user_id=user_id,
        quiet_hours=QuietHours(
            enabled=True,
            start_time=time(0, 0),
            end_time=time(23, 59),
            timezone="UTC",
        ),
        updated_at=datetime.now(UTC),
    )
    mock_repository.get_preferences.return_value = preferences

    # Mock notification creation
    created_notification = Notification(
        id=uuid4(),
        user_id=user_id,
        notification_type=NotificationType.EMERGENCY_EXIT,
        priority=NotificationPriority.CRITICAL,
        title="Emergency Exit",
        message="Critical emergency",
        metadata={},
        read=False,
        created_at=datetime.now(UTC),
    )
    mock_repository.create_notification.return_value = created_notification

    # Send CRITICAL notification during quiet hours
    result = await notification_service_with_websocket.send_notification(
        user_id=user_id,
        notification_type=NotificationType.EMERGENCY_EXIT,
        priority=NotificationPriority.CRITICAL,  # CRITICAL overrides quiet hours
        title="Emergency Exit",
        message="Critical emergency",
        metadata={},
    )

    # Notification should be sent (CRITICAL overrides quiet hours)
    assert result == created_notification

    # Toast SHOULD be sent even during quiet hours
    mock_websocket_manager.emit_notification_toast.assert_called_once()


@pytest.mark.asyncio
async def test_websocket_error_does_not_fail_notification(
    notification_service_with_websocket, mock_repository, mock_websocket_manager
):
    """Test that WebSocket errors don't prevent notification creation."""
    user_id = uuid4()

    # Mock preferences
    from src.models.notification import NotificationPreferences

    preferences = NotificationPreferences(
        user_id=user_id,
        updated_at=datetime.now(UTC),
    )
    mock_repository.get_preferences.return_value = preferences

    # Mock notification creation
    created_notification = Notification(
        id=uuid4(),
        user_id=user_id,
        notification_type=NotificationType.SIGNAL_GENERATED,
        priority=NotificationPriority.INFO,
        title="Test Signal",
        message="New signal",
        metadata={"confidence": 90},
        read=False,
        created_at=datetime.now(UTC),
    )
    mock_repository.create_notification.return_value = created_notification

    # Make WebSocket manager raise error
    mock_websocket_manager.emit_notification_toast.side_effect = Exception(
        "WebSocket connection failed"
    )

    # Should NOT raise error - WebSocket errors are caught
    result = await notification_service_with_websocket.send_notification(
        user_id=user_id,
        notification_type=NotificationType.SIGNAL_GENERATED,
        priority=NotificationPriority.INFO,
        title="Test Signal",
        message="New signal",
        metadata={"confidence": 90},
    )

    # Notification still created successfully despite WebSocket error
    assert result == created_notification
