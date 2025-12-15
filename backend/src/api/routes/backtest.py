"""
Backtest Preview API Routes (Story 11.2 Task 1)

Purpose:
--------
Provides REST endpoints for backtest preview functionality.
Enables traders to validate proposed configuration changes against
historical data before applying them.

Endpoints:
----------
- POST /api/v1/backtest/preview: Initiate backtest preview
- GET /api/v1/backtest/status/{run_id}: Get backtest status

Author: Story 11.2
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.websocket import manager
from src.backtesting.engine import BacktestEngine
from src.database import get_db
from src.models.backtest import (
    BacktestCompletedMessage,
    BacktestPreviewRequest,
    BacktestPreviewResponse,
    BacktestProgressUpdate,
)

router = APIRouter(prefix="/backtest", tags=["backtest"])
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

        # Initialize and run backtest engine
        engine = BacktestEngine(progress_callback=progress_callback)

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
