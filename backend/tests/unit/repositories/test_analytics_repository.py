"""Unit tests for analytics repository."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from redis.asyncio import Redis

from src.models.analytics import PatternPerformanceResponse
from src.repositories.analytics_repository import AnalyticsRepository


@pytest.fixture
def mock_session():
    """Create mock async session."""
    session = AsyncMock()
    return session


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    redis = AsyncMock(spec=Redis)
    return redis


@pytest.fixture
def analytics_repo(mock_session, mock_redis):
    """Create analytics repository with mocked dependencies."""
    return AnalyticsRepository(
        session=mock_session,
        redis=mock_redis,
        cache_ttl=86400,
    )


@pytest.fixture
def analytics_repo_no_cache(mock_session):
    """Create analytics repository without Redis caching."""
    return AnalyticsRepository(
        session=mock_session,
        redis=None,
        cache_ttl=86400,
    )


class TestGetPatternPerformance:
    """Test get_pattern_performance method."""

    @pytest.mark.asyncio
    async def test_valid_days_parameters(self, analytics_repo: AnalyticsRepository) -> None:
        """Test that valid days parameters are accepted."""
        analytics_repo.redis.get = AsyncMock(return_value=None)  # type: ignore

        for days in [7, 30, 90, None]:
            response = await analytics_repo.get_pattern_performance(days=days)
            assert isinstance(response, PatternPerformanceResponse)
            assert response.time_period_days == days

    @pytest.mark.asyncio
    async def test_invalid_days_parameter(self, analytics_repo: AnalyticsRepository) -> None:
        """Test that invalid days parameter raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            await analytics_repo.get_pattern_performance(days=45)
        assert "days must be 7, 30, 90, or None" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cache_hit(
        self, analytics_repo: AnalyticsRepository, mock_redis: AsyncMock
    ) -> None:
        """Test that cache hit returns cached data without database query."""
        now = datetime.now(UTC)
        cached_data = {
            "patterns": [
                {
                    "pattern_type": "SPRING",
                    "win_rate": "0.7200",
                    "average_r_multiple": "3.45",
                    "profit_factor": "2.80",
                    "trade_count": 42,
                    "test_confirmed_count": 0,
                    "phase_distribution": {},
                }
            ],
            "sector_breakdown": [],
            "time_period_days": 30,
            "generated_at": now.isoformat(),
            "cache_expires_at": (now + timedelta(hours=24)).isoformat(),
        }

        import json

        # Mock Redis get to return awaitable with JSON string
        async def mock_get(key):
            return json.dumps(cached_data, default=str)

        mock_redis.get = mock_get

        response = await analytics_repo.get_pattern_performance(days=30)

        assert response.time_period_days == 30
        assert len(response.patterns) == 1
        assert response.patterns[0].pattern_type == "SPRING"

    @pytest.mark.asyncio
    async def test_cache_miss_queries_database(
        self, analytics_repo: AnalyticsRepository, mock_redis: AsyncMock
    ) -> None:
        """Test that cache miss triggers database query and caches result."""
        mock_redis.get.return_value = None

        response = await analytics_repo.get_pattern_performance(days=30)

        assert isinstance(response, PatternPerformanceResponse)
        assert response.time_period_days == 30
        assert len(response.patterns) == 4  # SPRING, SOS, LPS, UTAD
        assert mock_redis.get.called
        assert mock_redis.setex.called  # Verify data was cached

    @pytest.mark.asyncio
    async def test_no_redis_skips_caching(
        self, analytics_repo_no_cache: AnalyticsRepository
    ) -> None:
        """Test that repository works without Redis caching."""
        response = await analytics_repo_no_cache.get_pattern_performance(days=30)

        assert isinstance(response, PatternPerformanceResponse)
        assert response.time_period_days == 30
        # Should not raise any errors even without Redis

    @pytest.mark.asyncio
    async def test_detection_phase_filter(
        self, analytics_repo: AnalyticsRepository, mock_redis: AsyncMock
    ) -> None:
        """Test filtering by detection phase."""
        mock_redis.get.return_value = None

        response = await analytics_repo.get_pattern_performance(days=30, detection_phase="C")

        assert isinstance(response, PatternPerformanceResponse)
        # Verify phase filter is passed to cache key
        cache_key_calls = [call[0][0] for call in mock_redis.get.call_args_list]
        assert any("C" in key for key in cache_key_calls)


