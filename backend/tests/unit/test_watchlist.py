"""
Unit tests for Watchlist Management (Story 19.12)

Tests watchlist models, repository, and service operations.
Repository/Service tests use mocks to avoid database dependencies.

Author: Story 19.12
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from src.models.watchlist import (
    DEFAULT_WATCHLIST_SYMBOLS,
    MAX_WATCHLIST_SYMBOLS,
    AddSymbolRequest,
    UpdateSymbolRequest,
    WatchlistEntry,
    WatchlistPriority,
    WatchlistResponse,
)
from src.services.watchlist_service import WatchlistService

# Test user ID
TEST_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


class TestWatchlistModels:
    """Test Pydantic models for watchlist."""

    def test_watchlist_entry_defaults(self):
        """Test WatchlistEntry default values."""
        entry = WatchlistEntry(
            symbol="AAPL",
            added_at=datetime.now(UTC),
        )

        assert entry.symbol == "AAPL"
        assert entry.priority == WatchlistPriority.MEDIUM
        assert entry.min_confidence is None
        assert entry.enabled is True

    def test_watchlist_entry_uppercase_symbol(self):
        """Test symbol is converted to uppercase."""
        entry = WatchlistEntry(
            symbol="aapl",
            added_at=datetime.now(UTC),
        )

        assert entry.symbol == "AAPL"

    def test_watchlist_entry_with_all_fields(self):
        """Test WatchlistEntry with all fields specified."""
        now = datetime.now(UTC)
        entry = WatchlistEntry(
            symbol="TSLA",
            priority=WatchlistPriority.HIGH,
            min_confidence=Decimal("85.50"),
            enabled=False,
            added_at=now,
        )

        assert entry.symbol == "TSLA"
        assert entry.priority == WatchlistPriority.HIGH
        assert entry.min_confidence == Decimal("85.50")
        assert entry.enabled is False
        assert entry.added_at == now

    def test_add_symbol_request_validation(self):
        """Test AddSymbolRequest validation."""
        request = AddSymbolRequest(
            symbol="googl",
            priority=WatchlistPriority.HIGH,
            min_confidence=Decimal("85.0"),
        )

        assert request.symbol == "GOOGL"
        assert request.priority == WatchlistPriority.HIGH
        assert request.min_confidence == Decimal("85.0")

    def test_add_symbol_request_defaults(self):
        """Test AddSymbolRequest default values."""
        request = AddSymbolRequest(symbol="AAPL")

        assert request.symbol == "AAPL"
        assert request.priority == WatchlistPriority.MEDIUM
        assert request.min_confidence is None

    def test_add_symbol_request_min_confidence_range(self):
        """Test min_confidence must be 0-100."""
        with pytest.raises(ValueError):
            AddSymbolRequest(
                symbol="AAPL",
                min_confidence=Decimal("150.0"),  # Out of range
            )

        with pytest.raises(ValueError):
            AddSymbolRequest(
                symbol="AAPL",
                min_confidence=Decimal("-10.0"),  # Negative
            )

    def test_add_symbol_request_invalid_format(self):
        """Test symbol format validation rejects invalid symbols."""
        # Invalid: special characters
        with pytest.raises(ValueError, match="Invalid symbol format"):
            AddSymbolRequest(symbol="!@#$%")

        # Invalid: numeric only
        with pytest.raises(ValueError, match="Invalid symbol format"):
            AddSymbolRequest(symbol="12345")

        # Invalid: too long
        with pytest.raises(ValueError, match="Invalid symbol format"):
            AddSymbolRequest(symbol="ABCDEFG")

    def test_add_symbol_request_valid_formats(self):
        """Test symbol format validation accepts valid symbols."""
        # Standard symbols
        assert AddSymbolRequest(symbol="AAPL").symbol == "AAPL"
        assert AddSymbolRequest(symbol="A").symbol == "A"
        assert AddSymbolRequest(symbol="GOOG").symbol == "GOOG"

        # Share class symbols (e.g., BRK.A, BRK.B)
        assert AddSymbolRequest(symbol="BRK.A").symbol == "BRK.A"
        assert AddSymbolRequest(symbol="BRK.B").symbol == "BRK.B"

    def test_update_symbol_request_all_optional(self):
        """Test UpdateSymbolRequest allows all fields optional."""
        request = UpdateSymbolRequest()

        assert request.priority is None
        assert request.min_confidence is None
        assert request.enabled is None

    def test_update_symbol_request_partial(self):
        """Test UpdateSymbolRequest with partial fields."""
        request = UpdateSymbolRequest(
            priority=WatchlistPriority.LOW,
            enabled=False,
        )

        assert request.priority == WatchlistPriority.LOW
        assert request.min_confidence is None
        assert request.enabled is False

    def test_watchlist_response_structure(self):
        """Test WatchlistResponse structure."""
        entry = WatchlistEntry(
            symbol="AAPL",
            added_at=datetime.now(UTC),
        )
        response = WatchlistResponse(
            symbols=[entry],
            count=1,
            max_allowed=100,
        )

        assert len(response.symbols) == 1
        assert response.count == 1
        assert response.max_allowed == 100

    def test_watchlist_response_empty(self):
        """Test WatchlistResponse with no symbols."""
        response = WatchlistResponse(
            symbols=[],
            count=0,
            max_allowed=100,
        )

        assert len(response.symbols) == 0
        assert response.count == 0

    def test_watchlist_priority_values(self):
        """Test WatchlistPriority enum values."""
        assert WatchlistPriority.LOW.value == "low"
        assert WatchlistPriority.MEDIUM.value == "medium"
        assert WatchlistPriority.HIGH.value == "high"


class TestWatchlistServiceWithMocks:
    """Test watchlist service business logic with mocked repository."""

    @pytest.fixture
    def mock_repository(self):
        """Create mock repository."""
        repo = MagicMock()
        repo.get_watchlist = AsyncMock(return_value=[])
        repo.get_enabled_symbols = AsyncMock(return_value=[])
        repo.add_symbol = AsyncMock()
        repo.add_symbols_batch = AsyncMock()
        repo.remove_symbol = AsyncMock()
        repo.update_symbol = AsyncMock()
        repo.count_symbols = AsyncMock(return_value=0)
        repo.symbol_exists = AsyncMock(return_value=False)
        repo.get_symbol = AsyncMock(return_value=None)
        return repo

    @pytest.fixture
    def watchlist_service(self, mock_repository):
        """Create watchlist service with mock repository."""
        return WatchlistService(repository=mock_repository)

    @pytest.mark.asyncio
    async def test_get_watchlist_initializes_defaults_when_empty(
        self, watchlist_service, mock_repository
    ):
        """Test getting watchlist initializes defaults for new user."""
        # Arrange
        mock_repository.get_watchlist.return_value = []
        mock_entries = [
            WatchlistEntry(symbol=s, added_at=datetime.now(UTC)) for s in DEFAULT_WATCHLIST_SYMBOLS
        ]
        mock_repository.add_symbols_batch.return_value = mock_entries

        # Act
        response = await watchlist_service.get_watchlist(TEST_USER_ID)

        # Assert
        mock_repository.add_symbols_batch.assert_called_once()
        assert response.count == len(DEFAULT_WATCHLIST_SYMBOLS)

    @pytest.mark.asyncio
    async def test_get_watchlist_returns_existing(self, watchlist_service, mock_repository):
        """Test getting existing watchlist."""
        # Arrange
        existing_entries = [
            WatchlistEntry(symbol="AAPL", added_at=datetime.now(UTC)),
            WatchlistEntry(symbol="TSLA", added_at=datetime.now(UTC)),
        ]
        mock_repository.get_watchlist.return_value = existing_entries

        # Act
        response = await watchlist_service.get_watchlist(TEST_USER_ID)

        # Assert
        mock_repository.add_symbols_batch.assert_not_called()
        assert response.count == 2
        assert response.symbols[0].symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_add_symbol_without_validation(self, watchlist_service, mock_repository):
        """Test adding symbol without validation."""
        # Arrange
        new_entry = WatchlistEntry(
            symbol="NVDA",
            priority=WatchlistPriority.HIGH,
            added_at=datetime.now(UTC),
        )
        mock_repository.add_symbol.return_value = new_entry

        # Act
        entry = await watchlist_service.add_symbol(
            user_id=TEST_USER_ID,
            symbol="NVDA",
            priority=WatchlistPriority.HIGH,
            validate=False,
        )

        # Assert
        assert entry.symbol == "NVDA"
        assert entry.priority == WatchlistPriority.HIGH
        mock_repository.add_symbol.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_symbol_with_min_confidence(self, watchlist_service, mock_repository):
        """Test adding symbol with min_confidence."""
        # Arrange
        new_entry = WatchlistEntry(
            symbol="GOOGL",
            min_confidence=Decimal("80.0"),
            added_at=datetime.now(UTC),
        )
        mock_repository.add_symbol.return_value = new_entry

        # Act
        entry = await watchlist_service.add_symbol(
            user_id=TEST_USER_ID,
            symbol="GOOGL",
            min_confidence=Decimal("80.0"),
            validate=False,
        )

        # Assert
        assert entry.symbol == "GOOGL"
        assert entry.min_confidence == Decimal("80.0")

    @pytest.mark.asyncio
    async def test_remove_symbol_success(self, watchlist_service, mock_repository):
        """Test removing symbol."""
        # Arrange
        mock_repository.remove_symbol.return_value = True

        # Act
        removed = await watchlist_service.remove_symbol(TEST_USER_ID, "AAPL")

        # Assert
        assert removed is True
        mock_repository.remove_symbol.assert_called_once_with(TEST_USER_ID, "AAPL")

    @pytest.mark.asyncio
    async def test_remove_symbol_not_found(self, watchlist_service, mock_repository):
        """Test removing nonexistent symbol."""
        # Arrange
        mock_repository.remove_symbol.return_value = False

        # Act
        removed = await watchlist_service.remove_symbol(TEST_USER_ID, "NONEXISTENT")

        # Assert
        assert removed is False

    @pytest.mark.asyncio
    async def test_update_symbol_success(self, watchlist_service, mock_repository):
        """Test updating symbol."""
        # Arrange
        updated_entry = WatchlistEntry(
            symbol="AAPL",
            priority=WatchlistPriority.HIGH,
            enabled=False,
            added_at=datetime.now(UTC),
        )
        mock_repository.update_symbol.return_value = updated_entry

        # Act
        entry = await watchlist_service.update_symbol(
            user_id=TEST_USER_ID,
            symbol="AAPL",
            priority=WatchlistPriority.HIGH,
            enabled=False,
        )

        # Assert
        assert entry is not None
        assert entry.priority == WatchlistPriority.HIGH
        assert entry.enabled is False

    @pytest.mark.asyncio
    async def test_update_symbol_not_found(self, watchlist_service, mock_repository):
        """Test updating nonexistent symbol."""
        # Arrange
        mock_repository.update_symbol.return_value = None

        # Act
        entry = await watchlist_service.update_symbol(
            user_id=TEST_USER_ID,
            symbol="NONEXISTENT",
            priority=WatchlistPriority.HIGH,
        )

        # Assert
        assert entry is None

    @pytest.mark.asyncio
    async def test_validate_symbol_no_coordinator(self, watchlist_service):
        """Test symbol validation returns True when no coordinator."""
        # Act
        is_valid = await watchlist_service.validate_symbol("AAPL")

        # Assert
        assert is_valid is True  # Defaults to True when no coordinator

    @pytest.mark.asyncio
    async def test_validate_symbol_with_coordinator(self, mock_repository):
        """Test symbol validation with mock coordinator."""
        # Arrange
        mock_coordinator = AsyncMock()
        mock_coordinator.validate_symbol = AsyncMock(return_value=True)

        service = WatchlistService(
            repository=mock_repository,
            market_data_coordinator=mock_coordinator,
        )

        # Act
        is_valid = await service.validate_symbol("AAPL")

        # Assert
        assert is_valid is True
        mock_coordinator.validate_symbol.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_validate_symbol_coordinator_returns_false(self, mock_repository):
        """Test symbol validation when coordinator returns False."""
        # Arrange
        mock_coordinator = AsyncMock()
        mock_coordinator.validate_symbol = AsyncMock(return_value=False)

        service = WatchlistService(
            repository=mock_repository,
            market_data_coordinator=mock_coordinator,
        )

        # Act
        is_valid = await service.validate_symbol("INVALID")

        # Assert
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_validate_symbol_coordinator_error(self, mock_repository):
        """Test symbol validation when coordinator raises error."""
        # Arrange
        mock_coordinator = AsyncMock()
        mock_coordinator.validate_symbol = AsyncMock(side_effect=Exception("API error"))

        service = WatchlistService(
            repository=mock_repository,
            market_data_coordinator=mock_coordinator,
        )

        # Act
        is_valid = await service.validate_symbol("AAPL")

        # Assert - defaults to True on error
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_get_enabled_symbols(self, watchlist_service, mock_repository):
        """Test getting enabled symbols."""
        # Arrange
        mock_repository.get_enabled_symbols.return_value = ["AAPL", "TSLA"]

        # Act
        symbols = await watchlist_service.get_enabled_symbols(TEST_USER_ID)

        # Assert
        assert "AAPL" in symbols
        assert "TSLA" in symbols


class TestWatchlistLimits:
    """Test watchlist limits and constraints."""

    def test_default_watchlist_symbols_count(self):
        """Test default watchlist has expected symbols."""
        assert len(DEFAULT_WATCHLIST_SYMBOLS) == 7
        assert "AAPL" in DEFAULT_WATCHLIST_SYMBOLS
        assert "TSLA" in DEFAULT_WATCHLIST_SYMBOLS
        assert "SPY" in DEFAULT_WATCHLIST_SYMBOLS
        assert "QQQ" in DEFAULT_WATCHLIST_SYMBOLS
        assert "NVDA" in DEFAULT_WATCHLIST_SYMBOLS
        assert "MSFT" in DEFAULT_WATCHLIST_SYMBOLS
        assert "AMZN" in DEFAULT_WATCHLIST_SYMBOLS

    def test_max_watchlist_symbols_value(self):
        """Test max watchlist symbols is 100."""
        assert MAX_WATCHLIST_SYMBOLS == 100


class TestWatchlistEntryTimezone:
    """Test timezone handling in WatchlistEntry."""

    def test_added_at_utc_conversion(self):
        """Test added_at is converted to UTC."""
        # Arrange - create datetime without timezone
        naive_dt = datetime(2026, 1, 15, 10, 30, 0)

        # Act
        entry = WatchlistEntry(
            symbol="AAPL",
            added_at=naive_dt,
        )

        # Assert - should be converted to UTC
        assert entry.added_at.tzinfo is not None or entry.added_at.tzinfo == UTC

    def test_added_at_iso_string(self):
        """Test added_at accepts ISO string."""
        # Arrange
        iso_string = "2026-01-15T10:30:00Z"

        # Act
        entry = WatchlistEntry(
            symbol="AAPL",
            added_at=iso_string,
        )

        # Assert
        assert entry.added_at.year == 2026
        assert entry.added_at.month == 1
        assert entry.added_at.day == 15
