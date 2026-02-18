"""Additional tests for paper trading API endpoints (Story 23.8a coverage).

Covers endpoints not tested by test_paper_trading.py:
enable, disable, get_account, list_positions, list_trades, compare success path,
check_live_eligibility, get_paper_trading_service dependency, and error branches.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.models.paper_trading import (
    PaperAccount,
    PaperPosition,
    PaperTrade,
    PaperTradingConfig,
)

# ---------------------------------------------------------------------------
# Helpers (shared with test_paper_trading.py but defined locally to stay independent)
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


def _make_position(**overrides) -> PaperPosition:
    now = datetime.now(UTC)
    defaults = {
        "signal_id": uuid4(),
        "symbol": "AAPL",
        "entry_time": now,
        "entry_price": Decimal("150.00"),
        "quantity": Decimal("100"),
        "stop_loss": Decimal("148.00"),
        "target_1": Decimal("154.00"),
        "target_2": Decimal("156.00"),
        "current_price": Decimal("151.00"),
        "unrealized_pnl": Decimal("100.00"),
        "status": "OPEN",
        "commission_paid": Decimal("0.50"),
        "slippage_cost": Decimal("3.00"),
    }
    defaults.update(overrides)
    return PaperPosition(**defaults)


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
# get_paper_trading_service dependency
# ---------------------------------------------------------------------------


class TestGetPaperTradingService:
    """Tests for the get_paper_trading_service dependency."""

    @pytest.mark.asyncio
    async def test_creates_service_with_default_config(self):
        """Should create service with default config when none saved."""
        from src.api.routes.paper_trading import get_paper_trading_service

        mock_db = AsyncMock()
        mock_config_repo = AsyncMock()
        mock_config_repo.get_config = AsyncMock(return_value=None)

        with (
            patch("src.api.routes.paper_trading.PaperAccountRepository"),
            patch("src.api.routes.paper_trading.PaperPositionRepository"),
            patch("src.api.routes.paper_trading.PaperTradeRepository"),
            patch(
                "src.api.routes.paper_trading.PaperConfigRepository",
                return_value=mock_config_repo,
            ),
            patch("src.api.routes.paper_trading.PaperBrokerAdapter") as mock_broker_cls,
            patch("src.api.routes.paper_trading.PaperTradingService") as mock_svc_cls,
        ):
            await get_paper_trading_service(db=mock_db)

        # PaperBrokerAdapter should have been called with a config (default)
        mock_broker_cls.assert_called_once()
        mock_svc_cls.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_service_with_saved_config(self):
        """Should use saved config when one exists in DB."""
        from src.api.routes.paper_trading import get_paper_trading_service

        mock_db = AsyncMock()
        saved_config = PaperTradingConfig(
            enabled=True,
            starting_capital=Decimal("50000.00"),
        )
        mock_config_repo = AsyncMock()
        mock_config_repo.get_config = AsyncMock(return_value=saved_config)

        with (
            patch("src.api.routes.paper_trading.PaperAccountRepository"),
            patch("src.api.routes.paper_trading.PaperPositionRepository"),
            patch("src.api.routes.paper_trading.PaperTradeRepository"),
            patch(
                "src.api.routes.paper_trading.PaperConfigRepository",
                return_value=mock_config_repo,
            ),
            patch("src.api.routes.paper_trading.PaperBrokerAdapter") as mock_broker_cls,
            patch("src.api.routes.paper_trading.PaperTradingService"),
        ):
            await get_paper_trading_service(db=mock_db)

        # Should have used the saved config
        mock_broker_cls.assert_called_once_with(saved_config)


# ---------------------------------------------------------------------------
# enable_paper_trading
# ---------------------------------------------------------------------------


class TestEnablePaperTrading:
    """Tests for POST /enable."""

    @pytest.mark.asyncio
    async def test_enable_creates_new_account(self):
        """Should create a new account when none exists."""
        from src.api.routes.paper_trading import (
            EnablePaperTradingRequest,
            enable_paper_trading,
        )

        mock_db = AsyncMock()
        mock_account_repo = AsyncMock()
        mock_account_repo.get_account = AsyncMock(return_value=None)
        mock_account_repo.create_account = AsyncMock(return_value=_make_account())

        request = EnablePaperTradingRequest(starting_capital=Decimal("100000.00"))

        with patch(
            "src.api.routes.paper_trading.PaperAccountRepository",
            return_value=mock_account_repo,
        ):
            result = await enable_paper_trading(request=request, db=mock_db, _user_id=uuid4())

        assert result.success is True
        assert "enabled" in result.message.lower() or "Paper trading" in result.message
        mock_account_repo.create_account.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_enable_returns_existing_account(self):
        """Should return existing account when already enabled."""
        from src.api.routes.paper_trading import (
            EnablePaperTradingRequest,
            enable_paper_trading,
        )

        mock_db = AsyncMock()
        existing_account = _make_account()
        mock_account_repo = AsyncMock()
        mock_account_repo.get_account = AsyncMock(return_value=existing_account)

        request = EnablePaperTradingRequest()

        with patch(
            "src.api.routes.paper_trading.PaperAccountRepository",
            return_value=mock_account_repo,
        ):
            result = await enable_paper_trading(request=request, db=mock_db, _user_id=uuid4())

        assert result.success is True
        assert "already" in result.message.lower()

    @pytest.mark.asyncio
    async def test_enable_handles_exception(self):
        """Should raise 500 on unexpected error."""
        from fastapi import HTTPException

        from src.api.routes.paper_trading import (
            EnablePaperTradingRequest,
            enable_paper_trading,
        )

        mock_db = AsyncMock()
        mock_account_repo = AsyncMock()
        mock_account_repo.get_account = AsyncMock(side_effect=RuntimeError("DB down"))

        request = EnablePaperTradingRequest()

        with (
            patch(
                "src.api.routes.paper_trading.PaperAccountRepository",
                return_value=mock_account_repo,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await enable_paper_trading(request=request, db=mock_db, _user_id=uuid4())

        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# disable_paper_trading
# ---------------------------------------------------------------------------


class TestDisablePaperTrading:
    """Tests for POST /disable."""

    @pytest.mark.asyncio
    async def test_disable_closes_positions_and_returns(self):
        """Should close positions and return final metrics."""
        from src.api.routes.paper_trading import disable_paper_trading

        account = _make_account()
        positions = [_make_position()]

        mock_service = AsyncMock()
        mock_service.account_repo = AsyncMock()
        mock_service.account_repo.get_account = AsyncMock(return_value=account)
        mock_service.position_repo = AsyncMock()
        mock_service.position_repo.list_open_positions = AsyncMock(return_value=positions)
        mock_service.close_all_positions_atomic = AsyncMock(return_value=1)
        mock_service.calculate_performance_metrics = AsyncMock(return_value={"total_trades": 10})

        result = await disable_paper_trading(service=mock_service, _user_id=uuid4())

        assert result.success is True
        assert "1 positions" in result.message or "Closed 1" in result.message
        mock_service.close_all_positions_atomic.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disable_returns_404_when_no_account(self):
        """Should return 404 if no account exists."""
        from fastapi import HTTPException

        from src.api.routes.paper_trading import disable_paper_trading

        mock_service = AsyncMock()
        mock_service.account_repo = AsyncMock()
        mock_service.account_repo.get_account = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await disable_paper_trading(service=mock_service, _user_id=uuid4())

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_disable_handles_close_failure(self):
        """Should return 500 if atomic close fails."""
        from fastapi import HTTPException

        from src.api.routes.paper_trading import disable_paper_trading

        account = _make_account()
        mock_service = AsyncMock()
        mock_service.account_repo = AsyncMock()
        mock_service.account_repo.get_account = AsyncMock(return_value=account)
        mock_service.position_repo = AsyncMock()
        mock_service.position_repo.list_open_positions = AsyncMock(return_value=[])
        mock_service.close_all_positions_atomic = AsyncMock(
            side_effect=RuntimeError("commit failed")
        )

        with pytest.raises(HTTPException) as exc_info:
            await disable_paper_trading(service=mock_service, _user_id=uuid4())

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_disable_handles_general_exception(self):
        """Should return 500 on unexpected error."""
        from fastapi import HTTPException

        from src.api.routes.paper_trading import disable_paper_trading

        account = _make_account()
        mock_service = AsyncMock()
        mock_service.account_repo = AsyncMock()
        mock_service.account_repo.get_account = AsyncMock(return_value=account)
        mock_service.position_repo = AsyncMock()
        mock_service.position_repo.list_open_positions = AsyncMock(return_value=[])
        mock_service.close_all_positions_atomic = AsyncMock(return_value=0)
        mock_service.calculate_performance_metrics = AsyncMock(
            side_effect=RuntimeError("metrics failed")
        )

        with pytest.raises(HTTPException) as exc_info:
            await disable_paper_trading(service=mock_service, _user_id=uuid4())

        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# get_account
# ---------------------------------------------------------------------------


class TestGetAccount:
    """Tests for GET /account."""

    @pytest.mark.asyncio
    async def test_get_account_returns_account(self):
        """Should return account when it exists."""
        from src.api.routes.paper_trading import get_account

        account = _make_account()
        mock_db = AsyncMock()
        mock_account_repo = AsyncMock()
        mock_account_repo.get_account = AsyncMock(return_value=account)

        with patch(
            "src.api.routes.paper_trading.PaperAccountRepository",
            return_value=mock_account_repo,
        ):
            result = await get_account(db=mock_db, _user_id=uuid4())

        assert result is not None
        assert result.id == account.id

    @pytest.mark.asyncio
    async def test_get_account_returns_none(self):
        """Should return None when no account exists."""
        from src.api.routes.paper_trading import get_account

        mock_db = AsyncMock()
        mock_account_repo = AsyncMock()
        mock_account_repo.get_account = AsyncMock(return_value=None)

        with patch(
            "src.api.routes.paper_trading.PaperAccountRepository",
            return_value=mock_account_repo,
        ):
            result = await get_account(db=mock_db, _user_id=uuid4())

        assert result is None


# ---------------------------------------------------------------------------
# list_positions
# ---------------------------------------------------------------------------


class TestListPositions:
    """Tests for GET /positions."""

    @pytest.mark.asyncio
    async def test_list_positions_returns_positions(self):
        """Should return positions and heat when account exists."""
        from src.api.routes.paper_trading import list_positions

        account = _make_account(current_heat=Decimal("4.00"))
        positions = [_make_position(), _make_position(symbol="MSFT")]

        mock_service = AsyncMock()
        mock_service.account_repo = AsyncMock()
        mock_service.account_repo.get_account = AsyncMock(return_value=account)
        mock_service.position_repo = AsyncMock()
        mock_service.position_repo.list_open_positions = AsyncMock(return_value=positions)

        result = await list_positions(service=mock_service, _user_id=uuid4())

        assert result.total == 2
        assert len(result.positions) == 2
        assert result.current_heat == Decimal("4.00000000")

    @pytest.mark.asyncio
    async def test_list_positions_404_when_no_account(self):
        """Should return 404 if account not found."""
        from fastapi import HTTPException

        from src.api.routes.paper_trading import list_positions

        mock_service = AsyncMock()
        mock_service.account_repo = AsyncMock()
        mock_service.account_repo.get_account = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await list_positions(service=mock_service, _user_id=uuid4())

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_list_positions_handles_exception(self):
        """Should return 500 on unexpected error."""
        from fastapi import HTTPException

        from src.api.routes.paper_trading import list_positions

        mock_service = AsyncMock()
        mock_service.account_repo = AsyncMock()
        mock_service.account_repo.get_account = AsyncMock(side_effect=RuntimeError("DB error"))

        with pytest.raises(HTTPException) as exc_info:
            await list_positions(service=mock_service, _user_id=uuid4())

        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# list_trades
# ---------------------------------------------------------------------------


class TestListTrades:
    """Tests for GET /trades."""

    @pytest.mark.asyncio
    async def test_list_trades_returns_trades(self):
        """Should return paginated trades."""
        from src.api.routes.paper_trading import list_trades

        trades = [_make_trade(), _make_trade(symbol="MSFT")]

        mock_service = AsyncMock()
        mock_service.trade_repo = AsyncMock()
        mock_service.trade_repo.list_trades = AsyncMock(return_value=(trades, 2))

        result = await list_trades(limit=50, offset=0, service=mock_service, _user_id=uuid4())

        assert result.total == 2
        assert len(result.trades) == 2
        assert result.limit == 50
        assert result.offset == 0

    @pytest.mark.asyncio
    async def test_list_trades_handles_exception(self):
        """Should return 500 on unexpected error."""
        from fastapi import HTTPException

        from src.api.routes.paper_trading import list_trades

        mock_service = AsyncMock()
        mock_service.trade_repo = AsyncMock()
        mock_service.trade_repo.list_trades = AsyncMock(side_effect=RuntimeError("DB error"))

        with pytest.raises(HTTPException) as exc_info:
            await list_trades(limit=50, offset=0, service=mock_service, _user_id=uuid4())

        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# compare_to_backtest success path
# ---------------------------------------------------------------------------


class TestCompareSuccess:
    """Tests for GET /compare/{backtest_id} success path."""

    @pytest.mark.asyncio
    async def test_compare_returns_comparison_result(self):
        """Should return comparison dict when backtest exists."""
        from src.api.routes.paper_trading import compare_to_backtest

        account = _make_account()
        comparison_result = {
            "status": "OK",
            "deltas": {},
            "warnings": [],
            "errors": [],
        }

        mock_service = AsyncMock()
        mock_service.account_repo = AsyncMock()
        mock_service.account_repo.get_account = AsyncMock(return_value=account)
        mock_service.compare_to_backtest = AsyncMock(return_value=comparison_result)

        mock_db = AsyncMock()
        mock_backtest_repo = AsyncMock()
        mock_backtest_repo.get_result = AsyncMock(return_value=MagicMock())

        with patch(
            "src.repositories.backtest_repository.BacktestRepository",
            return_value=mock_backtest_repo,
        ):
            result = await compare_to_backtest(
                backtest_id=uuid4(),
                db=mock_db,
                service=mock_service,
                _user_id=uuid4(),
            )

        assert result["status"] == "OK"
        mock_service.compare_to_backtest.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_compare_handles_exception(self):
        """Should return 500 on unexpected error."""
        from fastapi import HTTPException

        from src.api.routes.paper_trading import compare_to_backtest

        account = _make_account()
        mock_service = AsyncMock()
        mock_service.account_repo = AsyncMock()
        mock_service.account_repo.get_account = AsyncMock(return_value=account)

        mock_db = AsyncMock()
        mock_backtest_repo = AsyncMock()
        mock_backtest_repo.get_result = AsyncMock(side_effect=RuntimeError("DB error"))

        with (
            patch(
                "src.repositories.backtest_repository.BacktestRepository",
                return_value=mock_backtest_repo,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await compare_to_backtest(
                backtest_id=uuid4(),
                db=mock_db,
                service=mock_service,
                _user_id=uuid4(),
            )

        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# check_live_eligibility
# ---------------------------------------------------------------------------


class TestCheckLiveEligibility:
    """Tests for GET /live-eligibility."""

    @pytest.mark.asyncio
    async def test_check_live_eligibility_returns_result(self):
        """Should return eligibility dict."""
        from src.api.routes.paper_trading import check_live_eligibility

        mock_service = AsyncMock()
        mock_service.validate_live_trading_eligibility = AsyncMock(
            return_value={"eligible": False, "days_remaining": 45}
        )

        result = await check_live_eligibility(service=mock_service, _user_id=uuid4())

        assert result["eligible"] is False
        assert result["days_remaining"] == 45

    @pytest.mark.asyncio
    async def test_check_live_eligibility_handles_exception(self):
        """Should return 500 on unexpected error."""
        from fastapi import HTTPException

        from src.api.routes.paper_trading import check_live_eligibility

        mock_service = AsyncMock()
        mock_service.validate_live_trading_eligibility = AsyncMock(
            side_effect=RuntimeError("error")
        )

        with pytest.raises(HTTPException) as exc_info:
            await check_live_eligibility(service=mock_service, _user_id=uuid4())

        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# get_report
# ---------------------------------------------------------------------------


class TestGetReport:
    """Tests for GET /report."""

    @pytest.mark.asyncio
    async def test_get_report_404_when_no_account(self):
        """Should return 404 if no account exists."""
        from fastapi import HTTPException

        from src.api.routes.paper_trading import get_report

        mock_service = AsyncMock()
        mock_service.account_repo = AsyncMock()
        mock_service.account_repo.get_account = AsyncMock(return_value=None)

        mock_db = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_report(
                backtest_id=None,
                db=mock_db,
                service=mock_service,
                _user_id=uuid4(),
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_report_handles_exception(self):
        """Should return 500 on unexpected error."""
        from fastapi import HTTPException

        from src.api.routes.paper_trading import get_report

        mock_service = AsyncMock()
        mock_service.account_repo = AsyncMock()
        mock_service.account_repo.get_account = AsyncMock(side_effect=RuntimeError("DB error"))

        mock_db = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_report(
                backtest_id=None,
                db=mock_db,
                service=mock_service,
                _user_id=uuid4(),
            )

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_get_report_skips_missing_backtest(self):
        """Report should have None backtest_comparison when backtest not found."""
        from src.api.routes.paper_trading import get_report

        account = _make_account()
        mock_service = AsyncMock()
        mock_service.account_repo = AsyncMock()
        mock_service.account_repo.get_account = AsyncMock(return_value=account)
        mock_service.calculate_performance_metrics = AsyncMock(return_value={"total_trades": 5})
        mock_service.validate_live_trading_eligibility = AsyncMock(return_value={"eligible": False})

        mock_db = AsyncMock()
        mock_backtest_repo = AsyncMock()
        mock_backtest_repo.get_result = AsyncMock(return_value=None)

        backtest_id = uuid4()

        with patch(
            "src.repositories.backtest_repository.BacktestRepository",
            return_value=mock_backtest_repo,
        ):
            result = await get_report(
                backtest_id=backtest_id,
                db=mock_db,
                service=mock_service,
                _user_id=uuid4(),
            )

        assert result.backtest_comparison is None


# ---------------------------------------------------------------------------
# update_settings exception branch
# ---------------------------------------------------------------------------


class TestUpdateSettingsError:
    """Tests for PUT /settings error path."""

    @pytest.mark.asyncio
    async def test_update_settings_handles_exception(self):
        """Should return 500 on unexpected error."""
        from fastapi import HTTPException

        from src.api.routes.paper_trading import (
            PaperTradingSettingsRequest,
            update_settings,
        )

        mock_db = AsyncMock()
        mock_config_repo = AsyncMock()
        mock_config_repo.save_config = AsyncMock(side_effect=RuntimeError("save failed"))

        request = PaperTradingSettingsRequest(starting_capital=Decimal("100000.00"))

        with (
            patch(
                "src.api.routes.paper_trading.PaperConfigRepository",
                return_value=mock_config_repo,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await update_settings(request=request, db=mock_db, _user_id=uuid4())

        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# reset_account rollback branch
# ---------------------------------------------------------------------------


class TestResetAccountRollback:
    """Tests for POST /reset error and rollback branches."""

    @pytest.mark.asyncio
    async def test_reset_account_rolls_back_on_error(self):
        """Reset should rollback on unexpected error."""
        from fastapi import HTTPException

        from src.api.routes.paper_trading import reset_account

        mock_db = AsyncMock()
        mock_db.rollback = AsyncMock()
        mock_account_repo = AsyncMock()
        account = _make_account()
        mock_account_repo.get_account = AsyncMock(return_value=account)

        mock_trade_repo = AsyncMock()
        mock_trade_repo.list_trades = AsyncMock(side_effect=RuntimeError("DB exploded"))

        with (
            patch(
                "src.api.routes.paper_trading.PaperAccountRepository",
                return_value=mock_account_repo,
            ),
            patch(
                "src.api.routes.paper_trading.PaperTradeRepository",
                return_value=mock_trade_repo,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await reset_account(db=mock_db, _user_id=uuid4())

        assert exc_info.value.status_code == 500
        mock_db.rollback.assert_awaited_once()


# ---------------------------------------------------------------------------
# list_sessions and get_session error paths
# ---------------------------------------------------------------------------


class TestSessionEndpointErrors:
    """Tests for session endpoint error branches."""

    @pytest.mark.asyncio
    async def test_list_sessions_handles_exception(self):
        """Should return 500 on unexpected error."""
        from fastapi import HTTPException

        from src.api.routes.paper_trading import list_sessions

        mock_db = AsyncMock()
        mock_session_repo = AsyncMock()
        mock_session_repo.list_sessions = AsyncMock(side_effect=RuntimeError("DB error"))

        with (
            patch(
                "src.api.routes.paper_trading.PaperSessionRepository",
                return_value=mock_session_repo,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await list_sessions(limit=50, offset=0, db=mock_db, _user_id=uuid4())

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_get_session_handles_exception(self):
        """Should return 500 on unexpected error (non-HTTPException)."""
        from fastapi import HTTPException

        from src.api.routes.paper_trading import get_session

        mock_db = AsyncMock()
        mock_session_repo = AsyncMock()
        mock_session_repo.get_session = AsyncMock(side_effect=RuntimeError("DB error"))

        with (
            patch(
                "src.api.routes.paper_trading.PaperSessionRepository",
                return_value=mock_session_repo,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_session(session_id=uuid4(), db=mock_db, _user_id=uuid4())

        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# start_validation error branch
# ---------------------------------------------------------------------------


class TestStartValidationError:
    """Tests for POST /validation/start error branches."""

    @pytest.mark.asyncio
    async def test_start_validation_handles_general_exception(self):
        """Should return 500 on unexpected error (not ValueError)."""
        from fastapi import HTTPException

        from src.api.routes.paper_trading import (
            StartValidationRequest,
            start_validation_run,
        )

        request = StartValidationRequest()

        with (
            patch("src.api.routes.paper_trading._validator") as mock_validator,
            pytest.raises(HTTPException) as exc_info,
        ):
            mock_validator.start_run.side_effect = RuntimeError("unexpected")
            await start_validation_run(request=request, _user_id=uuid4())

        assert exc_info.value.status_code == 500
