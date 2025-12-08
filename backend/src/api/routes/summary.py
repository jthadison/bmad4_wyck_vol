"""
Summary API Routes - Daily Summary Endpoints (Story 10.3)

Purpose:
--------
Provides REST API endpoint for daily trading activity summary.

Endpoints:
----------
GET /api/v1/summary/daily - Returns daily summary with overnight activity metrics

Author: Story 10.3
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.summary import DailySummary
from src.repositories.summary_repository import SummaryRepository

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/summary", tags=["summary"])


@router.get("/daily", response_model=DailySummary)
async def get_daily_summary(db_session: AsyncSession = Depends(get_db)) -> DailySummary:
    """
    Get daily summary of overnight trading activity (Story 10.3, AC: 3, 4, 6).

    Returns aggregated metrics from the last 24 hours including:
    - symbols_scanned: Unique symbols analyzed
    - patterns_detected: Total patterns detected
    - signals_executed: Count of executed signals
    - signals_rejected: Count of rejected signals
    - portfolio_heat_change: Change in portfolio heat % over 24 hours
    - suggested_actions: Business logic generated action items

    Target Response Time: < 500ms (per Story 10.3 performance notes)

    Parameters:
    -----------
    db_session : AsyncSession
        Database session (injected via FastAPI dependency)

    Returns:
    --------
    DailySummary
        Complete daily summary with all aggregated metrics:
        ```json
        {
          "symbols_scanned": 15,
          "patterns_detected": 23,
          "signals_executed": 4,
          "signals_rejected": 8,
          "portfolio_heat_change": "1.2",
          "suggested_actions": [
            "Review Campaign C-2024-03-15-AAPL: 2 positions approaching stops",
            "Portfolio heat at 7.8% - capacity for ~2 more signals"
          ],
          "timestamp": "2024-03-15T14:30:00Z"
        }
        ```

    Raises:
    -------
    HTTPException
        500 Internal Server Error if aggregation query fails
        503 Service Unavailable if database connection fails

    Example Usage:
    --------------
    ```bash
    curl -X GET "http://localhost:8000/api/v1/summary/daily"
    ```
    """
    try:
        # Create repository with db session
        summary_repository = SummaryRepository(db_session)

        # Aggregate daily summary metrics
        summary = await summary_repository.get_daily_summary()

        logger.info(
            "daily_summary_retrieved",
            symbols_scanned=summary.symbols_scanned,
            patterns_detected=summary.patterns_detected,
            signals_executed=summary.signals_executed,
            signals_rejected=summary.signals_rejected,
            portfolio_heat_change=str(summary.portfolio_heat_change),
            action_count=len(summary.suggested_actions),
            timestamp=summary.timestamp.isoformat(),
        )

        return summary

    except Exception as e:
        # Database or aggregation error
        logger.error(
            "daily_summary_error",
            error=str(e),
            error_type=type(e).__name__,
        )

        # Determine appropriate HTTP status code
        if "connection" in str(e).lower() or "database" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection failed. Please try again later.",
            ) from e
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to aggregate daily summary. Please try again later.",
            ) from e
