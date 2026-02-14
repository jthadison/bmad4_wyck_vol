"""
Backtest preview endpoints.

Story 11.2 Endpoints:
- POST /preview: Initiate backtest preview
- GET /status/{run_id}: Get backtest status

Provides quick backtest previews without full execution.
"""

import asyncio
import logging
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.websocket import manager
from src.backtesting.engine import BacktestEngine as PreviewEngine
from src.database import async_session_maker, get_db
from src.models.backtest import (
    BacktestCompletedMessage,
    BacktestConfig,
    BacktestPreviewRequest,
    BacktestPreviewResponse,
    BacktestProgressUpdate,
    BacktestResult,
)
from src.repositories.backtest_repository import BacktestRepository

from .utils import backtest_runs, fetch_historical_data, get_current_configuration

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/preview", response_model=BacktestPreviewResponse, status_code=status.HTTP_202_ACCEPTED
)
async def start_backtest_preview(
    request: BacktestPreviewRequest,
    session: AsyncSession = Depends(get_db),
) -> BacktestPreviewResponse:
    """
    Initiate backtest preview with proposed configuration.

    This endpoint queues an asynchronous backtest that compares the current
    system configuration against the proposed changes using historical data.

    Args:
        request: Backtest preview request with proposed config and parameters
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
    # DEPRECATION: Preview mode disabled due to critical statistical flaws
    # See Story 13.5 / Bug C-1 for details
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Preview mode temporarily disabled due to critical statistical issues:\n"
            "1. Same-bar entry/exit violates chronological ordering\n"
            "2. Confidence-scaled exits have no statistical justification\n"
            "3. No stop-loss simulation (assumes all trades profitable)\n\n"
            "Please use /api/v1/backtest/full for accurate backtesting.\n"
            "Preview mode will be re-enabled in a future release with proper multi-bar simulation."
        ),
    )

    # DEPRECATED CODE BELOW - Will be removed in next cleanup
    print(f"[ROUTE DEBUG] start_backtest_preview called, request={request}", flush=True)

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

    # Queue background task - Use asyncio.create_task for better Windows compatibility
    print(f"[QUEUE DEBUG] About to queue task for {run_id}", flush=True)

    async def _run_task_with_error_handling():
        try:
            await run_backtest_preview_task(run_id, request)
        except Exception as e:
            print(f"[ERROR] Background task failed with exception: {e}", flush=True)
            import traceback

            traceback.print_exc()
            raise

    asyncio.create_task(_run_task_with_error_handling())
    print("[QUEUE DEBUG] Task queued successfully", flush=True)

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


async def run_backtest_preview_task(run_id: UUID, request: BacktestPreviewRequest) -> None:
    """
    Background task to execute backtest preview.

    Args:
        run_id: Backtest run identifier
        request: Backtest request parameters
    """
    print(f"[TASK DEBUG] Background task started for {run_id}", flush=True)
    try:
        # Update status to running
        print(f"[TASK DEBUG] About to update status for {run_id}", flush=True)
        backtest_runs[run_id]["status"] = "running"
        print("[TASK DEBUG] Status updated to running", flush=True)

        logger.info("Starting backtest preview execution", extra={"backtest_run_id": str(run_id)})
        print("[TASK DEBUG] Logger info called", flush=True)

        # Fetch historical data from Polygon.io (or fallback to synthetic)
        print("[TASK DEBUG] About to fetch historical data", flush=True)
        historical_bars = await fetch_historical_data(
            request.days, request.symbol, request.timeframe
        )
        print(f"[TASK DEBUG] Fetched {len(historical_bars)} bars", flush=True)
        total_bars = len(historical_bars)
        backtest_runs[run_id]["progress"]["total_bars"] = total_bars

        # Get current configuration (simplified for MVP) - create session manually
        print("[TASK DEBUG] About to get current configuration", flush=True)
        async with async_session_maker() as session:
            print("[TASK DEBUG] Session created, calling get_current_configuration", flush=True)
            current_config = await get_current_configuration(session)
            print(f"[TASK DEBUG] Got current config: {current_config}", flush=True)

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
        print("[TASK DEBUG] Creating PreviewEngine", flush=True)
        engine = PreviewEngine(progress_callback=progress_callback)
        print("[TASK DEBUG] PreviewEngine created", flush=True)

        try:
            print("[TASK DEBUG] About to call engine.run_preview()", flush=True)
            comparison = await engine.run_preview(
                backtest_run_id=run_id,
                current_config=current_config,
                proposed_config=request.proposed_config,
                historical_bars=historical_bars,
                timeout_seconds=300,  # 5 minutes
            )
            print("[TASK DEBUG] engine.run_preview() completed", flush=True)

            # Mark as completed
            print("[TASK DEBUG] Marking backtest as completed", flush=True)
            backtest_runs[run_id]["status"] = "completed"
            backtest_runs[run_id]["comparison"] = comparison
            print("[TASK DEBUG] Backtest marked as completed", flush=True)

            # Save backtest result to database for persistence
            try:
                print("[TASK DEBUG] Saving backtest result to database", flush=True)

                # Calculate start and end dates from historical bars
                start_date = (
                    datetime.fromisoformat(str(historical_bars[0]["timestamp"])).date()
                    if historical_bars
                    else date.today()
                )
                end_date = (
                    datetime.fromisoformat(str(historical_bars[-1]["timestamp"])).date()
                    if historical_bars
                    else date.today()
                )

                # Construct BacktestResult from comparison (using proposed config metrics)
                backtest_result = BacktestResult(
                    backtest_run_id=run_id,
                    symbol=request.symbol or "SYNTHETIC",
                    timeframe=request.timeframe,
                    start_date=start_date,
                    end_date=end_date,
                    config=BacktestConfig(
                        symbol=request.symbol or "SYNTHETIC",
                        start_date=start_date,
                        end_date=end_date,
                        # Use defaults for other config fields
                    ),
                    equity_curve=comparison.equity_curve_proposed,
                    trades=[],  # Preview engine doesn't track individual trades
                    summary=comparison.proposed_metrics,
                    look_ahead_bias_check=False,
                    execution_time_seconds=0.0,
                    created_at=datetime.now(UTC),
                )

                # Save to database using BacktestRepository
                async with async_session_maker() as db_session:
                    repository = BacktestRepository(db_session)
                    await repository.save_result(backtest_result)
                    print("[TASK DEBUG] Backtest result saved to database successfully", flush=True)
                    logger.info(
                        "Backtest result saved to database",
                        extra={"backtest_run_id": str(run_id), "symbol": request.symbol},
                    )
            except Exception as db_error:
                # Log database save error but don't fail the backtest
                logger.error(
                    "Failed to save backtest result to database",
                    extra={"backtest_run_id": str(run_id), "error": str(db_error)},
                    exc_info=True,
                )
                print(f"[TASK DEBUG] Database save failed: {db_error}", flush=True)

            # Emit completion message via WebSocket
            sequence_number += 1
            print("[TASK DEBUG] Creating completion message", flush=True)
            completion_msg = BacktestCompletedMessage(
                sequence_number=sequence_number,
                backtest_run_id=run_id,
                comparison=comparison,
                timestamp=datetime.now(UTC),
            )
            print("[TASK DEBUG] About to broadcast completion message", flush=True)

            await manager.broadcast(completion_msg.model_dump(mode="json"))
            print("[TASK DEBUG] Broadcast completed", flush=True)

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
