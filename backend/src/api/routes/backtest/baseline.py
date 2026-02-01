"""
Regression baseline endpoints.

Story 12.7 Baseline Endpoints:
- POST /regression/{test_id}/establish-baseline: Establish baseline
- GET /regression/baseline/current: Get current baseline
- GET /regression/baseline/history: List baseline history
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.repositories.regression_baseline_repository import RegressionBaselineRepository
from src.repositories.regression_test_repository import RegressionTestRepository

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/regression/{test_id}/establish-baseline")
async def establish_baseline_from_test(
    test_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Establish baseline from regression test result.

    Story 12.7 Task 11 Subtask 11.10-11.12:
    Creates new baseline from specified test result and marks it as current.

    Args:
        test_id: Test identifier to use as baseline
        session: Database session

    Returns:
        RegressionBaseline object

    Raises:
        404 Not Found: Test not found
        400 Bad Request: Test status not PASS

    Example Response:
        {
            "baseline_id": "660e8400...",
            "test_id": "550e8400...",
            "version": "abc123",
            "metrics": {...},
            "per_symbol_metrics": {...},
            "is_current": true,
            "established_at": "2024-01-15T02:00:00Z"
        }
    """
    from src.backtesting.regression_test_engine import RegressionTestEngine

    # Get test result
    test_repo = RegressionTestRepository(session)
    result = await test_repo.get_result(test_id)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Regression test {test_id} not found",
        )

    if result.status != "PASS":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot establish baseline from test with status {result.status}. Only PASS tests can be used as baselines.",
        )

    # Create baseline repository
    baseline_repo = RegressionBaselineRepository(session)

    # Create engine
    engine = RegressionTestEngine(
        test_repository=test_repo,
        baseline_repository=baseline_repo,
    )

    # Establish baseline
    baseline = await engine.establish_baseline(result)

    logger.info(
        "Baseline established",
        extra={
            "baseline_id": str(baseline.baseline_id),
            "test_id": str(test_id),
            "version": baseline.version,
        },
    )

    return baseline


@router.get("/regression/baseline/current")
async def get_current_baseline(
    session: AsyncSession = Depends(get_db),
):
    """
    Get current active baseline.

    Story 12.7 Task 11 Subtask 11.13-11.14:
    Returns current baseline or 404 if not set.

    Args:
        session: Database session

    Returns:
        RegressionBaseline if exists

    Raises:
        404 Not Found: No current baseline set

    Example Response:
        {
            "baseline_id": "660e8400...",
            "test_id": "550e8400...",
            "version": "abc123",
            "metrics": {...},
            "per_symbol_metrics": {...},
            "is_current": true,
            "established_at": "2024-01-15T02:00:00Z"
        }
    """
    repository = RegressionBaselineRepository(session)
    baseline = await repository.get_current_baseline()

    if baseline is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No current baseline set. Establish a baseline first.",
        )

    return baseline


@router.get("/regression/baseline/history")
async def list_baseline_history(
    limit: int = 10,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
):
    """
    List baseline history with pagination.

    Story 12.7 Task 11 Subtask 11.15-11.16:
    Returns paginated list of historical baselines.

    Args:
        limit: Maximum results to return (default 10, max 50)
        offset: Number of results to skip (default 0)
        session: Database session

    Returns:
        List of RegressionBaseline objects ordered by established_at DESC

    Example Response:
        [
            {
                "baseline_id": "660e8400...",
                "version": "abc123",
                "is_current": true,
                "established_at": "2024-01-15T02:00:00Z",
                ...
            },
            ...
        ]
    """
    # Validate pagination
    if limit > 50:
        limit = 50
    if limit < 1:
        limit = 10
    if offset < 0:
        offset = 0

    # Query database
    repository = RegressionBaselineRepository(session)
    baselines = await repository.list_baselines(limit=limit, offset=offset)

    return baselines
