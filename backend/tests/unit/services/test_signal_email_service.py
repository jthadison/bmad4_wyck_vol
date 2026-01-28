"""
Unit tests for Signal Email Notification Service (Story 19.25).

Tests:
- Email filtering by confidence grade
- Rate limiting enforcement
- Email content generation
- Service initialization
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.models.notification import (
    EmailNotificationSettings,
    SignalEmailData,
    SignalNotification,
)
from src.notifications.rate_limiter import EmailRateLimiter
from src.services.signal_email_service import (
    EmailSendStatus,
    SignalEmailService,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_email_client():
    """Create mock email client."""
    client = AsyncMock()
    client.send_email = AsyncMock(return_value=True)
    return client


@pytest.fixture
def rate_limiter():
    """Create rate limiter with 10/hour limit."""
    return EmailRateLimiter(max_per_hour=10)


@pytest.fixture
def signal_email_service(mock_email_client, rate_limiter):
    """Create SignalEmailService with mocked dependencies."""
    return SignalEmailService(
        email_client=mock_email_client,
        rate_limiter=rate_limiter,
    )


@pytest.fixture
def sample_signal():
    """Create sample signal notification."""
    return SignalNotification(
        signal_id=uuid4(),
        timestamp=datetime.now(UTC),
        symbol="AAPL",
        pattern_type="SPRING",
        confidence_score=92,
        confidence_grade="A+",
        entry_price="150.25",
        stop_loss="149.50",
        target_price="152.75",
        risk_amount="75.00",
        risk_percentage=1.5,
        r_multiple=3.33,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )


@pytest.fixture
def enabled_email_settings():
    """Create enabled email notification settings."""
    return EmailNotificationSettings(
        email_enabled=True,
        email_address="trader@example.com",
        notify_all_signals=False,  # High confidence only
        notify_auto_executions=True,
        notify_circuit_breaker=True,
    )


@pytest.fixture
def disabled_email_settings():
    """Create disabled email notification settings."""
    return EmailNotificationSettings(
        email_enabled=False,
        email_address="trader@example.com",
    )


# ============================================================================
# Rate Limiter Tests
# ============================================================================


class TestEmailRateLimiter:
    """Tests for EmailRateLimiter."""

    def test_initial_can_send(self, rate_limiter):
        """Test that user can send when no emails sent yet."""
        user_id = uuid4()
        assert rate_limiter.can_send(user_id) is True

    def test_can_send_under_limit(self, rate_limiter):
        """Test that user can send when under the limit."""
        user_id = uuid4()

        # Send 9 emails (under limit of 10)
        for _ in range(9):
            rate_limiter.record_send(user_id)

        assert rate_limiter.can_send(user_id) is True

    def test_cannot_send_at_limit(self, rate_limiter):
        """Test that user cannot send when at the limit."""
        user_id = uuid4()

        # Send 10 emails (at limit)
        for _ in range(10):
            rate_limiter.record_send(user_id)

        assert rate_limiter.can_send(user_id) is False

    def test_get_remaining_initial(self, rate_limiter):
        """Test remaining count for new user."""
        user_id = uuid4()
        assert rate_limiter.get_remaining(user_id) == 10

    def test_get_remaining_after_sends(self, rate_limiter):
        """Test remaining count after sending."""
        user_id = uuid4()

        for _ in range(3):
            rate_limiter.record_send(user_id)

        assert rate_limiter.get_remaining(user_id) == 7

    def test_get_remaining_at_limit(self, rate_limiter):
        """Test remaining count at limit."""
        user_id = uuid4()

        for _ in range(10):
            rate_limiter.record_send(user_id)

        assert rate_limiter.get_remaining(user_id) == 0

    def test_reset_single_user(self, rate_limiter):
        """Test resetting rate limit for single user."""
        user_id = uuid4()

        for _ in range(5):
            rate_limiter.record_send(user_id)

        rate_limiter.reset(user_id)
        assert rate_limiter.get_remaining(user_id) == 10

    def test_reset_all_users(self, rate_limiter):
        """Test resetting rate limits for all users."""
        user1 = uuid4()
        user2 = uuid4()

        rate_limiter.record_send(user1)
        rate_limiter.record_send(user2)

        rate_limiter.reset()

        assert rate_limiter.get_remaining(user1) == 10
        assert rate_limiter.get_remaining(user2) == 10

    def test_different_users_independent(self, rate_limiter):
        """Test that rate limits are independent per user."""
        user1 = uuid4()
        user2 = uuid4()

        # User 1 sends 10 emails
        for _ in range(10):
            rate_limiter.record_send(user1)

        # User 2 should still be able to send
        assert rate_limiter.can_send(user1) is False
        assert rate_limiter.can_send(user2) is True


# ============================================================================
# Signal Email Service Tests
# ============================================================================


class TestSignalEmailService:
    """Tests for SignalEmailService."""

    @pytest.mark.asyncio
    async def test_send_notification_success(
        self,
        signal_email_service,
        sample_signal,
        enabled_email_settings,
        mock_email_client,
    ):
        """Test successful email notification."""
        user_id = uuid4()

        result = await signal_email_service.send_signal_notification(
            user_id=user_id,
            signal=sample_signal,
            preferences=enabled_email_settings,
        )

        assert result.status == EmailSendStatus.SUCCESS
        assert result.user_id == user_id
        assert result.signal_id == sample_signal.signal_id
        mock_email_client.send_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_notification_disabled(
        self,
        signal_email_service,
        sample_signal,
        disabled_email_settings,
        mock_email_client,
    ):
        """Test that notification is skipped when disabled."""
        user_id = uuid4()

        result = await signal_email_service.send_signal_notification(
            user_id=user_id,
            signal=sample_signal,
            preferences=disabled_email_settings,
        )

        assert result.status == EmailSendStatus.DISABLED
        mock_email_client.send_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_notification_filtered_by_confidence(
        self,
        signal_email_service,
        enabled_email_settings,
        mock_email_client,
    ):
        """Test that low-confidence signals are filtered."""
        user_id = uuid4()

        # Create B-grade signal (should be filtered when notify_all_signals=False)
        low_confidence_signal = SignalNotification(
            signal_id=uuid4(),
            timestamp=datetime.now(UTC),
            symbol="AAPL",
            pattern_type="SPRING",
            confidence_score=82,
            confidence_grade="B",  # Not A+ or A
            entry_price="150.25",
            stop_loss="149.50",
            target_price="152.75",
            risk_amount="75.00",
            risk_percentage=1.5,
            r_multiple=3.33,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )

        result = await signal_email_service.send_signal_notification(
            user_id=user_id,
            signal=low_confidence_signal,
            preferences=enabled_email_settings,
        )

        assert result.status == EmailSendStatus.FILTERED
        mock_email_client.send_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_notification_all_signals_enabled(
        self,
        signal_email_service,
        mock_email_client,
    ):
        """Test that all signals are sent when notify_all_signals=True."""
        user_id = uuid4()

        # Create B-grade signal
        low_confidence_signal = SignalNotification(
            signal_id=uuid4(),
            timestamp=datetime.now(UTC),
            symbol="AAPL",
            pattern_type="SPRING",
            confidence_score=82,
            confidence_grade="B",
            entry_price="150.25",
            stop_loss="149.50",
            target_price="152.75",
            risk_amount="75.00",
            risk_percentage=1.5,
            r_multiple=3.33,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )

        # Enable all signals
        settings = EmailNotificationSettings(
            email_enabled=True,
            email_address="trader@example.com",
            notify_all_signals=True,  # Send all signals
        )

        result = await signal_email_service.send_signal_notification(
            user_id=user_id,
            signal=low_confidence_signal,
            preferences=settings,
        )

        assert result.status == EmailSendStatus.SUCCESS
        mock_email_client.send_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_notification_rate_limited(
        self,
        signal_email_service,
        sample_signal,
        enabled_email_settings,
        rate_limiter,
        mock_email_client,
    ):
        """Test that notifications are rate limited."""
        user_id = uuid4()

        # Exhaust rate limit
        for _ in range(10):
            rate_limiter.record_send(user_id)

        result = await signal_email_service.send_signal_notification(
            user_id=user_id,
            signal=sample_signal,
            preferences=enabled_email_settings,
        )

        assert result.status == EmailSendStatus.RATE_LIMITED
        mock_email_client.send_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_notification_no_email_address(
        self,
        signal_email_service,
        sample_signal,
        mock_email_client,
    ):
        """Test failure when no email address configured."""
        user_id = uuid4()

        settings = EmailNotificationSettings(
            email_enabled=True,
            email_address=None,  # No email address
        )

        result = await signal_email_service.send_signal_notification(
            user_id=user_id,
            signal=sample_signal,
            preferences=settings,
        )

        assert result.status == EmailSendStatus.FAILED
        assert "No email address" in result.message
        mock_email_client.send_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_notification_email_failure(
        self,
        signal_email_service,
        sample_signal,
        enabled_email_settings,
        mock_email_client,
    ):
        """Test handling of email delivery failure."""
        user_id = uuid4()
        mock_email_client.send_email.return_value = False

        result = await signal_email_service.send_signal_notification(
            user_id=user_id,
            signal=sample_signal,
            preferences=enabled_email_settings,
        )

        assert result.status == EmailSendStatus.FAILED
        assert "delivery failed" in result.message

    @pytest.mark.asyncio
    async def test_send_notification_email_exception(
        self,
        signal_email_service,
        sample_signal,
        enabled_email_settings,
        mock_email_client,
    ):
        """Test handling of email exception."""
        user_id = uuid4()
        mock_email_client.send_email.side_effect = Exception("SMTP connection failed")

        result = await signal_email_service.send_signal_notification(
            user_id=user_id,
            signal=sample_signal,
            preferences=enabled_email_settings,
        )

        assert result.status == EmailSendStatus.FAILED
        assert "SMTP connection failed" in result.message

    def test_get_rate_limit_remaining(self, signal_email_service, rate_limiter):
        """Test getting remaining rate limit."""
        user_id = uuid4()

        # Send a few emails
        rate_limiter.record_send(user_id)
        rate_limiter.record_send(user_id)

        remaining = signal_email_service.get_rate_limit_remaining(user_id)
        assert remaining == 8

    def test_build_email_data(self, signal_email_service, sample_signal):
        """Test email data building."""
        email_data = signal_email_service._build_email_data(sample_signal)

        assert isinstance(email_data, SignalEmailData)
        assert email_data.signal_id == sample_signal.signal_id
        assert email_data.symbol == sample_signal.symbol
        assert email_data.pattern_type == sample_signal.pattern_type
        assert email_data.confidence_grade == sample_signal.confidence_grade
        assert "approve" in email_data.approve_url
        assert "settings" in email_data.unsubscribe_url

    def test_render_text_template(self, signal_email_service, sample_signal):
        """Test text email rendering."""
        email_data = signal_email_service._build_email_data(sample_signal)
        text = signal_email_service._render_text_template(email_data)

        assert sample_signal.symbol in text
        assert sample_signal.pattern_type in text
        assert str(sample_signal.confidence_score) in text
        assert email_data.entry_price in text
        assert email_data.stop_loss in text
        assert email_data.target_price in text

    def test_render_html_template_fallback(self, signal_email_service, sample_signal):
        """Test HTML email rendering (fallback)."""
        email_data = signal_email_service._build_email_data(sample_signal)
        html = signal_email_service._render_inline_html(email_data)

        assert sample_signal.symbol in html
        assert sample_signal.pattern_type in html
        assert "<!DOCTYPE html>" in html
        assert email_data.approve_url in html
        assert email_data.unsubscribe_url in html


# ============================================================================
# High Confidence Filtering Tests
# ============================================================================


class TestConfidenceFiltering:
    """Tests for confidence grade filtering."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "grade,expected_status",
        [
            ("A+", EmailSendStatus.SUCCESS),
            ("A", EmailSendStatus.SUCCESS),
            ("B", EmailSendStatus.FILTERED),
            ("C", EmailSendStatus.FILTERED),
        ],
    )
    async def test_confidence_filter_grades(
        self,
        signal_email_service,
        enabled_email_settings,
        mock_email_client,
        grade,
        expected_status,
    ):
        """Test filtering by different confidence grades."""
        user_id = uuid4()

        # Map grades to scores
        scores = {"A+": 92, "A": 87, "B": 82, "C": 75}

        signal = SignalNotification(
            signal_id=uuid4(),
            timestamp=datetime.now(UTC),
            symbol="AAPL",
            pattern_type="SPRING",
            confidence_score=scores[grade],
            confidence_grade=grade,
            entry_price="150.25",
            stop_loss="149.50",
            target_price="152.75",
            risk_amount="75.00",
            risk_percentage=1.5,
            r_multiple=3.33,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )

        result = await signal_email_service.send_signal_notification(
            user_id=user_id,
            signal=signal,
            preferences=enabled_email_settings,
        )

        assert result.status == expected_status
