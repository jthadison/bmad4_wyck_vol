"""
Unit tests for ScannerRepository (Story 20.1).

Tests CRUD operations for scanner persistence:
- Watchlist: add/remove/get/toggle symbols
- Config: get/update singleton config
- History: add/get scan cycle records

Target: ≥85% code coverage

Author: Story 20.1
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

# All tests in this file require a PostgreSQL database (JSONB columns).
pytestmark = pytest.mark.database

from src.models.scanner_persistence import (
    AssetClass,
    ScanCycleStatus,
    ScannerConfigUpdate,
    ScannerHistoryCreate,
    Timeframe,
    validate_symbol,
)
from src.orm.scanner import (
    ScannerConfigORM,
    ScannerHistoryORM,
)
from src.repositories.scanner_repository import ScannerRepository

# =========================================
# Symbol Validation Tests
# =========================================


class TestSymbolValidation:
    """Test symbol validation function."""

    def test_validate_symbol_valid(self):
        """Test valid symbols pass validation."""
        assert validate_symbol("EURUSD") == "EURUSD"
        assert validate_symbol("EUR/USD") == "EUR/USD"
        assert validate_symbol("BTC-USD") == "BTC-USD"
        assert validate_symbol("^SPX") == "^SPX"
        assert validate_symbol("A") == "A"
        assert validate_symbol("12345") == "12345"

    def test_validate_symbol_uppercase(self):
        """Test symbols are uppercased."""
        assert validate_symbol("eurusd") == "EURUSD"
        assert validate_symbol("Eur/Usd") == "EUR/USD"

    def test_validate_symbol_empty_raises(self):
        """Test empty symbol raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_symbol("")

    def test_validate_symbol_too_long_raises(self):
        """Test symbol > 20 chars raises ValueError."""
        with pytest.raises(ValueError, match="1-20 characters"):
            validate_symbol("A" * 21)

    def test_validate_symbol_invalid_chars_raises(self):
        """Test invalid characters raise ValueError."""
        with pytest.raises(ValueError, match="uppercase alphanumeric"):
            validate_symbol("EUR_USD")  # underscore not allowed

        with pytest.raises(ValueError, match="uppercase alphanumeric"):
            validate_symbol("EUR USD")  # space not allowed

        with pytest.raises(ValueError, match="uppercase alphanumeric"):
            validate_symbol("EUR@USD")  # @ not allowed


# =========================================
# Watchlist Add Symbol Tests
# =========================================


