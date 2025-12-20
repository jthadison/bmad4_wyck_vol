"""
Backtest API Routes (Story 11.2 + Story 12.1)

Purpose:
--------
Provides REST endpoints for backtesting functionality.

Story 11.2 Endpoints (Preview):
- POST /api/v1/backtest/preview: Initiate backtest preview
- GET /api/v1/backtest/status/{run_id}: Get backtest status

Story 12.1 Endpoints (Full Backtest):
- POST /api/v1/backtest/run: Run full backtest with persistence
- GET /api/v1/backtest/results/{backtest_run_id}: Get specific result
- GET /api/v1/backtest/results: List all results (paginated)

Author: Story 11.2, Story 12.1 Task 8
"""

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.websocket import manager
from src.backtesting.backtest_engine import BacktestEngine
from src.backtesting.engine import BacktestEngine as PreviewEngine
from src.database import get_db
from src.models.backtest import (
    BacktestCompletedMessage,
    BacktestConfig,
    BacktestPreviewRequest,
    BacktestPreviewResponse,
    BacktestProgressUpdate,
)
from src.models.ohlcv import OHLCVBar

router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])
logger = logging.getLogger(__name__)

# In-memory storage for backtest runs (MVP - replace with database in production)
backtest_runs: dict[UUID, dict] = {}


@router.post(
    "/preview", response_model=BacktestPreviewResponse, status_code=status.HTTP_202_ACCEPTED
)
async def start_backtest_preview(
    request: BacktestPreviewRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
) -> BacktestPreviewResponse:
    """
    Initiate backtest preview with proposed configuration.

    This endpoint queues an asynchronous backtest that compares the current
    system configuration against the proposed changes using historical data.

    Args:
        request: Backtest preview request with proposed config and parameters
        background_tasks: FastAPI background tasks for async execution
        session: Database session

    Returns:
        BacktestPreviewResponse with run_id and status

    Raises:
        400 Bad Request: Invalid config payload
        422 Unprocessable Entity: Validation error (days out of range)
        503 Service Unavailable: Too many concurrent backtests

    Example Response:
        {
            "backtest_run_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "queued",
            "estimated_duration_seconds": 120
        }
    """
    # Check for concurrent backtest limit (MVP: max 5 concurrent)
    running_backtests = sum(
        1 for run in backtest_runs.values() if run["status"] in ["queued", "running"]
    )
    if running_backtests >= 5:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backtest engine overloaded - too many concurrent backtests. Please try again later.",
        )

    # Generate unique run ID
    run_id = uuid4()

    # Initialize backtest run tracking
    backtest_runs[run_id] = {
        "status": "queued",
        "progress": {"bars_analyzed": 0, "total_bars": 0, "percent_complete": 0},
        "created_at": datetime.now(UTC),
        "error": None,
    }

    # Estimate duration (roughly 1 second per day of data for 90 days = ~90-120s)
    estimated_duration = int(request.days * 1.5)  # 1.5 seconds per day estimate

    # Queue background task
    background_tasks.add_task(
        run_backtest_preview_task,
        run_id,
        request,
        session,  # Pass session if needed
    )

    logger.info(
        "Backtest preview queued",
        extra={
            "backtest_run_id": str(run_id),
            "days": request.days,
            "estimated_duration_seconds": estimated_duration,
        },
    )

    return BacktestPreviewResponse(
        backtest_run_id=run_id, status="queued", estimated_duration_seconds=estimated_duration
    )


@router.get("/status/{run_id}")
async def get_backtest_status(run_id: UUID) -> dict:
    """
    Get current status and progress of a backtest run.

    This endpoint provides REST polling fallback when WebSocket is unavailable.

    Args:
        run_id: Backtest run identifier

    Returns:
        Status object with current progress

    Raises:
        404 Not Found: Backtest run not found

    Example Response:
        {
            "status": "running",
            "progress": {
                "bars_analyzed": 1245,
                "total_bars": 2268,
                "percent_complete": 54
            }
        }
    """
    if run_id not in backtest_runs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Backtest run {run_id} not found"
        )

    run = backtest_runs[run_id]
    return {"status": run["status"], "progress": run["progress"], "error": run.get("error")}


