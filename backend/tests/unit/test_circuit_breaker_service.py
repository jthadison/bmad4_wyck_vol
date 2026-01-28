"""
Unit tests for Circuit Breaker Service

Tests circuit breaker logic including state management, threshold triggers, and reset functionality.
Story 19.21: Circuit Breaker Logic
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.models.circuit_breaker import CircuitBreakerState
from src.services.circuit_breaker_service import CircuitBreakerService


class MockPipeline:
    """Mock Redis pipeline with async context manager support."""

    def __init__(self):
        self.set = MagicMock()
        self.delete = MagicMock()
        self.execute = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


@pytest.fixture
def mock_pipeline():
    """Create a mock Redis pipeline."""
    return MockPipeline()


@pytest.fixture
def mock_redis(mock_pipeline):
    """Create a mock Redis client with pipeline support."""
    redis = AsyncMock()
    # Configure pipeline as a regular method that returns the mock pipeline
    redis.pipeline = MagicMock(return_value=mock_pipeline)
    return redis


@pytest.fixture
def service(mock_redis):
    """Create circuit breaker service with mock Redis."""
    return CircuitBreakerService(mock_redis)


@pytest.fixture
def user_id():
    """Create a test user ID."""
    return uuid4()


class TestGetState:
    """Tests for get_state method."""

    @pytest.mark.asyncio
    async def test_returns_closed_when_no_state(self, service, mock_redis, user_id):
        """Test returns CLOSED when no state exists in Redis."""
        mock_redis.get.return_value = None

        state = await service.get_state(user_id)

        assert state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_returns_stored_state_closed(self, service, mock_redis, user_id):
        """Test returns CLOSED state from Redis."""
        mock_redis.get.return_value = b"closed"

        state = await service.get_state(user_id)

        assert state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_returns_stored_state_open(self, service, mock_redis, user_id):
        """Test returns OPEN state from Redis."""
        mock_redis.get.return_value = b"open"

        state = await service.get_state(user_id)

        assert state == CircuitBreakerState.OPEN

    @pytest.mark.asyncio
    async def test_handles_redis_error(self, service, mock_redis, user_id):
        """Test returns CLOSED on Redis error to not block trading."""
        from redis.exceptions import RedisError

        mock_redis.get.side_effect = RedisError("Connection failed")

        state = await service.get_state(user_id)

        # Should default to CLOSED on error
        assert state == CircuitBreakerState.CLOSED


class TestGetConsecutiveLosses:
    """Tests for get_consecutive_losses method."""

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_losses(self, service, mock_redis, user_id):
        """Test returns 0 when no losses recorded."""
        mock_redis.get.return_value = None

        losses = await service.get_consecutive_losses(user_id)

        assert losses == 0

    @pytest.mark.asyncio
    async def test_returns_stored_losses(self, service, mock_redis, user_id):
        """Test returns loss count from Redis."""
        mock_redis.get.return_value = b"2"

        losses = await service.get_consecutive_losses(user_id)

        assert losses == 2

    @pytest.mark.asyncio
    async def test_handles_redis_error(self, service, mock_redis, user_id):
        """Test returns 0 on Redis error."""
        from redis.exceptions import RedisError

        mock_redis.get.side_effect = RedisError("Connection failed")

        losses = await service.get_consecutive_losses(user_id)

        assert losses == 0


class TestRecordTradeResult:
    """Tests for record_trade_result method."""

    @pytest.mark.asyncio
    async def test_winning_trade_resets_counter(self, service, mock_redis, user_id):
        """Test winning trade resets consecutive loss counter."""
        mock_redis.set = AsyncMock()
        mock_redis.get.return_value = b"closed"

        state = await service.record_trade_result(user_id, is_winner=True, threshold=3)

        # Should set losses to 0
        mock_redis.set.assert_called()
        assert state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_losing_trade_increments_counter(self, service, mock_redis, user_id):
        """Test losing trade increments consecutive loss counter."""
        mock_redis.incr.return_value = 1
        mock_redis.get.return_value = b"closed"

        state = await service.record_trade_result(user_id, is_winner=False, threshold=3)

        mock_redis.incr.assert_called_once()
        assert state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_threshold_breach_triggers_breaker(
        self, service, mock_redis, mock_pipeline, user_id
    ):
        """Test reaching threshold triggers circuit breaker."""
        mock_redis.incr.return_value = 3  # Matches threshold

        state = await service.record_trade_result(user_id, is_winner=False, threshold=3)

        assert state == CircuitBreakerState.OPEN
        # Should have set state to OPEN via pipeline
        assert mock_pipeline.set.call_count >= 2  # state + triggered_at
        mock_pipeline.execute.assert_called()

    @pytest.mark.asyncio
    async def test_exceeds_threshold_triggers_breaker(
        self, service, mock_redis, mock_pipeline, user_id
    ):
        """Test exceeding threshold triggers circuit breaker."""
        mock_redis.incr.return_value = 5  # Exceeds threshold

        state = await service.record_trade_result(user_id, is_winner=False, threshold=3)

        assert state == CircuitBreakerState.OPEN
        mock_pipeline.execute.assert_called()

    @pytest.mark.asyncio
    async def test_below_threshold_stays_closed(self, service, mock_redis, user_id):
        """Test below threshold keeps breaker closed."""
        mock_redis.incr.return_value = 2  # Below threshold of 3
        mock_redis.get.return_value = b"closed"

        state = await service.record_trade_result(user_id, is_winner=False, threshold=3)

        assert state == CircuitBreakerState.CLOSED


class TestResetBreaker:
    """Tests for reset_breaker method."""

    @pytest.mark.asyncio
    async def test_resets_state_to_closed(self, service, mock_redis, mock_pipeline, user_id):
        """Test reset sets state to CLOSED."""
        await service.reset_breaker(user_id, manual=True)

        # Should set state to closed via pipeline (with TTL)
        mock_pipeline.set.assert_any_call(
            f"circuit_breaker:state:{user_id}",
            CircuitBreakerState.CLOSED.value,
            ex=7 * 24 * 60 * 60,  # BREAKER_TTL_SECONDS
        )
        mock_pipeline.execute.assert_called()

    @pytest.mark.asyncio
    async def test_resets_loss_counter_to_zero(self, service, mock_redis, mock_pipeline, user_id):
        """Test reset sets loss counter to 0."""
        await service.reset_breaker(user_id, manual=True)

        # Should set losses to 0 via pipeline (with TTL)
        mock_pipeline.set.assert_any_call(
            f"circuit_breaker:losses:{user_id}",
            0,
            ex=7 * 24 * 60 * 60,  # BREAKER_TTL_SECONDS
        )
        mock_pipeline.execute.assert_called()

    @pytest.mark.asyncio
    async def test_clears_triggered_timestamp(self, service, mock_redis, mock_pipeline, user_id):
        """Test reset clears triggered_at timestamp."""
        await service.reset_breaker(user_id, manual=True)

        # Should delete triggered_at key via pipeline
        mock_pipeline.delete.assert_called_once_with(f"circuit_breaker:triggered_at:{user_id}")
        mock_pipeline.execute.assert_called()

    @pytest.mark.asyncio
    async def test_propagates_redis_error(self, service, mock_redis, mock_pipeline, user_id):
        """Test Redis errors are propagated."""
        from redis.exceptions import RedisError

        mock_pipeline.execute.side_effect = RedisError("Connection failed")

        with pytest.raises(RedisError):
            await service.reset_breaker(user_id, manual=True)


class TestIsBreakerOpen:
    """Tests for is_breaker_open method."""

    @pytest.mark.asyncio
    async def test_returns_true_when_open(self, service, mock_redis, user_id):
        """Test returns True when breaker is open."""
        mock_redis.get.return_value = b"open"

        is_open = await service.is_breaker_open(user_id)

        assert is_open is True

    @pytest.mark.asyncio
    async def test_returns_false_when_closed(self, service, mock_redis, user_id):
        """Test returns False when breaker is closed."""
        mock_redis.get.return_value = b"closed"

        is_open = await service.is_breaker_open(user_id)

        assert is_open is False

    @pytest.mark.asyncio
    async def test_returns_false_when_no_state(self, service, mock_redis, user_id):
        """Test returns False when no state exists."""
        mock_redis.get.return_value = None

        is_open = await service.is_breaker_open(user_id)

        assert is_open is False


class TestGetAllOpenBreakers:
    """Tests for get_all_open_breakers method."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_none_open(self, service, mock_redis):
        """Test returns empty list when no breakers are open."""

        async def empty_gen():
            return
            yield  # Make it a generator

        mock_redis.scan_iter = MagicMock(return_value=empty_gen())

        open_breakers = await service.get_all_open_breakers()

        assert open_breakers == []

    @pytest.mark.asyncio
    async def test_returns_open_breaker_user_ids(self, service, mock_redis):
        """Test returns list of user IDs with open breakers."""
        user1 = uuid4()
        user2 = uuid4()

        async def key_gen():
            yield f"circuit_breaker:state:{user1}".encode()
            yield f"circuit_breaker:state:{user2}".encode()

        mock_redis.scan_iter = MagicMock(return_value=key_gen())

        # Mock get to return open state for both
        mock_redis.get.side_effect = [b"open", b"open"]

        open_breakers = await service.get_all_open_breakers()

        assert user1 in open_breakers
        assert user2 in open_breakers
        assert len(open_breakers) == 2

    @pytest.mark.asyncio
    async def test_filters_closed_breakers(self, service, mock_redis):
        """Test only returns users with OPEN state, not CLOSED."""
        user_open = uuid4()
        user_closed = uuid4()

        async def key_gen():
            yield f"circuit_breaker:state:{user_open}".encode()
            yield f"circuit_breaker:state:{user_closed}".encode()

        mock_redis.scan_iter = MagicMock(return_value=key_gen())

        # First user open, second user closed
        mock_redis.get.side_effect = [b"open", b"closed"]

        open_breakers = await service.get_all_open_breakers()

        assert user_open in open_breakers
        assert user_closed not in open_breakers
        assert len(open_breakers) == 1