class TestGetWinRateTrend:
    """Test get_win_rate_trend method."""

    @pytest.mark.asyncio
    async def test_returns_trend_data(
        self, analytics_repo: AnalyticsRepository, mock_redis: AsyncMock
    ) -> None:
        """Test that trend data is returned."""
        mock_redis.get.return_value = None

        trend_data = await analytics_repo.get_win_rate_trend(pattern_type="SPRING", days=30)

        assert isinstance(trend_data, list)
        # MVP returns empty list, but structure is correct
        assert mock_redis.get.called

    @pytest.mark.asyncio
    async def test_cache_hit_for_trend(
        self, analytics_repo: AnalyticsRepository, mock_redis: AsyncMock
    ) -> None:
        """Test cache hit for trend data."""
        import json

        cached_trend = [
            {
                "date": "2024-03-01",
                "win_rate": "0.7000",
                "pattern_type": "SPRING",
            }
        ]
        mock_redis.get.return_value = json.dumps(cached_trend)

        trend_data = await analytics_repo.get_win_rate_trend(pattern_type="SPRING", days=30)

        assert len(trend_data) == 1
        assert trend_data[0].win_rate == Decimal("0.7000")


class TestGetTradeDetails:
    """Test get_trade_details method."""

    @pytest.mark.asyncio
    async def test_returns_trade_list_and_count(self, analytics_repo: AnalyticsRepository) -> None:
        """Test that trade details and total count are returned."""
        trades, total_count = await analytics_repo.get_trade_details(
            pattern_type="SPRING", days=30, limit=50, offset=0
        )

        assert isinstance(trades, list)
        assert isinstance(total_count, int)
        assert total_count >= 0

    @pytest.mark.asyncio
    async def test_pagination_parameters(self, analytics_repo: AnalyticsRepository) -> None:
        """Test pagination with limit and offset."""
        trades, total_count = await analytics_repo.get_trade_details(
            pattern_type="SPRING", days=30, limit=10, offset=20
        )

        assert isinstance(trades, list)
        assert len(trades) <= 10  # Respects limit


class TestVSAMetrics:
    """Test get_vsa_metrics method."""

    @pytest.mark.asyncio
    async def test_returns_vsa_metrics(self, analytics_repo: AnalyticsRepository) -> None:
        """Test that VSA metrics are returned."""
        vsa = await analytics_repo.get_vsa_metrics(pattern_type="SPRING", days=30)

        assert vsa.no_demand_count >= 0
        assert vsa.no_supply_count >= 0
        assert vsa.stopping_volume_count >= 0


class TestPreliminaryEvents:
    """Test get_preliminary_events method."""

    @pytest.mark.asyncio
    async def test_returns_preliminary_events(self, analytics_repo: AnalyticsRepository) -> None:
        """Test that preliminary events are returned."""
        events = await analytics_repo.get_preliminary_events(pattern_type="SPRING", days=30)

        assert events.ps_count >= 0
        assert events.sc_count >= 0
        assert events.ar_count >= 0
        assert events.st_count >= 0


class TestCacheOperations:
    """Test Redis cache helper methods."""

    @pytest.mark.asyncio
    async def test_cache_retrieval_failure_returns_none(
        self, analytics_repo: AnalyticsRepository, mock_redis: AsyncMock
    ) -> None:
        """Test that cache retrieval failure is handled gracefully."""
        mock_redis.get.side_effect = Exception("Redis connection error")

        result = await analytics_repo._get_from_cache("test_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_storage_failure_logged(
        self, analytics_repo: AnalyticsRepository, mock_redis: AsyncMock
    ) -> None:
        """Test that cache storage failure is logged but doesn't raise."""
        mock_redis.setex.side_effect = Exception("Redis connection error")

        # Should not raise exception
        await analytics_repo._set_cache("test_key", {"data": "test"})

    @pytest.mark.asyncio
    async def test_cache_ttl_respected(
        self, analytics_repo: AnalyticsRepository, mock_redis: AsyncMock
    ) -> None:
        """Test that cache TTL is set correctly."""
        await analytics_repo._set_cache("test_key", {"data": "test"})

        assert mock_redis.setex.called
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "test_key"
        assert call_args[0][1] == 86400  # TTL
