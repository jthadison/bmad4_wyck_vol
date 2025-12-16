"""Charts API routes.

Story 11.5: Advanced Charting Integration
Provides chart data endpoint for Lightweight Charts frontend component.
"""

from datetime import datetime
from typing import Optional, Literal
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.dependencies import get_db_session
from backend.src.models.chart import ChartDataResponse
from backend.src.repositories.chart_repository import ChartRepository

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/charts", tags=["charts"])


@router.get(
    "/data",
    response_model=ChartDataResponse,
    summary="Get chart data for symbol",
    description="""
    Fetch OHLCV bars with pattern markers, level lines, and phase annotations
    for charting visualization.

    Story 11.5: Advanced Charting Integration
    - Returns data in Lightweight Charts format (Unix timestamps in seconds)
    - Includes detected patterns (Spring, UTAD, SOS, LPS, Test) with confidence scores
    - Includes trading range levels (Creek, Ice, Jump)
    - Includes Wyckoff phase annotations (A, B, C, D, E)
    - Includes preliminary events (PS, SC, AR, ST)

    Performance: Response time < 100ms for 500 bars (p95)
    """
)
async def get_chart_data(
    symbol: str = Query(..., description="Ticker symbol", max_length=20),
    timeframe: Literal["1D", "1W", "1M"] = Query(
        "1D",
        description="Bar interval: 1 Day, 1 Week, or 1 Month"
    ),
    start_date: Optional[datetime] = Query(
        None,
        description="Start date (default: 90 days ago)"
    ),
    end_date: Optional[datetime] = Query(
        None,
        description="End date (default: now)"
    ),
    limit: int = Query(
        500,
        ge=50,
        le=2000,
        description="Maximum number of bars (default: 500, max: 2000)"
    ),
    session: AsyncSession = Depends(get_db_session)
) -> ChartDataResponse:
    """Get chart data for symbol and timeframe.

    Args:
        symbol: Ticker symbol
        timeframe: Bar interval (1D/1W/1M)
        start_date: Optional start date
        end_date: Optional end date
        limit: Max number of bars (50-2000)
        session: Database session (injected)

    Returns:
        ChartDataResponse with all chart data

    Raises:
        HTTPException 400: Invalid parameters
        HTTPException 404: Symbol not found
        HTTPException 500: Server error
    """
    try:
        logger.info(
            "Chart data request",
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )

        # Validate symbol
        symbol = symbol.upper().strip()
        if not symbol:
            raise HTTPException(
                status_code=400,
                detail="Symbol is required"
            )

        # Create repository and fetch data
        repository = ChartRepository(session)
        chart_data = await repository.get_chart_data(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )

        logger.info(
            "Chart data retrieved successfully",
            symbol=symbol,
            bar_count=chart_data.bar_count,
            pattern_count=len(chart_data.patterns),
            level_line_count=len(chart_data.level_lines)
        )

        return chart_data

    except ValueError as e:
        logger.warning(
            "Invalid chart data request",
            symbol=symbol,
            error=str(e)
        )
        raise HTTPException(
            status_code=404,
            detail=f"No data found for {symbol} {timeframe}: {str(e)}"
        )

    except Exception as e:
        logger.error(
            "Error retrieving chart data",
            symbol=symbol,
            timeframe=timeframe,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error retrieving chart data"
        )