class TestGetTriggeredAt:
    """Tests for get_triggered_at method."""

    @pytest.mark.asyncio
    async def test_returns_none_when_not_triggered(self, service, mock_redis, user_id):
        """Test returns None when breaker not triggered."""
        mock_redis.get.return_value = None

        triggered_at = await service.get_triggered_at(user_id)

        assert triggered_at is None

    @pytest.mark.asyncio
    async def test_returns_stored_timestamp(self, service, mock_redis, user_id):
        """Test returns trigger timestamp from Redis."""
        expected_time = datetime.now(UTC)
        mock_redis.get.return_value = expected_time.isoformat().encode()

        triggered_at = await service.get_triggered_at(user_id)

        assert triggered_at is not None
        # Compare with tolerance for parsing
        assert abs((triggered_at - expected_time).total_seconds()) < 1


class TestCalculateResetTime:
    """Tests for calculate_reset_time method."""

    def test_returns_next_midnight_et(self, service):
        """Test calculates next midnight ET."""
        # Use a fixed time for testing
        with patch("src.services.circuit_breaker_service.datetime") as mock_datetime:
            # Mock current time as 2pm ET
            from zoneinfo import ZoneInfo

            et_tz = ZoneInfo("America/New_York")
            mock_now = datetime(2026, 1, 27, 14, 0, 0, tzinfo=et_tz)
            mock_datetime.now.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            reset_time = service.calculate_reset_time()

            # Should be midnight of next day
            assert reset_time.hour == 0
            assert reset_time.minute == 0
            assert reset_time.day == 28  # Next day


