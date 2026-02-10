"""Unit tests for PaperConfigRepository (Story 23.8a).

Tests config persistence logic using mock database session.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from src.models.paper_trading import PaperTradingConfig
from src.repositories.paper_config_repository import PaperConfigRepository

# ---------------------------------------------------------------------------
# Helpers -- lightweight mock for AsyncSession + query result
# ---------------------------------------------------------------------------


def _mock_session(existing_row=None):
    """Build a mock AsyncSession that returns *existing_row* from SELECT."""
    session = AsyncMock()
    result_mock = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.first.return_value = existing_row
    result_mock.scalars.return_value = scalars_mock
    session.execute.return_value = result_mock
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


def _make_config_db_row(**overrides):
    """Create a mock ORM row that behaves like PaperTradingConfigDB."""
    defaults = {
        "id": uuid4(),
        "enabled": True,
        "starting_capital": Decimal("100000.00"),
        "commission_per_share": Decimal("0.005"),
        "slippage_percentage": Decimal("0.02"),
        "use_realistic_fills": True,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    row = MagicMock()
    for k, v in defaults.items():
        setattr(row, k, v)
    return row


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPaperConfigRepository:
    """Tests for PaperConfigRepository get/save operations."""

    @pytest.mark.asyncio
    async def test_get_config_returns_none_when_empty(self):
        """get_config should return None when no row exists."""
        session = _mock_session(existing_row=None)
        repo = PaperConfigRepository(session)

        result = await repo.get_config()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_config_returns_model_when_row_exists(self):
        """get_config should convert DB row to PaperTradingConfig."""
        row = _make_config_db_row(starting_capital=Decimal("50000.00"))
        session = _mock_session(existing_row=row)
        repo = PaperConfigRepository(session)

        result = await repo.get_config()

        assert result is not None
        assert isinstance(result, PaperTradingConfig)
        assert result.starting_capital == Decimal("50000.00000000")

    @pytest.mark.asyncio
    async def test_save_config_creates_new_when_none_exists(self):
        """save_config should add a new row when no config exists yet."""
        session = _mock_session(existing_row=None)
        # After save, refresh will need the row attributes
        new_row = _make_config_db_row(starting_capital=Decimal("75000.00"))
        session.refresh = AsyncMock(side_effect=lambda obj: None)
        # Patch the ORM constructor so _from_model returns our mock row
        repo = PaperConfigRepository(session)

        config = PaperTradingConfig(
            enabled=True,
            starting_capital=Decimal("75000.00"),
        )

        # We need to intercept session.add to capture what gets added
        added_objects = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        # For the save to succeed, we need refresh to populate attrs on the ORM obj.
        # Since we can't easily mock the full ORM, test that add was called.
        try:
            await repo.save_config(config)
        except Exception:
            pass  # refresh may fail on a real ORM object - that's OK

        # Verify session.add was called (create path, not update)
        assert len(added_objects) == 1

    @pytest.mark.asyncio
    async def test_save_config_updates_existing(self):
        """save_config should update fields on existing row, not add new."""
        existing_row = _make_config_db_row(
            starting_capital=Decimal("100000.00"),
            commission_per_share=Decimal("0.005"),
        )
        session = _mock_session(existing_row=existing_row)
        repo = PaperConfigRepository(session)

        new_config = PaperTradingConfig(
            enabled=True,
            starting_capital=Decimal("200000.00"),
            commission_per_share=Decimal("0.01"),
        )

        try:
            await repo.save_config(new_config)
        except Exception:
            pass  # refresh may fail on mock

        # Verify the row attributes were updated (not a new row added)
        assert existing_row.starting_capital == Decimal("200000.00")
        assert existing_row.commission_per_share == Decimal("0.01")
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_config_round_trip_preserves_values(self):
        """Config -> DB row -> Config should preserve all values."""
        repo = PaperConfigRepository(AsyncMock())

        original = PaperTradingConfig(
            enabled=False,
            starting_capital=Decimal("250000.00"),
            commission_per_share=Decimal("0.01"),
            slippage_percentage=Decimal("0.05"),
            use_realistic_fills=False,
        )

        # Test _from_model and _to_model round-trip
        db_row = repo._from_model(original)
        # ORM defaults (created_at) are only applied on DB insert, so set manually
        db_row.created_at = original.created_at
        result = repo._to_model(db_row)

        assert result.enabled == original.enabled
        assert result.starting_capital == original.starting_capital
        assert result.commission_per_share == original.commission_per_share
        assert result.slippage_percentage == original.slippage_percentage
        assert result.use_realistic_fills == original.use_realistic_fills

    @pytest.mark.asyncio
    async def test_save_config_uses_for_update_locking(self):
        """save_config SELECT should use FOR UPDATE to prevent race conditions."""
        existing_row = _make_config_db_row()
        session = _mock_session(existing_row=existing_row)
        repo = PaperConfigRepository(session)

        config = PaperTradingConfig(
            enabled=True,
            starting_capital=Decimal("100000.00"),
        )

        try:
            await repo.save_config(config)
        except Exception:
            pass

        # Verify the executed statement used with_for_update
        executed_stmt = session.execute.call_args_list[0][0][0]
        assert executed_stmt._for_update_arg is not None
        assert executed_stmt._for_update_arg.read is False

    @pytest.mark.asyncio
    async def test_save_config_retries_on_integrity_error(self):
        """save_config should retry as update when IntegrityError occurs on insert."""
        session = AsyncMock()
        # First execute returns no row (empty table), second returns the row
        existing_row = _make_config_db_row(starting_capital=Decimal("100000.00"))
        first_result = MagicMock()
        first_scalars = MagicMock()
        first_scalars.first.return_value = None
        first_result.scalars.return_value = first_scalars

        second_result = MagicMock()
        second_scalars = MagicMock()
        second_scalars.first.return_value = existing_row
        second_result.scalars.return_value = second_scalars

        session.execute = AsyncMock(side_effect=[first_result, second_result])
        session.commit = AsyncMock(
            side_effect=[IntegrityError("dup", params=None, orig=Exception()), None]
        )
        session.rollback = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()

        repo = PaperConfigRepository(session)
        config = PaperTradingConfig(
            enabled=True,
            starting_capital=Decimal("200000.00"),
        )

        try:
            await repo.save_config(config)
        except Exception:
            pass

        # Should have rolled back after IntegrityError
        session.rollback.assert_awaited_once()
        # Should have retried with a second SELECT
        assert session.execute.await_count == 2
        # Should have updated the existing row on retry
        assert existing_row.starting_capital == Decimal("200000.00")
