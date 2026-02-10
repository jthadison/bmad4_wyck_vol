"""
Paper Trading API Routes (Story 12.8 Task 8)

REST API endpoints for paper trading mode including account management,
position tracking, trade history, and live trading eligibility.

Author: Story 12.8
"""

from datetime import UTC
from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user_id, get_db_session
from src.brokers.paper_broker_adapter import PaperBrokerAdapter
from src.models.paper_trading import PaperAccount, PaperPosition, PaperTrade, PaperTradingConfig
from src.repositories.paper_account_repository import PaperAccountRepository
from src.repositories.paper_config_repository import PaperConfigRepository
from src.repositories.paper_position_repository import PaperPositionRepository
from src.repositories.paper_session_repository import PaperSessionRepository
from src.repositories.paper_trade_repository import PaperTradeRepository
from src.trading.paper_trading_comparison import generate_comparison_report
from src.trading.paper_trading_service import PaperTradingService
from src.trading.paper_trading_validator import (
    PaperTradingValidator,
    ValidationRunConfig,
    ValidationSymbolConfig,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/paper-trading", tags=["Paper Trading"])

# Singleton validator instance for the application lifecycle
_validator = PaperTradingValidator()


# Request/Response Models


class EnablePaperTradingRequest(BaseModel):
    """Request to enable paper trading mode."""

    starting_capital: Decimal = Field(
        default=Decimal("100000.00"),
        ge=Decimal("1000.00"),
        le=Decimal("100000000.00"),
        description="Initial virtual capital",
    )
    commission_per_share: Decimal = Field(
        default=Decimal("0.005"),
        ge=Decimal("0"),
        le=Decimal("1.00"),
        description="Commission cost per share",
    )
    slippage_percentage: Decimal = Field(
        default=Decimal("0.02"),
        ge=Decimal("0"),
        le=Decimal("10.0"),
        description="Slippage as percentage",
    )
    use_realistic_fills: bool = Field(
        default=True, description="Apply slippage and commission to fills"
    )


class PaperTradingSettingsRequest(BaseModel):
    """Request to update paper trading settings."""

    starting_capital: Decimal = Field(
        default=Decimal("100000.00"),
        ge=Decimal("1000.00"),
        le=Decimal("100000000.00"),
        description="Initial virtual capital",
    )
    commission_per_share: Decimal = Field(
        default=Decimal("0.005"),
        ge=Decimal("0"),
        le=Decimal("1.00"),
        description="Commission cost per share",
    )
    slippage_percentage: Decimal = Field(
        default=Decimal("0.02"),
        ge=Decimal("0"),
        le=Decimal("10.0"),
        description="Slippage as percentage",
    )
    use_realistic_fills: bool = Field(
        default=True, description="Apply slippage and commission to fills"
    )


class PaperTradingResponse(BaseModel):
    """Generic response with success status."""

    success: bool
    message: str
    data: Optional[dict] = None


class PositionsResponse(BaseModel):
    """Response for list of open positions."""

    positions: list[PaperPosition]
    total: int
    current_heat: Decimal


class TradesResponse(BaseModel):
    """Response for paginated trades list."""

    trades: list[PaperTrade]
    total: int
    limit: int
    offset: int


class ReportResponse(BaseModel):
    """Comprehensive performance report."""

    account: PaperAccount
    performance_metrics: dict
    backtest_comparison: Optional[dict] = None
    live_eligibility: dict


# Dependency to get paper trading service


async def get_paper_trading_service(
    db: AsyncSession = Depends(get_db_session),
) -> PaperTradingService:
    """Create and return paper trading service with dependencies."""
    account_repo = PaperAccountRepository(db)
    position_repo = PaperPositionRepository(db)
    trade_repo = PaperTradeRepository(db)

    # Load config from database, fall back to defaults
    config_repo = PaperConfigRepository(db)
    config = await config_repo.get_config()
    if not config:
        config = PaperTradingConfig(enabled=True)

    broker = PaperBrokerAdapter(config)
    service = PaperTradingService(account_repo, position_repo, trade_repo, broker)

    return service


# API Endpoints


@router.post("/enable", response_model=PaperTradingResponse, status_code=status.HTTP_201_CREATED)
async def enable_paper_trading(
    request: EnablePaperTradingRequest,
    db: AsyncSession = Depends(get_db_session),
    _user_id: UUID = Depends(get_current_user_id),
) -> PaperTradingResponse:
    """
    Enable paper trading mode and create virtual account.

    Creates a new paper trading account with specified configuration.
    If account already exists, returns existing account.

    Args:
        request: Configuration for paper trading account
        db: Database session

    Returns:
        PaperTradingResponse with account details

    Raises:
        HTTPException: If account creation fails
    """
    try:
        account_repo = PaperAccountRepository(db)

        # Check if account already exists
        existing_account = await account_repo.get_account()
        if existing_account:
            logger.info("paper_trading_already_enabled", account_id=str(existing_account.id))
            return PaperTradingResponse(
                success=True,
                message="Paper trading already enabled",
                data={"account": existing_account.model_dump()},
            )

        # Create new paper account
        from datetime import datetime

        account = PaperAccount(
            starting_capital=request.starting_capital,
            current_capital=request.starting_capital,
            equity=request.starting_capital,
            paper_trading_start_date=datetime.now(UTC),
        )

        saved_account = await account_repo.create_account(account)

        logger.info(
            "paper_trading_enabled",
            account_id=str(saved_account.id),
            starting_capital=float(saved_account.starting_capital),
        )

        return PaperTradingResponse(
            success=True,
            message="Paper trading enabled successfully",
            data={"account": saved_account.model_dump()},
        )

    except Exception as e:
        logger.error("paper_trading_enable_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enable paper trading",
        ) from e


@router.post("/disable", response_model=PaperTradingResponse)
async def disable_paper_trading(
    service: PaperTradingService = Depends(get_paper_trading_service),
    _user_id: UUID = Depends(get_current_user_id),
) -> PaperTradingResponse:
    """
    Disable paper trading mode and close all open positions.

    Closes all open positions at current market prices and archives
    the paper trading account.

    Args:
        service: Paper trading service

    Returns:
        PaperTradingResponse with final account summary

    Raises:
        HTTPException: If disable fails
    """
    try:
        # Get account
        account = await service.account_repo.get_account()
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Paper trading not enabled"
            )

        # Close all open positions atomically
        positions = await service.position_repo.list_open_positions()
        try:
            closed_count = await service.close_all_positions_atomic(positions, account)
        except Exception as e:
            logger.error("failed_to_close_positions_atomically", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to close positions during disable",
            ) from e

        # Get final performance metrics
        metrics = await service.calculate_performance_metrics()

        logger.info(
            "paper_trading_disabled",
            account_id=str(account.id),
            positions_closed=closed_count,
            final_equity=float(account.equity),
        )

        return PaperTradingResponse(
            success=True,
            message=f"Paper trading disabled. Closed {closed_count} positions.",
            data={"account": account.model_dump(), "performance_metrics": metrics},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("paper_trading_disable_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disable paper trading",
        ) from e


@router.get("/account", response_model=Optional[PaperAccount])
async def get_account(
    db: AsyncSession = Depends(get_db_session),
    _user_id: UUID = Depends(get_current_user_id),
) -> Optional[PaperAccount]:
    """
    Get current paper trading account.

    Returns the current paper trading account with all metrics,
    or None if paper trading is not enabled.

    Args:
        db: Database session

    Returns:
        PaperAccount or None
    """
    account_repo = PaperAccountRepository(db)
    account = await account_repo.get_account()

    if account:
        logger.debug("paper_account_fetched", account_id=str(account.id))

    return account


@router.get("/settings", response_model=PaperTradingConfig)
async def get_settings(
    db: AsyncSession = Depends(get_db_session),
    _user_id: UUID = Depends(get_current_user_id),
) -> PaperTradingConfig:
    """
    Get current paper trading settings.

    Returns the saved config or defaults if none saved yet.
    """
    config_repo = PaperConfigRepository(db)
    config = await config_repo.get_config()
    if not config:
        config = PaperTradingConfig(enabled=True)
    return config


@router.put("/settings", response_model=PaperTradingConfig)
async def update_settings(
    request: PaperTradingSettingsRequest,
    db: AsyncSession = Depends(get_db_session),
    _user_id: UUID = Depends(get_current_user_id),
) -> PaperTradingConfig:
    """
    Save or update paper trading settings.

    Creates the config row if it does not exist, otherwise updates it.
    """
    try:
        config_repo = PaperConfigRepository(db)
        config = PaperTradingConfig(
            enabled=True,
            starting_capital=request.starting_capital,
            commission_per_share=request.commission_per_share,
            slippage_percentage=request.slippage_percentage,
            use_realistic_fills=request.use_realistic_fills,
        )
        saved = await config_repo.save_config(config)
        return saved
    except Exception as e:
        logger.error("update_settings_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update settings",
        ) from e


@router.get("/positions", response_model=PositionsResponse)
async def list_positions(
    service: PaperTradingService = Depends(get_paper_trading_service),
    _user_id: UUID = Depends(get_current_user_id),
) -> PositionsResponse:
    """
    List all open paper trading positions.

    Returns all currently open positions with unrealized P&L
    and current portfolio heat.

    Args:
        service: Paper trading service

    Returns:
        PositionsResponse with list of positions

    Raises:
        HTTPException: If account not found
    """
    try:
        account = await service.account_repo.get_account()
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Paper trading not enabled"
            )

        positions = await service.position_repo.list_open_positions()

        return PositionsResponse(
            positions=positions, total=len(positions), current_heat=account.current_heat
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_positions_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list positions",
        ) from e