class TestAddSymbol:
    """Test ScannerRepository.add_symbol()."""

    @pytest.mark.asyncio
    async def test_add_symbol_success(self, db_session):
        """Test adding a symbol to watchlist."""
        # Create config first (required for foreign keys)
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        result = await repository.add_symbol("EURUSD", "1H", "forex")

        assert result.symbol == "EURUSD"
        assert result.timeframe == Timeframe.H1
        assert result.asset_class == AssetClass.FOREX
        assert result.enabled is True
        assert result.last_scanned_at is None

    @pytest.mark.asyncio
    async def test_add_symbol_uppercase(self, db_session):
        """Test symbol is uppercased on add."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        result = await repository.add_symbol("eurusd", "1H", "forex")

        assert result.symbol == "EURUSD"

    @pytest.mark.asyncio
    async def test_add_symbol_duplicate_raises(self, db_session):
        """Test adding duplicate symbol raises ValueError."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        await repository.add_symbol("EURUSD", "1H", "forex")

        with pytest.raises(ValueError, match="already exists"):
            await repository.add_symbol("EURUSD", "1D", "forex")

    @pytest.mark.asyncio
    async def test_add_symbol_invalid_format_raises(self, db_session):
        """Test adding invalid symbol raises ValueError."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        with pytest.raises(ValueError, match="uppercase alphanumeric"):
            await repository.add_symbol("EUR_USD", "1H", "forex")


# =========================================
# Watchlist Remove Symbol Tests
# =========================================


class TestRemoveSymbol:
    """Test ScannerRepository.remove_symbol()."""

    @pytest.mark.asyncio
    async def test_remove_symbol_success(self, db_session):
        """Test removing an existing symbol."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        await repository.add_symbol("EURUSD", "1H", "forex")

        result = await repository.remove_symbol("EURUSD")

        assert result is True

        # Verify symbol is gone
        symbol = await repository.get_symbol("EURUSD")
        assert symbol is None

    @pytest.mark.asyncio
    async def test_remove_symbol_not_found(self, db_session):
        """Test removing non-existent symbol returns False."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        result = await repository.remove_symbol("NONEXISTENT")

        assert result is False


# =========================================
# Watchlist Get Symbol Tests
# =========================================


class TestGetSymbol:
    """Test ScannerRepository.get_symbol()."""

    @pytest.mark.asyncio
    async def test_get_symbol_exists(self, db_session):
        """Test getting an existing symbol."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        await repository.add_symbol("EURUSD", "1H", "forex")

        result = await repository.get_symbol("EURUSD")

        assert result is not None
        assert result.symbol == "EURUSD"

    @pytest.mark.asyncio
    async def test_get_symbol_not_found(self, db_session):
        """Test getting non-existent symbol returns None."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        result = await repository.get_symbol("NONEXISTENT")

        assert result is None


# =========================================
# Watchlist Get All Symbols Tests
# =========================================


class TestGetAllSymbols:
    """Test ScannerRepository.get_all_symbols()."""

    @pytest.mark.asyncio
    async def test_get_all_symbols(self, db_session):
        """Test getting all symbols."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        await repository.add_symbol("EURUSD", "1H", "forex")
        await repository.add_symbol("AAPL", "1D", "stock")
        await repository.add_symbol("BTCUSD", "4H", "crypto")

        result = await repository.get_all_symbols()

        assert len(result) == 3
        symbols = {s.symbol for s in result}
        assert symbols == {"EURUSD", "AAPL", "BTCUSD"}

    @pytest.mark.asyncio
    async def test_get_all_symbols_empty(self, db_session):
        """Test getting all symbols when empty."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        result = await repository.get_all_symbols()

        assert result == []


# =========================================
# Watchlist Get Enabled Symbols Tests
# =========================================


class TestGetEnabledSymbols:
    """Test ScannerRepository.get_enabled_symbols()."""

    @pytest.mark.asyncio
    async def test_get_enabled_symbols_filters_disabled(self, db_session):
        """Test enabled filter excludes disabled symbols."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        await repository.add_symbol("EURUSD", "1H", "forex")
        await repository.add_symbol("AAPL", "1D", "stock")

        # Disable one symbol
        await repository.toggle_symbol_enabled("AAPL", False)

        result = await repository.get_enabled_symbols()

        assert len(result) == 1
        assert result[0].symbol == "EURUSD"


# =========================================
# Watchlist Symbol Count Tests
# =========================================


class TestGetSymbolCount:
    """Test ScannerRepository.get_symbol_count()."""

    @pytest.mark.asyncio
    async def test_get_symbol_count(self, db_session):
        """Test symbol count."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        assert await repository.get_symbol_count() == 0

        await repository.add_symbol("EURUSD", "1H", "forex")
        assert await repository.get_symbol_count() == 1

        await repository.add_symbol("AAPL", "1D", "stock")
        assert await repository.get_symbol_count() == 2


# =========================================
# Watchlist Toggle Enabled Tests
# =========================================


class TestToggleSymbolEnabled:
    """Test ScannerRepository.toggle_symbol_enabled()."""

    @pytest.mark.asyncio
    async def test_toggle_symbol_enabled(self, db_session):
        """Test toggling enabled state."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        await repository.add_symbol("EURUSD", "1H", "forex")

        # Disable
        result = await repository.toggle_symbol_enabled("EURUSD", False)
        assert result is not None
        assert result.enabled is False

        # Re-enable
        result = await repository.toggle_symbol_enabled("EURUSD", True)
        assert result is not None
        assert result.enabled is True

    @pytest.mark.asyncio
    async def test_toggle_symbol_not_found(self, db_session):
        """Test toggling non-existent symbol returns None."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        result = await repository.toggle_symbol_enabled("NONEXISTENT", False)

        assert result is None


# =========================================
# Watchlist Update Last Scanned Tests
# =========================================


class TestUpdateLastScanned:
    """Test ScannerRepository.update_last_scanned()."""

    @pytest.mark.asyncio
    async def test_update_last_scanned(self, db_session):
        """Test updating last_scanned_at timestamp."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        await repository.add_symbol("EURUSD", "1H", "forex")

        now = datetime.now(UTC)
        await repository.update_last_scanned("EURUSD", now)

        result = await repository.get_symbol("EURUSD")
        assert result is not None
        assert result.last_scanned_at is not None
        # Ensure both datetimes have timezone info for comparison
        result_ts = result.last_scanned_at
        if result_ts.tzinfo is None:
            result_ts = result_ts.replace(tzinfo=UTC)
        # Allow small time difference for test execution
        assert abs((result_ts - now).total_seconds()) < 1