class TestEndToEndScenarios:
    """Integration-style tests for complete scenarios."""

    @pytest.mark.asyncio
    async def test_three_losses_trigger_breaker(
        self, service, mock_redis, mock_pipeline, user_id
    ):
        """Test complete scenario: 3 consecutive losses triggers breaker."""
        # First loss
        mock_redis.incr.return_value = 1
        mock_redis.get.return_value = b"closed"
        state = await service.record_trade_result(user_id, is_winner=False, threshold=3)
        assert state == CircuitBreakerState.CLOSED

        # Second loss
        mock_redis.incr.return_value = 2
        state = await service.record_trade_result(user_id, is_winner=False, threshold=3)
        assert state == CircuitBreakerState.CLOSED

        # Third loss - should trigger
        mock_redis.incr.return_value = 3
        state = await service.record_trade_result(user_id, is_winner=False, threshold=3)
        assert state == CircuitBreakerState.OPEN
        # Pipeline should have been used to trigger breaker
        mock_pipeline.execute.assert_called()

    @pytest.mark.asyncio
    async def test_win_after_losses_resets_counter(self, service, mock_redis, user_id):
        """Test winning trade after losses resets counter."""
        # Two losses
        mock_redis.incr.return_value = 2
        mock_redis.get.return_value = b"closed"
        await service.record_trade_result(user_id, is_winner=False, threshold=3)

        # Win - should reset (direct set, not via pipeline)
        state = await service.record_trade_result(user_id, is_winner=True, threshold=3)
        assert state == CircuitBreakerState.CLOSED

        # Verify losses were reset to 0 (with TTL)
        losses_key = f"circuit_breaker:losses:{user_id}"
        mock_redis.set.assert_any_call(losses_key, 0, ex=7 * 24 * 60 * 60)

    @pytest.mark.asyncio
    async def test_manual_reset_after_trigger(
        self, service, mock_redis, mock_pipeline, user_id
    ):
        """Test manual reset after breaker triggers."""
        # Trigger breaker
        mock_redis.incr.return_value = 3
        state = await service.record_trade_result(user_id, is_winner=False, threshold=3)
        assert state == CircuitBreakerState.OPEN

        # Manual reset
        await service.reset_breaker(user_id, manual=True)

        # Verify state was set to closed via pipeline (with TTL)
        state_key = f"circuit_breaker:state:{user_id}"
        mock_pipeline.set.assert_any_call(
            state_key, CircuitBreakerState.CLOSED.value, ex=7 * 24 * 60 * 60
        )
