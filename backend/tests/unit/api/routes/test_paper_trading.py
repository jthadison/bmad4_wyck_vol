"""Unit tests for paper trading API routes (Story 23.8a).

Tests settings endpoints, backtest comparison endpoints, and session
archiving endpoints using mock repositories.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.models.paper_trading import (
    PaperAccount,
    PaperTrade,
    PaperTradingConfig,
)

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


# ---------------------------------------------------------------------------
# Mock repositories
# ---------------------------------------------------------------------------


class MockPaperConfigRepository:
    def __init__(self, config=None):
        self.config = config

    async def get_config(self):
        return self.config

    async def save_config(self, config):
        self.config = config
        return config


class MockPaperSessionRepository:
    def __init__(self):
        self.sessions: dict[str, dict] = {}

    async def archive_session(self, account, trades, metrics):
        session_id = uuid4()
        self.sessions[str(session_id)] = {
            "id": str(session_id),
            "account_snapshot": account.model_dump(mode="json"),
            "trades_snapshot": [t.model_dump(mode="json") for t in trades],
            "final_metrics": metrics,
            "session_start": datetime.now(UTC).isoformat(),
            "session_end": datetime.now(UTC).isoformat(),
            "archived_at": datetime.now(UTC).isoformat(),
        }
        return session_id

    async def get_session(self, session_id):
        return self.sessions.get(str(session_id))

    async def list_sessions(self, limit=50, offset=0):
        all_sessions = list(self.sessions.values())
        return all_sessions[offset : offset + limit], len(all_sessions)


# ---------------------------------------------------------------------------
# Settings endpoint tests
# ---------------------------------------------------------------------------


class TestGetSettings:
    """Tests for GET /settings."""

    @pytest.mark.asyncio
    async def test_get_settings_returns_defaults_when_no_config_saved(self):
        """When no config exists in DB, should return default PaperTradingConfig."""
        from src.api.routes.paper_trading import get_settings

        mock_db = AsyncMock()
        mock_config_repo = MockPaperConfigRepository(config=None)

        with patch(
            "src.api.routes.paper_trading.PaperConfigRepository",
            return_value=mock_config_repo,
        ):
            result = await get_settings(db=mock_db, _user_id=uuid4())

        assert isinstance(result, PaperTradingConfig)
        assert result.enabled is True
        assert result.starting_capital == Decimal("100000.00000000")

    @pytest.mark.asyncio
    async def test_get_settings_returns_saved_config(self):
        """When a config exists, should return it directly."""
        from src.api.routes.paper_trading import get_settings

        saved = PaperTradingConfig(
            enabled=True,
            starting_capital=Decimal("50000.00"),
            commission_per_share=Decimal("0.01"),
            slippage_percentage=Decimal("0.05"),
            use_realistic_fills=False,
        )
        mock_config_repo = MockPaperConfigRepository(config=saved)
        mock_db = AsyncMock()

        with patch(
            "src.api.routes.paper_trading.PaperConfigRepository",
            return_value=mock_config_repo,
        ):
            result = await get_settings(db=mock_db, _user_id=uuid4())

        assert result.starting_capital == Decimal("50000.00000000")
        assert result.use_realistic_fills is False


class TestUpdateSettings:
    """Tests for PUT /settings."""

    @pytest.mark.asyncio
    async def test_update_settings_saves_config(self):
        """Updating settings should persist the new config."""
        from src.api.routes.paper_trading import (
            PaperTradingSettingsRequest,
            update_settings,
        )

        mock_config_repo = MockPaperConfigRepository(config=None)
        mock_db = AsyncMock()

        request = PaperTradingSettingsRequest(
            starting_capital=Decimal("200000.00"),
            commission_per_share=Decimal("0.01"),
            slippage_percentage=Decimal("0.03"),
            use_realistic_fills=True,
        )

        with patch(
            "src.api.routes.paper_trading.PaperConfigRepository",
            return_value=mock_config_repo,
        ):
            result = await update_settings(request=request, db=mock_db, _user_id=uuid4())

        assert result.starting_capital == Decimal("200000.00000000")
        assert result.commission_per_share == Decimal("0.01000000")
        # Config should have been persisted in the mock
        assert mock_config_repo.config is not None


# ---------------------------------------------------------------------------
# Compare endpoint tests
# ---------------------------------------------------------------------------


class TestCompareEndpoint:
    """Tests for GET /compare/{backtest_id}."""

    @pytest.mark.asyncio
    async def test_compare_endpoint_returns_404_when_no_account(self):
        """Should return 404 if paper trading is not enabled (no account)."""
        from fastapi import HTTPException

        from src.api.routes.paper_trading import compare_to_backtest

        mock_service = AsyncMock()
        mock_service.account_repo = AsyncMock()
        mock_service.account_repo.get_account = AsyncMock(return_value=None)
        mock_db = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await compare_to_backtest(
                backtest_id=uuid4(), db=mock_db, service=mock_service, _user_id=uuid4()
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_compare_endpoint_returns_404_when_backtest_not_found(self):
        """Should return 404 if the given backtest_id does not exist."""
        from fastapi import HTTPException

        from src.api.routes.paper_trading import compare_to_backtest

        account = _make_account()
        mock_service = AsyncMock()
        mock_service.account_repo = AsyncMock()
        mock_service.account_repo.get_account = AsyncMock(return_value=account)
        mock_db = AsyncMock()

        mock_backtest_repo = AsyncMock()
        mock_backtest_repo.get_result = AsyncMock(return_value=None)

        with (
            patch(
                "src.repositories.backtest_repository.BacktestRepository",
                return_value=mock_backtest_repo,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await compare_to_backtest(
                backtest_id=uuid4(), db=mock_db, service=mock_service, _user_id=uuid4()
            )

        assert exc_info.value.status_code == 404


class TestReportEndpoint:
    """Tests for GET /report."""

    @pytest.mark.asyncio
    async def test_report_includes_backtest_comparison_when_id_provided(self):
        """Report should include backtest_comparison dict when backtest_id given."""
        from src.api.routes.paper_trading import get_report

        account = _make_account()
        comparison_result = {"status": "OK", "deltas": {}, "warnings": [], "errors": []}

        mock_service = AsyncMock()
        mock_service.account_repo = AsyncMock()
        mock_service.account_repo.get_account = AsyncMock(return_value=account)
        mock_service.calculate_performance_metrics = AsyncMock(return_value={"total_trades": 10})
        mock_service.validate_live_trading_eligibility = AsyncMock(return_value={"eligible": False})
        mock_service.compare_to_backtest = AsyncMock(return_value=comparison_result)

        mock_db = AsyncMock()
        mock_backtest_repo = AsyncMock()
        mock_backtest_repo.get_result = AsyncMock(return_value=MagicMock())

        backtest_id = uuid4()

        with patch(
            "src.repositories.backtest_repository.BacktestRepository",
            return_value=mock_backtest_repo,
        ):
            result = await get_report(
                backtest_id=backtest_id, db=mock_db, service=mock_service, _user_id=uuid4()
            )

        assert result.backtest_comparison == comparison_result
        mock_service.compare_to_backtest.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_report_no_comparison_when_no_backtest_id(self):
        """Report should have None backtest_comparison when no backtest_id."""
        from src.api.routes.paper_trading import get_report

        account = _make_account()
        mock_service = AsyncMock()
        mock_service.account_repo = AsyncMock()
        mock_service.account_repo.get_account = AsyncMock(return_value=account)
        mock_service.calculate_performance_metrics = AsyncMock(return_value={"total_trades": 10})
        mock_service.validate_live_trading_eligibility = AsyncMock(return_value={"eligible": False})

        mock_db = AsyncMock()

        result = await get_report(
            backtest_id=None, db=mock_db, service=mock_service, _user_id=uuid4()
        )

        assert result.backtest_comparison is None


# ---------------------------------------------------------------------------
# Session endpoint tests
# ---------------------------------------------------------------------------


class TestSessionEndpoints:
    """Tests for GET /sessions and GET /sessions/{session_id}."""

    @pytest.mark.asyncio
    async def test_list_sessions_returns_empty(self):
        """Should return empty list and total=0 when no sessions exist."""
        from src.api.routes.paper_trading import list_sessions

        mock_session_repo = MockPaperSessionRepository()
        mock_db = AsyncMock()

        with patch(
            "src.api.routes.paper_trading.PaperSessionRepository",
            return_value=mock_session_repo,
        ):
            result = await list_sessions(limit=50, offset=0, db=mock_db, _user_id=uuid4())

        assert result["sessions"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_list_sessions_returns_archived_sessions(self):
        """Should return archived sessions when they exist."""
        from src.api.routes.paper_trading import list_sessions

        mock_session_repo = MockPaperSessionRepository()
        account = _make_account()
        trades = [_make_trade()]
        await mock_session_repo.archive_session(account, trades, {"total_trades": 1})

        mock_db = AsyncMock()

        with patch(
            "src.api.routes.paper_trading.PaperSessionRepository",
            return_value=mock_session_repo,
        ):
            result = await list_sessions(limit=50, offset=0, db=mock_db, _user_id=uuid4())

        assert result["total"] == 1
        assert len(result["sessions"]) == 1

    @pytest.mark.asyncio
    async def test_get_session_returns_404_when_not_found(self):
        """Should return 404 for unknown session ID."""
        from fastapi import HTTPException

        from src.api.routes.paper_trading import get_session

        mock_session_repo = MockPaperSessionRepository()
        mock_db = AsyncMock()

        with (
            patch(
                "src.api.routes.paper_trading.PaperSessionRepository",
                return_value=mock_session_repo,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_session(session_id=uuid4(), db=mock_db, _user_id=uuid4())

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Reset endpoint tests
# ---------------------------------------------------------------------------


class TestResetEndpoint:
    """Tests for POST /reset (atomic transaction with capped trade archive)."""

    @pytest.mark.asyncio
    async def test_reset_account_returns_404_when_no_account(self):
        """Should return 404 if paper trading is not enabled."""
        from fastapi import HTTPException

        from src.api.routes.paper_trading import reset_account

        mock_db = AsyncMock()
        mock_account_repo = AsyncMock()
        mock_account_repo.get_account = AsyncMock(return_value=None)

        with (
            patch(
                "src.api.routes.paper_trading.PaperAccountRepository",
                return_value=mock_account_repo,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await reset_account(db=mock_db, _user_id=uuid4())

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_reset_account_happy_path(self):
        """Reset should archive, delete, recreate in one commit."""
        from src.api.routes.paper_trading import reset_account

        account = _make_account()
        trades = [_make_trade(), _make_trade()]

        added_objects: list = []

        mock_db = AsyncMock()
        mock_db.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        # flush assigns UUIDs to ORM objects that don't have them yet
        async def _fake_flush() -> None:
            for obj in added_objects:
                if getattr(obj, "id", None) is None:
                    obj.id = uuid4()

        mock_db.flush = AsyncMock(side_effect=_fake_flush)
        mock_db.commit = AsyncMock()
        mock_db.execute = AsyncMock()

        mock_account_repo = AsyncMock()
        mock_account_repo.get_account = AsyncMock(return_value=account)

        mock_trade_repo = AsyncMock()
        mock_trade_repo.list_trades = AsyncMock(return_value=(trades, 2))
        mock_trade_repo.delete_all_trades = AsyncMock(return_value=2)

        mock_position_repo = AsyncMock()
        mock_position_repo.delete_all_positions = AsyncMock(return_value=0)

        with (
            patch(
                "src.api.routes.paper_trading.PaperAccountRepository",
                return_value=mock_account_repo,
            ),
            patch(
                "src.api.routes.paper_trading.PaperTradeRepository",
                return_value=mock_trade_repo,
            ),
            patch(
                "src.api.routes.paper_trading.PaperPositionRepository",
                return_value=mock_position_repo,
            ),
        ):
            result = await reset_account(db=mock_db, _user_id=uuid4())

        # db.add called for session archive + new account
        assert mock_db.add.call_count == 2
        mock_db.flush.assert_awaited_once()
        mock_db.commit.assert_awaited_once()
        assert result.success is True
        assert result.data is not None
        assert "archived_session_id" in result.data

    @pytest.mark.asyncio
    async def test_reset_account_deletes_trades_before_positions(self):
        """Reset must delete trades then positions (FK ordering)."""
        from src.api.routes.paper_trading import reset_account

        account = _make_account()
        added_objects: list = []

        mock_db = AsyncMock()
        mock_db.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        async def _fake_flush() -> None:
            for obj in added_objects:
                if getattr(obj, "id", None) is None:
                    obj.id = uuid4()

        mock_db.flush = AsyncMock(side_effect=_fake_flush)
        mock_db.commit = AsyncMock()
        mock_db.execute = AsyncMock()

        mock_account_repo = AsyncMock()
        mock_account_repo.get_account = AsyncMock(return_value=account)

        mock_trade_repo = AsyncMock()
        mock_trade_repo.list_trades = AsyncMock(return_value=([], 0))
        mock_trade_repo.delete_all_trades = AsyncMock(return_value=0)

        mock_position_repo = AsyncMock()
        mock_position_repo.delete_all_positions = AsyncMock(return_value=0)

        with (
            patch(
                "src.api.routes.paper_trading.PaperAccountRepository",
                return_value=mock_account_repo,
            ),
            patch(
                "src.api.routes.paper_trading.PaperTradeRepository",
                return_value=mock_trade_repo,
            ),
            patch(
                "src.api.routes.paper_trading.PaperPositionRepository",
                return_value=mock_position_repo,
            ),
        ):
            await reset_account(db=mock_db, _user_id=uuid4())

        mock_trade_repo.delete_all_trades.assert_awaited_once()
        mock_position_repo.delete_all_positions.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reset_account_caps_trades_at_10000(self):
        """list_trades should be called with limit=10000 to cap archive size."""
        from src.api.routes.paper_trading import reset_account

        account = _make_account()
        added_objects: list = []

        mock_db = AsyncMock()
        mock_db.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        async def _fake_flush() -> None:
            for obj in added_objects:
                if getattr(obj, "id", None) is None:
                    obj.id = uuid4()

        mock_db.flush = AsyncMock(side_effect=_fake_flush)
        mock_db.commit = AsyncMock()
        mock_db.execute = AsyncMock()

        mock_account_repo = AsyncMock()
        mock_account_repo.get_account = AsyncMock(return_value=account)

        mock_trade_repo = AsyncMock()
        mock_trade_repo.list_trades = AsyncMock(return_value=([], 0))
        mock_trade_repo.delete_all_trades = AsyncMock(return_value=0)

        mock_position_repo = AsyncMock()
        mock_position_repo.delete_all_positions = AsyncMock(return_value=0)

        with (
            patch(
                "src.api.routes.paper_trading.PaperAccountRepository",
                return_value=mock_account_repo,
            ),
            patch(
                "src.api.routes.paper_trading.PaperTradeRepository",
                return_value=mock_trade_repo,
            ),
            patch(
                "src.api.routes.paper_trading.PaperPositionRepository",
                return_value=mock_position_repo,
            ),
        ):
            await reset_account(db=mock_db, _user_id=uuid4())

        mock_trade_repo.list_trades.assert_awaited_once_with(limit=10000, offset=0)


# ---------------------------------------------------------------------------
# Validation endpoint tests (Story 23.8b - m-5)
# ---------------------------------------------------------------------------


class TestValidationEndpoints:
    """Tests for validation API endpoints (POST /validation/start, GET /validation/status, GET /validation/report)."""

    @pytest.mark.asyncio
    async def test_start_validation_returns_201(self):
        """POST /validation/start should return 201 with valid config."""
        from src.api.routes.paper_trading import (
            StartValidationRequest,
            _validator,
            start_validation_run,
        )

        # Ensure no active run
        if _validator.current_run:
            _validator.stop_run()

        request = StartValidationRequest(
            symbols=["EURUSD", "SPX500"],
            duration_days=7,
            tolerance_pct=10.0,
        )

        result = await start_validation_run(request=request, _user_id=uuid4())

        assert result["success"] is True
        assert result["message"] == "Validation run started"
        assert "run_id" in result
        assert result["symbols"] == ["EURUSD", "SPX500"]
        assert result["duration_days"] == 7

        # Clean up
        _validator.stop_run()

    @pytest.mark.asyncio
    async def test_start_validation_conflict_when_already_running(self):
        """POST /validation/start should return 409 when a run is already active."""
        from fastapi import HTTPException

        from src.api.routes.paper_trading import (
            StartValidationRequest,
            _validator,
            start_validation_run,
        )

        # Ensure no active run, then start one
        if _validator.current_run:
            _validator.stop_run()
        _validator.start_run()

        request = StartValidationRequest(symbols=["EURUSD"], duration_days=7, tolerance_pct=10.0)

        with pytest.raises(HTTPException) as exc_info:
            await start_validation_run(request=request, _user_id=uuid4())

        assert exc_info.value.status_code == 409

        # Clean up
        _validator.stop_run()

    @pytest.mark.asyncio
    async def test_get_validation_status_no_run(self):
        """GET /validation/status should return inactive when no run exists."""
        from src.api.routes.paper_trading import _validator, get_validation_status

        # Ensure no active run
        if _validator.current_run:
            _validator.stop_run()
        _validator._current_run = None

        result = await get_validation_status(_user_id=uuid4())

        assert result["active"] is False

    @pytest.mark.asyncio
    async def test_get_validation_status_with_active_run(self):
        """GET /validation/status should return active state when run is ongoing."""
        from src.api.routes.paper_trading import _validator, get_validation_status

        # Ensure clean state, then start
        if _validator.current_run:
            _validator.stop_run()
        _validator._current_run = None
        _validator.start_run()

        result = await get_validation_status(_user_id=uuid4())

        assert result["active"] is True
        assert result["status"] == "RUNNING"

        # Clean up
        _validator.stop_run()

    def test_get_validation_report_404_when_no_run(self):
        """GET /validation/report should return 404 when no validation run exists."""
        from fastapi import HTTPException

        from src.api.routes.paper_trading import _validator, get_validation_report

        # Ensure no run
        if _validator.current_run:
            _validator.stop_run()
        _validator._current_run = None

        with pytest.raises(HTTPException) as exc_info:
            get_validation_report(_user_id=uuid4())

        assert exc_info.value.status_code == 404

    def test_get_validation_report_returns_report(self):
        """GET /validation/report should return report dict when run exists."""
        from src.api.routes.paper_trading import _validator, get_validation_report

        # Ensure clean state
        if _validator.current_run:
            _validator.stop_run()
        _validator._current_run = None

        _validator.start_run()
        _validator.record_signal("EURUSD", executed=True)

        result = get_validation_report(_user_id=uuid4())

        assert "run_id" in result
        assert "overall_status" in result
        assert result["signals_generated"] == 1

        # Clean up
        _validator.stop_run()
