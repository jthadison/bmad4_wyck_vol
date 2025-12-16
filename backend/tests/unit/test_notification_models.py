"""
Unit tests for notification data models.

Tests Pydantic validation, field constraints, and data transformations
for all notification-related models.
"""

from datetime import datetime, time
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.models.notification import (
    ChannelPreferences,
    Notification,
    NotificationChannel,
    NotificationPreferences,
    NotificationPriority,
    NotificationToast,
    NotificationType,
    PushSubscription,
    QuietHours,
    TestNotificationRequest,
)


class TestNotificationEnums:
    """Test notification enum definitions."""

    def test_notification_type_values(self):
        """Verify all notification types are defined."""
        assert NotificationType.SIGNAL_GENERATED == "signal_generated"
        assert NotificationType.RISK_WARNING == "risk_warning"
        assert NotificationType.EMERGENCY_EXIT == "emergency_exit"
        assert NotificationType.SYSTEM_ERROR == "system_error"

    def test_notification_priority_values(self):
        """Verify all priority levels are defined."""
        assert NotificationPriority.INFO == "info"
        assert NotificationPriority.WARNING == "warning"
        assert NotificationPriority.CRITICAL == "critical"

    def test_notification_channel_values(self):
        """Verify all channels are defined."""
        assert NotificationChannel.TOAST == "toast"
        assert NotificationChannel.EMAIL == "email"
        assert NotificationChannel.SMS == "sms"
        assert NotificationChannel.PUSH == "push"


class TestNotification:
    """Test Notification model validation and serialization."""

    def test_create_valid_notification(self):
        """Test creating a valid notification."""
        notification_id = uuid4()
        user_id = uuid4()
        now = datetime.utcnow()

        notification = Notification(
            id=notification_id,
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority=NotificationPriority.WARNING,
            title="New Signal: AAPL Spring",
            message="Spring pattern detected on AAPL with 87% confidence",
            metadata={
                "signal_id": str(uuid4()),
                "symbol": "AAPL",
                "pattern_type": "SPRING",
                "confidence": 87,
            },
            user_id=user_id,
            read=False,
            created_at=now,
        )

        assert notification.id == notification_id
        assert notification.notification_type == NotificationType.SIGNAL_GENERATED
        assert notification.priority == NotificationPriority.WARNING
        assert notification.title == "New Signal: AAPL Spring"
        assert notification.user_id == user_id
        assert notification.read is False
        assert notification.metadata["confidence"] == 87

    def test_notification_title_max_length(self):
        """Test title length constraint (max 200 chars)."""
        with pytest.raises(ValidationError) as exc_info:
            Notification(
                id=uuid4(),
                notification_type=NotificationType.SIGNAL_GENERATED,
                priority=NotificationPriority.INFO,
                title="x" * 201,  # Exceeds max length
                message="Test message",
                user_id=uuid4(),
                created_at=datetime.utcnow(),
            )

        assert "title" in str(exc_info.value)

    def test_notification_message_max_length(self):
        """Test message length constraint (max 1000 chars)."""
        with pytest.raises(ValidationError) as exc_info:
            Notification(
                id=uuid4(),
                notification_type=NotificationType.SIGNAL_GENERATED,
                priority=NotificationPriority.INFO,
                title="Test",
                message="x" * 1001,  # Exceeds max length
                user_id=uuid4(),
                created_at=datetime.utcnow(),
            )

        assert "message" in str(exc_info.value)

    def test_notification_default_read_false(self):
        """Test that read defaults to False."""
        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.RISK_WARNING,
            priority=NotificationPriority.WARNING,
            title="Risk Alert",
            message="Portfolio heat exceeds threshold",
            user_id=uuid4(),
            created_at=datetime.utcnow(),
        )

        assert notification.read is False

    def test_notification_json_serialization(self):
        """Test JSON serialization with datetime encoding."""
        notification_id = uuid4()
        now = datetime.utcnow()

        notification = Notification(
            id=notification_id,
            notification_type=NotificationType.SYSTEM_ERROR,
            priority=NotificationPriority.CRITICAL,
            title="Database Connection Error",
            message="Unable to connect to database",
            user_id=uuid4(),
            created_at=now,
        )

        json_data = notification.model_dump(mode="json")
        assert isinstance(json_data["created_at"], str)
        assert isinstance(json_data["id"], str)


