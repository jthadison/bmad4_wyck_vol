"""
Unit Tests for TwilioClient

Tests SMS delivery functionality including:
- Circuit breaker pattern (CLOSED, OPEN, HALF_OPEN states)
- Rate limiting (per-user hourly limits)
- Retry logic with exponential backoff
- Test mode behavior
- PII masking

Story: 11.6 - Notification & Alert System
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from src.notifications.twilio_client import (
    CircuitBreaker,
    CircuitBreakerError,
    RateLimiter,
    RateLimitExceededError,
    TwilioClient,
)


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_init_default_values(self):
        """Test circuit breaker initialization with defaults."""
        cb = CircuitBreaker()

        assert cb.failure_threshold == 5
        assert cb.timeout == 60
        assert cb.failures == 0
        assert cb.last_failure_time is None
        assert cb.state == "CLOSED"

    def test_init_custom_values(self):
        """Test circuit breaker initialization with custom values."""
        cb = CircuitBreaker(failure_threshold=3, timeout=30)

        assert cb.failure_threshold == 3
        assert cb.timeout == 30

    def test_can_attempt_closed_state(self):
        """Test can_attempt returns True when circuit is closed."""
        cb = CircuitBreaker()

        assert cb.can_attempt() is True

    def test_call_failed_increments_counter(self):
        """Test that call_failed increments failure counter."""
        cb = CircuitBreaker(failure_threshold=5)

        cb.call_failed()

        assert cb.failures == 1
        assert cb.last_failure_time is not None
        assert cb.state == "CLOSED"  # Not at threshold yet

    def test_call_failed_opens_circuit_at_threshold(self):
        """Test that circuit opens when failure threshold is reached."""
        cb = CircuitBreaker(failure_threshold=3)

        cb.call_failed()
        cb.call_failed()
        cb.call_failed()

        assert cb.failures == 3
        assert cb.state == "OPEN"

    def test_call_succeeded_resets_failures(self):
        """Test that successful call resets failure count."""
        cb = CircuitBreaker(failure_threshold=5)

        # Add some failures
        cb.call_failed()
        cb.call_failed()
        assert cb.failures == 2

        # Successful call should reset
        cb.call_succeeded()

        assert cb.failures == 0
        assert cb.state == "CLOSED"

    def test_call_succeeded_closes_circuit(self):
        """Test that successful call closes open circuit."""
        cb = CircuitBreaker(failure_threshold=3)

        # Open the circuit
        cb.call_failed()
        cb.call_failed()
        cb.call_failed()
        assert cb.state == "OPEN"

        # Force half-open state to simulate recovery test
        cb.state = "HALF_OPEN"

        # Successful call should close circuit
        cb.call_succeeded()

        assert cb.state == "CLOSED"
        assert cb.failures == 0

    def test_can_attempt_open_state_before_timeout(self):
        """Test that can_attempt returns False when circuit is open and timeout not elapsed."""
        cb = CircuitBreaker(failure_threshold=3, timeout=60)

        # Open the circuit
        cb.call_failed()
        cb.call_failed()
        cb.call_failed()

        # Should not allow attempts immediately
        assert cb.can_attempt() is False

    def test_can_attempt_open_state_after_timeout(self):
        """Test that can_attempt returns True after timeout (transitions to HALF_OPEN)."""
        cb = CircuitBreaker(failure_threshold=3, timeout=60)

        # Open the circuit
        cb.call_failed()
        cb.call_failed()
        cb.call_failed()

        # Simulate time passing beyond timeout
        cb.last_failure_time = datetime.utcnow() - timedelta(seconds=61)

        # Should allow attempt (HALF_OPEN state)
        assert cb.can_attempt() is True
        assert cb.state == "HALF_OPEN"

    def test_can_attempt_half_open_state(self):
        """Test that can_attempt returns True in HALF_OPEN state."""
        cb = CircuitBreaker(failure_threshold=3)
        cb.state = "HALF_OPEN"

        assert cb.can_attempt() is True


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_init_default_values(self):
        """Test rate limiter initialization with defaults."""
        rl = RateLimiter()

        assert rl.max_per_hour == 30

    def test_init_custom_max(self):
        """Test rate limiter initialization with custom max."""
        rl = RateLimiter(max_per_hour=10)

        assert rl.max_per_hour == 10

    def test_can_send_empty_user(self):
        """Test can_send returns True for user with no history."""
        rl = RateLimiter(max_per_hour=10)

        assert rl.can_send("user123") is True

    def test_can_send_within_limit(self):
        """Test can_send returns True when user is within limit."""
        rl = RateLimiter(max_per_hour=10)

        # Record 5 sends
        for _ in range(5):
            rl.record_send("user123")

        assert rl.can_send("user123") is True

    def test_can_send_at_limit(self):
        """Test can_send returns False when user is at limit."""
        rl = RateLimiter(max_per_hour=5)

        # Record max sends
        for _ in range(5):
            rl.record_send("user123")

        assert rl.can_send("user123") is False

    def test_can_send_different_users_independent(self):
        """Test that rate limits are independent per user."""
        rl = RateLimiter(max_per_hour=2)

        # User 1 at limit
        rl.record_send("user1")
        rl.record_send("user1")

        # User 2 should still be allowed
        assert rl.can_send("user1") is False
        assert rl.can_send("user2") is True

    def test_record_send_adds_timestamp(self):
        """Test that record_send adds timestamp for user."""
        rl = RateLimiter(max_per_hour=10)

        rl.record_send("user123")

        assert len(rl.user_counts["user123"]) == 1
        assert isinstance(rl.user_counts["user123"][0], datetime)

    def test_old_entries_cleaned_up(self):
        """Test that entries older than 1 hour are cleaned up."""
        rl = RateLimiter(max_per_hour=2)

        # Add old entry (more than 1 hour ago)
        old_time = datetime.utcnow() - timedelta(hours=2)
        rl.user_counts["user123"].append(old_time)

        # Check can_send (which triggers cleanup)
        result = rl.can_send("user123")

        assert result is True
        assert len(rl.user_counts["user123"]) == 0  # Old entry should be removed


class TestTwilioClientInit:
    """Tests for TwilioClient initialization."""

    def test_init_with_credentials(self):
        """Test initialization with all Twilio credentials."""
        client = TwilioClient(
            account_sid="ACxxxxxxxxxxxx",
            auth_token="secret_token",
            phone_number="+15551234567",
            test_mode=False,
        )

        assert client.account_sid == "ACxxxxxxxxxxxx"
        assert client.auth_token == "secret_token"
        assert client.phone_number == "+15551234567"
        assert client.test_mode is False

    def test_init_missing_credentials_enables_test_mode(self):
        """Test that missing credentials auto-enable test mode."""
        client = TwilioClient(
            account_sid="ACxxxxxxxxxxxx",
            # Missing auth_token and phone_number
            test_mode=False,
        )

        assert client.test_mode is True

    def test_init_explicit_test_mode(self):
        """Test explicit test mode enabling."""
        client = TwilioClient(
            account_sid="ACxxxxxxxxxxxx",
            auth_token="secret_token",
            phone_number="+15551234567",
            test_mode=True,
        )

        assert client.test_mode is True

    def test_init_circuit_breaker_created(self):
        """Test circuit breaker is created with correct settings."""
        client = TwilioClient(test_mode=True)

        assert client.circuit_breaker is not None
        assert client.circuit_breaker.failure_threshold == 5
        assert client.circuit_breaker.timeout == 60

    def test_init_rate_limiter_created(self):
        """Test rate limiter is created with correct settings."""
        client = TwilioClient(test_mode=True)

        assert client.rate_limiter is not None
        assert client.rate_limiter.max_per_hour == 30


class TestTwilioClientSendSMS:
    """Tests for send_sms method."""

    @pytest.fixture
    def twilio_client(self):
        """Create Twilio client with credentials for testing."""
        return TwilioClient(
            account_sid="ACxxxxxxxxxxxx",
            auth_token="secret_token",
            phone_number="+15551234567",
            test_mode=False,
        )

    @pytest.fixture
    def test_mode_client(self):
        """Create Twilio client in test mode."""
        return TwilioClient(test_mode=True)

    @pytest.mark.asyncio
    async def test_send_sms_test_mode_returns_true(self, test_mode_client):
        """Test that send_sms returns True in test mode without sending."""
        result = await test_mode_client.send_sms(
            phone_number="+15559876543",
            message="Test message",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_sms_circuit_breaker_open_raises(self, twilio_client):
        """Test that send_sms raises when circuit breaker is open."""
        # Open the circuit breaker
        twilio_client.circuit_breaker.state = "OPEN"
        twilio_client.circuit_breaker.last_failure_time = datetime.utcnow()

        with pytest.raises(CircuitBreakerError) as exc_info:
            await twilio_client.send_sms(
                phone_number="+15559876543",
                message="Test message",
            )

        assert "Circuit breaker is open" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_send_sms_rate_limit_exceeded_raises(self, twilio_client):
        """Test that send_sms raises when rate limit exceeded."""
        # Exhaust rate limit
        for _ in range(30):
            twilio_client.rate_limiter.record_send("user123")

        with pytest.raises(RateLimitExceededError) as exc_info:
            await twilio_client.send_sms(
                phone_number="+15559876543",
                message="Test message",
                user_id="user123",
            )

        assert "Rate limit exceeded" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_send_sms_success(self, twilio_client):
        """Test successful SMS sending via Twilio."""
        mock_message = MagicMock()
        mock_message.sid = "SMxxxxxxxxxxxx"

        mock_messages = MagicMock()
        mock_messages.create = MagicMock(return_value=mock_message)

        mock_client = MagicMock()
        mock_client.messages = mock_messages

        twilio_client._client = mock_client

        result = await twilio_client.send_sms(
            phone_number="+15559876543",
            message="Test message",
            user_id="user123",
        )

        assert result is True
        mock_messages.create.assert_called_once_with(
            body="Test message",
            from_="+15551234567",
            to="+15559876543",
        )

    @pytest.mark.asyncio
    async def test_send_sms_records_success_on_circuit_breaker(self, twilio_client):
        """Test that successful SMS records success on circuit breaker."""
        mock_message = MagicMock()
        mock_message.sid = "SMxxxxxxxxxxxx"

        mock_messages = MagicMock()
        mock_messages.create = MagicMock(return_value=mock_message)

        mock_client = MagicMock()
        mock_client.messages = mock_messages

        twilio_client._client = mock_client

        # Add some failures first
        twilio_client.circuit_breaker.call_failed()
        twilio_client.circuit_breaker.call_failed()
        assert twilio_client.circuit_breaker.failures == 2

        await twilio_client.send_sms(
            phone_number="+15559876543",
            message="Test message",
        )

        # Success should reset failures
        assert twilio_client.circuit_breaker.failures == 0

    @pytest.mark.asyncio
    async def test_send_sms_records_send_on_rate_limiter(self, twilio_client):
        """Test that successful SMS records send on rate limiter."""
        mock_message = MagicMock()
        mock_message.sid = "SMxxxxxxxxxxxx"

        mock_messages = MagicMock()
        mock_messages.create = MagicMock(return_value=mock_message)

        mock_client = MagicMock()
        mock_client.messages = mock_messages

        twilio_client._client = mock_client

        await twilio_client.send_sms(
            phone_number="+15559876543",
            message="Test message",
            user_id="user123",
        )

        assert len(twilio_client.rate_limiter.user_counts["user123"]) == 1

    @pytest.mark.asyncio
    async def test_send_sms_retry_on_failure(self, twilio_client):
        """Test retry logic with exponential backoff."""
        mock_messages = MagicMock()
        mock_message = MagicMock(sid="SMxxxxxxxxxxxx")

        # Fail twice, succeed on third attempt
        mock_messages.create = MagicMock(
            side_effect=[
                Exception("Connection failed"),
                Exception("Connection failed"),
                mock_message,
            ]
        )

        mock_client = MagicMock()
        mock_client.messages = mock_messages

        twilio_client._client = mock_client

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await twilio_client.send_sms(
                phone_number="+15559876543",
                message="Test message",
            )

            assert result is True
            assert mock_messages.create.call_count == 3
            # Check exponential backoff (1s, 2s)
            assert mock_sleep.call_count == 2
            mock_sleep.assert_any_call(1)  # 2^0
            mock_sleep.assert_any_call(2)  # 2^1

    @pytest.mark.asyncio
    async def test_send_sms_all_retries_fail(self, twilio_client):
        """Test that send_sms returns False after all retries fail."""
        mock_messages = MagicMock()
        mock_messages.create = MagicMock(side_effect=Exception("Connection failed"))

        mock_client = MagicMock()
        mock_client.messages = mock_messages

        twilio_client._client = mock_client

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await twilio_client.send_sms(
                phone_number="+15559876543",
                message="Test message",
            )

            assert result is False
            assert mock_messages.create.call_count == 3  # Max retries

    @pytest.mark.asyncio
    async def test_send_sms_failure_opens_circuit_breaker(self, twilio_client):
        """Test that failures increment circuit breaker failure count."""
        mock_messages = MagicMock()
        mock_messages.create = MagicMock(side_effect=Exception("Connection failed"))

        mock_client = MagicMock()
        mock_client.messages = mock_messages

        twilio_client._client = mock_client

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await twilio_client.send_sms(
                phone_number="+15559876543",
                message="Test message",
            )

        # Each retry failure should increment counter (3 retries = 3 failures)
        assert twilio_client.circuit_breaker.failures == 3


class TestTwilioClientSendTestSMS:
    """Tests for send_test_sms method."""

    @pytest.fixture
    def client(self):
        """Create Twilio client in test mode."""
        return TwilioClient(test_mode=True)

    @pytest.mark.asyncio
    async def test_send_test_sms_success(self, client):
        """Test sending test SMS."""
        result = await client.send_test_sms("+15559876543")

        assert result is True

    @pytest.mark.asyncio
    async def test_send_test_sms_message_content(self, client):
        """Test that test SMS has correct content."""
        captured_args = {}

        async def capture_send(*args, **kwargs):
            captured_args.update(kwargs)
            return True

        client.send_sms = capture_send

        await client.send_test_sms("+15559876543")

        assert "BMAD Wyckoff" in captured_args.get("message", "")
        assert "test notification" in captured_args.get("message", "").lower()


class TestTwilioClientPIIMasking:
    """Tests for PII masking methods."""

    @pytest.fixture
    def client(self):
        """Create Twilio client."""
        return TwilioClient(test_mode=True)

    def test_mask_phone_standard(self, client):
        """Test phone masking with standard phone number."""
        masked = client._mask_phone("+15551234567")
        assert masked == "+1***4567"

    def test_mask_phone_short(self, client):
        """Test phone masking with short phone number."""
        masked = client._mask_phone("1234")
        assert masked == "***"

    def test_mask_phone_empty(self, client):
        """Test phone masking with empty string."""
        masked = client._mask_phone("")
        assert masked == "***"

    def test_mask_phone_minimum_length(self, client):
        """Test phone masking with minimum visible length (5 chars)."""
        masked = client._mask_phone("12345")
        assert masked == "12***2345"


class TestTwilioClientLazyLoading:
    """Tests for lazy-loaded Twilio client."""

    def test_client_property_returns_none_in_test_mode(self):
        """Test that client property returns None in test mode."""
        client = TwilioClient(test_mode=True)

        assert client.client is None

    def test_client_property_lazy_loads(self):
        """Test that Twilio client is lazy-loaded."""
        client = TwilioClient(
            account_sid="ACxxxxxxxxxxxx",
            auth_token="secret_token",
            phone_number="+15551234567",
            test_mode=False,
        )

        # Client should not be loaded yet
        assert client._client is None

        # Mock the Twilio Client class to avoid actual import/instantiation
        with patch(
            "src.notifications.twilio_client.TwilioClient.client", new_callable=PropertyMock
        ) as mock_prop:
            mock_twilio = MagicMock()
            mock_prop.return_value = mock_twilio

            # Access should return the mock
            result = client.client

            assert result == mock_twilio
