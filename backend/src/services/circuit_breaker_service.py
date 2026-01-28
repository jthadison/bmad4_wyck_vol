"""
Circuit Breaker Service (Story 19.21)

Manages circuit breaker logic for auto-execution protection.
Pauses auto-execution after consecutive losing trades.

Author: Story 19.21
"""

from datetime import UTC, datetime, timedelta
from enum import Enum
from uuid import UUID

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = structlog.get_logger(__name__)


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, auto-execution active
    OPEN = "open"  # Triggered, auto-execution paused


class CircuitBreakerService:
    """
    Service for managing circuit breaker state.

    Tracks consecutive losses and triggers circuit breaker when threshold
    is exceeded. Provides manual and automatic reset functionality.

    Redis Keys:
    - circuit_breaker:losses:{user_id} - Consecutive loss count
    - circuit_breaker:state:{user_id} - Current breaker state
    - circuit_breaker:triggered_at:{user_id} - Trigger timestamp
    """

    # Redis key prefixes
    LOSSES_KEY_PREFIX = "circuit_breaker:losses:"
    STATE_KEY_PREFIX = "circuit_breaker:state:"
    TRIGGERED_KEY_PREFIX = "circuit_breaker:triggered_at:"

    def __init__(self, redis: Redis):
        """
        Initialize circuit breaker service.

        Args:
            redis: Async Redis client
        """
        self.redis = redis

    def _losses_key(self, user_id: UUID) -> str:
        """Get Redis key for consecutive losses."""
        return f"{self.LOSSES_KEY_PREFIX}{user_id}"

    def _state_key(self, user_id: UUID) -> str:
        """Get Redis key for breaker state."""
        return f"{self.STATE_KEY_PREFIX}{user_id}"

    def _triggered_key(self, user_id: UUID) -> str:
        """Get Redis key for trigger timestamp."""
        return f"{self.TRIGGERED_KEY_PREFIX}{user_id}"

    async def get_state(self, user_id: UUID) -> CircuitBreakerState:
        """
        Get current circuit breaker state for user.

        Args:
            user_id: User UUID

        Returns:
            CircuitBreakerState (CLOSED or OPEN)
        """
        try:
            state = await self.redis.get(self._state_key(user_id))
            if state:
                return CircuitBreakerState(state.decode() if isinstance(state, bytes) else state)
            return CircuitBreakerState.CLOSED
        except RedisError as e:
            logger.error("circuit_breaker_get_state_failed", user_id=str(user_id), error=str(e))
            # Default to CLOSED on error to not block trading
            return CircuitBreakerState.CLOSED

    async def get_consecutive_losses(self, user_id: UUID) -> int:
        """
        Get current consecutive loss count for user.

        Args:
            user_id: User UUID

        Returns:
            Number of consecutive losses
        """
        try:
            losses = await self.redis.get(self._losses_key(user_id))
            if losses:
                return int(losses.decode() if isinstance(losses, bytes) else losses)
            return 0
        except RedisError as e:
            logger.error("circuit_breaker_get_losses_failed", user_id=str(user_id), error=str(e))
            return 0

    async def get_triggered_at(self, user_id: UUID) -> datetime | None:
        """
        Get timestamp when circuit breaker was triggered.

        Args:
            user_id: User UUID

        Returns:
            Trigger timestamp or None if not triggered
        """
        try:
            triggered = await self.redis.get(self._triggered_key(user_id))
            if triggered:
                ts = triggered.decode() if isinstance(triggered, bytes) else triggered
                return datetime.fromisoformat(ts)
            return None
        except RedisError as e:
            logger.error("circuit_breaker_get_triggered_failed", user_id=str(user_id), error=str(e))
            return None

    async def record_trade_result(
        self, user_id: UUID, is_winner: bool, threshold: int = 3
    ) -> CircuitBreakerState:
        """
        Record trade result and check if circuit breaker should trigger.

        Args:
            user_id: User UUID
            is_winner: True if trade was a winner, False if loser
            threshold: Number of consecutive losses to trigger breaker

        Returns:
            Current CircuitBreakerState after recording result
        """
        try:
            if is_winner:
                # Reset consecutive losses on a win
                await self.redis.set(self._losses_key(user_id), 0)
                logger.info(
                    "circuit_breaker_loss_counter_reset",
                    user_id=str(user_id),
                    reason="winning_trade",
                )
                return await self.get_state(user_id)

            # Increment consecutive losses
            losses = await self.redis.incr(self._losses_key(user_id))

            logger.info(
                "circuit_breaker_loss_recorded",
                user_id=str(user_id),
                consecutive_losses=losses,
                threshold=threshold,
            )

            # Check threshold
            if losses >= threshold:
                await self._trigger_breaker(user_id, int(losses))
                return CircuitBreakerState.OPEN

            return CircuitBreakerState.CLOSED

        except RedisError as e:
            logger.error("circuit_breaker_record_failed", user_id=str(user_id), error=str(e))
            return await self.get_state(user_id)

    async def _trigger_breaker(self, user_id: UUID, consecutive_losses: int) -> None:
        """
        Trigger the circuit breaker.

        Args:
            user_id: User UUID
            consecutive_losses: Number of losses that triggered breaker
        """
        triggered_at = datetime.now(UTC)

        try:
            # Set state to OPEN
            await self.redis.set(self._state_key(user_id), CircuitBreakerState.OPEN.value)
            # Record trigger timestamp
            await self.redis.set(self._triggered_key(user_id), triggered_at.isoformat())

            logger.warning(
                "circuit_breaker_triggered",
                user_id=str(user_id),
                consecutive_losses=consecutive_losses,
                triggered_at=triggered_at.isoformat(),
            )

        except RedisError as e:
            logger.error("circuit_breaker_trigger_failed", user_id=str(user_id), error=str(e))

    async def reset_breaker(self, user_id: UUID, manual: bool = False) -> None:
        """
        Reset the circuit breaker.

        Args:
            user_id: User UUID
            manual: True if user manually reset, False if automatic
        """
        try:
            # Reset state to CLOSED
            await self.redis.set(self._state_key(user_id), CircuitBreakerState.CLOSED.value)
            # Reset consecutive losses
            await self.redis.set(self._losses_key(user_id), 0)
            # Clear trigger timestamp
            await self.redis.delete(self._triggered_key(user_id))

            reset_type = "manual" if manual else "automatic"
            logger.info(
                "circuit_breaker_reset",
                user_id=str(user_id),
                reset_type=reset_type,
            )

        except RedisError as e:
            logger.error("circuit_breaker_reset_failed", user_id=str(user_id), error=str(e))
            raise

    async def is_breaker_open(self, user_id: UUID) -> bool:
        """
        Check if circuit breaker is open (trading paused).

        Args:
            user_id: User UUID

        Returns:
            True if breaker is open, False if closed
        """
        state = await self.get_state(user_id)
        return state == CircuitBreakerState.OPEN

    async def get_all_open_breakers(self) -> list[UUID]:
        """
        Get all user IDs with open circuit breakers.

        Used by midnight reset scheduler.

        Returns:
            List of user UUIDs with open breakers
        """
        try:
            open_breakers = []
            pattern = f"{self.STATE_KEY_PREFIX}*"

            async for key in self.redis.scan_iter(match=pattern):
                key_str = key.decode() if isinstance(key, bytes) else key
                state = await self.redis.get(key)
                if state:
                    state_str = state.decode() if isinstance(state, bytes) else state
                    if state_str == CircuitBreakerState.OPEN.value:
                        # Extract user_id from key
                        user_id_str = key_str.replace(self.STATE_KEY_PREFIX, "")
                        try:
                            open_breakers.append(UUID(user_id_str))
                        except ValueError:
                            logger.warning("circuit_breaker_invalid_user_id", key=key_str)

            return open_breakers

        except RedisError as e:
            logger.error("circuit_breaker_scan_failed", error=str(e))
            return []

    def calculate_reset_time(self, triggered_at: datetime | None = None) -> datetime:
        """
        Calculate next midnight ET reset time.

        Args:
            triggered_at: Optional trigger timestamp for reference

        Returns:
            Datetime of next midnight ET
        """
        from zoneinfo import ZoneInfo

        et_tz = ZoneInfo("America/New_York")
        now_et = datetime.now(et_tz)

        # Next midnight ET
        next_midnight = now_et.replace(hour=0, minute=0, second=0, microsecond=0)
        if next_midnight <= now_et:
            next_midnight += timedelta(days=1)

        return next_midnight
