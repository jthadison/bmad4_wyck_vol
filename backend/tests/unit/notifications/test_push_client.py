"""
Unit Tests for PushClient

Tests Web Push notification functionality including:
- VAPID authentication
- Payload creation
- Subscription handling
- 410 Gone (expired subscription) handling
- Test mode behavior
- PII masking
- Key generation and persistence

Story: 11.6 - Notification & Alert System
"""

import json
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from src.models.notification import (
    Notification,
    NotificationPriority,
    NotificationType,
    PushSubscription,
)
from src.notifications.push_client import PushClient


class TestPushClientInit:
    """Tests for PushClient initialization."""

    def test_init_with_credentials(self):
        """Test initialization with VAPID credentials."""
        client = PushClient(
            vapid_private_key="test_private_key",
            vapid_claims_email="mailto:admin@example.com",
            test_mode=False,
        )

        assert client.vapid_private_key == "test_private_key"
        assert client.vapid_claims_email == "mailto:admin@example.com"
        assert client.test_mode is False

    def test_init_missing_credentials_enables_test_mode(self):
        """Test that missing VAPID credentials auto-enable test mode."""
        client = PushClient(
            vapid_private_key="test_private_key",
            # Missing vapid_claims_email
            test_mode=False,
        )

        assert client.test_mode is True

    def test_init_explicit_test_mode(self):
        """Test explicit test mode enabling."""
        client = PushClient(
            vapid_private_key="test_private_key",
            vapid_claims_email="mailto:admin@example.com",
            test_mode=True,
        )

        assert client.test_mode is True

    def test_init_no_credentials(self):
        """Test initialization with no credentials defaults to test mode."""
        client = PushClient()

        assert client.test_mode is True