async def run_backtest_preview_task(
    run_id: UUID, request: BacktestPreviewRequest, session: AsyncSession
) -> None:
    """
    Background task to execute backtest preview.

    Args:
        run_id: Backtest run identifier
        request: Backtest request parameters
        session: Database session for data access
    """
    try:
        # Update status to running
        backtest_runs[run_id]["status"] = "running"

        logger.info("Starting backtest preview execution", extra={"backtest_run_id": str(run_id)})

        # Fetch historical data (MVP: Generate sample data)
        historical_bars = await fetch_historical_data(request.days, request.symbol)
        total_bars = len(historical_bars)
        backtest_runs[run_id]["progress"]["total_bars"] = total_bars

        # Get current configuration (simplified for MVP)
        current_config = await get_current_configuration(session)

        # Create progress callback for WebSocket updates
        sequence_number = 0

        async def progress_callback(bars_analyzed: int, total_bars: int, percent_complete: int):
            nonlocal sequence_number
            sequence_number += 1

            # Update in-memory tracking
            backtest_runs[run_id]["progress"] = {
                "bars_analyzed": bars_analyzed,
                "total_bars": total_bars,
                "percent_complete": percent_complete,
            }

            # Emit WebSocket progress update
            progress_msg = BacktestProgressUpdate(
                sequence_number=sequence_number,
                backtest_run_id=run_id,
                bars_analyzed=bars_analyzed,
                total_bars=total_bars,
                percent_complete=percent_complete,
                timestamp=datetime.now(UTC),
            )

            await manager.broadcast(progress_msg.model_dump(mode="json"))

        # Initialize and run backtest engine (Story 11.2 preview engine)
        engine = PreviewEngine(progress_callback=progress_callback)

        try:
            comparison = await engine.run_preview(
                backtest_run_id=run_id,
                current_config=current_config,
                proposed_config=request.proposed_config,
                historical_bars=historical_bars,
                timeout_seconds=300,  # 5 minutes
            )

            # Mark as completed
            backtest_runs[run_id]["status"] = "completed"
            backtest_runs[run_id]["comparison"] = comparison

            # Emit completion message via WebSocket
            sequence_number += 1
            completion_msg = BacktestCompletedMessage(
                sequence_number=sequence_number,
                backtest_run_id=run_id,
                comparison=comparison,
                timestamp=datetime.now(UTC),
            )

            await manager.broadcast(completion_msg.model_dump(mode="json"))

            logger.info(
                "Backtest preview completed successfully",
                extra={
                    "backtest_run_id": str(run_id),
                    "recommendation": comparison.recommendation,
                },
            )

        except asyncio.TimeoutError:
            # Handle timeout - mark as timeout with partial results
            backtest_runs[run_id]["status"] = "timeout"
            logger.warning(
                "Backtest preview timed out",
                extra={
                    "backtest_run_id": str(run_id),
                    "bars_analyzed": backtest_runs[run_id]["progress"]["bars_analyzed"],
                },
            )

    except Exception as e:
        # Handle errors
        backtest_runs[run_id]["status"] = "failed"
        backtest_runs[run_id]["error"] = str(e)

        logger.error(
            "Backtest preview failed",
            extra={"backtest_run_id": str(run_id), "error": str(e)},
            exc_info=True,
        )


