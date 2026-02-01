"""
Full backtest endpoints.

Story 12.1 Endpoints:
- POST /run: Run full backtest with persistence
- GET /results/{backtest_run_id}: Get specific result
- GET /results: List all results (paginated)

Note: Report export endpoints (HTML, PDF, CSV) are in reports.py
"""

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.backtesting.backtest_engine import BacktestEngine
from src.database import get_db
from src.models.backtest import BacktestConfig
from src.models.ohlcv import OHLCVBar
from src.repositories.backtest_repository import BacktestRepository

from .utils import backtest_runs, fetch_historical_bars

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/run", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def run_backtest(
    config: BacktestConfig,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    Run a full backtest with the provided configuration.

    AC7 Subtask 8.1-8.5: Run backtest as background task, return immediately.

    Args:
        config: Backtest configuration (symbol, date range, initial capital)
        session: Database session

    Returns:
        Response with backtest_run_id and status: RUNNING

    Raises:
        400 Bad Request: Invalid config
        422 Unprocessable Entity: Validation errors

    Example Request:
        POST /api/v1/backtest/run
        {
            "symbol": "AAPL",
            "timeframe": "1d",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "initial_capital": 100000
        }

    Example Response:
        {
            "backtest_run_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "RUNNING"
        }
    """
    # Generate unique run ID
    run_id = uuid4()

    # Validate config
    if config.start_date >= config.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before end_date",
        )

    if config.initial_capital <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="initial_capital must be greater than 0",
        )

    # Initialize tracking (in-memory for now)
    backtest_runs[run_id] = {
        "status": "RUNNING",
        "created_at": datetime.now(UTC),
        "error": None,
    }

    # Queue background task
    asyncio.create_task(
        run_backtest_task(
            run_id,
            config,
            session,
        )
    )

    logger.info(
        "Backtest queued",
        extra={
            "backtest_run_id": str(run_id),
            "symbol": config.symbol,
            "start_date": str(config.start_date),
            "end_date": str(config.end_date),
        },
    )

    return {"backtest_run_id": run_id, "status": "RUNNING"}


@router.get("/results/{backtest_run_id}")
async def get_backtest_result(
    backtest_run_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get backtest result by backtest_run_id.

    AC7 Subtask 8.6-8.7: Return result if completed, status if running, 404 if not found.

    Args:
        backtest_run_id: Backtest run identifier
        session: Database session

    Returns:
        BacktestResult if completed, status object if running

    Raises:
        404 Not Found: Backtest not found

    Example Response (Running):
        {
            "status": "RUNNING"
        }

    Example Response (Completed):
        {
            "backtest_run_id": "...",
            "symbol": "AAPL",
            "metrics": {...},
            "trades": [...],
            ...
        }
    """
    # Check in-memory tracking first
    if backtest_run_id in backtest_runs:
        run_status = backtest_runs[backtest_run_id]["status"]
        if run_status == "RUNNING":
            return {"status": "RUNNING"}
        elif run_status == "FAILED":
            error = backtest_runs[backtest_run_id].get("error", "Unknown error")
            return {"status": "FAILED", "error": error}

    # Check database for completed result
    repository = BacktestRepository(session)
    result = await repository.get_result(backtest_run_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest run {backtest_run_id} not found",
        )

    return result.model_dump(mode="json")