# =========================================
# Config Get Tests
# =========================================


class TestGetConfig:
    """Test ScannerRepository.get_config()."""

    @pytest.mark.asyncio
    async def test_get_config_returns_singleton(self, db_session):
        """Test getting singleton config."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        result = await repository.get_config()

        assert result is not None
        assert result.scan_interval_seconds == 300
        assert result.batch_size == 10
        assert result.session_filter_enabled is True
        assert result.is_running is False

    @pytest.mark.asyncio
    async def test_get_config_missing_raises(self, db_session):
        """Test missing config raises RuntimeError."""
        repository = ScannerRepository(db_session)

        with pytest.raises(RuntimeError, match="config not found"):
            await repository.get_config()


# =========================================
# Config Update Tests
# =========================================


class TestUpdateConfig:
    """Test ScannerRepository.update_config()."""

    @pytest.mark.asyncio
    async def test_update_config_scan_interval(self, db_session):
        """Test updating scan interval."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        updates = ScannerConfigUpdate(scan_interval_seconds=600)
        result = await repository.update_config(updates)

        assert result.scan_interval_seconds == 600

    @pytest.mark.asyncio
    async def test_update_config_batch_size(self, db_session):
        """Test updating batch size."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        updates = ScannerConfigUpdate(batch_size=20)
        result = await repository.update_config(updates)

        assert result.batch_size == 20

    @pytest.mark.asyncio
    async def test_update_config_session_filter(self, db_session):
        """Test updating session filter."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        updates = ScannerConfigUpdate(session_filter_enabled=False)
        result = await repository.update_config(updates)

        assert result.session_filter_enabled is False

    @pytest.mark.asyncio
    async def test_update_config_is_running(self, db_session):
        """Test updating is_running state."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        updates = ScannerConfigUpdate(is_running=True)
        result = await repository.update_config(updates)

        assert result.is_running is True

    @pytest.mark.asyncio
    async def test_update_config_multiple_fields(self, db_session):
        """Test updating multiple fields at once."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        updates = ScannerConfigUpdate(
            scan_interval_seconds=120,
            batch_size=5,
            is_running=True,
        )
        result = await repository.update_config(updates)

        assert result.scan_interval_seconds == 120
        assert result.batch_size == 5
        assert result.is_running is True

    @pytest.mark.asyncio
    async def test_update_config_persists_changes(self, db_session):
        """Test config changes persist."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        updates = ScannerConfigUpdate(scan_interval_seconds=900)
        await repository.update_config(updates)

        # Get fresh config
        result = await repository.get_config()
        assert result.scan_interval_seconds == 900


# =========================================
# Config Set Last Cycle Tests
# =========================================


class TestSetLastCycleAt:
    """Test ScannerRepository.set_last_cycle_at()."""

    @pytest.mark.asyncio
    async def test_set_last_cycle_at(self, db_session):
        """Test setting last cycle timestamp."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        now = datetime.now(UTC)
        await repository.set_last_cycle_at(now)

        result = await repository.get_config()
        assert result.last_cycle_at is not None
        # Ensure both datetimes have timezone info for comparison
        result_ts = result.last_cycle_at
        if result_ts.tzinfo is None:
            result_ts = result_ts.replace(tzinfo=UTC)
        assert abs((result_ts - now).total_seconds()) < 1


# =========================================
# History Add Tests
# =========================================


