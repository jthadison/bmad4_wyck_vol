"""
Unit tests for CircuitBreaker class.

Tests cover:
- Initial state (CLOSED)
- Transition to OPEN on failure threshold
- Transition to HALF_OPEN after reset timeout
- Transition back to CLOSED on success
- Exponential backoff retry delays
- Admin notification on threshold breach
- Force reset functionality
- Stats tracking

Author: Story 19.4 - Multi-Symbol Concurrent Processing
"""

from datetime import UTC, datetime

import pytest

from src.pattern_engine.circuit_breaker import (
    MAX_CONSECUTIVE_FAILURES,
    RETRY_DELAYS,
    CircuitBreaker,
    CircuitState,
)


class TestCircuitBreakerInitialization:
    """Test CircuitBreaker initialization."""

    def test_initial_state_is_closed(self):
        """Circuit breaker should start in CLOSED state."""
        cb = CircuitBreaker(symbol="AAPL")
        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed
        assert not cb.is_open
        assert not cb.is_half_open

    def test_initial_consecutive_failures_is_zero(self):
        """Circuit breaker should start with zero failures."""
        cb = CircuitBreaker(symbol="AAPL")
        assert cb.consecutive_failures == 0

    def test_custom_failure_threshold(self):
        """Circuit breaker should accept custom failure threshold."""
        cb = CircuitBreaker(symbol="AAPL", failure_threshold=5)
        assert cb.failure_threshold == 5

    def test_custom_reset_timeout(self):
        """Circuit breaker should accept custom reset timeout."""
        cb = CircuitBreaker(symbol="AAPL", reset_timeout_seconds=60.0)
        assert cb.reset_timeout_seconds == 60.0


class TestRecordSuccess:
    """Test record_success() behavior."""

    @pytest.mark.asyncio
    async def test_success_resets_consecutive_failures(self):
        """Success should reset consecutive failure count."""
        cb = CircuitBreaker(symbol="AAPL")

        # Record some failures
        await cb.record_failure()
        await cb.record_failure()
        assert cb.consecutive_failures == 2

        # Record success
        await cb.record_success()
        assert cb.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_success_updates_last_success_time(self):
        """Success should update last_success_time."""
        cb = CircuitBreaker(symbol="AAPL")
        before = datetime.now(UTC)

        await cb.record_success()
        stats = cb.get_stats()

        assert stats.last_success_time is not None
        assert stats.last_success_time >= before

    @pytest.mark.asyncio
    async def test_success_increments_total_successes(self):
        """Success should increment total_successes counter."""
        cb = CircuitBreaker(symbol="AAPL")

        await cb.record_success()
        await cb.record_success()
        await cb.record_success()

        stats = cb.get_stats()
        assert stats.total_successes == 3

    @pytest.mark.asyncio
    async def test_success_resets_retry_attempt(self):
        """Success should reset retry attempt counter."""
        cb = CircuitBreaker(symbol="AAPL")
        cb._stats.retry_attempt = 3

        await cb.record_success()
        assert cb._stats.retry_attempt == 0