@router.get("/trades", response_model=TradesResponse)
async def list_trades(
    limit: int = Query(default=50, ge=1, le=1000, description="Number of trades to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    service: PaperTradingService = Depends(get_paper_trading_service),
    _user_id: UUID = Depends(get_current_user_id),
) -> TradesResponse:
    """
    List paper trading trade history with pagination.

    Returns closed trades sorted by exit time (most recent first).

    Args:
        limit: Number of trades to return (max 1000)
        offset: Offset for pagination
        service: Paper trading service

    Returns:
        TradesResponse with paginated trades

    Raises:
        HTTPException: If query fails
    """
    try:
        trades, total = await service.trade_repo.list_trades(limit=limit, offset=offset)

        return TradesResponse(trades=trades, total=total, limit=limit, offset=offset)

    except Exception as e:
        logger.error("list_trades_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list trades",
        ) from e


@router.get("/report", response_model=ReportResponse)
async def get_report(
    backtest_id: Optional[UUID] = Query(default=None, description="Backtest ID to compare against"),
    db: AsyncSession = Depends(get_db_session),
    service: PaperTradingService = Depends(get_paper_trading_service),
    _user_id: UUID = Depends(get_current_user_id),
) -> ReportResponse:
    """
    Get comprehensive paper trading performance report.

    Returns account details, performance metrics, optional backtest
    comparison, and live trading eligibility status.

    Args:
        backtest_id: Optional backtest ID for comparison
        service: Paper trading service

    Returns:
        ReportResponse with comprehensive report

    Raises:
        HTTPException: If report generation fails
    """
    try:
        account = await service.account_repo.get_account()
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Paper trading not enabled"
            )

        # Calculate performance metrics
        performance_metrics = await service.calculate_performance_metrics()

        # Get live trading eligibility
        live_eligibility = await service.validate_live_trading_eligibility()

        # Get backtest comparison if backtest_id provided
        backtest_comparison = None
        if backtest_id:
            from src.repositories.backtest_repository import BacktestRepository

            backtest_repo = BacktestRepository(db)
            backtest_result = await backtest_repo.get_result(backtest_id)
            if backtest_result:
                backtest_comparison = await service.compare_to_backtest(backtest_result)
            else:
                logger.warning("backtest_not_found", backtest_id=str(backtest_id))

        return ReportResponse(
            account=account,
            performance_metrics=performance_metrics,
            backtest_comparison=backtest_comparison,
            live_eligibility=live_eligibility,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_report_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate report",
        ) from e


