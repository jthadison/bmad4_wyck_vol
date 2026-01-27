"""
Unit tests for Daily Counters Service

Tests Redis-based tracking for auto-execution daily limits.
Story 19.16: Auto-Execution Engine
"""

from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.models.auto_execution import DailyCountersSnapshot
from src.services.daily_counters import DailyCounters, _seconds_until_midnight, _today_str


@pytest.fixture
def mock_pipeline():
    """Create a mock Redis pipeline."""
    pipeline = AsyncMock()
    pipeline.incr = AsyncMock()
    pipeline.expire = AsyncMock()
    pipeline.incrbyfloat = AsyncMock()
    pipeline.decr = AsyncMock()
    pipeline.execute = AsyncMock(return_value=[1, True])
    return pipeline


@pytest.fixture
def mock_redis(mock_pipeline):
    """Create a mock Redis client with pipeline support."""
    from unittest.mock import MagicMock

    redis = AsyncMock()

    # Create async context manager for pipeline
    class MockPipelineContext:
        async def __aenter__(self):
            return mock_pipeline

        async def __aexit__(self, *args):
            return None

    # Make pipeline a regular MagicMock (not async) that returns our context manager
    redis.pipeline = MagicMock(return_value=MockPipelineContext())
    return redis


@pytest.fixture
def counters(mock_redis):
    """Create DailyCounters with mock Redis."""
    return DailyCounters(mock_redis)


@pytest.fixture
def user_id():
    """Create a test user ID."""
    return uuid4()


class TestTodayString:
    """Tests for date string helper."""

    def test_today_str_format(self):
        """Test today string is in YYYY-MM-DD format."""
        result = _today_str()
        # Should be in YYYY-MM-DD format
        assert len(result) == 10
        assert result[4] == "-"
        assert result[7] == "-"

    def test_seconds_until_midnight_positive(self):
        """Test seconds until midnight is positive."""
        result = _seconds_until_midnight()
        assert result > 0
        assert result <= 86400  # Max 24 hours


class TestGetTradestoday:
    """Tests for get_trades_today method."""

    @pytest.mark.asyncio
    async def test_get_trades_returns_zero_when_no_key(self, counters, mock_redis, user_id):
        """Test returns 0 when no trades recorded."""
        mock_redis.get.return_value = None

        result = await counters.get_trades_today(user_id)

        assert result == 0

    @pytest.mark.asyncio
    async def test_get_trades_returns_count(self, counters, mock_redis, user_id):
        """Test returns count when trades recorded."""
        mock_redis.get.return_value = "5"

        result = await counters.get_trades_today(user_id)

        assert result == 5

    @pytest.mark.asyncio
    async def test_get_trades_handles_redis_error(self, counters, mock_redis, user_id):
        """Test returns 0 on Redis error."""
        from redis.exceptions import RedisError

        mock_redis.get.side_effect = RedisError("Connection failed")

        result = await counters.get_trades_today(user_id)

        assert result == 0


class TestIncrementTrades:
    """Tests for increment_trades method."""

    @pytest.mark.asyncio
    async def test_increment_trades_returns_new_count(
        self, counters, mock_redis, mock_pipeline, user_id
    ):
        """Test increments and returns new count."""
        mock_pipeline.execute.return_value = [3, True]  # [incr result, expire result]

        result = await counters.increment_trades(user_id)

        assert result == 3

    @pytest.mark.asyncio
    async def test_increment_trades_sets_expiry(self, counters, mock_redis, mock_pipeline, user_id):
        """Test sets expiry for midnight via pipeline."""
        mock_pipeline.execute.return_value = [1, True]

        await counters.increment_trades(user_id)

        # Verify pipeline expire was called
        mock_pipeline.expire.assert_called_once()
        # Check that TTL is set to some positive value
        call_args = mock_pipeline.expire.call_args[0]
        ttl = call_args[1]
        assert ttl > 0
        assert ttl <= 86400

    @pytest.mark.asyncio
    async def test_increment_trades_uses_correct_key(
        self, counters, mock_redis, mock_pipeline, user_id
    ):
        """Test uses correct Redis key format."""
        mock_pipeline.execute.return_value = [1, True]

        await counters.increment_trades(user_id)

        call_args = mock_pipeline.incr.call_args[0][0]
        assert f"auto_exec:v1:trades:{user_id}" in call_args


class TestGetRiskToday:
    """Tests for get_risk_today method."""

    @pytest.mark.asyncio
    async def test_get_risk_returns_zero_when_no_key(self, counters, mock_redis, user_id):
        """Test returns 0 when no risk recorded."""
        mock_redis.get.return_value = None

        result = await counters.get_risk_today(user_id)

        assert result == Decimal("0.0")

    @pytest.mark.asyncio
    async def test_get_risk_returns_value(self, counters, mock_redis, user_id):
        """Test returns risk percentage when recorded."""
        mock_redis.get.return_value = b"2.5"

        result = await counters.get_risk_today(user_id)

        assert result == Decimal("2.5")

    @pytest.mark.asyncio
    async def test_get_risk_handles_string(self, counters, mock_redis, user_id):
        """Test handles string response from Redis."""
        mock_redis.get.return_value = "3.0"

        result = await counters.get_risk_today(user_id)

        assert result == Decimal("3.0")

    @pytest.mark.asyncio
    async def test_get_risk_handles_redis_error(self, counters, mock_redis, user_id):
        """Test returns 0 on Redis error."""
        from redis.exceptions import RedisError

        mock_redis.get.side_effect = RedisError("Connection failed")

        result = await counters.get_risk_today(user_id)

        assert result == Decimal("0.0")


