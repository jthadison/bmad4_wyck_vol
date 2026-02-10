"""Unit tests for PaperSessionRepository (Story 23.8a).

Tests session archiving, retrieval, and listing with mock database.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.models.paper_trading import PaperAccount, PaperTrade
from src.repositories.paper_session_repository import PaperSessionRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_account(**overrides) -> PaperAccount:
    defaults = {
        "id": uuid4(),
        "starting_capital": Decimal("100000.00"),
        "current_capital": Decimal("95000.00"),
        "equity": Decimal("96000.00"),
        "total_trades": 10,
        "winning_trades": 6,
        "losing_trades": 4,
        "win_rate": Decimal("60.00"),
        "average_r_multiple": Decimal("1.80"),
        "max_drawdown": Decimal("5.00"),
        "current_heat": Decimal("4.00"),
        "paper_trading_start_date": datetime.now(UTC),
    }
    defaults.update(overrides)
    return PaperAccount(**defaults)


def _make_trade(**overrides) -> PaperTrade:
    now = datetime.now(UTC)
    defaults = {
        "position_id": uuid4(),
        "signal_id": uuid4(),
        "symbol": "AAPL",
        "entry_time": now,
        "entry_price": Decimal("150.00"),
        "exit_time": now,
        "exit_price": Decimal("152.00"),
        "quantity": Decimal("100"),
        "realized_pnl": Decimal("196.00"),
        "r_multiple_achieved": Decimal("1.50"),
        "commission_total": Decimal("1.00"),
        "slippage_total": Decimal("3.00"),
        "exit_reason": "TARGET_1",
    }
    defaults.update(overrides)
    return PaperTrade(**defaults)


def _mock_session_db_row(session_id=None, **overrides):
    """Create a mock PaperTradingSessionDB ORM row."""
    now = datetime.now(UTC)
    defaults = {
        "id": session_id or uuid4(),
        "account_snapshot": {"starting_capital": "100000.00"},
        "trades_snapshot": [],
        "final_metrics": {"total_trades": 0},
        "session_start": now,
        "session_end": now,
        "archived_at": now,
    }
    defaults.update(overrides)
    row = MagicMock()
    for k, v in defaults.items():
        setattr(row, k, v)
    return row


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPaperSessionRepository:
    """Tests for PaperSessionRepository."""

    @pytest.mark.asyncio
    async def test_archive_session_stores_data(self):
        """archive_session should add a row and return a UUID."""
        session = AsyncMock()
        added = []
        session.add = MagicMock(side_effect=lambda obj: added.append(obj))

        # Simulate DB commit assigning the id (ORM default only runs on insert)
        async def mock_commit():
            for obj in added:
                if obj.id is None:
                    obj.id = uuid4()

        session.commit = AsyncMock(side_effect=mock_commit)
        session.refresh = AsyncMock()

        repo = PaperSessionRepository(session)
        account = _make_account()
        trades = [_make_trade(), _make_trade(symbol="MSFT")]
        metrics = {"total_trades": 2, "win_rate": 50.0}

        result_id = await repo.archive_session(account, trades, metrics)

        assert result_id is not None
        assert len(added) == 1
        stored = added[0]
        assert len(stored.trades_snapshot) == 2
        assert stored.final_metrics == metrics

    @pytest.mark.asyncio
    async def test_get_session_returns_none_for_unknown_id(self):
        """get_session should return None for non-existent session."""
        session = AsyncMock()
        result_mock = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.first.return_value = None
        result_mock.scalars.return_value = scalars_mock
        session.execute.return_value = result_mock

        repo = PaperSessionRepository(session)
        result = await repo.get_session(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_get_session_returns_dict_for_known_id(self):
        """get_session should convert ORM row to dict."""
        sid = uuid4()
        row = _mock_session_db_row(
            session_id=sid,
            account_snapshot={"equity": "96000.00"},
            trades_snapshot=[{"symbol": "AAPL"}],
            final_metrics={"total_trades": 1},
        )
        session = AsyncMock()
        result_mock = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.first.return_value = row
        result_mock.scalars.return_value = scalars_mock
        session.execute.return_value = result_mock

        repo = PaperSessionRepository(session)
        result = await repo.get_session(sid)

        assert result is not None
        assert result["id"] == str(sid)
        assert result["account_snapshot"] == {"equity": "96000.00"}
        assert "session_start" in result
        assert "archived_at" in result

    @pytest.mark.asyncio
    async def test_list_sessions_pagination(self):
        """list_sessions should return paginated results and total count."""
        rows = [_mock_session_db_row() for _ in range(3)]

        session = AsyncMock()

        # First call: count query
        count_result = MagicMock()
        count_result.scalar.return_value = 3

        # Second call: list query
        list_result = MagicMock()
        list_scalars = MagicMock()
        list_scalars.all.return_value = rows[:2]  # limit=2
        list_result.scalars.return_value = list_scalars

        session.execute = AsyncMock(side_effect=[count_result, list_result])

        repo = PaperSessionRepository(session)
        sessions, total = await repo.list_sessions(limit=2, offset=0)

        assert total == 3
        assert len(sessions) == 2

    @pytest.mark.asyncio
    async def test_archived_session_contains_required_fields(self):
        """Archived session dict should have all expected keys."""
        row = _mock_session_db_row(
            account_snapshot={"capital": "100000"},
            trades_snapshot=[],
            final_metrics={"win_rate": 60.0},
        )

        repo = PaperSessionRepository(AsyncMock())
        result = repo._to_dict(row)

        required_keys = {
            "id",
            "account_snapshot",
            "trades_snapshot",
            "final_metrics",
            "session_start",
            "session_end",
            "archived_at",
        }
        assert required_keys.issubset(set(result.keys()))
        assert isinstance(result["session_start"], str)  # ISO format string
