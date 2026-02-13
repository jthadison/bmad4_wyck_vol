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

from src.backtesting.engine.backtest_engine import UnifiedBacktestEngine
from src.backtesting.engine.cost_model import ZeroCostModel
from src.backtesting.engine.interfaces import EngineConfig
from src.backtesting.engine.validated_detector import ValidatedSignalDetector
from src.backtesting.engine.wyckoff_detector import WyckoffSignalDetector
from src.backtesting.position_manager import PositionManager
from src.backtesting.risk_integration import BacktestRiskManager
from src.database import async_session_maker, get_db
from src.models.backtest import BacktestConfig
from src.repositories.backtest_repository import BacktestRepository

from .utils import backtest_runs, cleanup_stale_entries, fetch_historical_bars

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/run", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def run_backtest(
    config: BacktestConfig,
) -> dict:
    """
    Run a full backtest with the provided configuration.

    AC7 Subtask 8.1-8.5: Run backtest as background task, return immediately.

    Args:
        config: Backtest configuration (symbol, date range, initial capital)

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
    cleanup_stale_entries(backtest_runs)
    backtest_runs[run_id] = {
        "status": "RUNNING",
        "created_at": datetime.now(UTC),
        "error": None,
    }

    # Queue background task (uses its own DB session, not the request-scoped one).
    # Store task reference to prevent garbage collection and enable error logging.
    task = asyncio.create_task(
        run_backtest_task(
            run_id,
            config,
        ),
        name=f"backtest-{run_id}",
    )
    backtest_runs[run_id]["task"] = task

    def _on_task_done(t: asyncio.Task) -> None:  # type: ignore[type-arg]
        if t.cancelled():
            logger.warning("Backtest task cancelled", extra={"backtest_run_id": str(run_id)})
        elif exc := t.exception():
            logger.error(
                "Backtest task raised unhandled exception",
                extra={"backtest_run_id": str(run_id), "error": str(exc)},
            )

    task.add_done_callback(_on_task_done)

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
) -> None:
    """
    Background task to execute full backtest using Wyckoff pattern detection.

    AC7 Subtask 8.4-8.10: Execute engine, save to database via repository.

    Bug C-3 (verified 2026-02): This task creates its own database session
    via ``async with async_session_maker() as session`` rather than accepting
    the request-scoped session (which is closed after the HTTP 202 response).
    The repository calls ``await session.commit()`` explicitly, and the
    ``async with`` block calls ``session.close()`` on exit (both success and
    error paths). This pattern is also used in preview.py, regression.py,
    and walk_forward.py background tasks.

    Args:
        run_id: Backtest run identifier
        config: Backtest configuration
    """
    try:
        logger.info("Starting backtest execution", extra={"backtest_run_id": str(run_id)})

        # Fetch historical data
        bars = await fetch_historical_bars(config.symbol, config.start_date, config.end_date)

        if not bars:
            raise ValueError(f"No historical data found for {config.symbol}")

        # Build Wyckoff signal detection pipeline
        wyckoff_detector = WyckoffSignalDetector()
        validated_detector = ValidatedSignalDetector(wyckoff_detector)

        # Build engine dependencies
        cost_model = ZeroCostModel()
        position_manager = PositionManager(config.initial_capital)
        engine_config = EngineConfig(
            initial_capital=config.initial_capital,
            max_position_size=config.max_position_size,
        )
        risk_manager = BacktestRiskManager(initial_capital=config.initial_capital)

        # Create and run unified backtest engine.
        # engine.run() is synchronous and CPU-bound, so run it in a thread
        # to avoid blocking the async event loop.
        engine = UnifiedBacktestEngine(
            signal_detector=validated_detector,
            cost_model=cost_model,
            position_manager=position_manager,
            config=engine_config,
            risk_manager=risk_manager,
        )
        result = await asyncio.to_thread(engine.run, bars)

        # Update result with correct run_id
        result.backtest_run_id = run_id

        # Save to database using a fresh session (not request-scoped)
        async with async_session_maker() as session:
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