class TestAddHistory:
    """Test ScannerRepository.add_history()."""

    @pytest.mark.asyncio
    async def test_add_history_success(self, db_session):
        """Test adding history entry."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        now = datetime.now(UTC)
        cycle_data = ScannerHistoryCreate(
            cycle_started_at=now - timedelta(minutes=5),
            cycle_ended_at=now,
            symbols_scanned=10,
            signals_generated=2,
            errors_count=1,
            status=ScanCycleStatus.COMPLETED,
        )

        result = await repository.add_history(cycle_data)

        assert result.symbols_scanned == 10
        assert result.signals_generated == 2
        assert result.errors_count == 1
        assert result.status == ScanCycleStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_add_history_creates_record(self, db_session):
        """Test history entry is persisted."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        now = datetime.now(UTC)
        cycle_data = ScannerHistoryCreate(
            cycle_started_at=now,
            symbols_scanned=5,
            signals_generated=0,
            status=ScanCycleStatus.SKIPPED,
        )

        await repository.add_history(cycle_data)

        # Verify in database
        stmt = select(ScannerHistoryORM)
        result = await db_session.execute(stmt)
        entries = result.scalars().all()

        assert len(entries) == 1
        assert entries[0].status == "SKIPPED"


# =========================================
# History Get Tests
# =========================================


class TestGetHistory:
    """Test ScannerRepository.get_history()."""

    @pytest.mark.asyncio
    async def test_get_history_ordered_by_date_desc(self, db_session):
        """Test history is ordered by date descending."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        # Add entries with different times
        base_time = datetime.now(UTC)
        for i in range(3):
            cycle_data = ScannerHistoryCreate(
                cycle_started_at=base_time - timedelta(hours=i),
                symbols_scanned=i + 1,
                signals_generated=0,
                status=ScanCycleStatus.COMPLETED,
            )
            await repository.add_history(cycle_data)

        result = await repository.get_history()

        assert len(result) == 3
        # Most recent first
        assert result[0].symbols_scanned == 1
        assert result[1].symbols_scanned == 2
        assert result[2].symbols_scanned == 3

    @pytest.mark.asyncio
    async def test_get_history_respects_limit(self, db_session):
        """Test history limit parameter."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        # Add 10 entries
        base_time = datetime.now(UTC)
        for i in range(10):
            cycle_data = ScannerHistoryCreate(
                cycle_started_at=base_time - timedelta(hours=i),
                symbols_scanned=i,
                signals_generated=0,
                status=ScanCycleStatus.COMPLETED,
            )
            await repository.add_history(cycle_data)

        # Get only 5
        result = await repository.get_history(limit=5)

        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_get_history_empty(self, db_session):
        """Test getting history when empty."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        result = await repository.get_history()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_history_includes_correlation_ids(self, db_session):
        """Test that correlation_ids are persisted and retrieved (M-3)."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        # Create history with correlation_ids
        correlation_ids = ["11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"]
        history_data = ScannerHistoryCreate(
            cycle_started_at=datetime.now(UTC),
            cycle_ended_at=datetime.now(UTC),
            symbols_scanned=2,
            signals_generated=2,
            errors_count=0,
            status=ScanCycleStatus.COMPLETED,
            correlation_ids=correlation_ids,  # Task #25
        )

        created_history = await repository.add_history(history_data)

        # Verify correlation_ids were persisted
        assert created_history.correlation_ids == correlation_ids

        # Verify correlation_ids are retrieved
        history_list = await repository.get_history(limit=1)
        assert len(history_list) == 1
        assert history_list[0].correlation_ids == correlation_ids

    @pytest.mark.asyncio
    async def test_get_history_handles_null_correlation_ids(self, db_session):
        """Test that NULL correlation_ids (old records) are handled gracefully (M-3)."""
        await _create_singleton_config(db_session)

        repository = ScannerRepository(db_session)

        # Create history without correlation_ids (simulating old records)
        history_data = ScannerHistoryCreate(
            cycle_started_at=datetime.now(UTC),
            cycle_ended_at=datetime.now(UTC),
            symbols_scanned=0,
            signals_generated=0,
            errors_count=0,
            status=ScanCycleStatus.COMPLETED,
            correlation_ids=None,  # Explicitly None
        )

        created_history = await repository.add_history(history_data)

        # Verify None is handled
        assert created_history.correlation_ids is None

        # Verify retrieval doesn't crash
        history_list = await repository.get_history(limit=1)
        assert len(history_list) == 1
        assert history_list[0].correlation_ids is None


# =========================================
# Helper Functions
# =========================================


async def _create_singleton_config(session) -> None:
    """
    Create singleton scanner config for tests.

    This mimics what the migration does.
    """
    orm_config = ScannerConfigORM(
        scan_interval_seconds=300,
        batch_size=10,
        session_filter_enabled=True,
        is_running=False,
        last_cycle_at=None,
        updated_at=datetime.now(UTC),
    )
    session.add(orm_config)
    await session.commit()
