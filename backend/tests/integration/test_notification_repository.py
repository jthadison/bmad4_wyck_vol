"""
Integration tests for NotificationRepository

Tests all repository methods against a test database.
Story: 11.6 - Notification & Alert System
"""

from datetime import datetime, time
from uuid import uuid4

import pytest

from src.models.notification import (
    ChannelPreferences,
    NotificationChannel,
    NotificationPreferences,
    NotificationPriority,
    NotificationType,
    QuietHours,
)
from src.repositories.notification_repository import NotificationRepository


class TestNotificationRepository:
    """Test NotificationRepository CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_notification(self, notification_repository: NotificationRepository):
        """Test creating a notification."""
        user_id = uuid4()

        notification = await notification_repository.create_notification(
            user_id=user_id,
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority="info",
            title="Test Signal",
            message="New signal detected for AAPL",
            metadata={"signal_id": str(uuid4()), "symbol": "AAPL", "confidence": 87},
        )

        assert notification.id is not None
        assert notification.user_id == user_id
        assert notification.notification_type == NotificationType.SIGNAL_GENERATED
        assert notification.priority == NotificationPriority.INFO
        assert notification.title == "Test Signal"
        assert notification.message == "New signal detected for AAPL"
        assert notification.metadata["symbol"] == "AAPL"
        assert notification.metadata["confidence"] == 87
        assert notification.read is False
        assert notification.created_at is not None

    @pytest.mark.asyncio
    async def test_get_notifications_all(self, notification_repository: NotificationRepository):
        """Test getting all notifications for a user."""
        user_id = uuid4()

        # Create 3 notifications
        for i in range(3):
            await notification_repository.create_notification(
                user_id=user_id,
                notification_type=NotificationType.SIGNAL_GENERATED,
                priority="info",
                title=f"Signal {i}",
                message=f"Message {i}",
                metadata={"index": i},
            )

        # Get all notifications
        notifications, total_count = await notification_repository.get_notifications(
            user_id=user_id,
            limit=50,
            offset=0,
        )

        assert len(notifications) == 3
        assert total_count == 3
        # Should be ordered by created_at DESC (newest first)
        assert notifications[0].title == "Signal 2"
        assert notifications[1].title == "Signal 1"
        assert notifications[2].title == "Signal 0"

    @pytest.mark.asyncio
    async def test_get_notifications_pagination(
        self, notification_repository: NotificationRepository
    ):
        """Test pagination of notifications."""
        user_id = uuid4()

        # Create 5 notifications
        for i in range(5):
            await notification_repository.create_notification(
                user_id=user_id,
                notification_type=NotificationType.SIGNAL_GENERATED,
                priority="info",
                title=f"Signal {i}",
                message=f"Message {i}",
                metadata={"index": i},
            )

        # Get first page (limit=2, offset=0)
        page1, total_count = await notification_repository.get_notifications(
            user_id=user_id,
            limit=2,
            offset=0,
        )

        assert len(page1) == 2
        assert total_count == 5
        assert page1[0].title == "Signal 4"  # Newest first
        assert page1[1].title == "Signal 3"

        # Get second page (limit=2, offset=2)
        page2, total_count = await notification_repository.get_notifications(
            user_id=user_id,
            limit=2,
            offset=2,
        )

        assert len(page2) == 2
        assert total_count == 5
        assert page2[0].title == "Signal 2"
        assert page2[1].title == "Signal 1"

        # Get third page (limit=2, offset=4)
        page3, total_count = await notification_repository.get_notifications(
            user_id=user_id,
            limit=2,
            offset=4,
        )

        assert len(page3) == 1
        assert total_count == 5
        assert page3[0].title == "Signal 0"

    @pytest.mark.asyncio
    async def test_get_notifications_unread_only(
        self, notification_repository: NotificationRepository
    ):
        """Test filtering notifications by unread status."""
        user_id = uuid4()

        # Create 3 notifications
        notif_ids = []
        for i in range(3):
            notif = await notification_repository.create_notification(
                user_id=user_id,
                notification_type=NotificationType.SIGNAL_GENERATED,
                priority="info",
                title=f"Signal {i}",
                message=f"Message {i}",
                metadata={},
            )
            notif_ids.append(notif.id)

        # Mark first notification as read
        await notification_repository.mark_as_read(notif_ids[0], user_id)

        # Get unread only
        unread, total_count = await notification_repository.get_notifications(
            user_id=user_id,
            unread_only=True,
            limit=50,
            offset=0,
        )

        assert len(unread) == 2
        assert total_count == 2
        assert all(not n.read for n in unread)
        assert notif_ids[0] not in [n.id for n in unread]

    @pytest.mark.asyncio
    async def test_get_notifications_by_type(self, notification_repository: NotificationRepository):
        """Test filtering notifications by type."""
        user_id = uuid4()

        # Create notifications of different types
        await notification_repository.create_notification(
            user_id=user_id,
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority="info",
            title="Signal",
            message="Signal message",
            metadata={},
        )
        await notification_repository.create_notification(
            user_id=user_id,
            notification_type=NotificationType.RISK_WARNING,
            priority="warning",
            title="Risk Warning",
            message="Risk message",
            metadata={},
        )
        await notification_repository.create_notification(
            user_id=user_id,
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority="info",
            title="Signal 2",
            message="Signal message 2",
            metadata={},
        )

        # Get only SIGNAL_GENERATED
        signals, total_count = await notification_repository.get_notifications(
            user_id=user_id,
            notification_type=NotificationType.SIGNAL_GENERATED,
            limit=50,
            offset=0,
        )

        assert len(signals) == 2
        assert total_count == 2
        assert all(n.notification_type == NotificationType.SIGNAL_GENERATED for n in signals)

        # Get only RISK_WARNING
        risks, total_count = await notification_repository.get_notifications(
            user_id=user_id,
            notification_type=NotificationType.RISK_WARNING,
            limit=50,
            offset=0,
        )

        assert len(risks) == 1
        assert total_count == 1
        assert risks[0].notification_type == NotificationType.RISK_WARNING

    @pytest.mark.asyncio
    async def test_get_notifications_user_isolation(
        self, notification_repository: NotificationRepository
    ):
        """Test that users can only see their own notifications."""
        user1_id = uuid4()
        user2_id = uuid4()

        # Create notifications for both users
        await notification_repository.create_notification(
            user_id=user1_id,
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority="info",
            title="User 1 Signal",
            message="Message",
            metadata={},
        )
        await notification_repository.create_notification(
            user_id=user2_id,
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority="info",
            title="User 2 Signal",
            message="Message",
            metadata={},
        )

        # Get notifications for user 1
        user1_notifs, total_count = await notification_repository.get_notifications(
            user_id=user1_id,
            limit=50,
            offset=0,
        )

        assert len(user1_notifs) == 1
        assert total_count == 1
        assert user1_notifs[0].title == "User 1 Signal"

        # Get notifications for user 2
        user2_notifs, total_count = await notification_repository.get_notifications(
            user_id=user2_id,
            limit=50,
            offset=0,
        )

        assert len(user2_notifs) == 1
        assert total_count == 1
        assert user2_notifs[0].title == "User 2 Signal"

    @pytest.mark.asyncio
    async def test_mark_as_read(self, notification_repository: NotificationRepository):
        """Test marking notification as read."""
        user_id = uuid4()

        # Create notification
        notification = await notification_repository.create_notification(
            user_id=user_id,
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority="info",
            title="Test",
            message="Message",
            metadata={},
        )

        assert notification.read is False

        # Mark as read
        await notification_repository.mark_as_read(notification.id, user_id)

        # Verify updated
        notifications, _ = await notification_repository.get_notifications(
            user_id=user_id,
            limit=50,
            offset=0,
        )

        assert len(notifications) == 1
        assert notifications[0].read is True

    @pytest.mark.asyncio
    async def test_get_preferences_not_exists(
        self, notification_repository: NotificationRepository
    ):
        """Test getting preferences when they don't exist."""
        user_id = uuid4()

        preferences = await notification_repository.get_preferences(user_id)

        assert preferences is None

    @pytest.mark.asyncio
    async def test_update_preferences_create(self, notification_repository: NotificationRepository):
        """Test creating preferences via update."""
        user_id = uuid4()

        preferences = NotificationPreferences(
            user_id=user_id,
            email_enabled=True,
            email_address="test@example.com",
            sms_enabled=True,
            sms_phone_number="+12345678901",
            push_enabled=False,
            min_confidence_threshold=90,
            quiet_hours=QuietHours(
                enabled=True,
                start_time=time(22, 0),
                end_time=time(8, 0),
                timezone="America/New_York",
            ),
            channel_preferences=ChannelPreferences(
                info_channels=[NotificationChannel.TOAST],
                warning_channels=[NotificationChannel.TOAST, NotificationChannel.EMAIL],
                critical_channels=[
                    NotificationChannel.TOAST,
                    NotificationChannel.EMAIL,
                    NotificationChannel.SMS,
                ],
            ),
            updated_at=datetime.utcnow(),
        )

        await notification_repository.update_preferences(preferences)

        # Verify created
        retrieved = await notification_repository.get_preferences(user_id)

        assert retrieved is not None
        assert retrieved.user_id == user_id
        assert retrieved.email_enabled is True
        assert retrieved.email_address == "test@example.com"
        assert retrieved.sms_enabled is True
        assert retrieved.sms_phone_number == "+12345678901"
        assert retrieved.push_enabled is False
        assert retrieved.min_confidence_threshold == 90
        assert retrieved.quiet_hours.enabled is True
        assert retrieved.quiet_hours.start_time == time(22, 0)
        assert retrieved.quiet_hours.end_time == time(8, 0)
        assert retrieved.quiet_hours.timezone == "America/New_York"
        assert NotificationChannel.TOAST in retrieved.channel_preferences.info_channels
        assert NotificationChannel.EMAIL in retrieved.channel_preferences.warning_channels
        assert NotificationChannel.SMS in retrieved.channel_preferences.critical_channels

    @pytest.mark.asyncio
    async def test_update_preferences_upsert(self, notification_repository: NotificationRepository):
        """Test updating existing preferences."""
        user_id = uuid4()

        # Create initial preferences
        initial_prefs = NotificationPreferences(
            user_id=user_id,
            email_enabled=True,
            email_address="test@example.com",
            min_confidence_threshold=85,
            updated_at=datetime.utcnow(),
        )
        await notification_repository.update_preferences(initial_prefs)

        # Update preferences
        updated_prefs = NotificationPreferences(
            user_id=user_id,
            email_enabled=False,  # Changed
            email_address="newemail@example.com",  # Changed
            sms_enabled=True,  # New field
            sms_phone_number="+19876543210",
            min_confidence_threshold=95,  # Changed
            updated_at=datetime.utcnow(),
        )
        await notification_repository.update_preferences(updated_prefs)

        # Verify updated
        retrieved = await notification_repository.get_preferences(user_id)

        assert retrieved is not None
        assert retrieved.email_enabled is False
        assert retrieved.email_address == "newemail@example.com"
        assert retrieved.sms_enabled is True
        assert retrieved.sms_phone_number == "+19876543210"
        assert retrieved.min_confidence_threshold == 95

    @pytest.mark.asyncio
    async def test_create_push_subscription(self, notification_repository: NotificationRepository):
        """Test creating push subscription."""
        user_id = uuid4()
        endpoint = "https://fcm.googleapis.com/fcm/send/test123"

        subscription = await notification_repository.create_push_subscription(
            user_id=user_id,
            endpoint=endpoint,
            p256dh_key="test_p256dh_key",
            auth_key="test_auth_key",
        )

        assert subscription.user_id == user_id
        assert subscription.endpoint == endpoint
        assert subscription.p256dh_key == "test_p256dh_key"
        assert subscription.auth_key == "test_auth_key"
        assert subscription.created_at is not None

    @pytest.mark.asyncio
    async def test_create_push_subscription_upsert(
        self, notification_repository: NotificationRepository
    ):
        """Test upserting push subscription with same endpoint."""
        user_id = uuid4()
        endpoint = "https://fcm.googleapis.com/fcm/send/test123"

        # Create initial subscription
        sub1 = await notification_repository.create_push_subscription(
            user_id=user_id,
            endpoint=endpoint,
            p256dh_key="old_p256dh_key",
            auth_key="old_auth_key",
        )

        # Upsert with same endpoint (should update keys)
        sub2 = await notification_repository.create_push_subscription(
            user_id=user_id,
            endpoint=endpoint,
            p256dh_key="new_p256dh_key",
            auth_key="new_auth_key",
        )

        # Should have same endpoint but updated keys
        assert sub2.endpoint == endpoint
        assert sub2.p256dh_key == "new_p256dh_key"
        assert sub2.auth_key == "new_auth_key"

        # Verify only one subscription exists
        subscriptions = await notification_repository.get_push_subscriptions(user_id)
        assert len(subscriptions) == 1
        assert subscriptions[0].p256dh_key == "new_p256dh_key"

    @pytest.mark.asyncio
    async def test_get_push_subscriptions(self, notification_repository: NotificationRepository):
        """Test getting all push subscriptions for a user."""
        user_id = uuid4()

        # Create 2 subscriptions
        await notification_repository.create_push_subscription(
            user_id=user_id,
            endpoint="https://fcm.googleapis.com/fcm/send/sub1",
            p256dh_key="key1",
            auth_key="auth1",
        )
        await notification_repository.create_push_subscription(
            user_id=user_id,
            endpoint="https://fcm.googleapis.com/fcm/send/sub2",
            p256dh_key="key2",
            auth_key="auth2",
        )

        subscriptions = await notification_repository.get_push_subscriptions(user_id)

        assert len(subscriptions) == 2
        endpoints = [sub.endpoint for sub in subscriptions]
        assert "https://fcm.googleapis.com/fcm/send/sub1" in endpoints
        assert "https://fcm.googleapis.com/fcm/send/sub2" in endpoints

    @pytest.mark.asyncio
    async def test_get_push_subscriptions_user_isolation(
        self, notification_repository: NotificationRepository
    ):
        """Test that users can only see their own subscriptions."""
        user1_id = uuid4()
        user2_id = uuid4()

        # Create subscriptions for both users
        await notification_repository.create_push_subscription(
            user_id=user1_id,
            endpoint="https://fcm.googleapis.com/fcm/send/user1",
            p256dh_key="key1",
            auth_key="auth1",
        )
        await notification_repository.create_push_subscription(
            user_id=user2_id,
            endpoint="https://fcm.googleapis.com/fcm/send/user2",
            p256dh_key="key2",
            auth_key="auth2",
        )

        # Get subscriptions for user 1
        user1_subs = await notification_repository.get_push_subscriptions(user1_id)
        assert len(user1_subs) == 1
        assert user1_subs[0].endpoint == "https://fcm.googleapis.com/fcm/send/user1"

        # Get subscriptions for user 2
        user2_subs = await notification_repository.get_push_subscriptions(user2_id)
        assert len(user2_subs) == 1
        assert user2_subs[0].endpoint == "https://fcm.googleapis.com/fcm/send/user2"

    @pytest.mark.asyncio
    async def test_delete_push_subscription(self, notification_repository: NotificationRepository):
        """Test deleting push subscription."""
        user_id = uuid4()
        endpoint = "https://fcm.googleapis.com/fcm/send/test123"

        # Create subscription
        await notification_repository.create_push_subscription(
            user_id=user_id,
            endpoint=endpoint,
            p256dh_key="key",
            auth_key="auth",
        )

        # Verify exists
        subscriptions = await notification_repository.get_push_subscriptions(user_id)
        assert len(subscriptions) == 1

        # Delete subscription
        await notification_repository.delete_push_subscription(user_id, endpoint)

        # Verify deleted
        subscriptions = await notification_repository.get_push_subscriptions(user_id)
        assert len(subscriptions) == 0

    @pytest.mark.asyncio
    async def test_delete_push_subscription_idempotent(
        self, notification_repository: NotificationRepository
    ):
        """Test deleting non-existent subscription is idempotent."""
        user_id = uuid4()
        endpoint = "https://fcm.googleapis.com/fcm/send/nonexistent"

        # Delete non-existent subscription (should not raise error)
        await notification_repository.delete_push_subscription(user_id, endpoint)

        # Verify still 0 subscriptions
        subscriptions = await notification_repository.get_push_subscriptions(user_id)
        assert len(subscriptions) == 0

    @pytest.mark.asyncio
    async def test_jsonb_metadata_serialization(
        self, notification_repository: NotificationRepository
    ):
        """Test that complex metadata is correctly serialized/deserialized."""
        user_id = uuid4()

        complex_metadata = {
            "signal_id": str(uuid4()),
            "symbol": "AAPL",
            "confidence": 87.5,
            "indicators": {
                "rsi": 65.3,
                "macd": {"value": 1.2, "signal": 0.8},
                "volume_spike": True,
            },
            "tags": ["momentum", "breakout"],
        }

        notification = await notification_repository.create_notification(
            user_id=user_id,
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority="info",
            title="Complex Signal",
            message="Signal with complex metadata",
            metadata=complex_metadata,
        )

        # Retrieve and verify
        retrieved, _ = await notification_repository.get_notifications(
            user_id=user_id,
            limit=1,
            offset=0,
        )

        assert len(retrieved) == 1
        assert retrieved[0].metadata == complex_metadata
        assert retrieved[0].metadata["indicators"]["macd"]["value"] == 1.2
        assert "momentum" in retrieved[0].metadata["tags"]
