"""
Walk-forward testing endpoints.

Story 12.4 Endpoints:
- POST /walk-forward: Run walk-forward validation test
- GET /walk-forward/{walk_forward_id}: Get walk-forward result
- GET /walk-forward: List walk-forward results (paginated)

Story 23.9 Endpoints:
- POST /walk-forward/suite: Run full walk-forward validation suite
- GET /walk-forward/suite/results: Get latest suite results
"""

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import async_session_maker, get_db
from src.models.backtest import WalkForwardConfig
from src.repositories.walk_forward_repository import WalkForwardRepository

from .utils import cleanup_stale_entries, walk_forward_runs

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/walk-forward",
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_walk_forward_test(
    config: WalkForwardConfig,
):
    """
    Run walk-forward validation test.

    AC9 Subtask 9.1-9.5: Initiate walk-forward test as background task.

    This endpoint queues an asynchronous walk-forward test that validates
    system performance across multiple rolling windows.

    Args:
        config: Walk-forward configuration

    Returns:
        Response with walk_forward_id and status

    Raises:
        400 Bad Request: Invalid configuration
        503 Service Unavailable: Too many concurrent tests

    Example Response:
        {
            "walk_forward_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "RUNNING",
            "estimated_duration_seconds": 300
        }
    """
    from src.backtesting.walk_forward_engine import WalkForwardEngine

    # Check for concurrent test limit (MVP: max 3 concurrent)
    running_tests = sum(1 for run in walk_forward_runs.values() if run["status"] == "RUNNING")
    if running_tests >= 3:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Walk-forward engine overloaded - too many concurrent tests. Please try again later.",
        )

    # Generate unique walk-forward ID
    walk_forward_id = uuid4()

    # Initialize walk-forward run tracking
    cleanup_stale_entries(walk_forward_runs)
    walk_forward_runs[walk_forward_id] = {
        "status": "RUNNING",
        "config": config,
        "created_at": datetime.now(UTC),
    }

    # Queue background task (uses its own DB session, not the request-scoped one)
    async def run_walk_forward():
        """Background task to execute walk-forward test."""
        try:
            from .utils import fetch_historical_bars

            bars = await fetch_historical_bars(
                config.symbols[0],
                config.overall_start_date,
                config.overall_end_date,
            )
            engine = WalkForwardEngine(market_data=bars)
            result = engine.walk_forward_test(config.symbols, config)

            # Save to database using a fresh session (not request-scoped)
            async with async_session_maker() as bg_session:
                repository = WalkForwardRepository(bg_session)
                await repository.save_result(result)

            # Update run tracking
            walk_forward_runs[walk_forward_id]["status"] = "COMPLETED"
            walk_forward_runs[walk_forward_id]["result"] = result

        except Exception as e:
            logger.error(f"Walk-forward test failed: {e}")
            walk_forward_runs[walk_forward_id]["status"] = "FAILED"
            walk_forward_runs[walk_forward_id]["error"] = str(e)

    asyncio.create_task(run_walk_forward())

    # Estimate duration: ~10 seconds per window, assume 10 windows
    estimated_duration = 100

    return {
        "walk_forward_id": str(walk_forward_id),
        "status": "RUNNING",
        "estimated_duration_seconds": estimated_duration,
    }


