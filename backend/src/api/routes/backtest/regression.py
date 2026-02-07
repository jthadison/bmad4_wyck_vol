"""
Regression testing endpoints.

Story 12.7 Endpoints:
- POST /regression: Run regression test
- GET /regression/{test_id}: Get regression test result
- GET /regression: List regression test results (paginated)

Note: Baseline endpoints are in baseline.py
"""

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import async_session_maker, get_db
from src.models.backtest import RegressionTestConfig
from src.repositories.regression_baseline_repository import RegressionBaselineRepository
from src.repositories.regression_test_repository import RegressionTestRepository

from .utils import cleanup_stale_entries, regression_test_runs

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/regression", status_code=status.HTTP_202_ACCEPTED)
async def run_regression_test(
    config: RegressionTestConfig,
):
    """
    Run regression test across multiple symbols.

    Story 12.7 Task 11 Subtask 11.1-11.5:
    Executes regression test as background task and returns immediately with test_id.

    Args:
        config: RegressionTestConfig with symbols, date range, thresholds

    Returns:
        test_id and status: RUNNING

    Raises:
        400 Bad Request: Invalid config (empty symbols, invalid date range)
        503 Service Unavailable: Too many concurrent regression tests

    Example Request:
        {
            "symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
            "start_date": "2020-01-01",
            "end_date": "2023-12-31",
            "degradation_thresholds": {
                "win_rate": 5.0,
                "average_r_multiple": 10.0,
                "profit_factor": 15.0
            }
        }

    Example Response:
        {
            "test_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "RUNNING"
        }
    """
    # Validate config
    if not config.symbols:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Config must include at least one symbol",
        )

    if config.start_date >= config.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before end_date",
        )

    # Check concurrent test limit (max 3)
    running_tests = sum(1 for run in regression_test_runs.values() if run["status"] == "RUNNING")
    if running_tests >= 3:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Too many concurrent regression tests. Please try again later.",
        )

    # Generate test_id
    test_id = uuid4()

    # Initialize tracking
    cleanup_stale_entries(regression_test_runs)
    regression_test_runs[test_id] = {
        "status": "RUNNING",
        "created_at": datetime.now(UTC),
        "error": None,
    }

    # Queue background task (uses its own DB session, not the request-scoped one)
    asyncio.create_task(
        run_regression_test_task(
            test_id,
            config,
        )
    )

    logger.info(
        "Regression test queued",
        extra={
            "test_id": str(test_id),
            "symbols": config.symbols,
            "start_date": str(config.start_date),
            "end_date": str(config.end_date),
        },
    )

    return {"test_id": test_id, "status": "RUNNING"}


async def run_regression_test_task(
    test_id: UUID,
    config: RegressionTestConfig,
) -> None:
    """
    Background task to execute regression test.

    Creates its own database session rather than using the request-scoped
    session, which is closed after the HTTP 202 response is sent.

    Args:
        test_id: Test identifier
        config: RegressionTestConfig
    """
    from src.backtesting.regression_test_engine import RegressionTestEngine

    try:
        logger.info("Starting regression test execution", extra={"test_id": str(test_id)})

        # Create a fresh session for the background task (not request-scoped)
        async with async_session_maker() as session:
            # Create repositories
            test_repo = RegressionTestRepository(session)
            baseline_repo = RegressionBaselineRepository(session)

            # Create engine
            engine = RegressionTestEngine(
                test_repository=test_repo,
                baseline_repository=baseline_repo,
            )

            # Run regression test
            result = await engine.run_regression_test(config)

        # Update status
        regression_test_runs[test_id]["status"] = result.status
        regression_test_runs[test_id]["result"] = result

        logger.info(
            "Regression test completed",
            extra={
                "test_id": str(test_id),
                "status": result.status,
                "regression_detected": result.regression_detected,
            },
        )

    except Exception as e:
        logger.error(
            "Regression test failed",
            extra={"test_id": str(test_id), "error": str(e)},
            exc_info=True,
        )
        regression_test_runs[test_id]["status"] = "FAILED"
        regression_test_runs[test_id]["error"] = str(e)


@router.get("/regression/{test_id}")
async def get_regression_test_result(
    test_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Get regression test result by test_id.

    Story 12.7 Task 11 Subtask 11.6-11.7:
    Returns result if completed, RUNNING if in progress, 404 if not found.

    Args:
        test_id: Test identifier
        session: Database session

    Returns:
        RegressionTestResult if completed, status if running

    Raises:
        404 Not Found: Test not found

    Example Response (running):
        {
            "test_id": "550e8400...",
            "status": "RUNNING"
        }

    Example Response (completed):
        {
            "test_id": "550e8400...",
            "codebase_version": "abc123",
            "aggregate_metrics": {...},
            "per_symbol_results": {...},
            "baseline_comparison": {...},
            "regression_detected": false,
            "status": "PASS",
            ...
        }
    """
    # Check in-memory storage first
    if test_id in regression_test_runs:
        run_info = regression_test_runs[test_id]

        if run_info["status"] == "RUNNING":
            return {"test_id": test_id, "status": "RUNNING"}
        elif run_info["status"] == "FAILED":
            return {
                "test_id": test_id,
                "status": "FAILED",
                "error": run_info.get("error"),
            }

    # Query database
    repository = RegressionTestRepository(session)
    result = await repository.get_result(test_id)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Regression test {test_id} not found",
        )

    return result


@router.get("/regression")
async def list_regression_test_results(
    limit: int = 50,
    offset: int = 0,
    status_filter: str | None = None,
    session: AsyncSession = Depends(get_db),
):
    """
    List regression test results with pagination and filtering.

    Story 12.7 Task 11 Subtask 11.8-11.9:
    Returns paginated list of regression test results.

    Args:
        limit: Maximum results to return (default 50, max 100)
        offset: Number of results to skip (default 0)
        status_filter: Filter by status (PASS/FAIL/BASELINE_NOT_SET)
        session: Database session

    Returns:
        List of RegressionTestResult objects

    Example Response:
        [
            {
                "test_id": "550e8400...",
                "status": "PASS",
                "regression_detected": false,
                "test_run_time": "2024-01-15T02:00:00Z",
                ...
            },
            ...
        ]
    """
    # Validate pagination
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 50
    if offset < 0:
        offset = 0

    # Validate status filter
    if status_filter and status_filter not in ["PASS", "FAIL", "BASELINE_NOT_SET"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="status_filter must be one of: PASS, FAIL, BASELINE_NOT_SET",
        )

    # Query database
    repository = RegressionTestRepository(session)
    results = await repository.list_results(limit=limit, offset=offset, status_filter=status_filter)

    return results
