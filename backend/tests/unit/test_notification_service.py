"""
Unit Tests for NotificationService

Tests filtering logic, channel routing, and client delegation with mocks.
Integration tests for repository are in tests/integration/test_notification_repository.py.

Story: 11.6 - Notification & Alert System
"""

from datetime import datetime, time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.models.notification import (
    ChannelPreferences,
    Notification,
    NotificationChannel,
    NotificationPreferences,
    NotificationPriority,
    NotificationType,
    QuietHours,
)
from src.notifications.service import NotificationService


class TestNotificationService:
    """Test suite for NotificationService."""

    @pytest.fixture
    def mock_repository(self):
        """Mock NotificationRepository."""
        return AsyncMock()

    @pytest.fixture
    def mock_twilio_client(self):
        """Mock TwilioClient."""
        return AsyncMock()

    @pytest.fixture
    def mock_email_client(self):
        """Mock EmailClient."""
        return AsyncMock()

    @pytest.fixture
    def mock_push_client(self):
        """Mock PushClient."""
        return AsyncMock()

    @pytest.fixture
    def mock_websocket_manager(self):
        """Mock WebSocket manager."""
        return AsyncMock()

    @pytest.fixture
    def notification_service(
        self,
        mock_repository,
        mock_twilio_client,
        mock_email_client,
        mock_push_client,
        mock_websocket_manager,
    ):
        """NotificationService with all mocked dependencies."""
        return NotificationService(
            repository=mock_repository,
            twilio_client=mock_twilio_client,
            email_client=mock_email_client,
            push_client=mock_push_client,
            websocket_manager=mock_websocket_manager,
        )

    @pytest.fixture
    def default_preferences(self):
        """Default user preferences."""
        user_id = uuid4()
        return NotificationPreferences(
            user_id=user_id,
            email_enabled=True,
            email_address="test@example.com",
            sms_enabled=True,
            sms_phone_number="+11234567890",
            push_enabled=True,
            min_confidence_threshold=85,
            updated_at=datetime.utcnow(),
        )

    # =============================
    # Confidence Threshold Filtering
    # =============================

    @pytest.mark.asyncio
    async def test_send_notification_filters_low_confidence_signal(
        self, notification_service, mock_repository
    ):
        """Test that signals below confidence threshold are filtered out."""
        user_id = uuid4()
        preferences = NotificationPreferences(
            user_id=user_id,
            min_confidence_threshold=85,
            updated_at=datetime.utcnow(),
        )
        mock_repository.get_preferences.return_value = preferences

        # Send signal with confidence below threshold
        result = await notification_service.send_notification(
            user_id=user_id,
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority=NotificationPriority.INFO,
            title="Low Confidence Signal",
            message="Signal at 75% confidence",
            metadata={"confidence": 75, "symbol": "AAPL"},
        )

        # Should be filtered out
        assert result is None
        mock_repository.create_notification.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_notification_passes_high_confidence_signal(
        self, notification_service, mock_repository
    ):
        """Test that signals above confidence threshold are sent."""
        user_id = uuid4()
        preferences = NotificationPreferences(
            user_id=user_id,
            min_confidence_threshold=85,
            updated_at=datetime.utcnow(),
        )
        mock_repository.get_preferences.return_value = preferences

        # Mock notification creation
        created_notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority=NotificationPriority.INFO,
            title="High Confidence Signal",
            message="Signal at 90% confidence",
            metadata={"confidence": 90},
            user_id=user_id,
            read=False,
            created_at=datetime.utcnow(),
        )
        mock_repository.create_notification.return_value = created_notification

        # Send signal with confidence above threshold
        result = await notification_service.send_notification(
            user_id=user_id,
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority=NotificationPriority.INFO,
            title="High Confidence Signal",
            message="Signal at 90% confidence",
            metadata={"confidence": 90, "symbol": "AAPL"},
        )

        # Should be created
        assert result is not None
        assert result.id == created_notification.id
        mock_repository.create_notification.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_notification_confidence_only_applies_to_signals(
        self, notification_service, mock_repository
    ):
        """Test that confidence threshold only applies to SIGNAL_GENERATED notifications."""
        user_id = uuid4()
        preferences = NotificationPreferences(
            user_id=user_id,
            min_confidence_threshold=85,
            updated_at=datetime.utcnow(),
        )
        mock_repository.get_preferences.return_value = preferences

        # Mock notification creation
        created_notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.RISK_WARNING,
            priority=NotificationPriority.WARNING,
            title="Risk Warning",
            message="Risk exceeded",
            metadata={"risk_level": "high"},  # No confidence field
            user_id=user_id,
            read=False,
            created_at=datetime.utcnow(),
        )
        mock_repository.create_notification.return_value = created_notification

        # Send non-signal notification (should not filter even without confidence)
        result = await notification_service.send_notification(
            user_id=user_id,
            notification_type=NotificationType.RISK_WARNING,
            priority=NotificationPriority.WARNING,
            title="Risk Warning",
            message="Risk exceeded",
            metadata={"risk_level": "high"},
        )

        # Should be created (confidence filter doesn't apply)
        assert result is not None
        mock_repository.create_notification.assert_called_once()

    # =============================
    # Quiet Hours Filtering
    # =============================

    @pytest.mark.asyncio
    async def test_send_notification_filters_during_quiet_hours(
        self, notification_service, mock_repository
    ):
        """Test that INFO/WARNING notifications are filtered during quiet hours."""
        user_id = uuid4()

        # Mock current time to be in quiet hours (11 PM)
        with patch("src.notifications.service.datetime") as mock_datetime:
            mock_datetime.now.return_value = MagicMock(time=MagicMock(return_value=time(23, 0)))

            preferences = NotificationPreferences(
                user_id=user_id,
                quiet_hours=QuietHours(
                    enabled=True,
                    start_time=time(22, 0),  # 10 PM
                    end_time=time(8, 0),  # 8 AM
                    timezone="America/New_York",
                ),
                updated_at=datetime.utcnow(),
            )
            mock_repository.get_preferences.return_value = preferences

            # Send INFO notification during quiet hours
            result = await notification_service.send_notification(
                user_id=user_id,
                notification_type=NotificationType.SIGNAL_GENERATED,
                priority=NotificationPriority.INFO,
                title="Signal",
                message="New signal",
                metadata={"confidence": 90},
            )

            # Should be filtered out
            assert result is None
            mock_repository.create_notification.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_notification_critical_overrides_quiet_hours(
        self, notification_service, mock_repository
    ):
        """Test that CRITICAL notifications bypass quiet hours."""
        user_id = uuid4()

        # Mock current time to be in quiet hours (11 PM)
        with patch("src.notifications.service.datetime") as mock_datetime:
            mock_datetime.now.return_value = MagicMock(time=MagicMock(return_value=time(23, 0)))

            preferences = NotificationPreferences(
                user_id=user_id,
                quiet_hours=QuietHours(
                    enabled=True,
                    start_time=time(22, 0),  # 10 PM
                    end_time=time(8, 0),  # 8 AM
                    timezone="America/New_York",
                ),
                updated_at=datetime.utcnow(),
            )
            mock_repository.get_preferences.return_value = preferences

            # Mock notification creation
            created_notification = Notification(
                id=uuid4(),
                notification_type=NotificationType.EMERGENCY_EXIT,
                priority=NotificationPriority.CRITICAL,
                title="Emergency Exit",
                message="Emergency exit triggered",
                metadata={},
                user_id=user_id,
                read=False,
                created_at=datetime.utcnow(),
            )
            mock_repository.create_notification.return_value = created_notification

            # Send CRITICAL notification during quiet hours
            result = await notification_service.send_notification(
                user_id=user_id,
                notification_type=NotificationType.EMERGENCY_EXIT,
                priority=NotificationPriority.CRITICAL,
                title="Emergency Exit",
                message="Emergency exit triggered",
                metadata={},
            )

            # Should NOT be filtered (critical overrides)
            assert result is not None
            mock_repository.create_notification.assert_called_once()

    # =============================
    # Quiet Hours Logic
    # =============================

    def test_is_quiet_hours_disabled(self, notification_service):
        """Test quiet hours disabled returns False."""
        quiet_hours = QuietHours(
            enabled=False,
            start_time=time(22, 0),
            end_time=time(8, 0),
        )
        assert notification_service._is_quiet_hours(quiet_hours) is False

    def test_is_quiet_hours_normal_range(self, notification_service):
        """Test quiet hours logic for normal time range (no midnight crossing)."""
        quiet_hours = QuietHours(
            enabled=True,
            start_time=time(22, 0),  # 10 PM
            end_time=time(23, 59),  # 11:59 PM
            timezone="America/New_York",
        )

        # Mock time within range
        with patch("src.notifications.service.datetime") as mock_datetime:
            mock_datetime.now.return_value = MagicMock(time=MagicMock(return_value=time(23, 0)))
            assert notification_service._is_quiet_hours(quiet_hours) is True

        # Mock time outside range
        with patch("src.notifications.service.datetime") as mock_datetime:
            mock_datetime.now.return_value = MagicMock(time=MagicMock(return_value=time(21, 0)))
            assert notification_service._is_quiet_hours(quiet_hours) is False

    def test_is_quiet_hours_spanning_midnight(self, notification_service):
        """Test quiet hours logic for time range spanning midnight."""
        quiet_hours = QuietHours(
            enabled=True,
            start_time=time(22, 0),  # 10 PM
            end_time=time(8, 0),  # 8 AM
            timezone="America/New_York",
        )

        # Mock time after start (11 PM)
        with patch("src.notifications.service.datetime") as mock_datetime:
            mock_datetime.now.return_value = MagicMock(time=MagicMock(return_value=time(23, 0)))
            assert notification_service._is_quiet_hours(quiet_hours) is True

        # Mock time before end (7 AM)
        with patch("src.notifications.service.datetime") as mock_datetime:
            mock_datetime.now.return_value = MagicMock(time=MagicMock(return_value=time(7, 0)))
            assert notification_service._is_quiet_hours(quiet_hours) is True

        # Mock time outside range (3 PM)
        with patch("src.notifications.service.datetime") as mock_datetime:
            mock_datetime.now.return_value = MagicMock(time=MagicMock(return_value=time(15, 0)))
            assert notification_service._is_quiet_hours(quiet_hours) is False

    # =============================
    # Channel Routing
    # =============================

    def test_get_channels_for_priority_info(self, notification_service):
        """Test channel selection for INFO priority."""
        preferences = NotificationPreferences(
            user_id=uuid4(),
            email_enabled=True,
            email_address="test@example.com",
            sms_enabled=True,
            sms_phone_number="+11234567890",
            push_enabled=True,
            channel_preferences=ChannelPreferences(
                info_channels=[NotificationChannel.TOAST],  # Only toast for INFO
                warning_channels=[
                    NotificationChannel.TOAST,
                    NotificationChannel.EMAIL,
                ],
                critical_channels=[
                    NotificationChannel.TOAST,
                    NotificationChannel.EMAIL,
                    NotificationChannel.SMS,
                    NotificationChannel.PUSH,
                ],
            ),
            updated_at=datetime.utcnow(),
        )

        channels = notification_service._get_channels_for_priority(
            NotificationPriority.INFO, preferences
        )

        # Should only get TOAST for INFO
        assert channels == [NotificationChannel.TOAST]

    def test_get_channels_for_priority_warning(self, notification_service):
        """Test channel selection for WARNING priority."""
        preferences = NotificationPreferences(
            user_id=uuid4(),
            email_enabled=True,
            email_address="test@example.com",
            sms_enabled=False,  # SMS disabled
            channel_preferences=ChannelPreferences(
                info_channels=[NotificationChannel.TOAST],
                warning_channels=[
                    NotificationChannel.TOAST,
                    NotificationChannel.EMAIL,
                ],
                critical_channels=[
                    NotificationChannel.TOAST,
                    NotificationChannel.EMAIL,
                    NotificationChannel.SMS,
                ],
            ),
            updated_at=datetime.utcnow(),
        )

        channels = notification_service._get_channels_for_priority(
            NotificationPriority.WARNING, preferences
        )

        # Should get TOAST and EMAIL (SMS disabled)
        assert set(channels) == {NotificationChannel.TOAST, NotificationChannel.EMAIL}

    def test_get_channels_for_priority_critical(self, notification_service):
        """Test channel selection for CRITICAL priority."""
        preferences = NotificationPreferences(
            user_id=uuid4(),
            email_enabled=True,
            email_address="test@example.com",
            sms_enabled=True,
            sms_phone_number="+11234567890",
            push_enabled=True,
            channel_preferences=ChannelPreferences(
                critical_channels=[
                    NotificationChannel.TOAST,
                    NotificationChannel.EMAIL,
                    NotificationChannel.SMS,
                    NotificationChannel.PUSH,
                ],
            ),
            updated_at=datetime.utcnow(),
        )

        channels = notification_service._get_channels_for_priority(
            NotificationPriority.CRITICAL, preferences
        )

        # Should get all channels
        assert set(channels) == {
            NotificationChannel.TOAST,
            NotificationChannel.EMAIL,
            NotificationChannel.SMS,
            NotificationChannel.PUSH,
        }

    def test_get_channels_filters_disabled_channels(self, notification_service):
        """Test that disabled channels are filtered out."""
        preferences = NotificationPreferences(
            user_id=uuid4(),
            email_enabled=False,  # Email disabled
            sms_enabled=False,  # SMS disabled
            push_enabled=False,  # Push disabled
            channel_preferences=ChannelPreferences(
                critical_channels=[
                    NotificationChannel.TOAST,
                    NotificationChannel.EMAIL,
                    NotificationChannel.SMS,
                    NotificationChannel.PUSH,
                ],
            ),
            updated_at=datetime.utcnow(),
        )

        channels = notification_service._get_channels_for_priority(
            NotificationPriority.CRITICAL, preferences
        )

        # Should only get TOAST (others disabled)
        assert channels == [NotificationChannel.TOAST]

    def test_get_channels_requires_contact_info(self, notification_service):
        """Test that channels without contact info are filtered out."""
        preferences = NotificationPreferences(
            user_id=uuid4(),
            email_enabled=True,
            email_address=None,  # No email address
            sms_enabled=True,
            sms_phone_number=None,  # No phone number
            channel_preferences=ChannelPreferences(
                critical_channels=[
                    NotificationChannel.TOAST,
                    NotificationChannel.EMAIL,
                    NotificationChannel.SMS,
                ],
            ),
            updated_at=datetime.utcnow(),
        )

        channels = notification_service._get_channels_for_priority(
            NotificationPriority.CRITICAL, preferences
        )

        # Should only get TOAST (no contact info for email/sms)
        assert channels == [NotificationChannel.TOAST]

    # =============================
    # Client Delegation
    # =============================

    @pytest.mark.asyncio
    async def test_route_to_channels_calls_email_client(
        self, notification_service, mock_email_client
    ):
        """Test that email client is called when EMAIL channel is enabled."""
        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority=NotificationPriority.WARNING,
            title="Signal",
            message="New signal",
            metadata={},
            user_id=uuid4(),
            read=False,
            created_at=datetime.utcnow(),
        )

        preferences = NotificationPreferences(
            user_id=uuid4(),
            email_enabled=True,
            email_address="test@example.com",
            updated_at=datetime.utcnow(),
        )

        await notification_service._route_to_channels(
            notification,
            [NotificationChannel.EMAIL],
            preferences,
        )

        mock_email_client.send_notification_email.assert_called_once_with(
            to_address="test@example.com",
            notification=notification,
        )

    @pytest.mark.asyncio
    async def test_route_to_channels_calls_sms_client(
        self, notification_service, mock_twilio_client
    ):
        """Test that Twilio client is called when SMS channel is enabled."""
        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.RISK_WARNING,
            priority=NotificationPriority.WARNING,
            title="Risk Warning",
            message="Risk exceeded",
            metadata={},
            user_id=uuid4(),
            read=False,
            created_at=datetime.utcnow(),
        )

        preferences = NotificationPreferences(
            user_id=uuid4(),
            sms_enabled=True,
            sms_phone_number="+11234567890",
            updated_at=datetime.utcnow(),
        )

        await notification_service._route_to_channels(
            notification,
            [NotificationChannel.SMS],
            preferences,
        )

        mock_twilio_client.send_sms.assert_called_once()
        call_args = mock_twilio_client.send_sms.call_args[1]
        assert call_args["phone_number"] == "+11234567890"
        assert "Risk Warning" in call_args["message"]

    @pytest.mark.asyncio
    async def test_route_to_channels_calls_push_client(
        self, notification_service, mock_push_client, mock_repository
    ):
        """Test that push client is called for each subscription when PUSH channel is enabled."""
        user_id = uuid4()
        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.EMERGENCY_EXIT,
            priority=NotificationPriority.CRITICAL,
            title="Emergency Exit",
            message="Exit triggered",
            metadata={},
            user_id=user_id,
            read=False,
            created_at=datetime.utcnow(),
        )

        # Mock push subscriptions
        from src.models.notification import PushSubscription

        subscriptions = [
            PushSubscription(
                user_id=user_id,
                endpoint="https://fcm.googleapis.com/fcm/send/sub1",
                p256dh_key="key1",
                auth_key="auth1",
                created_at=datetime.utcnow(),
            ),
            PushSubscription(
                user_id=user_id,
                endpoint="https://fcm.googleapis.com/fcm/send/sub2",
                p256dh_key="key2",
                auth_key="auth2",
                created_at=datetime.utcnow(),
            ),
        ]
        mock_repository.get_push_subscriptions.return_value = subscriptions

        preferences = NotificationPreferences(
            user_id=user_id,
            push_enabled=True,
            updated_at=datetime.utcnow(),
        )

        await notification_service._route_to_channels(
            notification,
            [NotificationChannel.PUSH],
            preferences,
        )

        # Should call push client for each subscription
        assert mock_push_client.send_push_notification.call_count == 2

    @pytest.mark.asyncio
    async def test_route_to_channels_handles_client_errors(
        self, notification_service, mock_email_client
    ):
        """Test that errors from channel clients are caught and logged."""
        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority=NotificationPriority.INFO,
            title="Signal",
            message="New signal",
            metadata={},
            user_id=uuid4(),
            read=False,
            created_at=datetime.utcnow(),
        )

        preferences = NotificationPreferences(
            user_id=uuid4(),
            email_enabled=True,
            email_address="test@example.com",
            updated_at=datetime.utcnow(),
        )

        # Make email client raise an error
        mock_email_client.send_notification_email.side_effect = Exception("SMTP connection failed")

        # Should not raise - errors are caught and logged
        await notification_service._route_to_channels(
            notification,
            [NotificationChannel.EMAIL],
            preferences,
        )

        # Email client was called
        mock_email_client.send_notification_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_push_deletes_expired_subscriptions(
        self, notification_service, mock_push_client, mock_repository
    ):
        """Test that expired push subscriptions (410 Gone) are deleted."""
        user_id = uuid4()
        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority=NotificationPriority.INFO,
            title="Signal",
            message="New signal",
            metadata={},
            user_id=user_id,
            read=False,
            created_at=datetime.utcnow(),
        )

        # Mock push subscription
        from src.models.notification import PushSubscription

        subscription = PushSubscription(
            user_id=user_id,
            endpoint="https://fcm.googleapis.com/fcm/send/expired",
            p256dh_key="key1",
            auth_key="auth1",
            created_at=datetime.utcnow(),
        )
        mock_repository.get_push_subscriptions.return_value = [subscription]

        # Make push client raise 410 error
        mock_push_client.send_push_notification.side_effect = Exception("410 Gone")

        await notification_service._send_push(notification, user_id)

        # Should delete expired subscription
        mock_repository.delete_push_subscription.assert_called_once_with(
            user_id=user_id,
            endpoint=subscription.endpoint,
        )

    # =============================
    # Default Preferences
    # =============================

    @pytest.mark.asyncio
    async def test_send_notification_uses_defaults_when_no_preferences(
        self, notification_service, mock_repository
    ):
        """Test that default preferences are used when user has no preferences set."""
        user_id = uuid4()
        mock_repository.get_preferences.return_value = None  # No preferences

        # Mock notification creation
        created_notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority=NotificationPriority.INFO,
            title="Signal",
            message="New signal",
            metadata={"confidence": 90},
            user_id=user_id,
            read=False,
            created_at=datetime.utcnow(),
        )
        mock_repository.create_notification.return_value = created_notification

        result = await notification_service.send_notification(
            user_id=user_id,
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority=NotificationPriority.INFO,
            title="Signal",
            message="New signal",
            metadata={"confidence": 90},
        )

        # Should create notification with defaults
        assert result is not None
        mock_repository.create_notification.assert_called_once()

    # =============================
    # End-to-End Flow
    # =============================

    @pytest.mark.asyncio
    async def test_send_notification_complete_flow(
        self,
        notification_service,
        mock_repository,
        mock_email_client,
        mock_twilio_client,
    ):
        """Test complete notification flow from filtering to channel delivery."""
        user_id = uuid4()

        # Set up preferences
        preferences = NotificationPreferences(
            user_id=user_id,
            email_enabled=True,
            email_address="test@example.com",
            sms_enabled=True,
            sms_phone_number="+11234567890",
            min_confidence_threshold=85,
            channel_preferences=ChannelPreferences(
                warning_channels=[
                    NotificationChannel.TOAST,
                    NotificationChannel.EMAIL,
                    NotificationChannel.SMS,
                ],
            ),
            updated_at=datetime.utcnow(),
        )
        mock_repository.get_preferences.return_value = preferences

        # Mock notification creation
        created_notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.RISK_WARNING,
            priority=NotificationPriority.WARNING,
            title="Risk Warning",
            message="Portfolio risk exceeded threshold",
            metadata={"risk_level": "high"},
            user_id=user_id,
            read=False,
            created_at=datetime.utcnow(),
        )
        mock_repository.create_notification.return_value = created_notification

        # Send notification
        result = await notification_service.send_notification(
            user_id=user_id,
            notification_type=NotificationType.RISK_WARNING,
            priority=NotificationPriority.WARNING,
            title="Risk Warning",
            message="Portfolio risk exceeded threshold",
            metadata={"risk_level": "high"},
        )

        # Verify notification was created
        assert result is not None
        assert result.id == created_notification.id
        mock_repository.create_notification.assert_called_once()

        # Verify email was sent
        mock_email_client.send_notification_email.assert_called_once_with(
            to_address="test@example.com",
            notification=created_notification,
        )

        # Verify SMS was sent
        mock_twilio_client.send_sms.assert_called_once()
        sms_args = mock_twilio_client.send_sms.call_args[1]
        assert sms_args["phone_number"] == "+11234567890"
        assert "Risk Warning" in sms_args["message"]
