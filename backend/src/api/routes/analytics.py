"""Pattern Performance Analytics API Routes

**REGISTRATION STATUS:** Not yet registered in main.py (intentional).
See backend/src/api/routes/README.analytics.md for details.

This router will be registered in Story 11.9 after production implementation.

This module provides REST API endpoints for retrieving pattern performance
analytics with caching headers for optimization.
"""

from typing import Annotated, Literal, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session, get_redis_client
from src.models.analytics import (
    PatternPerformanceResponse,
    TradeListResponse,
    TrendResponse,
)
from src.repositories.analytics_repository import AnalyticsRepository

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get(
    "/pattern-performance",
    response_model=PatternPerformanceResponse,
    summary="Get pattern performance metrics",
    description="""
    Retrieve performance statistics for all pattern types (SPRING, SOS, LPS, UTAD)
    including win rates, average R-multiples, profit factors, and sector breakdowns.

    Data is cached for 24 hours for performance optimization.

    Query Parameters:
    - days: Time period (7, 30, 90, or None for all time)
    - detection_phase: Optional filter by Wyckoff phase (A, B, C, D, E)

    Returns:
    - Pattern performance metrics for all pattern types
    - Sector breakdown aggregated across patterns
    - Cache metadata (generated_at, cache_expires_at)
    """,
)
async def get_pattern_performance(
    days: Annotated[
        Optional[int],
        Query(
            description="Time period in days (7, 30, 90, or None for all time)",
            example=30,
        ),
    ] = None,
    detection_phase: Annotated[
        Optional[Literal["A", "B", "C", "D", "E"]],
        Query(
            description="Filter by Wyckoff detection phase",
            example="C",
        ),
    ] = None,
    session: AsyncSession = Depends(get_db_session),
    redis_client=Depends(get_redis_client),
) -> PatternPerformanceResponse:
    """Get pattern performance metrics with caching."""
    try:
        repo = AnalyticsRepository(session=session, redis=redis_client)
        response = await repo.get_pattern_performance(days=days, detection_phase=detection_phase)

        logger.info(
            "Pattern performance retrieved",
            extra={
                "time_period_days": days,
                "detection_phase": detection_phase,
                "pattern_count": len(response.patterns),
            },
        )

        return response

    except ValueError as e:
        logger.warning(
            "Invalid query parameters",
            extra={"error": str(e), "days": days, "detection_phase": detection_phase},
        )
        raise HTTPException(status_code=400, detail=str(e)) from e

    except Exception as e:
        logger.error(
            "Error retrieving pattern performance",
            extra={"error": str(e), "days": days, "detection_phase": detection_phase},
        )
        raise HTTPException(
            status_code=500, detail="Failed to retrieve pattern performance data"
        ) from e


