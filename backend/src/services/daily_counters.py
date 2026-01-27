"""
Daily Counters Service

Redis-based tracking for daily auto-execution limits.
Story 19.16: Auto-Execution Engine

Tracks:
- Daily trade count per user
- Daily risk percentage deployed per user

Counters automatically expire at midnight UTC.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog
from redis.asyncio import Redis  # type: ignore[import-untyped]
from redis.exceptions import RedisError  # type: ignore[import-untyped]

from src.models.auto_execution import DailyCountersSnapshot

logger = structlog.get_logger(__name__)


def _today_str() -> str:
    """Get today's date as YYYY-MM-DD string in UTC."""
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _end_of_day_timestamp() -> int:
    """Get Unix timestamp for end of current UTC day."""
    now = datetime.now(UTC)
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)
    # If we're past end of day (edge case), use next day
    if now > end_of_day:
        end_of_day = end_of_day + timedelta(days=1)
    return int(end_of_day.timestamp())


def _seconds_until_midnight() -> int:
    """Get seconds remaining until midnight UTC."""
    now = datetime.now(UTC)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((midnight - now).total_seconds())


# Key version prefix for future-proofing
KEY_VERSION = "v1"


class DailyCounters:
    """
    Redis-based daily counters for auto-execution limits.

    Keys expire at midnight UTC to auto-reset daily counters.

    Key patterns:
    - auto_exec:v1:trades:{user_id}:{date} - Trade count
    - auto_exec:v1:risk:{user_id}:{date} - Risk percentage (stored as string)
    """

    def __init__(self, redis: Redis):
        """
        Initialize DailyCounters with Redis client.

        Args:
            redis: Async Redis client instance
        """
        self.redis = redis

    def _trade_key(self, user_id: UUID) -> str:
        """Generate Redis key for trade count."""
        return f"auto_exec:{KEY_VERSION}:trades:{user_id}:{_today_str()}"

    def _risk_key(self, user_id: UUID) -> str:
        """Generate Redis key for risk total."""
        return f"auto_exec:{KEY_VERSION}:risk:{user_id}:{_today_str()}"

    async def get_trades_today(self, user_id: UUID) -> int:
        """
        Get count of auto-executed trades today.

        Args:
            user_id: User UUID

        Returns:
            Number of trades executed today (0 if none)
        """
        key = self._trade_key(user_id)
        try:
            value = await self.redis.get(key)
            return int(value) if value else 0
        except RedisError as e:
            logger.error("redis_get_trades_failed", user_id=str(user_id), error=str(e))
            return 0

    async def increment_trades(self, user_id: UUID) -> int:
        """
        Increment daily trade counter.

        Uses pipeline for atomic increment + expiry.
        Sets expiry to midnight UTC for automatic reset.

        Args:
            user_id: User UUID

        Returns:
            New trade count after increment
        """
        key = self._trade_key(user_id)
        ttl = _seconds_until_midnight()
        try:
            # Use pipeline for atomic increment + expiry
            async with self.redis.pipeline() as pipe:
                pipe.incr(key)
                pipe.expire(key, ttl)
                results = await pipe.execute()
            count = results[0]

            logger.debug(
                "daily_trades_incremented",
                user_id=str(user_id),
                count=count,
                ttl_seconds=ttl,
            )
            return count
        except RedisError as e:
            logger.error("redis_incr_trades_failed", user_id=str(user_id), error=str(e))
            return 0

    async def get_risk_today(self, user_id: UUID) -> Decimal:
        """
        Get total risk deployed today as percentage.

        Args:
            user_id: User UUID

        Returns:
            Total risk percentage (0.0 if none)
        """
        key = self._risk_key(user_id)
        try:
            value = await self.redis.get(key)
            return (
                Decimal(value.decode() if isinstance(value, bytes) else value)
                if value
                else Decimal("0.0")
            )
        except (RedisError, Exception) as e:
            logger.error("redis_get_risk_failed", user_id=str(user_id), error=str(e))
            return Decimal("0.0")

    async def add_risk(self, user_id: UUID, risk_pct: Decimal) -> Decimal:
        """
        Add risk percentage to daily total.

        Uses pipeline for atomic INCRBYFLOAT + expiry.
        Sets expiry to midnight UTC for automatic reset.

        Args:
            user_id: User UUID
            risk_pct: Risk percentage to add

        Returns:
            New total risk after addition
        """
        key = self._risk_key(user_id)
        ttl = _seconds_until_midnight()
        try:
            # Use pipeline for atomic increment + expiry
            async with self.redis.pipeline() as pipe:
                pipe.incrbyfloat(key, float(risk_pct))
                pipe.expire(key, ttl)
                results = await pipe.execute()
            new_total = results[0]

            logger.debug(
                "daily_risk_added",
                user_id=str(user_id),
                added_risk=float(risk_pct),
                total_risk=new_total,
                ttl_seconds=ttl,
            )
            return Decimal(str(new_total))
        except RedisError as e:
            logger.error("redis_add_risk_failed", user_id=str(user_id), error=str(e))
            return Decimal("0.0")

    async def get_snapshot(self, user_id: UUID) -> DailyCountersSnapshot:
        """
        Get snapshot of all daily counters for a user.

        Args:
            user_id: User UUID

        Returns:
            DailyCountersSnapshot with current values
        """
        trades = await self.get_trades_today(user_id)
        risk = await self.get_risk_today(user_id)

        return DailyCountersSnapshot(
            trades_today=trades,
            risk_today=risk,
            date=_today_str(),
        )

    async def reset_counters(self, user_id: UUID) -> bool:
        """
        Manually reset counters for a user (admin function).

        Args:
            user_id: User UUID

        Returns:
            True if reset successful
        """
        try:
            trade_key = self._trade_key(user_id)
            risk_key = self._risk_key(user_id)
            await self.redis.delete(trade_key, risk_key)
            logger.info("daily_counters_reset", user_id=str(user_id))
            return True
        except RedisError as e:
            logger.error("redis_reset_failed", user_id=str(user_id), error=str(e))
            return False

    async def can_execute(
        self,
        user_id: UUID,
        max_trades: int,
        max_risk: Optional[Decimal],
        signal_risk: Decimal,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if execution is allowed within daily limits.

        Args:
            user_id: User UUID
            max_trades: Maximum trades per day limit
            max_risk: Maximum risk per day limit (None = unlimited)
            signal_risk: Risk percentage for the pending signal

        Returns:
            Tuple of (allowed: bool, reason: str | None)
        """
        trades_today = await self.get_trades_today(user_id)
        risk_today = await self.get_risk_today(user_id)

        # Check trade limit
        if trades_today >= max_trades:
            reason = f"Daily trade limit reached ({trades_today}/{max_trades})"
            return False, reason

        # Check risk limit (if configured)
        if max_risk is not None:
            projected_risk = risk_today + signal_risk
            if projected_risk > max_risk:
                reason = f"Daily risk limit exceeded ({risk_today}% + {signal_risk}% > {max_risk}%)"
                return False, reason

        return True, None

    async def reserve_execution(
        self,
        user_id: UUID,
        max_trades: int,
        max_risk: Optional[Decimal],
        signal_risk: Decimal,
    ) -> tuple[bool, Optional[str]]:
        """
        Atomically reserve execution slot by incrementing counters first.

        This prevents race conditions by incrementing counters BEFORE execution.
        If execution fails, call rollback_execution() to undo the reservation.

        Args:
            user_id: User UUID
            max_trades: Maximum trades per day limit
            max_risk: Maximum risk per day limit (None = unlimited)
            signal_risk: Risk percentage for the pending signal

        Returns:
            Tuple of (success: bool, reason: str | None)
        """
        trade_key = self._trade_key(user_id)
        risk_key = self._risk_key(user_id)
        ttl = _seconds_until_midnight()

        try:
            # Atomically increment both counters
            async with self.redis.pipeline() as pipe:
                pipe.incr(trade_key)
                pipe.expire(trade_key, ttl)
                pipe.incrbyfloat(risk_key, float(signal_risk))
                pipe.expire(risk_key, ttl)
                results = await pipe.execute()

            new_trade_count = results[0]
            new_risk_total = Decimal(str(results[2]))

            # Check if we exceeded limits after incrementing
            if new_trade_count > max_trades:
                # Rollback trade count
                await self.redis.decr(trade_key)
                reason = f"Daily trade limit reached ({new_trade_count - 1}/{max_trades})"
                return False, reason

            if max_risk is not None and new_risk_total > max_risk:
                # Rollback both counters
                await self.rollback_execution(user_id, signal_risk)
                old_risk = new_risk_total - signal_risk
                reason = f"Daily risk limit exceeded ({old_risk}% + {signal_risk}% > {max_risk}%)"
                return False, reason

            logger.debug(
                "execution_reserved",
                user_id=str(user_id),
                trades=new_trade_count,
                risk=float(new_risk_total),
            )
            return True, None

        except RedisError as e:
            logger.error("reserve_execution_failed", user_id=str(user_id), error=str(e))
            return False, "Failed to reserve execution slot"

    async def rollback_execution(self, user_id: UUID, signal_risk: Decimal) -> bool:
        """
        Rollback a reserved execution slot if execution fails.

        Args:
            user_id: User UUID
            signal_risk: Risk percentage to subtract

        Returns:
            True if rollback successful
        """
        trade_key = self._trade_key(user_id)
        risk_key = self._risk_key(user_id)

        try:
            async with self.redis.pipeline() as pipe:
                pipe.decr(trade_key)
                pipe.incrbyfloat(risk_key, -float(signal_risk))
                await pipe.execute()

            logger.debug(
                "execution_rolled_back",
                user_id=str(user_id),
                risk_removed=float(signal_risk),
            )
            return True
        except RedisError as e:
            logger.error("rollback_execution_failed", user_id=str(user_id), error=str(e))
            return False
