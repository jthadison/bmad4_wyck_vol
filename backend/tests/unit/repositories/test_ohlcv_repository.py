"""
Unit tests for OHLCVRepository.

Uses mocked database session to test repository methods without actual database.
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from src.models.ohlcv import OHLCVBar
from src.repositories.ohlcv_repository import OHLCVRepository


@pytest.fixture
def mock_session():
    """Create a mock async database session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def repository(mock_session):
    """Create OHLCVRepository with mocked session."""
    return OHLCVRepository(mock_session)


@pytest.fixture
def sample_bar():
    """Create a sample OHLCV bar for testing."""
    return OHLCVBar(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        open=Decimal("150.00"),
        high=Decimal("155.00"),
        low=Decimal("148.00"),
        close=Decimal("153.00"),
        volume=1000000,
        spread=Decimal("7.00"),
        spread_ratio=Decimal("1.2"),
        volume_ratio=Decimal("0.9"),
    )


class TestInsertBar:
    """Test insert_bar method."""

    @pytest.mark.asyncio
    async def test_insert_bar_success(self, repository, mock_session, sample_bar):
        """Test successful insertion of single bar."""
        # Mock successful insert (rowcount = 1)
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        bar_id = await repository.insert_bar(sample_bar)

        # Verify bar_id returned
        assert bar_id == str(sample_bar.id)

        # Verify session methods called
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert_bar_duplicate_skipped(self, repository, mock_session, sample_bar):
        """Test that duplicate bar returns None."""
        # Mock duplicate (rowcount = 0)
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result

        bar_id = await repository.insert_bar(sample_bar)

        # Duplicate should return None
        assert bar_id is None

        # Commit should still be called
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert_bar_exception_rollback(self, repository, mock_session, sample_bar):
        """Test that exception triggers rollback."""
        # Mock exception during execute
        mock_session.execute.side_effect = IntegrityError("mock", "mock", "mock")

        with pytest.raises(IntegrityError):
            await repository.insert_bar(sample_bar)

        # Verify rollback called
        mock_session.rollback.assert_called_once()


class TestInsertBars:
    """Test insert_bars bulk method."""

    @pytest.mark.asyncio
    async def test_insert_bars_empty_list(self, repository, mock_session):
        """Test inserting empty list returns 0."""
        count = await repository.insert_bars([])

        assert count == 0
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_insert_bars_success(self, repository, mock_session, sample_bar):
        """Test bulk insert of multiple bars."""
        bars = [sample_bar] * 3

        # Mock successful bulk insert
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_session.execute.return_value = mock_result

        count = await repository.insert_bars(bars)

        assert count == 3
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert_bars_partial_duplicates(self, repository, mock_session, sample_bar):
        """Test bulk insert with some duplicates."""
        bars = [sample_bar] * 5

        # Mock 3 inserted, 2 duplicates skipped
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_session.execute.return_value = mock_result

        count = await repository.insert_bars(bars)

        assert count == 3  # Only 3 inserted


class TestGetBars:
    """Test get_bars method."""

    @pytest.mark.asyncio
    async def test_get_bars_empty_result(self, repository, mock_session):
        """Test get_bars returns empty list when no data."""
        # Mock empty result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        bars = await repository.get_bars(
            "AAPL",
            "1d",
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 31, tzinfo=timezone.utc),
        )

        assert bars == []
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_bars_returns_data(self, repository, mock_session, sample_bar):
        """Test get_bars returns bars from database."""
        # Mock database models
        mock_db_model = MagicMock()
        mock_db_model.id = sample_bar.id
        mock_db_model.symbol = sample_bar.symbol
        mock_db_model.timeframe = sample_bar.timeframe
        mock_db_model.timestamp = sample_bar.timestamp
        mock_db_model.open = sample_bar.open
        mock_db_model.high = sample_bar.high
        mock_db_model.low = sample_bar.low
        mock_db_model.close = sample_bar.close
        mock_db_model.volume = sample_bar.volume
        mock_db_model.spread = sample_bar.spread
        mock_db_model.spread_ratio = sample_bar.spread_ratio
        mock_db_model.volume_ratio = sample_bar.volume_ratio
        mock_db_model.created_at = sample_bar.created_at

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_db_model]
        mock_session.execute.return_value = mock_result

        bars = await repository.get_bars(
            "AAPL",
            "1d",
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 31, tzinfo=timezone.utc),
        )

        assert len(bars) == 1
        assert bars[0].symbol == "AAPL"