class TestQuietHours:
    """Test QuietHours model validation."""

    def test_create_valid_quiet_hours(self):
        """Test creating valid quiet hours configuration."""
        quiet_hours = QuietHours(
            enabled=True,
            start_time=time(22, 0),  # 10 PM
            end_time=time(8, 0),  # 8 AM
            timezone="America/New_York",
        )

        assert quiet_hours.enabled is True
        assert quiet_hours.start_time == time(22, 0)
        assert quiet_hours.end_time == time(8, 0)
        assert quiet_hours.timezone == "America/New_York"

    def test_quiet_hours_defaults(self):
        """Test quiet hours default values."""
        quiet_hours = QuietHours()

        assert quiet_hours.enabled is False
        assert quiet_hours.timezone == "America/New_York"

    def test_invalid_timezone(self):
        """Test validation rejects invalid timezone."""
        with pytest.raises(ValidationError) as exc_info:
            QuietHours(
                enabled=True,
                start_time=time(22, 0),
                end_time=time(8, 0),
                timezone="Invalid/Timezone",
            )

        assert "timezone" in str(exc_info.value).lower()


class TestChannelPreferences:
    """Test ChannelPreferences model."""

    def test_default_channel_preferences(self):
        """Test default channel configuration."""
        prefs = ChannelPreferences()

        assert prefs.info_channels == [NotificationChannel.TOAST]
        assert NotificationChannel.TOAST in prefs.warning_channels
        assert NotificationChannel.EMAIL in prefs.warning_channels
        assert len(prefs.critical_channels) == 4  # All channels

    def test_custom_channel_preferences(self):
        """Test custom channel configuration."""
        prefs = ChannelPreferences(
            info_channels=[NotificationChannel.TOAST],
            warning_channels=[NotificationChannel.TOAST, NotificationChannel.EMAIL],
            critical_channels=[NotificationChannel.TOAST, NotificationChannel.SMS],
        )

        assert len(prefs.critical_channels) == 2
        assert NotificationChannel.SMS in prefs.critical_channels


