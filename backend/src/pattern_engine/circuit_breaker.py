"""
Circuit Breaker for Multi-Symbol Processing.

Implements per-symbol circuit breakers with exponential backoff retry.
Story 19.4 - Multi-Symbol Concurrent Processing.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, skip processing
    HALF_OPEN = "half_open"  # Testing recovery


# Exponential backoff delays in seconds
RETRY_DELAYS = [1, 2, 4, 8, 16, 30]
MAX_CONSECUTIVE_FAILURES = 3  # Before admin notification


@dataclass
class CircuitBreakerStats:
    """Statistics for a circuit breaker instance."""

    consecutive_failures: int = 0
    total_failures: int = 0
    total_successes: int = 0
    last_failure_time: datetime | None = None
    last_success_time: datetime | None = None
    state_changed_at: datetime | None = None
    retry_attempt: int = 0


@dataclass
class CircuitBreaker:
    """
    Circuit breaker for a single symbol.

    Implements the circuit breaker pattern with:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failures exceeded threshold, requests blocked
    - HALF_OPEN: Testing if service recovered

    Includes exponential backoff for retries.
    """

    symbol: str
    failure_threshold: int = MAX_CONSECUTIVE_FAILURES
    reset_timeout_seconds: float = 30.0
    on_admin_notify: Callable[[str, str], None] | None = None
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _stats: CircuitBreakerStats = field(default_factory=CircuitBreakerStats, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def consecutive_failures(self) -> int:
        """Get consecutive failure count."""
        return self._stats.consecutive_failures

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        return self._state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state == CircuitState.CLOSED

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self._state == CircuitState.HALF_OPEN

    def _get_next_retry_delay(self) -> float:
        """Get the next retry delay based on current retry attempt."""
        idx = min(self._stats.retry_attempt, len(RETRY_DELAYS) - 1)
        return RETRY_DELAYS[idx]

    async def record_success(self) -> None:
        """
        Record a successful operation.

        Resets failure count and transitions to CLOSED if in HALF_OPEN.
        """
        async with self._lock:
            self._stats.consecutive_failures = 0
            self._stats.total_successes += 1
            self._stats.last_success_time = datetime.now(UTC)
            self._stats.retry_attempt = 0

            if self._state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.CLOSED)
                logger.info(
                    "circuit_breaker_closed_on_success",
                    symbol=self.symbol,
                )

    async def record_failure(self, error: Exception | None = None) -> None:
        """
        Record a failed operation.

        Increments failure count and may transition to OPEN state.
        Triggers admin notification on threshold breach.

        Args:
            error: Optional exception that caused the failure
        """
        async with self._lock:
            self._stats.consecutive_failures += 1
            self._stats.total_failures += 1
            self._stats.last_failure_time = datetime.now(UTC)

            logger.warning(
                "circuit_breaker_failure_recorded",
                symbol=self.symbol,
                consecutive_failures=self._stats.consecutive_failures,
                error=str(error) if error else None,
            )

            # Check if we should open the circuit
            if self._stats.consecutive_failures >= self.failure_threshold:
                if self._state != CircuitState.OPEN:
                    self._transition_to(CircuitState.OPEN)
                    self._stats.retry_attempt = 0

                    logger.warning(
                        "circuit_breaker_opened",
                        symbol=self.symbol,
                        consecutive_failures=self._stats.consecutive_failures,
                        threshold=self.failure_threshold,
                    )

                    # Trigger admin notification
                    if self.on_admin_notify:
                        message = (
                            f"{self.symbol} processing failed "
                            f"{self._stats.consecutive_failures} times"
                        )
                        try:
                            self.on_admin_notify(self.symbol, message)
                        except Exception as notify_error:
                            logger.error(
                                "admin_notification_failed",
                                symbol=self.symbol,
                                error=str(notify_error),
                            )

    async def can_execute(self) -> bool:
        """
        Check if an operation can be executed.

        Returns True if circuit is CLOSED or if HALF_OPEN test is allowed.
        For OPEN circuits, checks if reset timeout has passed.

        Returns:
            True if operation should be attempted
        """
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.HALF_OPEN:
                # Allow one test request in half-open state
                return True

            if self._state == CircuitState.OPEN:
                # Check if we should transition to half-open
                if self._should_attempt_reset():
                    self._transition_to(CircuitState.HALF_OPEN)
                    self._stats.retry_attempt += 1
                    logger.info(
                        "circuit_breaker_half_open",
                        symbol=self.symbol,
                        retry_attempt=self._stats.retry_attempt,
                    )
                    return True

            return False

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self._stats.state_changed_at is None:
            return True

        # Use exponential backoff for reset attempts
        delay = self._get_next_retry_delay()
        elapsed = (datetime.now(UTC) - self._stats.state_changed_at).total_seconds()
        return elapsed >= delay

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        old_state = self._state
        self._state = new_state
        self._stats.state_changed_at = datetime.now(UTC)

        logger.info(
            "circuit_breaker_state_transition",
            symbol=self.symbol,
            old_state=old_state.value,
            new_state=new_state.value,
        )

    async def reset(self) -> None:
        """
        Force reset the circuit breaker to CLOSED state.

        Used for manual recovery or testing.
        """
        async with self._lock:
            self._stats.consecutive_failures = 0
            self._stats.retry_attempt = 0
            self._transition_to(CircuitState.CLOSED)
            logger.info(
                "circuit_breaker_force_reset",
                symbol=self.symbol,
            )

    def get_stats(self) -> CircuitBreakerStats:
        """Get a copy of current stats."""
        return CircuitBreakerStats(
            consecutive_failures=self._stats.consecutive_failures,
            total_failures=self._stats.total_failures,
            total_successes=self._stats.total_successes,
            last_failure_time=self._stats.last_failure_time,
            last_success_time=self._stats.last_success_time,
            state_changed_at=self._stats.state_changed_at,
            retry_attempt=self._stats.retry_attempt,
        )

    def time_until_retry(self) -> float | None:
        """
        Get seconds until next retry attempt is allowed.

        Returns:
            Seconds until retry, or None if retry is allowed now
        """
        if self._state != CircuitState.OPEN:
            return None

        if self._stats.state_changed_at is None:
            return None

        delay = self._get_next_retry_delay()
        elapsed = (datetime.now(UTC) - self._stats.state_changed_at).total_seconds()
        remaining = delay - elapsed

        return max(0.0, remaining) if remaining > 0 else None