class TestGetLatestBars:
    """Test get_latest_bars method."""

    @pytest.mark.asyncio
    async def test_get_latest_bars_returns_chronological_order(self, repository, mock_session):
        """Test that latest bars are returned in chronological order (oldest first)."""
        # Create mock bars (returned in DESC order from DB)
        mock_bars = []
        for i in range(3, 0, -1):  # 3, 2, 1
            mock_bar = MagicMock()
            mock_bar.id = uuid4()
            mock_bar.symbol = "AAPL"
            mock_bar.timeframe = "1d"
            mock_bar.timestamp = datetime(2024, 1, i, tzinfo=timezone.utc)
            mock_bar.open = Decimal("150.00")
            mock_bar.high = Decimal("155.00")
            mock_bar.low = Decimal("148.00")
            mock_bar.close = Decimal("153.00")
            mock_bar.volume = 1000000
            mock_bar.spread = Decimal("7.00")
            mock_bar.spread_ratio = Decimal("1.0")
            mock_bar.volume_ratio = Decimal("1.0")
            mock_bar.created_at = datetime.now(timezone.utc)
            mock_bars.append(mock_bar)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_bars
        mock_session.execute.return_value = mock_result

        bars = await repository.get_latest_bars("AAPL", "1d", count=3)

        # Should be reversed to chronological order
        assert len(bars) == 3
        assert bars[0].timestamp == datetime(2024, 1, 1, tzinfo=timezone.utc)
        assert bars[1].timestamp == datetime(2024, 1, 2, tzinfo=timezone.utc)
        assert bars[2].timestamp == datetime(2024, 1, 3, tzinfo=timezone.utc)


class TestBarExists:
    """Test bar_exists method."""

    @pytest.mark.asyncio
    async def test_bar_exists_returns_true(self, repository, mock_session):
        """Test bar_exists returns True when bar exists."""
        # Mock EXISTS query returning True
        mock_result = MagicMock()
        mock_result.scalar.return_value = True
        mock_session.execute.return_value = mock_result

        exists = await repository.bar_exists(
            "AAPL",
            "1d",
            datetime(2024, 1, 1, tzinfo=timezone.utc),
        )

        assert exists is True

    @pytest.mark.asyncio
    async def test_bar_exists_returns_false(self, repository, mock_session):
        """Test bar_exists returns False when bar doesn't exist."""
        # Mock EXISTS query returning False
        mock_result = MagicMock()
        mock_result.scalar.return_value = False
        mock_session.execute.return_value = mock_result

        exists = await repository.bar_exists(
            "AAPL",
            "1d",
            datetime(2024, 1, 1, tzinfo=timezone.utc),
        )

        assert exists is False


class TestCountBars:
    """Test count_bars method."""

    @pytest.mark.asyncio
    async def test_count_bars_returns_count(self, repository, mock_session):
        """Test count_bars returns correct count."""
        # Mock COUNT query returning 252
        mock_result = MagicMock()
        mock_result.scalar.return_value = 252
        mock_session.execute.return_value = mock_result

        count = await repository.count_bars("AAPL", "1d")

        assert count == 252

    @pytest.mark.asyncio
    async def test_count_bars_zero_when_empty(self, repository, mock_session):
        """Test count_bars returns 0 when no bars."""
        # Mock COUNT query returning None (no rows)
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_session.execute.return_value = mock_result

        count = await repository.count_bars("AAPL", "1d")

        assert count == 0


class TestIterBars:
    """Test iter_bars method."""

    def test_iter_bars_returns_iterator(self, repository):
        """Test that iter_bars returns BarIterator."""
        from src.repositories.bar_iterator import BarIterator

        iterator = repository.iter_bars(
            "AAPL",
            "1d",
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 12, 31, tzinfo=timezone.utc),
            batch_size=100,
        )

        assert isinstance(iterator, BarIterator)
        assert iterator.symbol == "AAPL"
        assert iterator.timeframe == "1d"
        assert iterator.batch_size == 100