async def fetch_historical_data(days: int, symbol: str | None) -> list[dict]:
    """
    Fetch historical OHLCV data for backtest.

    For MVP, this generates sample data. In production, this would:
    1. Query the database for stored historical bars
    2. Fetch from Polygon.io API if not available locally

    Args:
        days: Number of days of historical data
        symbol: Optional symbol filter

    Returns:
        List of OHLCV bar dictionaries
    """
    # Generate sample historical data for MVP
    # In production, query from database or external API

    bars = []
    start_date = datetime.now(UTC) - timedelta(days=days)

    # Generate daily bars (assuming 252 trading days per year)
    # For 90 days, this gives ~90 bars
    for i in range(days):
        timestamp = start_date + timedelta(days=i)

        # Generate realistic-looking OHLCV data
        base_price = Decimal("150.00") + Decimal(str(i * 0.5))  # Trending upward
        daily_range = Decimal("5.00")

        bars.append(
            {
                "timestamp": timestamp,
                "open": float(base_price),
                "high": float(base_price + daily_range),
                "low": float(base_price - daily_range),
                "close": float(base_price + (daily_range * Decimal("0.3"))),
                "volume": 1000000 + (i * 10000),
            }
        )

    return bars


async def get_current_configuration(session: AsyncSession) -> dict:
    """
    Fetch current system configuration.

    In production, this would query the configuration from the database.
    For MVP, returns a simplified default configuration.

    Args:
        session: Database session

    Returns:
        Current configuration dictionary
    """
    # Simplified default configuration for MVP
    # In production, fetch from ConfigurationService
    return {
        "volume_thresholds": {
            "ultra_high": 2.5,
            "high": 1.8,
            "medium": 1.2,
            "low": 0.8,
        },
        "risk_limits": {"max_portfolio_heat": 0.06, "max_campaign_heat": 0.02},
    }


# =============================
# Story 12.1 Task 8: Full Backtest Endpoints
# =============================


@router.post("/run", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def run_backtest(
    config: BacktestConfig,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    Run a full backtest with the provided configuration.

    AC7 Subtask 8.1-8.5: Run backtest as background task, return immediately.

    Args:
        config: Backtest configuration (symbol, date range, initial capital)
        background_tasks: FastAPI background tasks
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
    from uuid import uuid4

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
    background_tasks.add_task(
        run_backtest_task,
        run_id,
        config,
        session,
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
    from src.repositories.backtest_repository import BacktestRepository

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
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    List backtest results with pagination and optional filtering.

    AC7 Subtask 8.8-8.9: Paginated listing with optional symbol filter.

    Args:
        symbol: Optional symbol filter
        limit: Maximum number of results (default 100, max 1000)
        offset: Number of results to skip (default 0)
        session: Database session

    Returns:
        Paginated list of backtest results

    Example Response:
        {
            "results": [
                {
                    "backtest_run_id": "...",
                    "symbol": "AAPL",
                    "metrics": {...},
                    ...
                },
                ...
            ],
            "total": 42,
            "limit": 100,
            "offset": 0
        }
    """
    from src.repositories.backtest_repository import BacktestRepository

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
    from src.repositories.backtest_repository import BacktestRepository

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
                "win_rate": float(result.metrics.win_rate) if result.metrics.win_rate else 0,
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


async def fetch_historical_bars(symbol: str, start_date: date, end_date: date) -> list[OHLCVBar]:
    """
    Fetch historical OHLCV bars for backtest.

    In production, this would query the OHLCV repository.
    For MVP, generates sample data.

    Args:
        symbol: Trading symbol
        start_date: Start date
        end_date: End date

    Returns:
        List of OHLCV bars
    """
    bars = []
    current_date = start_date

    # Generate daily bars
    while current_date <= end_date:
        timestamp = datetime.combine(current_date, datetime.min.time(), tzinfo=UTC)

        # Generate realistic-looking OHLCV data
        day_offset = (current_date - start_date).days
        base_price = Decimal("150.00") + Decimal(str(day_offset * 0.5))
        daily_range = Decimal("5.00")

        bars.append(
            OHLCVBar(
                symbol=symbol,
                timeframe="1d",
                open=base_price,
                high=base_price + daily_range,
                low=base_price - daily_range,
                close=base_price + (daily_range * Decimal("0.3")),
                volume=1000000 + (day_offset * 10000),
                spread=daily_range,
                timestamp=timestamp,
            )
        )

        current_date += timedelta(days=1)

    return bars
