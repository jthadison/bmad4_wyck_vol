"""
Unit Tests for EmailClient

Tests email delivery functionality including:
- SMTP operations with mocks
- Template rendering (HTML/text)
- Retry logic with exponential backoff
- Test mode behavior
- MIME message construction
- PII masking

Story: 11.6 - Notification & Alert System
"""

from datetime import datetime
from email.mime.multipart import MIMEMultipart
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from src.models.notification import (
    Notification,
    NotificationPriority,
    NotificationType,
)
from src.notifications.email_client import EmailClient


class TestEmailClientInit:
    """Tests for EmailClient initialization."""

    def test_init_with_credentials(self):
        """Test initialization with all SMTP credentials."""
        client = EmailClient(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="user@example.com",
            smtp_password="secret123",
            from_email="noreply@example.com",
            test_mode=False,
        )

        assert client.smtp_host == "smtp.example.com"
        assert client.smtp_port == 587
        assert client.smtp_user == "user@example.com"
        assert client.smtp_password == "secret123"
        assert client.from_email == "noreply@example.com"
        assert client.test_mode is False

    def test_init_missing_credentials_enables_test_mode(self):
        """Test that missing credentials auto-enable test mode."""
        client = EmailClient(
            smtp_host="smtp.example.com",
            smtp_port=587,
            # Missing smtp_user, smtp_password, from_email
            test_mode=False,
        )

        assert client.test_mode is True

    def test_init_explicit_test_mode(self):
        """Test explicit test mode enabling."""
        client = EmailClient(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="user@example.com",
            smtp_password="secret123",
            from_email="noreply@example.com",
            test_mode=True,
        )

        assert client.test_mode is True

    def test_init_default_port(self):
        """Test default SMTP port is 587."""
        client = EmailClient(test_mode=True)
        assert client.smtp_port == 587

    def test_jinja_environment_created(self):
        """Test Jinja2 environment is initialized."""
        client = EmailClient(test_mode=True)

        assert client.jinja_env is not None
        assert hasattr(client.jinja_env, "get_template")