class TestPushClientSendPushNotification:
    """Tests for send_push_notification method."""

    @pytest.fixture
    def push_client(self):
        """Create push client with credentials for testing."""
        return PushClient(
            vapid_private_key="test_private_key",
            vapid_claims_email="mailto:admin@example.com",
            test_mode=False,
        )

    @pytest.fixture
    def test_mode_client(self):
        """Create push client in test mode."""
        return PushClient(test_mode=True)

    @pytest.fixture
    def sample_subscription(self):
        """Create sample push subscription."""
        return PushSubscription(
            user_id=uuid4(),
            endpoint="https://fcm.googleapis.com/fcm/send/abc123xyz",
            p256dh_key="BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM",
            auth_key="tBHItJI5svbpez7KI4CCXg",
            created_at=datetime.utcnow(),
        )

    @pytest.fixture
    def sample_notification(self):
        """Create sample notification for testing."""
        return Notification(
            id=uuid4(),
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority=NotificationPriority.WARNING,
            title="New Trading Signal",
            message="AAPL Spring pattern detected with 87% confidence",
            metadata={"symbol": "AAPL", "pattern": "Spring", "confidence": 87},
            user_id=uuid4(),
            read=False,
            created_at=datetime.utcnow(),
        )

    @pytest.mark.asyncio
    async def test_send_push_notification_test_mode_returns_true(
        self, test_mode_client, sample_subscription, sample_notification
    ):
        """Test that send_push_notification returns True in test mode without sending."""
        result = await test_mode_client.send_push_notification(
            subscription=sample_subscription,
            notification=sample_notification,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_push_notification_success(
        self, push_client, sample_subscription, sample_notification
    ):
        """Test successful push notification sending."""
        with patch("pywebpush.webpush") as mock_webpush:
            mock_webpush.return_value = None

            result = await push_client.send_push_notification(
                subscription=sample_subscription,
                notification=sample_notification,
            )

            assert result is True
            mock_webpush.assert_called_once()

            # Verify call arguments
            call_kwargs = mock_webpush.call_args[1]
            assert call_kwargs["subscription_info"]["endpoint"] == sample_subscription.endpoint
            assert call_kwargs["vapid_private_key"] == "test_private_key"
            assert call_kwargs["vapid_claims"]["sub"] == "mailto:admin@example.com"

    @pytest.mark.asyncio
    async def test_send_push_notification_failure(
        self, push_client, sample_subscription, sample_notification
    ):
        """Test push notification failure returns False."""
        with patch("pywebpush.webpush") as mock_webpush:
            mock_webpush.side_effect = Exception("Network error")

            result = await push_client.send_push_notification(
                subscription=sample_subscription,
                notification=sample_notification,
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_send_push_notification_expired_subscription_raises(
        self, push_client, sample_subscription, sample_notification
    ):
        """Test that 410 Gone error is re-raised for caller to handle."""
        with patch("pywebpush.webpush") as mock_webpush:
            mock_webpush.side_effect = Exception("Push failed: 410 Gone")

            with pytest.raises(Exception) as exc_info:
                await push_client.send_push_notification(
                    subscription=sample_subscription,
                    notification=sample_notification,
                )

            assert "410" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_send_push_notification_non_410_error_returns_false(
        self, push_client, sample_subscription, sample_notification
    ):
        """Test that non-410 errors return False (not raising).

        This verifies the distinction between 410 Gone errors (which are re-raised
        for the caller to handle subscription cleanup) and other errors (which
        return False to indicate delivery failure).
        """
        with patch("pywebpush.webpush") as mock_webpush:
            # Simulate a non-410 error (e.g., network timeout, 500 server error)
            mock_webpush.side_effect = Exception("Push failed: 500 Internal Server Error")

            result = await push_client.send_push_notification(
                subscription=sample_subscription,
                notification=sample_notification,
            )

            # Non-410 errors should return False, not raise
            assert result is False


class TestPushClientSendTestPush:
    """Tests for send_test_push method."""

    @pytest.fixture
    def client(self):
        """Create push client in test mode."""
        return PushClient(test_mode=True)

    @pytest.fixture
    def sample_subscription(self):
        """Create sample push subscription."""
        return PushSubscription(
            user_id=uuid4(),
            endpoint="https://fcm.googleapis.com/fcm/send/abc123xyz",
            p256dh_key="BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM",
            auth_key="tBHItJI5svbpez7KI4CCXg",
            created_at=datetime.utcnow(),
        )

    @pytest.mark.asyncio
    async def test_send_test_push_success(self, client, sample_subscription):
        """Test sending test push notification."""
        result = await client.send_test_push(sample_subscription)

        assert result is True

    @pytest.mark.asyncio
    async def test_send_test_push_creates_notification(self, client, sample_subscription):
        """Test that test push creates appropriate notification."""
        captured_notification = None

        async def capture_send(subscription, notification):
            nonlocal captured_notification
            captured_notification = notification
            return True

        client.send_push_notification = capture_send

        await client.send_test_push(sample_subscription)

        assert captured_notification is not None
        assert captured_notification.title == "Test Push Notification"
        assert "configured correctly" in captured_notification.message
        assert captured_notification.notification_type == NotificationType.SYSTEM_ERROR


class TestPushClientPayloadCreation:
    """Tests for _create_payload method."""

    @pytest.fixture
    def client(self):
        """Create push client."""
        return PushClient(test_mode=True)

    def test_create_payload_basic_structure(self, client):
        """Test payload has required Web Push fields."""
        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.RISK_WARNING,
            priority=NotificationPriority.WARNING,
            title="Risk Alert",
            message="Portfolio heat is high",
            metadata={},
            user_id=uuid4(),
            read=False,
            created_at=datetime.utcnow(),
        )

        payload = client._create_payload(notification)

        assert payload["title"] == "Risk Alert"
        assert payload["body"] == "Portfolio heat is high"
        assert payload["icon"] == "/static/icon-192.png"
        assert payload["badge"] == "/static/badge-72.png"
        assert "tag" in payload
        assert "data" in payload

    def test_create_payload_critical_requires_interaction(self, client):
        """Test that critical notifications require interaction.

        Note: The payload creation code compares priority == "CRITICAL" as a string.
        This works because NotificationPriority inherits from (str, Enum), making
        the enum value directly comparable to strings without calling .value.
        """
        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.EMERGENCY_EXIT,
            priority=NotificationPriority.CRITICAL,
            title="Emergency",
            message="Emergency exit triggered",
            metadata={},
            user_id=uuid4(),
            read=False,
            created_at=datetime.utcnow(),
        )

        payload = client._create_payload(notification)

        assert payload["requireInteraction"] is True

    def test_create_payload_non_critical_no_require_interaction(self, client):
        """Test that non-critical notifications don't require interaction."""
        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority=NotificationPriority.INFO,
            title="Signal",
            message="New signal detected",
            metadata={},
            user_id=uuid4(),
            read=False,
            created_at=datetime.utcnow(),
        )

        payload = client._create_payload(notification)

        assert payload["requireInteraction"] is False

    def test_create_payload_signal_has_action_buttons(self, client):
        """Test that signal notifications have action buttons."""
        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority=NotificationPriority.WARNING,
            title="New Signal",
            message="AAPL Spring detected",
            metadata={"symbol": "AAPL"},
            user_id=uuid4(),
            read=False,
            created_at=datetime.utcnow(),
        )

        payload = client._create_payload(notification)

        assert "actions" in payload
        assert len(payload["actions"]) == 2
        assert payload["actions"][0]["action"] == "view"
        assert payload["actions"][1]["action"] == "dismiss"

    def test_create_payload_non_signal_no_action_buttons(self, client):
        """Test that non-signal notifications don't have action buttons."""
        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.RISK_WARNING,
            priority=NotificationPriority.WARNING,
            title="Risk Warning",
            message="High portfolio heat",
            metadata={},
            user_id=uuid4(),
            read=False,
            created_at=datetime.utcnow(),
        )

        payload = client._create_payload(notification)

        assert "actions" not in payload

    def test_create_payload_data_contains_metadata(self, client):
        """Test that payload data contains notification metadata."""
        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority=NotificationPriority.WARNING,
            title="Signal",
            message="Signal detected",
            metadata={"symbol": "AAPL", "confidence": 87},
            user_id=uuid4(),
            read=False,
            created_at=datetime.utcnow(),
        )

        payload = client._create_payload(notification)

        data = payload["data"]
        assert str(notification.id) == data["notification_id"]
        assert notification.notification_type.value == data["notification_type"]
        assert data["metadata"]["symbol"] == "AAPL"
        assert data["metadata"]["confidence"] == 87