@router.get("/compare/{backtest_id}", response_model=dict)
async def compare_to_backtest(
    backtest_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    service: PaperTradingService = Depends(get_paper_trading_service),
    _user_id: UUID = Depends(get_current_user_id),
) -> dict:
    """Compare paper trading results to a specific backtest run."""
    try:
        account = await service.account_repo.get_account()
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Paper trading not enabled"
            )

        from src.repositories.backtest_repository import BacktestRepository

        backtest_repo = BacktestRepository(db)
        backtest_result = await backtest_repo.get_result(backtest_id)
        if not backtest_result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backtest {backtest_id} not found",
            )

        comparison = await service.compare_to_backtest(backtest_result)
        return comparison

    except HTTPException:
        raise
    except Exception as e:
        logger.error("compare_to_backtest_failed", backtest_id=str(backtest_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compare to backtest",
        ) from e


@router.post("/reset", response_model=PaperTradingResponse)
async def reset_account(
    db: AsyncSession = Depends(get_db_session),
    _user_id: UUID = Depends(get_current_user_id),
) -> PaperTradingResponse:
    """
    Reset paper trading account and archive data.

    Closes all positions, archives trade history, and creates
    a fresh paper trading account.  All mutations happen in a
    single transaction so a partial failure cannot leave
    orphaned data.

    Args:
        db: Database session

    Returns:
        PaperTradingResponse with new account details

    Raises:
        HTTPException: If reset fails
    """
    try:
        from datetime import datetime

        from sqlalchemy import delete as sa_delete

        from src.repositories.paper_trading_orm import PaperAccountDB, PaperTradingSessionDB

        account_repo = PaperAccountRepository(db)
        trade_repo = PaperTradeRepository(db)
        position_repo = PaperPositionRepository(db)

        # Get existing account
        account = await account_repo.get_account()
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paper trading not enabled. Enable first before resetting.",
            )

        # Fetch trades for archive (capped at 10000 to avoid memory bomb)
        trades, total_trade_count = await trade_repo.list_trades(limit=10000, offset=0)

        metrics = {
            "total_trades": account.total_trades,
            "archived_trade_count": len(trades),
            "total_trade_count": total_trade_count,
            "win_rate": float(account.win_rate),
            "average_r_multiple": float(account.average_r_multiple),
            "max_drawdown": float(account.max_drawdown),
            "total_realized_pnl": float(account.total_realized_pnl),
            "equity": float(account.equity),
            "starting_capital": float(account.starting_capital),
        }

        # --- All mutations in a single transaction ---
        now = datetime.now(UTC)

        # 1. Create archive session
        session_db = PaperTradingSessionDB(
            account_snapshot=account.model_dump(mode="json"),
            trades_snapshot=[t.model_dump(mode="json") for t in trades],
            final_metrics=metrics,
            session_start=account.paper_trading_start_date or account.created_at,
            session_end=now,
            archived_at=now,
        )
        db.add(session_db)

        # 2. Delete all trades then positions (trades FK → positions)
        await trade_repo.delete_all_trades()
        await position_repo.delete_all_positions()

        # 3. Delete old account
        await db.execute(sa_delete(PaperAccountDB).where(PaperAccountDB.id == account.id))

        # 4. Create new account
        new_account_db = PaperAccountDB(
            starting_capital=account.starting_capital,
            current_capital=account.starting_capital,
            equity=account.starting_capital,
            paper_trading_start_date=now,
            created_at=now,
            updated_at=now,
        )
        db.add(new_account_db)

        # 5. Flush to get IDs, then commit
        await db.flush()
        session_id = session_db.id
        new_account_id = new_account_db.id

        await db.commit()

        logger.info(
            "paper_account_reset",
            old_account_id=str(account.id),
            new_account_id=str(new_account_id),
            archived_session_id=str(session_id),
        )

        # Build response from the ORM object
        new_account = PaperAccount(
            id=new_account_db.id,
            starting_capital=Decimal(str(new_account_db.starting_capital)),
            current_capital=Decimal(str(new_account_db.current_capital)),
            equity=Decimal(str(new_account_db.equity)),
            paper_trading_start_date=new_account_db.paper_trading_start_date,
            created_at=new_account_db.created_at,
            updated_at=new_account_db.updated_at,
        )

        return PaperTradingResponse(
            success=True,
            message="Paper trading account reset successfully. Previous session archived.",
            data={"account": new_account.model_dump(), "archived_session_id": str(session_id)},
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("reset_account_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset account",
        ) from e


@router.get("/live-eligibility", response_model=dict)
async def check_live_eligibility(
    service: PaperTradingService = Depends(get_paper_trading_service),
    _user_id: UUID = Depends(get_current_user_id),
) -> dict:
    """
    Check eligibility for live trading (3-month requirement).

    Validates if user has met all requirements for transitioning
    to live trading mode:
    - Duration >= 90 days
    - Trade count >= 20
    - Win rate > 50%
    - Avg R-multiple > 1.5R

    Args:
        service: Paper trading service

    Returns:
        Dict with eligibility status and progress

    Raises:
        HTTPException: If check fails
    """
    try:
        eligibility = await service.validate_live_trading_eligibility()
        return eligibility

    except Exception as e:
        logger.error("check_live_eligibility_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check live eligibility",
        ) from e


@router.get("/sessions", response_model=dict)
async def list_sessions(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    _user_id: UUID = Depends(get_current_user_id),
) -> dict:
    """List archived paper trading sessions."""
    try:
        session_repo = PaperSessionRepository(db)
        sessions, total = await session_repo.list_sessions(limit=limit, offset=offset)
        return {"sessions": sessions, "total": total, "limit": limit, "offset": offset}
    except Exception as e:
        logger.error("list_sessions_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list sessions",
        ) from e


@router.get("/sessions/{session_id}", response_model=dict)
async def get_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    _user_id: UUID = Depends(get_current_user_id),
) -> dict:
    """Get details of an archived paper trading session."""
    try:
        session_repo = PaperSessionRepository(db)
        session_data = await session_repo.get_session(session_id)
        if not session_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found",
            )
        return session_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_session_failed", session_id=str(session_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get session",
        ) from e