@router.get("/results")
async def list_backtest_results(
    symbol: str | None = None,
    format: str | None = None,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    List backtest results with pagination and optional filtering.

    AC7 Subtask 8.8-8.9: Paginated listing with optional symbol filter.
    Story 12.6D Task 17: Added format=summary for lightweight list view.

    Args:
        symbol: Optional symbol filter
        format: Response format ('summary' for lightweight, None for full)
        limit: Maximum number of results (default 100, max 1000)
        offset: Number of results to skip (default 0)
        session: Database session

    Returns:
        Paginated list of backtest results

    Example Response (format=summary):
        {
            "results": [
                {
                    "backtest_run_id": "...",
                    "symbol": "AAPL",
                    "total_return_pct": "15.5",
                    "win_rate": "0.65",
                    ...
                },
                ...
            ],
            "total": 42,
            "limit": 100,
            "offset": 0
        }
    """
    # Validate pagination parameters
    if limit > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="limit cannot exceed 1000",
        )

    if limit < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="limit must be at least 1",
        )

    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="offset cannot be negative",
        )

    # Query repository
    repository = BacktestRepository(session)
    results = await repository.list_results(symbol=symbol, limit=limit, offset=offset)

    # If format=summary, return lightweight summary without equity_curve and trades
    if format == "summary":
        summary_results = []
        for r in results:
            summary_results.append(
                {
                    "backtest_run_id": str(r.backtest_run_id),
                    "symbol": r.symbol,
                    "timeframe": r.timeframe,
                    "start_date": r.start_date.isoformat(),
                    "end_date": r.end_date.isoformat(),
                    # Extract summary metrics (using actual BacktestMetrics fields)
                    "total_return_pct": str(r.summary.total_return_pct),
                    "cagr": str(r.summary.cagr),
                    "sharpe_ratio": str(r.summary.sharpe_ratio),
                    "max_drawdown_pct": str(
                        r.summary.max_drawdown
                    ),  # Field is named max_drawdown in model
                    "win_rate": str(r.summary.win_rate),
                    "total_trades": r.summary.total_trades,
                    "campaign_completion_rate": "0.0",  # Not yet implemented in Story 12.6A
                    "created_at": r.created_at.isoformat(),
                }
            )

        return {
            "results": summary_results,
            "total": len(summary_results),
            "limit": limit,
            "offset": offset,
        }

    # Default: return full results
    return {
        "results": [r.model_dump(mode="json") for r in results],
        "total": len(results),
        "limit": limit,
        "offset": offset,
    }


async def run_backtest_task(
    run_id: UUID,
    config: BacktestConfig,
    session: AsyncSession,
) -> None:
    """
    Background task to execute full backtest.

    AC7 Subtask 8.4-8.10: Execute engine, save to database via repository.

    Args:
        run_id: Backtest run identifier
        config: Backtest configuration
        session: Database session
    """
    try:
        logger.info("Starting backtest execution", extra={"backtest_run_id": str(run_id)})

        # Fetch historical data (simplified - in production, query from OHLCV repository)
        bars = await fetch_historical_bars(config.symbol, config.start_date, config.end_date)

        if not bars:
            raise ValueError(f"No historical data found for {config.symbol}")

        # Initialize backtest engine
        engine = BacktestEngine(config)

        # Define simple buy-and-hold strategy for MVP
        def simple_strategy(bar: OHLCVBar, context: dict) -> str | None:
            """Simple buy-and-hold strategy: buy on first bar, hold until end."""
            bar_count = context.get("bar_count", 0)
            if bar_count == 1:  # First bar
                return "BUY"
            return None

        # Run backtest
        result = engine.run(bars, strategy_func=simple_strategy)

        # Update result with correct run_id
        result.backtest_run_id = run_id

        # Save to database
        repository = BacktestRepository(session)
        await repository.save_result(result)

        # Update in-memory tracking
        backtest_runs[run_id]["status"] = "COMPLETED"

        logger.info(
            "Backtest completed successfully",
            extra={
                "backtest_run_id": str(run_id),
                "total_trades": len(result.trades),
                "win_rate": float(result.summary.win_rate) if result.summary.win_rate else 0,
            },
        )

    except Exception as e:
        # Handle errors
        backtest_runs[run_id]["status"] = "FAILED"
        backtest_runs[run_id]["error"] = str(e)

        logger.error(
            "Backtest failed",
            extra={"backtest_run_id": str(run_id), "error": str(e)},
            exc_info=True,
        )