@router.get(
    "/walk-forward/{walk_forward_id}",
)
async def get_walk_forward_result(
    walk_forward_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Get walk-forward test result by ID.

    AC9 Subtask 9.6-9.7: Retrieve walk-forward result.

    Args:
        walk_forward_id: UUID of the walk-forward test
        session: Database session

    Returns:
        WalkForwardResult if completed, status if running, 404 if not found

    Raises:
        404 Not Found: Walk-forward test not found

    Example Response (completed):
        {
            "walk_forward_id": "550e8400...",
            "windows": [...],
            "summary_statistics": {...},
            "stability_score": 0.15,
            "degradation_windows": [3, 7],
            "statistical_significance": {...},
            "chart_data": {...}
        }
    """
    # Check in-memory storage first
    if walk_forward_id in walk_forward_runs:
        run_info = walk_forward_runs[walk_forward_id]

        if run_info["status"] == "RUNNING":
            return {
                "walk_forward_id": str(walk_forward_id),
                "status": "RUNNING",
            }
        elif run_info["status"] == "FAILED":
            return {
                "walk_forward_id": str(walk_forward_id),
                "status": "FAILED",
                "error": run_info.get("error"),
            }

    # Query database
    repository = WalkForwardRepository(session)
    result = await repository.get_result(walk_forward_id)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Walk-forward test {walk_forward_id} not found",
        )

    return result


@router.get(
    "/walk-forward",
)
async def list_walk_forward_results(
    limit: int = 10,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
):
    """
    List walk-forward results with pagination.

    AC9 Subtask 9.8: List results with pagination.

    Args:
        limit: Maximum number of results (default 10, max 100)
        offset: Number of results to skip (default 0)
        session: Database session

    Returns:
        List of WalkForwardResult objects

    Example Response:
        [
            {
                "walk_forward_id": "550e8400...",
                "windows": [...],
                "summary_statistics": {...},
                ...
            },
            ...
        ]
    """
    # Validate pagination parameters
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 10
    if offset < 0:
        offset = 0

    # Query database
    repository = WalkForwardRepository(session)
    results = await repository.list_results(limit=limit, offset=offset)

    return results


# --- Story 23.9: Walk-Forward Validation Suite Endpoints ---

# In-memory storage for suite runs, keyed by UUID for cleanup_stale_entries compat
_suite_runs: dict[UUID, dict] = {}


@router.post(
    "/walk-forward/suite",
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_walk_forward_suite():
    """
    Run the full walk-forward validation suite (Story 23.9).

    Runs walk-forward tests on all configured symbols (EURUSD, GBPUSD, SPX500, US30),
    compares results against stored baselines, and flags regressions.

    Returns:
        Response with suite_id and status
    """
    from src.backtesting.walk_forward_config import get_default_suite_config
    from src.backtesting.walk_forward_suite import WalkForwardSuite

    # Check concurrent suite limit (max 1 concurrent)
    running = sum(1 for run in _suite_runs.values() if run["status"] == "RUNNING")
    if running >= 1:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Walk-forward suite already running. Please wait for completion.",
        )

    config = get_default_suite_config()
    suite = WalkForwardSuite(config)
    suite_id = uuid4()

    # Cleanup stale entries before inserting (same pattern as walk_forward_runs)
    cleanup_stale_entries(_suite_runs)

    _suite_runs[suite_id] = {
        "status": "RUNNING",
        "created_at": datetime.now(UTC),
    }

    async def run_suite():
        try:
            # Offload sync/CPU-bound suite.run() to a thread to avoid blocking the event loop
            result = await asyncio.to_thread(suite.run)
            _suite_runs[suite_id]["status"] = "COMPLETED"
            _suite_runs[suite_id]["result"] = result
        except Exception as e:
            logger.error(f"Walk-forward suite failed: {e}")
            _suite_runs[suite_id]["status"] = "FAILED"
            _suite_runs[suite_id]["error"] = str(e)

    asyncio.create_task(run_suite())

    return {
        "suite_id": str(suite_id),
        "status": "RUNNING",
        "symbols": [s.symbol for s in config.symbols],
    }


@router.get(
    "/walk-forward/{walk_forward_id}/stability",
)
async def get_walk_forward_stability(
    walk_forward_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Get per-window stability data for a walk-forward test (Feature 10).

    Returns IS vs OOS metrics per window, parameter stability across windows,
    and a robustness score summary used by quants to detect overfitting.

    Args:
        walk_forward_id: UUID of the walk-forward test
        session: Database session

    Returns:
        Stability data with per-window breakdown, parameter stability, and robustness score

    Raises:
        404 Not Found: Walk-forward test not found or still running
    """
    import statistics

    # Check in-memory storage first (still running or recently completed)
    if walk_forward_id in walk_forward_runs:
        run_info = walk_forward_runs[walk_forward_id]
        if run_info["status"] == "RUNNING":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Walk-forward test {walk_forward_id} is still running",
            )

    # Query database for the result
    repository = WalkForwardRepository(session)
    result = await repository.get_result(walk_forward_id)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Walk-forward test {walk_forward_id} not found",
        )

    windows_data = []
    for w in result.windows:
        # Extract Sharpe, return, drawdown from train/validate metrics
        is_sharpe = float(w.train_metrics.sharpe_ratio)
        oos_sharpe = float(w.validate_metrics.sharpe_ratio)
        is_return = float(w.train_metrics.total_return_pct)
        oos_return = float(w.validate_metrics.total_return_pct)
        is_drawdown = float(w.train_metrics.max_drawdown)
        oos_drawdown = float(w.validate_metrics.max_drawdown)

        windows_data.append(
            {
                "window_index": w.window_number,
                "is_start": w.train_start_date.isoformat(),
                "is_end": w.train_end_date.isoformat(),
                "oos_start": w.validate_start_date.isoformat(),
                "oos_end": w.validate_end_date.isoformat(),
                "is_sharpe": round(is_sharpe, 4),
                "oos_sharpe": round(oos_sharpe, 4),
                "is_return": round(is_return, 4),
                "oos_return": round(oos_return, 4),
                "is_drawdown": round(is_drawdown, 4),
                "oos_drawdown": round(oos_drawdown, 4),
                # optimal_params are derived from WalkForwardConfig backtest_config fields
                "optimal_params": {
                    "lookback_days": result.config.train_period_months * 21,
                    "validate_months": result.config.validate_period_months,
                },
            }
        )

    # Build parameter stability: track config-level params per window
    # Since the stored model holds a single config, we show stable params across windows
    n_windows = len(result.windows)
    train_months_list = [result.config.train_period_months] * n_windows
    validate_months_list = [result.config.validate_period_months] * n_windows
    parameter_stability = {
        "train_period_months": train_months_list,
        "validate_period_months": validate_months_list,
    }

    # Robustness score calculations
    profitable_windows = sum(1 for w in windows_data if w["oos_return"] > 0)
    profitable_window_pct = profitable_windows / n_windows if n_windows > 0 else 0.0

    oos_drawdowns = [w["oos_drawdown"] for w in windows_data]
    worst_oos_drawdown = max(oos_drawdowns) if oos_drawdowns else 0.0

    # IS/OOS Sharpe ratio: avg(IS Sharpe) / avg(OOS Sharpe) — lower is better
    is_sharpes = [w["is_sharpe"] for w in windows_data]
    oos_sharpes = [w["oos_sharpe"] for w in windows_data]
    avg_is_sharpe = statistics.mean(is_sharpes) if is_sharpes else 0.0
    avg_oos_sharpe = statistics.mean(oos_sharpes) if oos_sharpes else 0.0

    if avg_oos_sharpe != 0:
        avg_is_oos_sharpe_ratio = round(avg_is_sharpe / avg_oos_sharpe, 4)
    else:
        avg_is_oos_sharpe_ratio = float("inf") if avg_is_sharpe > 0 else 1.0

    robustness_score = {
        "profitable_window_pct": round(profitable_window_pct, 4),
        "worst_oos_drawdown": round(worst_oos_drawdown, 4),
        "avg_is_oos_sharpe_ratio": round(avg_is_oos_sharpe_ratio, 4),
    }

    return {
        "walk_forward_id": str(walk_forward_id),
        "windows": windows_data,
        "parameter_stability": parameter_stability,
        "robustness_score": robustness_score,
    }


@router.get(
    "/walk-forward/suite/results",
)
async def get_walk_forward_suite_results(
    suite_id: UUID | None = None,
):
    """
    Get walk-forward suite results (Story 23.9).

    Args:
        suite_id: Optional suite UUID. If not provided, returns the latest result.

    Returns:
        Suite results or status if still running
    """
    if suite_id:
        if suite_id not in _suite_runs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Suite run {suite_id} not found",
            )
        run = _suite_runs[suite_id]
    else:
        # Return the latest result
        if not _suite_runs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No suite runs found",
            )
        latest_id = max(_suite_runs.keys(), key=lambda k: _suite_runs[k]["created_at"])
        suite_id = latest_id
        run = _suite_runs[suite_id]

    if run["status"] == "RUNNING":
        return {"suite_id": str(suite_id), "status": "RUNNING"}
    elif run["status"] == "FAILED":
        return {"suite_id": str(suite_id), "status": "FAILED", "error": run.get("error")}
    else:
        return {"suite_id": str(suite_id), "status": "COMPLETED", "result": run.get("result")}