@router.get(
    "/pattern-performance/{pattern_type}/trend",
    response_model=TrendResponse,
    summary="Get win rate trend for pattern",
    description="""
    Retrieve daily win rate trend data for the specified pattern type.

    Used for rendering time-series charts showing performance over time.

    Path Parameters:
    - pattern_type: Pattern to analyze (SPRING, SOS, LPS, UTAD)

    Query Parameters:
    - days: Number of days of historical data (required)

    Returns:
    - List of date/win_rate data points for charting
    """,
)
async def get_win_rate_trend(
    pattern_type: Literal["SPRING", "SOS", "LPS", "UTAD"],
    days: Annotated[
        int,
        Query(
            description="Number of days of trend data",
            ge=7,
            le=365,
            example=30,
        ),
    ],
    session: AsyncSession = Depends(get_db_session),
    redis_client=Depends(get_redis_client),
) -> TrendResponse:
    """Get win rate trend data for charting."""
    try:
        repo = AnalyticsRepository(session=session, redis=redis_client)
        trend_data = await repo.get_win_rate_trend(pattern_type=pattern_type, days=days)

        logger.info(
            "Trend data retrieved",
            extra={
                "pattern_type": pattern_type,
                "days": days,
                "data_points": len(trend_data),
            },
        )

        return TrendResponse(
            pattern_type=pattern_type,
            trend_data=trend_data,
            time_period_days=days,
        )

    except Exception as e:
        logger.error(
            "Error retrieving trend data",
            extra={"error": str(e), "pattern_type": pattern_type, "days": days},
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve trend data") from e


@router.get(
    "/pattern-performance/{pattern_type}/trades",
    response_model=TradeListResponse,
    summary="Get individual trade details",
    description="""
    Retrieve drill-down list of individual trades for the specified pattern type.

    Supports pagination for large datasets.

    Path Parameters:
    - pattern_type: Pattern to filter (SPRING, SOS, LPS, UTAD)

    Query Parameters:
    - days: Time period (None for all time)
    - limit: Max trades per page (default: 50, max: 100)
    - offset: Pagination offset (default: 0)

    Returns:
    - Paginated list of trade details
    - Pagination metadata (returned_count, total_count, limit, offset)
    """,
)
async def get_trade_details(
    pattern_type: Literal["SPRING", "SOS", "LPS", "UTAD"],
    days: Annotated[
        Optional[int],
        Query(description="Time period in days (None for all time)", example=30),
    ] = None,
    limit: Annotated[
        int,
        Query(description="Max trades per page", ge=1, le=100, example=50),
    ] = 50,
    offset: Annotated[int, Query(description="Pagination offset", ge=0, example=0)] = 0,
    session: AsyncSession = Depends(get_db_session),
    redis_client=Depends(get_redis_client),
) -> TradeListResponse:
    """Get individual trade details for drill-down."""
    try:
        repo = AnalyticsRepository(session=session, redis=redis_client)
        trades, total_count = await repo.get_trade_details(
            pattern_type=pattern_type, days=days, limit=limit, offset=offset
        )

        logger.info(
            "Trade details retrieved",
            extra={
                "pattern_type": pattern_type,
                "days": days,
                "returned_count": len(trades),
                "total_count": total_count,
            },
        )

        return TradeListResponse(
            pattern_type=pattern_type,
            trades=trades,
            pagination={
                "returned_count": len(trades),
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
            },
            time_period_days=days,
        )

    except Exception as e:
        logger.error(
            "Error retrieving trade details",
            extra={
                "error": str(e),
                "pattern_type": pattern_type,
                "days": days,
                "limit": limit,
                "offset": offset,
            },
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve trade details") from e


@router.get(
    "/pattern-performance/export",
    summary="Export pattern performance as PDF",
    description="""
    Generate and download a PDF report of pattern performance metrics.

    Query Parameters:
    - days: Time period (7, 30, 90, or None for all time)

    Returns:
    - PDF file with Content-Type: application/pdf
    - Content-Disposition header with filename pattern-performance-{date}.pdf
    """,
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "PDF report successfully generated",
        }
    },
)
async def export_pattern_performance_pdf(
    days: Annotated[
        Optional[int],
        Query(
            description="Time period in days (7, 30, 90, or None for all time)",
            example=30,
        ),
    ] = None,
    session: AsyncSession = Depends(get_db_session),
    redis_client=Depends(get_redis_client),
) -> Response:
    """Export pattern performance report as PDF."""
    try:
        from datetime import UTC, datetime

        from src.services.pdf_export_service import PDFExportService

        # Get analytics data
        repo = AnalyticsRepository(session=session, redis=redis_client)
        data = await repo.get_pattern_performance(days=days)

        # Generate PDF
        pdf_service = PDFExportService()
        pdf_bytes = await pdf_service.generate_performance_report(data=data, days=days)

        # Create filename with current date
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        filename = f"pattern-performance-{date_str}.pdf"

        logger.info(
            "PDF report generated",
            extra={"filename": filename, "size_bytes": len(pdf_bytes)},
        )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except Exception as e:
        logger.error("Error generating PDF report", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Failed to generate PDF report") from e


@router.get(
    "/pattern-sequences",
    response_model=dict,
    summary="Get pattern sequence performance analysis",
    description="""
    Analyze completed campaigns by pattern sequences to identify which sequences
    have the highest win rates and profitability (Story 16.5a).

    Groups campaigns by their entry pattern sequences (e.g., Spring→SOS, Spring→AR→SOS,
    Spring→SOS→LPS) and calculates comprehensive performance metrics for each sequence.

    Metrics Calculated:
    - Win rate (% campaigns with R > 0)
    - Average R-multiple
    - Median R-multiple
    - Total R-multiple (cumulative profit)
    - Exit reason distribution
    - Best/worst campaign for each sequence

    Query Parameters:
    - symbol: Optional symbol filter (e.g., "AAPL")
    - timeframe: Optional timeframe filter (e.g., "1D")
    - limit: Maximum number of sequences to return (default: 100)

    Returns:
    - SequencePerformanceResponse with list of metrics and metadata

    Performance:
    - Optimized SQL queries for efficiency
    - Target: < 3 seconds for 1000 campaigns
    """,
)
async def get_pattern_sequence_analysis(
    symbol: Annotated[
        Optional[str],
        Query(
            description="Filter by trading symbol",
            example="AAPL",
        ),
    ] = None,
    timeframe: Annotated[
        Optional[str],
        Query(
            description="Filter by timeframe",
            example="1D",
        ),
    ] = None,
    limit: Annotated[
        int,
        Query(
            description="Maximum number of sequences to return",
            ge=1,
            le=1000,
            example=100,
        ),
    ] = 100,
    session: AsyncSession = Depends(get_db_session),
):
    """Get pattern sequence performance analysis (Story 16.5a)."""
    try:
        from src.analysis.campaign_success_analyzer import CampaignSuccessAnalyzer
        from src.models.campaign import SequencePerformanceResponse

        analyzer = CampaignSuccessAnalyzer(session)
        sequences, total_campaigns = await analyzer.get_pattern_sequence_analysis(
            symbol=symbol, timeframe=timeframe, limit=limit
        )

        # Build response with metadata
        response = SequencePerformanceResponse(
            sequences=sequences,
            total_sequences=len(sequences),
            filters_applied={"symbol": symbol, "timeframe": timeframe},
            total_campaigns=total_campaigns,
        )

        logger.info(
            "Pattern sequence analysis retrieved",
            extra={
                "symbol": symbol,
                "timeframe": timeframe,
                "sequence_count": len(sequences),
                "total_campaigns": total_campaigns,
                "limit": limit,
            },
        )

        return response

    except Exception as e:
        logger.error(
            "Error retrieving pattern sequence analysis",
            extra={"error": str(e), "symbol": symbol, "timeframe": timeframe},
        )
        raise HTTPException(
            status_code=500, detail="Failed to retrieve pattern sequence analysis"
        ) from e
