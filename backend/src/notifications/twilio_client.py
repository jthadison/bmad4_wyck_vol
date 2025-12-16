"""
Twilio SMS Client

Handles SMS notification delivery via Twilio API with:
- Retry logic with exponential backoff
- Circuit breaker pattern
- Rate limiting
- Test mode

Story: 11.6 - Notification & Alert System
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""

    pass


class RateLimitExceededError(Exception):
    """Raised when rate limit is exceeded."""

    pass


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.

    States:
    - CLOSED: Normal operation
    - OPEN: Service down, fail fast
    - HALF_OPEN: Testing recovery
    """

    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening
            timeout: Seconds before attempting recovery
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "CLOSED"

    def call_failed(self):
        """Record a failed call."""
        self.failures += 1
        self.last_failure_time = datetime.utcnow()

        if self.failures >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(
                "Circuit breaker opened",
                failures=self.failures,
                threshold=self.failure_threshold,
            )

    def call_succeeded(self):
        """Record a successful call."""
        self.failures = 0
        self.state = "CLOSED"
        logger.info("Circuit breaker closed")

    def can_attempt(self) -> bool:
        """Check if call can be attempted."""
        if self.state == "CLOSED":
            return True

        if self.state == "OPEN":
            # Check if timeout has elapsed
            if self.last_failure_time:
                elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
                if elapsed >= self.timeout:
                    self.state = "HALF_OPEN"
                    logger.info("Circuit breaker half-open, testing recovery")
                    return True

            return False

        # HALF_OPEN state
        return True


class RateLimiter:
    """
    Rate limiter to prevent excessive SMS costs.

    Tracks SMS count per user per hour.
    """

    def __init__(self, max_per_hour: int = 30):
        """
        Initialize rate limiter.

        Args:
            max_per_hour: Maximum SMS per user per hour
        """
        self.max_per_hour = max_per_hour
        self.user_counts: dict[str, list[datetime]] = defaultdict(list)

    def can_send(self, user_id: str) -> bool:
        """
        Check if user can send SMS.

        Args:
            user_id: User identifier

        Returns:
            True if within rate limit, False otherwise
        """
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)

        # Clean old entries
        self.user_counts[user_id] = [ts for ts in self.user_counts[user_id] if ts > one_hour_ago]

        return len(self.user_counts[user_id]) < self.max_per_hour

    def record_send(self, user_id: str):
        """Record an SMS send for rate limiting."""
        self.user_counts[user_id].append(datetime.utcnow())


class TwilioClient:
    """
    Twilio SMS client with resilience patterns.

    Implements:
    - Exponential backoff retry (3 attempts)
    - Circuit breaker (5 failures -> 60s timeout)
    - Rate limiting (30 SMS/hour per user)
    - Test mode
    """

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        phone_number: Optional[str] = None,
        test_mode: bool = False,
    ):
        """
        Initialize Twilio client.

        Args:
            account_sid: Twilio account SID
            auth_token: Twilio auth token
            phone_number: Twilio phone number (E.164 format)
            test_mode: If True, log instead of sending
        """
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.phone_number = phone_number
        self.test_mode = test_mode

        self.circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=60)
        self.rate_limiter = RateLimiter(max_per_hour=30)

        # Lazy-load Twilio client
        self._client = None

        if not test_mode and not all([account_sid, auth_token, phone_number]):
            logger.warning(
                "Twilio credentials not configured, running in test mode",
                test_mode=True,
            )
            self.test_mode = True

    @property
    def client(self):
        """Lazy-load Twilio client."""
        if not self._client and not self.test_mode:
            from twilio.rest import Client

            self._client = Client(self.account_sid, self.auth_token)
        return self._client

    async def send_sms(
        self,
        phone_number: str,
        message: str,
        user_id: Optional[str] = None,
    ) -> bool:
        """
        Send SMS with retry logic and rate limiting.

        Args:
            phone_number: Recipient phone number (E.164 format)
            message: SMS message text
            user_id: Optional user ID for rate limiting

        Returns:
            True if sent successfully, False otherwise

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitExceededError: If rate limit exceeded
        """
        # Check circuit breaker
        if not self.circuit_breaker.can_attempt():
            raise CircuitBreakerError("Circuit breaker is open, service unavailable")

        # Check rate limit
        if user_id and not self.rate_limiter.can_send(user_id):
            raise RateLimitExceededError(f"Rate limit exceeded for user {user_id}")

        # Test mode: just log
        if self.test_mode:
            logger.info(
                "TEST MODE: SMS would be sent",
                phone_number=self._mask_phone(phone_number),
                message=message[:50],
            )
            return True

        # Retry with exponential backoff
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Send via Twilio
                message_obj = self.client.messages.create(
                    body=message,
                    from_=self.phone_number,
                    to=phone_number,
                )

                logger.info(
                    "SMS sent successfully",
                    phone_number=self._mask_phone(phone_number),
                    message_sid=message_obj.sid,
                    attempt=attempt + 1,
                )

                # Record success
                self.circuit_breaker.call_succeeded()
                if user_id:
                    self.rate_limiter.record_send(user_id)

                return True

            except Exception as e:
                logger.error(
                    "Failed to send SMS",
                    phone_number=self._mask_phone(phone_number),
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    error=str(e),
                )

                # Record failure
                self.circuit_breaker.call_failed()

                # Retry with exponential backoff (1s, 2s, 4s)
                if attempt < max_retries - 1:
                    wait_time = 2**attempt
                    await asyncio.sleep(wait_time)
                else:
                    # Final attempt failed
                    return False

        return False

    async def send_test_sms(self, phone_number: str) -> bool:
        """
        Send test SMS for user verification.

        Args:
            phone_number: Recipient phone number

        Returns:
            True if sent successfully
        """
        test_message = (
            "BMAD Wyckoff: This is a test notification. "
            "Your SMS alerts are configured correctly."
        )

        return await self.send_sms(
            phone_number=phone_number,
            message=test_message,
        )

    def _mask_phone(self, phone_number: str) -> str:
        """Mask phone number for logging (PII protection)."""
        if len(phone_number) > 4:
            return phone_number[:2] + "***" + phone_number[-4:]
        return "***"