class TestPushClientEndpointMasking:
    """Tests for _mask_endpoint method."""

    @pytest.fixture
    def client(self):
        """Create push client."""
        return PushClient(test_mode=True)

    def test_mask_endpoint_long(self, client):
        """Test endpoint masking with long URL."""
        endpoint = "https://fcm.googleapis.com/fcm/send/abc123xyzdef456ghijkl789mnopqrs"
        masked = client._mask_endpoint(endpoint)

        # Masking format: first 20 chars + "..." + last 10 chars
        assert masked.startswith("https://fcm.googleap")
        assert masked.endswith("89mnopqrs")
        assert "..." in masked

    def test_mask_endpoint_short(self, client):
        """Test endpoint masking with short URL."""
        endpoint = "https://short.com/abc"
        masked = client._mask_endpoint(endpoint)

        # Short endpoints returned as-is
        assert masked == endpoint

    def test_mask_endpoint_exactly_40_chars(self, client):
        """Test endpoint masking at boundary (40 chars)."""
        endpoint = "a" * 40
        masked = client._mask_endpoint(endpoint)

        # Exactly 40 chars returned as-is
        assert masked == endpoint

    def test_mask_endpoint_just_over_40_chars(self, client):
        """Test endpoint masking just over boundary."""
        endpoint = "a" * 41
        masked = client._mask_endpoint(endpoint)

        # Should be masked
        assert "..." in masked