class TestAddRisk:
    """Tests for add_risk method."""

    @pytest.mark.asyncio
    async def test_add_risk_returns_new_total(self, counters, mock_redis, mock_pipeline, user_id):
        """Test adds risk and returns new total."""
        mock_pipeline.execute.return_value = [3.5, True]  # [incrbyfloat result, expire result]

        result = await counters.add_risk(user_id, Decimal("1.5"))

        assert result == Decimal("3.5")

    @pytest.mark.asyncio
    async def test_add_risk_sets_expiry(self, counters, mock_redis, mock_pipeline, user_id):
        """Test sets expiry for midnight via pipeline."""
        mock_pipeline.execute.return_value = [1.5, True]

        await counters.add_risk(user_id, Decimal("1.5"))

        mock_pipeline.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_risk_uses_correct_key(self, counters, mock_redis, mock_pipeline, user_id):
        """Test uses correct Redis key format."""
        mock_pipeline.execute.return_value = [1.5, True]

        await counters.add_risk(user_id, Decimal("1.5"))

        call_args = mock_pipeline.incrbyfloat.call_args[0][0]
        assert f"auto_exec:v1:risk:{user_id}" in call_args


class TestGetSnapshot:
    """Tests for get_snapshot method."""

    @pytest.mark.asyncio
    async def test_get_snapshot_returns_all_values(self, counters, mock_redis, user_id):
        """Test snapshot includes all counter values."""
        mock_redis.get.side_effect = ["3", b"2.5"]

        result = await counters.get_snapshot(user_id)

        assert isinstance(result, DailyCountersSnapshot)
        assert result.trades_today == 3
        assert result.risk_today == Decimal("2.5")
        assert result.date == _today_str()


class TestResetCounters:
    """Tests for reset_counters method."""

    @pytest.mark.asyncio
    async def test_reset_deletes_keys(self, counters, mock_redis, user_id):
        """Test reset deletes both trade and risk keys."""
        await counters.reset_counters(user_id)

        mock_redis.delete.assert_called_once()
        # Should delete both trade and risk keys
        call_args = mock_redis.delete.call_args[0]
        assert len(call_args) == 2

    @pytest.mark.asyncio
    async def test_reset_returns_true_on_success(self, counters, mock_redis, user_id):
        """Test returns True on successful reset."""
        result = await counters.reset_counters(user_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_reset_returns_false_on_error(self, counters, mock_redis, user_id):
        """Test returns False on Redis error."""
        from redis.exceptions import RedisError

        mock_redis.delete.side_effect = RedisError("Connection failed")

        result = await counters.reset_counters(user_id)

        assert result is False


class TestCanExecute:
    """Tests for can_execute convenience method."""

    @pytest.mark.asyncio
    async def test_can_execute_passes_all_limits(self, counters, mock_redis, user_id):
        """Test returns True when within all limits."""
        mock_redis.get.side_effect = ["2", b"1.5"]  # 2 trades, 1.5% risk

        allowed, reason = await counters.can_execute(
            user_id,
            max_trades=10,
            max_risk=Decimal("5.0"),
            signal_risk=Decimal("1.0"),
        )

        assert allowed is True
        assert reason is None

    @pytest.mark.asyncio
    async def test_can_execute_fails_trade_limit(self, counters, mock_redis, user_id):
        """Test returns False when trade limit reached."""
        mock_redis.get.side_effect = ["10", b"1.5"]  # At trade limit

        allowed, reason = await counters.can_execute(
            user_id,
            max_trades=10,
            max_risk=Decimal("5.0"),
            signal_risk=Decimal("1.0"),
        )

        assert allowed is False
        assert "trade limit" in reason.lower()
        assert "10/10" in reason

    @pytest.mark.asyncio
    async def test_can_execute_fails_risk_limit(self, counters, mock_redis, user_id):
        """Test returns False when risk limit would be exceeded."""
        mock_redis.get.side_effect = ["2", b"4.5"]  # 4.5% risk + 1.0% > 5.0%

        allowed, reason = await counters.can_execute(
            user_id,
            max_trades=10,
            max_risk=Decimal("5.0"),
            signal_risk=Decimal("1.0"),
        )

        assert allowed is False
        assert "risk limit" in reason.lower()

    @pytest.mark.asyncio
    async def test_can_execute_no_risk_limit(self, counters, mock_redis, user_id):
        """Test passes when no risk limit configured."""
        mock_redis.get.side_effect = ["2", b"100.0"]  # Very high risk, no limit

        allowed, reason = await counters.can_execute(
            user_id,
            max_trades=10,
            max_risk=None,  # No limit
            signal_risk=Decimal("1.0"),
        )

        assert allowed is True
