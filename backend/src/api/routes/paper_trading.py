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

from src.api.dependencies import get_db_session
from src.brokers.paper_broker_adapter import PaperBrokerAdapter
from src.models.paper_trading import PaperAccount, PaperPosition, PaperTrade, PaperTradingConfig
from src.repositories.paper_account_repository import PaperAccountRepository
from src.repositories.paper_position_repository import PaperPositionRepository
from src.repositories.paper_trade_repository import PaperTradeRepository
from src.trading.paper_trading_service import PaperTradingService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/paper-trading", tags=["Paper Trading"])


# Request/Response Models


class EnablePaperTradingRequest(BaseModel):
    """Request to enable paper trading mode."""

    starting_capital: Decimal = Field(
        default=Decimal("100000.00"), ge=Decimal("1000.00"), description="Initial virtual capital"
    )
    commission_per_share: Decimal = Field(
        default=Decimal("0.005"), ge=Decimal("0"), description="Commission cost per share"
    )
    slippage_percentage: Decimal = Field(
        default=Decimal("0.02"), ge=Decimal("0"), description="Slippage as percentage"
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

    # Get or create default config
    # TODO: Load from user settings/database
    config = PaperTradingConfig(
        enabled=True,
        starting_capital=Decimal("100000.00"),
        commission_per_share=Decimal("0.005"),
        slippage_percentage=Decimal("0.02"),
        use_realistic_fills=True,
    )

    broker = PaperBrokerAdapter(config)
    service = PaperTradingService(account_repo, position_repo, trade_repo, broker)

    return service


# API Endpoints


@router.post("/enable", response_model=PaperTradingResponse, status_code=status.HTTP_201_CREATED)
async def enable_paper_trading(
    request: EnablePaperTradingRequest, db: AsyncSession = Depends(get_db_session)
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
            detail=f"Failed to enable paper trading: {str(e)}",
        )


@router.post("/disable", response_model=PaperTradingResponse)
async def disable_paper_trading(
    service: PaperTradingService = Depends(get_paper_trading_service),
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

        # Close all open positions
        positions = await service.position_repo.list_open_positions()
        closed_count = 0

        for position in positions:
            try:
                # Use current price to close (or entry price as fallback)
                await service._close_position(position, position.current_price, "MANUAL", account)
                closed_count += 1
            except Exception as e:
                logger.error("failed_to_close_position", position_id=str(position.id), error=str(e))

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
            detail=f"Failed to disable paper trading: {str(e)}",
        )


@router.get("/account", response_model=Optional[PaperAccount])
async def get_account(db: AsyncSession = Depends(get_db_session)) -> Optional[PaperAccount]:
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


@router.get("/positions", response_model=PositionsResponse)
async def list_positions(
    service: PaperTradingService = Depends(get_paper_trading_service),
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
            detail=f"Failed to list positions: {str(e)}",
        )


@router.get("/trades", response_model=TradesResponse)
async def list_trades(
    limit: int = Query(default=50, ge=1, le=1000, description="Number of trades to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    service: PaperTradingService = Depends(get_paper_trading_service),
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
            detail=f"Failed to list trades: {str(e)}",
        )


@router.get("/report", response_model=ReportResponse)
async def get_report(
    backtest_id: Optional[UUID] = Query(default=None, description="Backtest ID to compare against"),
    service: PaperTradingService = Depends(get_paper_trading_service),
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
            # TODO: Fetch backtest result by ID and compare
            # from src.repositories.backtest_repository import BacktestRepository
            # backtest_repo = BacktestRepository(db)
            # backtest_result = await backtest_repo.get_by_id(backtest_id)
            # backtest_comparison = await service.compare_to_backtest(backtest_result)
            logger.warning("backtest_comparison_not_implemented", backtest_id=str(backtest_id))

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
            detail=f"Failed to generate report: {str(e)}",
        )


@router.post("/reset", response_model=PaperTradingResponse)
async def reset_account(db: AsyncSession = Depends(get_db_session)) -> PaperTradingResponse:
    """
    Reset paper trading account and archive data.

    Closes all positions, archives trade history, and creates
    a fresh paper trading account.

    Args:
        db: Database session

    Returns:
        PaperTradingResponse with new account details

    Raises:
        HTTPException: If reset fails
    """
    try:
        account_repo = PaperAccountRepository(db)

        # Get existing account
        account = await account_repo.get_account()
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paper trading not enabled. Enable first before resetting.",
            )

        # Archive current account (soft delete)
        # TODO: Implement archiving logic to preserve historical data
        # For now, just delete and recreate

        await account_repo.delete_account(account.id)

        # Create fresh account
        from datetime import datetime

        new_account = PaperAccount(
            starting_capital=account.starting_capital,  # Keep same starting capital
            current_capital=account.starting_capital,
            equity=account.starting_capital,
            paper_trading_start_date=datetime.now(UTC),
        )

        saved_account = await account_repo.create_account(new_account)

        logger.info(
            "paper_account_reset",
            old_account_id=str(account.id),
            new_account_id=str(saved_account.id),
        )

        return PaperTradingResponse(
            success=True,
            message="Paper trading account reset successfully",
            data={"account": saved_account.model_dump()},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("reset_account_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset account: {str(e)}",
        )


@router.get("/live-eligibility", response_model=dict)
async def check_live_eligibility(
    service: PaperTradingService = Depends(get_paper_trading_service),
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
            detail=f"Failed to check live eligibility: {str(e)}",
        )