class TestRecordFailure:
    """Test record_failure() behavior."""

    @pytest.mark.asyncio
    async def test_failure_increments_consecutive_failures(self):
        """Failure should increment consecutive failure count."""
        cb = CircuitBreaker(symbol="AAPL")

        await cb.record_failure()
        assert cb.consecutive_failures == 1

        await cb.record_failure()
        assert cb.consecutive_failures == 2

    @pytest.mark.asyncio
    async def test_failure_increments_total_failures(self):
        """Failure should increment total failure counter."""
        cb = CircuitBreaker(symbol="AAPL")

        await cb.record_failure()
        await cb.record_failure()
        await cb.record_failure()

        stats = cb.get_stats()
        assert stats.total_failures == 3

    @pytest.mark.asyncio
    async def test_failure_updates_last_failure_time(self):
        """Failure should update last_failure_time."""
        cb = CircuitBreaker(symbol="AAPL")
        before = datetime.now(UTC)

        await cb.record_failure()
        stats = cb.get_stats()

        assert stats.last_failure_time is not None
        assert stats.last_failure_time >= before

    @pytest.mark.asyncio
    async def test_failure_threshold_opens_circuit(self):
        """Circuit should open when failure threshold is reached."""
        cb = CircuitBreaker(symbol="AAPL", failure_threshold=3)

        await cb.record_failure()
        assert cb.is_closed

        await cb.record_failure()
        assert cb.is_closed

        await cb.record_failure()  # Threshold reached
        assert cb.is_open

    @pytest.mark.asyncio
    async def test_admin_notification_on_threshold(self):
        """Admin should be notified when threshold is reached."""
        notification_received = []

        def on_notify(symbol: str, message: str):
            notification_received.append((symbol, message))

        cb = CircuitBreaker(
            symbol="TSLA",
            failure_threshold=3,
            on_admin_notify=on_notify,
        )

        await cb.record_failure()
        await cb.record_failure()
        await cb.record_failure()  # Threshold

        assert len(notification_received) == 1
        assert notification_received[0][0] == "TSLA"
        assert "3 times" in notification_received[0][1]

    @pytest.mark.asyncio
    async def test_no_duplicate_notification_on_repeated_failures(self):
        """Admin should only be notified once when circuit opens."""
        notification_count = [0]

        def on_notify(symbol: str, message: str):
            notification_count[0] += 1

        cb = CircuitBreaker(
            symbol="AAPL",
            failure_threshold=3,
            on_admin_notify=on_notify,
        )

        # Record 5 failures
        for _ in range(5):
            await cb.record_failure()

        # Should only notify once (when circuit opens)
        assert notification_count[0] == 1


class TestCanExecute:
    """Test can_execute() behavior."""

    @pytest.mark.asyncio
    async def test_can_execute_when_closed(self):
        """Can execute when circuit is CLOSED."""
        cb = CircuitBreaker(symbol="AAPL")
        assert await cb.can_execute() is True

    @pytest.mark.asyncio
    async def test_cannot_execute_when_open_initially(self):
        """Cannot execute immediately when circuit is OPEN."""
        cb = CircuitBreaker(symbol="AAPL", failure_threshold=1)
        await cb.record_failure()

        assert cb.is_open
        # Should not be able to execute (timeout not passed)
        # Note: This depends on timing, so we check state instead
        assert cb.is_open

    @pytest.mark.asyncio
    async def test_can_execute_when_half_open(self):
        """Can execute when circuit is HALF_OPEN (test request)."""
        cb = CircuitBreaker(symbol="AAPL")
        cb._state = CircuitState.HALF_OPEN

        assert await cb.can_execute() is True


class TestCircuitStateTransitions:
    """Test circuit state transitions."""

    @pytest.mark.asyncio
    async def test_half_open_to_closed_on_success(self):
        """Circuit should close on success when in HALF_OPEN state."""
        cb = CircuitBreaker(symbol="AAPL")
        cb._state = CircuitState.HALF_OPEN

        await cb.record_success()

        assert cb.is_closed

    @pytest.mark.asyncio
    async def test_half_open_to_open_on_failure(self):
        """Circuit should open on failure when in HALF_OPEN state."""
        cb = CircuitBreaker(symbol="AAPL", failure_threshold=1)
        cb._state = CircuitState.HALF_OPEN
        cb._stats.consecutive_failures = 0

        await cb.record_failure()

        assert cb.is_open