# --- Validation Endpoints (Story 23.8b) ---


class StartValidationRequest(BaseModel):
    """Request to start a paper trading validation run."""

    symbols: list[str] = Field(
        default=["EURUSD", "SPX500"],
        description="Symbols to validate (at least 1 forex, 1 stock recommended)",
    )
    duration_days: int = Field(default=14, ge=1, le=90, description="Duration in days")
    tolerance_pct: float = Field(default=10.0, ge=0, le=100, description="Deviation tolerance %")


@router.get("/validation/status", response_model=dict)
async def get_validation_status(
    _user_id: UUID = Depends(get_current_user_id),
) -> dict:
    """
    Get the current validation run status.

    Returns information about whether a validation run is active,
    how many signals have been generated and executed, and elapsed time.
    """
    return _validator.get_status()


@router.post("/validation/start", response_model=dict, status_code=status.HTTP_201_CREATED)
async def start_validation_run(
    request: StartValidationRequest,
    _user_id: UUID = Depends(get_current_user_id),
) -> dict:
    """
    Start a paper trading validation run.

    Configures a new validation run with the specified symbols and duration.
    Results are accumulated and can be retrieved via the report endpoint.
    """
    try:
        config = ValidationRunConfig(
            symbols=[ValidationSymbolConfig(symbol=s) for s in request.symbols],
            duration_days=request.duration_days,
            tolerance_pct=Decimal(str(request.tolerance_pct)),
        )
        run = _validator.start_run(config)
        return {
            "success": True,
            "message": "Validation run started",
            "run_id": str(run.id),
            "symbols": request.symbols,
            "duration_days": request.duration_days,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except Exception as e:
        logger.error("start_validation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start validation run",
        ) from e


@router.post("/validation/stop", response_model=dict)
async def stop_validation_run(
    _user_id: UUID = Depends(get_current_user_id),
) -> dict:
    """Stop the current validation run."""
    run = _validator.stop_run()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No active validation run"
        )
    return {
        "success": True,
        "message": "Validation run stopped",
        "run_id": str(run.id),
        "signals_generated": run.signals_generated,
        "signals_executed": run.signals_executed,
    }


@router.get("/validation/report", response_model=dict)
async def get_validation_report(
    _user_id: UUID = Depends(get_current_user_id),
) -> dict:
    """
    Get the comparison report for the current or most recent validation run.

    Compares paper trading results against backtest baselines and returns
    per-symbol deviation metrics with severity classification.
    """
    run_state = _validator.current_run
    if not run_state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No validation run found. Start one first.",
        )

    tolerance = float(run_state.config.tolerance_pct)
    report = generate_comparison_report(run_state, tolerance_pct=tolerance)
    return report.model_dump()