class TestEmailClientSendEmail:
    """Tests for send_email method."""

    @pytest.fixture
    def email_client(self):
        """Create email client with credentials for testing."""
        return EmailClient(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="user@example.com",
            smtp_password="secret123",
            from_email="noreply@example.com",
            test_mode=False,
        )

    @pytest.fixture
    def test_mode_client(self):
        """Create email client in test mode."""
        return EmailClient(test_mode=True)

    @pytest.mark.asyncio
    async def test_send_email_test_mode_returns_true(self, test_mode_client):
        """Test that send_email returns True in test mode without sending."""
        result = await test_mode_client.send_email(
            to_address="recipient@example.com",
            subject="Test Subject",
            body_html="<h1>Hello</h1>",
            body_text="Hello",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_email_success(self, email_client):
        """Test successful email sending via SMTP."""
        with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            result = await email_client.send_email(
                to_address="recipient@example.com",
                subject="Test Subject",
                body_html="<h1>Hello</h1>",
                body_text="Hello",
            )

            assert result is True
            mock_send.assert_called_once()

            # Verify the message structure
            call_args = mock_send.call_args
            message = call_args[0][0]
            assert isinstance(message, MIMEMultipart)
            assert message["Subject"] == "Test Subject"
            assert message["From"] == "noreply@example.com"
            assert message["To"] == "recipient@example.com"

    @pytest.mark.asyncio
    async def test_send_email_retry_on_failure(self, email_client):
        """Test retry logic with exponential backoff."""
        with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            # Fail twice, succeed on third attempt
            mock_send.side_effect = [
                Exception("Connection failed"),
                Exception("Connection failed"),
                None,
            ]

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                result = await email_client.send_email(
                    to_address="recipient@example.com",
                    subject="Test",
                    body_html="<p>Test</p>",
                    body_text="Test",
                )

                assert result is True
                assert mock_send.call_count == 3
                # Check exponential backoff (1s, 2s)
                assert mock_sleep.call_count == 2
                mock_sleep.assert_any_call(1)  # 2^0
                mock_sleep.assert_any_call(2)  # 2^1

    @pytest.mark.asyncio
    async def test_send_email_all_retries_fail(self, email_client):
        """Test that send_email returns False after all retries fail."""
        with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = Exception("Connection failed")

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await email_client.send_email(
                    to_address="recipient@example.com",
                    subject="Test",
                    body_html="<p>Test</p>",
                    body_text="Test",
                )

                assert result is False
                assert mock_send.call_count == 3  # Max retries


class TestEmailClientSendNotificationEmail:
    """Tests for send_notification_email method."""

    @pytest.fixture
    def test_client(self):
        """Create email client in test mode."""
        return EmailClient(test_mode=True)

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
    async def test_send_notification_email_signal(self, test_client, sample_notification):
        """Test sending notification email for signal."""
        result = await test_client.send_notification_email(
            to_address="trader@example.com",
            notification=sample_notification,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_notification_email_risk_warning(self, test_client):
        """Test sending notification email for risk warning."""
        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.RISK_WARNING,
            priority=NotificationPriority.WARNING,
            title="Portfolio Risk Alert",
            message="Portfolio heat exceeds 8%",
            metadata={"portfolio_heat": 8.5, "max_heat": 10.0},
            user_id=uuid4(),
            read=False,
            created_at=datetime.utcnow(),
        )

        result = await test_client.send_notification_email(
            to_address="trader@example.com",
            notification=notification,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_notification_email_emergency_exit(self, test_client):
        """Test sending notification email for emergency exit."""
        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.EMERGENCY_EXIT,
            priority=NotificationPriority.CRITICAL,
            title="Emergency Exit Triggered",
            message="AAPL position closed at stop loss",
            metadata={"symbol": "AAPL", "exit_price": 149.50, "loss": -150.00},
            user_id=uuid4(),
            read=False,
            created_at=datetime.utcnow(),
        )

        result = await test_client.send_notification_email(
            to_address="trader@example.com",
            notification=notification,
        )

        assert result is True


class TestEmailClientSubjectGeneration:
    """Tests for _get_subject method."""

    @pytest.fixture
    def client(self):
        """Create email client."""
        return EmailClient(test_mode=True)

    def test_subject_signal_generated(self, client):
        """Test subject for signal generated notification."""
        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority=NotificationPriority.WARNING,
            title="New Signal",
            message="Test message",
            metadata={"symbol": "AAPL"},
            user_id=uuid4(),
            read=False,
            created_at=datetime.utcnow(),
        )

        subject = client._get_subject(notification)
        assert subject == "New Signal: AAPL"

    def test_subject_signal_generated_no_symbol(self, client):
        """Test subject for signal without symbol in metadata."""
        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority=NotificationPriority.WARNING,
            title="New Signal",
            message="Test message",
            metadata={},
            user_id=uuid4(),
            read=False,
            created_at=datetime.utcnow(),
        )

        subject = client._get_subject(notification)
        assert subject == "New Signal: "

    def test_subject_risk_warning(self, client):
        """Test subject for risk warning notification."""
        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.RISK_WARNING,
            priority=NotificationPriority.WARNING,
            title="Risk Alert",
            message="Test message",
            metadata={},
            user_id=uuid4(),
            read=False,
            created_at=datetime.utcnow(),
        )

        subject = client._get_subject(notification)
        assert subject == "Risk Warning Alert"

    def test_subject_emergency_exit(self, client):
        """Test subject for emergency exit notification."""
        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.EMERGENCY_EXIT,
            priority=NotificationPriority.CRITICAL,
            title="Emergency",
            message="Test message",
            metadata={},
            user_id=uuid4(),
            read=False,
            created_at=datetime.utcnow(),
        )

        subject = client._get_subject(notification)
        assert subject == "URGENT: Emergency Exit Triggered"

    def test_subject_system_error(self, client):
        """Test subject for system error notification."""
        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.SYSTEM_ERROR,
            priority=NotificationPriority.CRITICAL,
            title="System Error",
            message="Test message",
            metadata={},
            user_id=uuid4(),
            read=False,
            created_at=datetime.utcnow(),
        )

        subject = client._get_subject(notification)
        assert subject == "System Error Notification"


