"""
Walk-forward testing endpoints.

Story 12.4 Endpoints:
- POST /walk-forward: Run walk-forward validation test
- GET /walk-forward/{walk_forward_id}: Get walk-forward result
- GET /walk-forward: List walk-forward results (paginated)
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
            engine = WalkForwardEngine()
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