class TestNotificationPreferences:
    """Test NotificationPreferences model validation."""

    def test_create_valid_preferences(self):
        """Test creating valid notification preferences."""
        user_id = uuid4()
        now = datetime.utcnow()

        prefs = NotificationPreferences(
            user_id=user_id,
            email_enabled=True,
            email_address="trader@example.com",
            sms_enabled=True,
            sms_phone_number="+12345678901",
            push_enabled=False,
            min_confidence_threshold=85,
            updated_at=now,
        )

        assert prefs.user_id == user_id
        assert prefs.email_address == "trader@example.com"
        assert prefs.sms_phone_number == "+12345678901"
        assert prefs.min_confidence_threshold == 85

    def test_valid_e164_phone_numbers(self):
        """Test valid E.164 phone number formats."""
        valid_numbers = [
            "+12345678901",  # US
            "+442071234567",  # UK
            "+81312345678",  # Japan
            "+61212345678",  # Australia
        ]

        for phone in valid_numbers:
            prefs = NotificationPreferences(
                user_id=uuid4(), sms_phone_number=phone, updated_at=datetime.utcnow()
            )
            assert prefs.sms_phone_number == phone

    def test_invalid_phone_number_formats(self):
        """Test invalid phone number formats are rejected."""
        invalid_numbers = [
            "1234567890",  # Missing +
            "+0234567890",  # Starts with 0
            "+1-234-567-8901",  # Contains hyphens
            "+1 234 567 8901",  # Contains spaces
            "12345678901",  # Missing +
        ]

        for phone in invalid_numbers:
            with pytest.raises(ValidationError):
                NotificationPreferences(
                    user_id=uuid4(), sms_phone_number=phone, updated_at=datetime.utcnow()
                )

    def test_confidence_threshold_range(self):
        """Test confidence threshold must be 70-95."""
        # Valid thresholds
        for threshold in [70, 85, 95]:
            prefs = NotificationPreferences(
                user_id=uuid4(), min_confidence_threshold=threshold, updated_at=datetime.utcnow()
            )
            assert prefs.min_confidence_threshold == threshold

        # Invalid thresholds
        for threshold in [69, 96, 50, 100]:
            with pytest.raises(ValidationError):
                NotificationPreferences(
                    user_id=uuid4(),
                    min_confidence_threshold=threshold,
                    updated_at=datetime.utcnow(),
                )

    def test_default_quiet_hours(self):
        """Test quiet hours default to disabled."""
        prefs = NotificationPreferences(user_id=uuid4(), updated_at=datetime.utcnow())

        assert prefs.quiet_hours.enabled is False

    def test_preferences_with_quiet_hours(self):
        """Test preferences with custom quiet hours."""
        quiet_hours = QuietHours(
            enabled=True, start_time=time(22, 0), end_time=time(8, 0), timezone="America/Chicago"
        )

        prefs = NotificationPreferences(
            user_id=uuid4(), quiet_hours=quiet_hours, updated_at=datetime.utcnow()
        )

        assert prefs.quiet_hours.enabled is True
        assert prefs.quiet_hours.timezone == "America/Chicago"


class TestNotificationToast:
    """Test NotificationToast WebSocket message model."""

    def test_create_valid_toast_message(self):
        """Test creating valid toast message."""
        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority=NotificationPriority.INFO,
            title="Test Signal",
            message="Test message",
            user_id=uuid4(),
            created_at=datetime.utcnow(),
        )

        toast = NotificationToast(
            sequence_number=1250, notification=notification, timestamp=datetime.utcnow()
        )

        assert toast.type == "notification_toast"
        assert toast.sequence_number == 1250
        assert toast.notification.title == "Test Signal"

    def test_toast_type_is_literal(self):
        """Test that type field is always 'notification_toast'."""
        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.RISK_WARNING,
            priority=NotificationPriority.WARNING,
            title="Risk Alert",
            message="Test",
            user_id=uuid4(),
            created_at=datetime.utcnow(),
        )

        toast = NotificationToast(
            sequence_number=100, notification=notification, timestamp=datetime.utcnow()
        )

        # Type should always be the literal value
        assert toast.type == "notification_toast"


class TestPushSubscription:
    """Test PushSubscription model."""

    def test_create_valid_push_subscription(self):
        """Test creating valid push subscription."""
        user_id = uuid4()
        now = datetime.utcnow()

        subscription = PushSubscription(
            user_id=user_id,
            endpoint="https://fcm.googleapis.com/fcm/send/...",
            p256dh_key="BGxQ...",
            auth_key="Ah3x...",
            created_at=now,
        )

        assert subscription.user_id == user_id
        assert subscription.endpoint.startswith("https://")
        assert subscription.p256dh_key == "BGxQ..."
        assert subscription.auth_key == "Ah3x..."


class TestTestNotificationRequest:
    """Test TestNotificationRequest model."""

    def test_create_test_request_for_each_channel(self):
        """Test creating test requests for all channels."""
        channels = [NotificationChannel.SMS, NotificationChannel.EMAIL, NotificationChannel.PUSH]

        for channel in channels:
            request = TestNotificationRequest(channel=channel)
            assert request.channel == channel

    def test_toast_not_testable(self):
        """Test that toast can be in test request (though typically not used)."""
        # Toast notifications are sent via WebSocket, not typically tested via API
        # But the model should accept it
        request = TestNotificationRequest(channel=NotificationChannel.TOAST)
        assert request.channel == NotificationChannel.TOAST