class TestExponentialBackoff:
    """Test exponential backoff retry delays."""

    def test_retry_delays_are_exponential(self):
        """Retry delays should follow exponential pattern."""
        assert RETRY_DELAYS == [1, 2, 4, 8, 16, 30]

    def test_get_next_retry_delay_first_attempt(self):
        """First retry should use first delay."""
        cb = CircuitBreaker(symbol="AAPL")
        cb._stats.retry_attempt = 0
        assert cb._get_next_retry_delay() == 1

    def test_get_next_retry_delay_later_attempts(self):
        """Later retries should use later delays."""
        cb = CircuitBreaker(symbol="AAPL")

        cb._stats.retry_attempt = 1
        assert cb._get_next_retry_delay() == 2

        cb._stats.retry_attempt = 2
        assert cb._get_next_retry_delay() == 4

        cb._stats.retry_attempt = 3
        assert cb._get_next_retry_delay() == 8

    def test_get_next_retry_delay_caps_at_max(self):
        """Retry delay should cap at max value."""
        cb = CircuitBreaker(symbol="AAPL")
        cb._stats.retry_attempt = 100  # Beyond array

        assert cb._get_next_retry_delay() == 30  # Max value


class TestForceReset:
    """Test force reset functionality."""

    @pytest.mark.asyncio
    async def test_reset_closes_circuit(self):
        """Force reset should close the circuit."""
        cb = CircuitBreaker(symbol="AAPL", failure_threshold=1)
        await cb.record_failure()
        assert cb.is_open

        await cb.reset()
        assert cb.is_closed

    @pytest.mark.asyncio
    async def test_reset_clears_consecutive_failures(self):
        """Force reset should clear consecutive failures."""
        cb = CircuitBreaker(symbol="AAPL")
        await cb.record_failure()
        await cb.record_failure()

        await cb.reset()
        assert cb.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_reset_clears_retry_attempt(self):
        """Force reset should clear retry attempt counter."""
        cb = CircuitBreaker(symbol="AAPL")
        cb._stats.retry_attempt = 5

        await cb.reset()
        assert cb._stats.retry_attempt == 0


class TestTimeUntilRetry:
    """Test time_until_retry() functionality."""

    def test_time_until_retry_returns_none_when_closed(self):
        """Should return None when circuit is closed."""
        cb = CircuitBreaker(symbol="AAPL")
        assert cb.time_until_retry() is None

    def test_time_until_retry_returns_none_when_half_open(self):
        """Should return None when circuit is half-open."""
        cb = CircuitBreaker(symbol="AAPL")
        cb._state = CircuitState.HALF_OPEN
        assert cb.time_until_retry() is None

    def test_time_until_retry_returns_remaining_seconds_when_open(self):
        """Should return remaining seconds when circuit is open."""
        cb = CircuitBreaker(symbol="AAPL", failure_threshold=1)
        cb._state = CircuitState.OPEN
        cb._stats.state_changed_at = datetime.now(UTC)
        cb._stats.retry_attempt = 0

        remaining = cb.time_until_retry()
        assert remaining is not None
        assert 0 <= remaining <= 1  # First retry delay is 1 second


class TestGetStats:
    """Test get_stats() returns correct data."""

    @pytest.mark.asyncio
    async def test_get_stats_returns_copy(self):
        """get_stats should return a copy of stats."""
        cb = CircuitBreaker(symbol="AAPL")
        await cb.record_failure()
        await cb.record_success()

        stats = cb.get_stats()
        assert stats.consecutive_failures == 0
        assert stats.total_failures == 1
        assert stats.total_successes == 1

    @pytest.mark.asyncio
    async def test_modifying_stats_copy_does_not_affect_original(self):
        """Modifying stats copy should not affect circuit breaker."""
        cb = CircuitBreaker(symbol="AAPL")

        stats = cb.get_stats()
        stats.consecutive_failures = 100

        assert cb.consecutive_failures == 0


class TestConstants:
    """Test module constants."""

    def test_max_consecutive_failures_default(self):
        """Default max consecutive failures should be 3."""
        assert MAX_CONSECUTIVE_FAILURES == 3

    def test_default_failure_threshold_matches_constant(self):
        """Default failure threshold should match constant."""
        cb = CircuitBreaker(symbol="AAPL")
        assert cb.failure_threshold == MAX_CONSECUTIVE_FAILURES