class TestEmailClientTemplateRendering:
    """Tests for template rendering methods."""

    @pytest.fixture
    def client(self):
        """Create email client."""
        return EmailClient(test_mode=True)

    @pytest.fixture
    def sample_notification(self):
        """Create sample notification."""
        return Notification(
            id=uuid4(),
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority=NotificationPriority.WARNING,
            title="Trading Signal Alert",
            message="AAPL Spring pattern detected",
            metadata={"symbol": "AAPL"},
            user_id=uuid4(),
            read=False,
            created_at=datetime.utcnow(),
        )

    def test_render_generic_html_info_priority(self, client):
        """Test HTML rendering with info priority color."""
        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority=NotificationPriority.INFO,
            title="Info Alert",
            message="Test message",
            metadata={},
            user_id=uuid4(),
            read=False,
            created_at=datetime.utcnow(),
        )

        html = client._render_generic_html(notification)

        assert "Info Alert" in html
        assert "Test message" in html
        assert "#4299e1" in html  # Info color (blue)

    def test_render_generic_html_warning_priority(self, client):
        """Test HTML rendering with warning priority color."""
        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.RISK_WARNING,
            priority=NotificationPriority.WARNING,
            title="Warning Alert",
            message="Test message",
            metadata={},
            user_id=uuid4(),
            read=False,
            created_at=datetime.utcnow(),
        )

        html = client._render_generic_html(notification)

        assert "Warning Alert" in html
        assert "#ed8936" in html  # Warning color (orange)

    def test_render_generic_html_critical_priority(self, client):
        """Test HTML rendering with critical priority color."""
        notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.EMERGENCY_EXIT,
            priority=NotificationPriority.CRITICAL,
            title="Critical Alert",
            message="Test message",
            metadata={},
            user_id=uuid4(),
            read=False,
            created_at=datetime.utcnow(),
        )

        html = client._render_generic_html(notification)

        assert "Critical Alert" in html
        assert "#f56565" in html  # Critical color (red)

    def test_render_text_template(self, client, sample_notification):
        """Test plain text template rendering."""
        text = client._render_text_template(sample_notification)

        assert "Trading Signal Alert" in text
        assert "AAPL Spring pattern detected" in text
        assert "WARNING" in text
        assert "Signal Generated" in text
        assert "BMAD Wyckoff Trading System" in text

    def test_render_html_fallback_to_generic(self, client, sample_notification):
        """Test HTML rendering falls back to generic when template not found."""
        # This should use generic template since specific template doesn't exist
        html = client._render_html_template(sample_notification)

        assert "Trading Signal Alert" in html
        assert "<html>" in html
        assert "</html>" in html


class TestEmailClientSendTestEmail:
    """Tests for send_test_email method."""

    @pytest.fixture
    def client(self):
        """Create email client in test mode."""
        return EmailClient(test_mode=True)

    @pytest.mark.asyncio
    async def test_send_test_email_success(self, client):
        """Test sending test email."""
        result = await client.send_test_email("test@example.com")

        assert result is True

    @pytest.mark.asyncio
    async def test_send_test_email_content(self, client):
        """Test that test email has correct content."""
        # Override send_email to capture arguments
        captured_args = {}

        async def capture_send(*args, **kwargs):
            captured_args.update(kwargs)
            return True

        client.send_email = capture_send

        await client.send_test_email("test@example.com")

        assert "BMAD Wyckoff: Test Notification" in captured_args.get("subject", "")
        assert "Email Notifications Configured" in captured_args.get("body_html", "")
        assert "Email Notifications Configured" in captured_args.get("body_text", "")


class TestEmailClientPIIMasking:
    """Tests for PII masking methods."""

    @pytest.fixture
    def client(self):
        """Create email client."""
        return EmailClient(test_mode=True)

    def test_mask_email_long_user(self, client):
        """Test email masking with long username."""
        masked = client._mask_email("johndoe@example.com")
        assert masked == "jo***@example.com"

    def test_mask_email_short_user(self, client):
        """Test email masking with short username (3 chars or less)."""
        masked = client._mask_email("joe@example.com")
        # When user is exactly 3 chars, it gets masked to "***"
        assert masked == "***@example.com"

    def test_mask_email_very_short_user(self, client):
        """Test email masking with very short username."""
        masked = client._mask_email("ab@example.com")
        assert masked == "***@example.com"

    def test_mask_email_single_char_user(self, client):
        """Test email masking with single character username."""
        masked = client._mask_email("a@example.com")
        assert masked == "***@example.com"

    def test_mask_email_no_at_symbol(self, client):
        """Test email masking with invalid email (no @ symbol)."""
        masked = client._mask_email("notanemail")
        assert masked == "***"

    def test_mask_email_empty_string(self, client):
        """Test email masking with empty string."""
        masked = client._mask_email("")
        assert masked == "***"