class TestPushClientVAPIDKeyManagement:
    """Tests for VAPID key generation and persistence."""

    def test_generate_vapid_keys(self):
        """Test VAPID key generation."""
        with patch("py_vapid.Vapid") as mock_vapid_class:
            mock_vapid = MagicMock()
            mock_private_key = MagicMock()
            mock_public_key = MagicMock()
            mock_private_key.to_string.return_value = b"private_key_string"
            mock_public_key.to_string.return_value = b"public_key_string"
            mock_vapid.private_key = mock_private_key
            mock_vapid.public_key = mock_public_key
            mock_vapid_class.return_value = mock_vapid

            private_key, public_key = PushClient.generate_vapid_keys()

            mock_vapid.generate_keys.assert_called_once()
            assert private_key == "private_key_string"
            assert public_key == "public_key_string"

    def test_save_vapid_keys(self):
        """Test VAPID key saving to file."""
        with TemporaryDirectory() as tmpdir:
            file_path = str(Path(tmpdir) / "vapid_keys.json")

            PushClient.save_vapid_keys(
                private_key="test_private",
                public_key="test_public",
                file_path=file_path,
            )

            # Verify file was created and contains correct data
            with open(file_path) as f:
                data = json.load(f)

            assert data["private_key"] == "test_private"
            assert data["public_key"] == "test_public"

    def test_load_vapid_keys(self):
        """Test VAPID key loading from file."""
        with TemporaryDirectory() as tmpdir:
            file_path = str(Path(tmpdir) / "vapid_keys.json")

            # Write test keys
            with open(file_path, "w") as f:
                json.dump(
                    {"private_key": "loaded_private", "public_key": "loaded_public"},
                    f,
                )

            private_key, public_key = PushClient.load_vapid_keys(file_path)

            assert private_key == "loaded_private"
            assert public_key == "loaded_public"

    def test_load_vapid_keys_file_not_found(self):
        """Test loading from non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            PushClient.load_vapid_keys("nonexistent_file.json")


class TestPushClientEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def client(self):
        """Create push client."""
        return PushClient(
            vapid_private_key="test_private_key",
            vapid_claims_email="mailto:admin@example.com",
            test_mode=False,
        )

    @pytest.fixture
    def sample_subscription(self):
        """Create sample push subscription."""
        return PushSubscription(
            user_id=uuid4(),
            endpoint="https://fcm.googleapis.com/fcm/send/abc123xyz",
            p256dh_key="BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM",
            auth_key="tBHItJI5svbpez7KI4CCXg",
            created_at=datetime.utcnow(),
        )

    @pytest.mark.asyncio
    async def test_send_notification_with_empty_metadata(self, client, sample_subscription):
        """Test sending notification with empty metadata."""
        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.SYSTEM_ERROR,
            priority=NotificationPriority.INFO,
            title="System Notice",
            message="System message",
            metadata={},
            user_id=uuid4(),
            read=False,
            created_at=datetime.utcnow(),
        )

        with patch("pywebpush.webpush") as mock_webpush:
            mock_webpush.return_value = None

            result = await client.send_push_notification(
                subscription=sample_subscription,
                notification=notification,
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_send_notification_with_large_metadata(self, client, sample_subscription):
        """Test sending notification with large metadata."""
        large_metadata = {f"key_{i}": f"value_{i}" for i in range(100)}

        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority=NotificationPriority.WARNING,
            title="Signal",
            message="Signal with large metadata",
            metadata=large_metadata,
            user_id=uuid4(),
            read=False,
            created_at=datetime.utcnow(),
        )

        with patch("pywebpush.webpush") as mock_webpush:
            mock_webpush.return_value = None

            result = await client.send_push_notification(
                subscription=sample_subscription,
                notification=notification,
            )

            assert result is True

            # Verify metadata was included in payload
            call_args = mock_webpush.call_args
            payload = json.loads(call_args[1]["data"])
            assert len(payload["data"]["metadata"]) == 100

    @pytest.mark.asyncio
    async def test_send_notification_webpush_not_installed(self, client, sample_subscription):
        """Test graceful handling when pywebpush not installed."""
        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.SYSTEM_ERROR,
            priority=NotificationPriority.INFO,
            title="Test",
            message="Test message",
            metadata={},
            user_id=uuid4(),
            read=False,
            created_at=datetime.utcnow(),
        )

        with patch("pywebpush.webpush") as mock_webpush:
            mock_webpush.side_effect = ImportError("pywebpush not installed")

            result = await client.send_push_notification(
                subscription=sample_subscription,
                notification=notification,
            )

            assert result is False
