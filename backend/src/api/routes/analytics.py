"""Pattern Performance Analytics API Routes

**REGISTRATION STATUS:** Not yet registered in main.py (intentional).
See backend/src/api/routes/README.analytics.md for details.

This router will be registered in Story 11.9 after production implementation.

This module provides REST API endpoints for retrieving pattern performance
analytics with caching headers for optimization.
"""

import io
import json
from datetime import UTC, datetime
from typing import Annotated, Literal, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.campaign_success_analyzer import CampaignSuccessAnalyzer
from src.api.dependencies import get_db_session, get_redis_client
from src.models.analytics import (
    PatternPerformanceResponse,
    TradeListResponse,
    TrendResponse,
)
from src.models.campaign import (
    CampaignDurationReport,
    QualityCorrelationReport,
    SequencePerformanceResponse,
)
from src.repositories.analytics_repository import AnalyticsRepository

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])


def _sanitize_csv_value(value: str) -> str:
    """
    Sanitize CSV value to prevent CSV injection attacks.

    CSV injection occurs when a CSV field starts with special characters
    like =, +, -, @ which can be interpreted as formulas by spreadsheet software.

    Args:
        value: Raw CSV value

    Returns:
        Sanitized CSV value with potential formula characters escaped
    """
    if not value:
        return value

    # Check if value starts with formula characters
    if value[0] in ("=", "+", "-", "@", "\t", "\r"):
        # Prefix with single quote to treat as text
        return f"'{value}"

    # Escape double quotes for CSV format
    if '"' in value:
        value = value.replace('"', '""')

    # Quote value if it contains comma, newline, or quote
    if any(char in value for char in (',', '\n', '\r', '"')):
        return f'"{value}"'

    return value


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
    response_model=SequencePerformanceResponse,
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


@router.get(
    "/quality-correlation",
    response_model=QualityCorrelationReport,
    summary="Get quality correlation analysis",
    description="""
    Analyze correlation between quality scores and R-multiples (Story 16.5b).

    Groups campaigns by quality tier (EXCEPTIONAL, STRONG, ACCEPTABLE, WEAK) and
    calculates performance metrics to identify optimal quality thresholds for
    signal filtering.

    Metrics Calculated:
    - Pearson correlation coefficient between quality scores and R-multiples
    - Performance metrics by quality tier (win rate, avg R, median R, total R)
    - Recommended optimal quality threshold
    - Sample size (total campaigns analyzed)

    Query Parameters:
    - symbol: Optional symbol filter (e.g., "AAPL")
    - timeframe: Optional timeframe filter (e.g., "1D")

    Returns:
    - QualityCorrelationReport with correlation metrics and tier performance

    Performance:
    - Cached for 1 hour (3600 seconds)
    - Target: < 2 seconds for 1000 campaigns
    """,
)
async def get_quality_correlation_analysis(
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
    session: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis_client),
):
    """Get quality correlation analysis (Story 16.5b AC #1)."""
    try:
        # Check cache first
        cache_key = f"analytics:quality_correlation:{symbol or 'all'}:{timeframe or 'all'}"
        cache_ttl = 3600  # 1 hour

        if redis:
            try:
                cached_data = await redis.get(cache_key)
                if cached_data:
                    logger.info(
                        "Quality correlation cache hit",
                        extra={"cache_key": cache_key, "symbol": symbol, "timeframe": timeframe},
                    )
                    return QualityCorrelationReport(**json.loads(cached_data))
            except Exception as cache_error:
                logger.warning(
                    "Cache retrieval failed",
                    extra={"cache_key": cache_key, "error": str(cache_error)},
                )

        # Cache miss - query database
        analyzer = CampaignSuccessAnalyzer(session)
        report = await analyzer.get_quality_correlation_report(symbol=symbol, timeframe=timeframe)

        # Store in cache
        if redis:
            try:
                await redis.setex(
                    cache_key,
                    cache_ttl,
                    json.dumps(report.model_dump(mode="json"), default=str),
                )
                logger.debug(
                    "Quality correlation data cached",
                    extra={"cache_key": cache_key, "ttl_seconds": cache_ttl},
                )
            except Exception as cache_error:
                logger.warning(
                    "Cache storage failed",
                    extra={"cache_key": cache_key, "error": str(cache_error)},
                )

        logger.info(
            "Quality correlation analysis retrieved",
            extra={
                "symbol": symbol,
                "timeframe": timeframe,
                "correlation": str(report.correlation_coefficient),
                "optimal_threshold": report.optimal_threshold,
                "sample_size": report.sample_size,
            },
        )

        return report

    except Exception as e:
        logger.error(
            "Error retrieving quality correlation analysis",
            extra={"error": str(e), "symbol": symbol, "timeframe": timeframe},
        )
        raise HTTPException(
            status_code=500, detail="Failed to retrieve quality correlation analysis"
        ) from e


@router.get(
    "/campaign-duration",
    response_model=CampaignDurationReport,
    summary="Get campaign duration analysis",
    description="""
    Analyze campaign duration by pattern sequence (Story 16.5b).

    Groups campaigns by pattern sequence and calculates duration metrics to
    understand typical timeframes for each sequence type (e.g., Spring→SOS,
    Spring→AR→SOS, Spring→SOS→LPS).

    Metrics Calculated:
    - Average duration by sequence
    - Median duration by sequence
    - Min/max duration by sequence
    - Overall average and median duration across all campaigns
    - Campaign count per sequence

    Query Parameters:
    - symbol: Optional symbol filter (e.g., "AAPL")
    - timeframe: Optional timeframe filter (e.g., "1D")

    Returns:
    - CampaignDurationReport with duration metrics by sequence

    Performance:
    - Cached for 1 hour (3600 seconds)
    - Target: < 2 seconds for 1000 campaigns
    """,
)
async def get_campaign_duration_analysis(
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
    session: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis_client),
):
    """Get campaign duration analysis (Story 16.5b AC #2)."""
    try:
        # Check cache first
        cache_key = f"analytics:campaign_duration:{symbol or 'all'}:{timeframe or 'all'}"
        cache_ttl = 3600  # 1 hour

        if redis:
            try:
                cached_data = await redis.get(cache_key)
                if cached_data:
                    logger.info(
                        "Campaign duration cache hit",
                        extra={"cache_key": cache_key, "symbol": symbol, "timeframe": timeframe},
                    )
                    return CampaignDurationReport(**json.loads(cached_data))
            except Exception as cache_error:
                logger.warning(
                    "Cache retrieval failed",
                    extra={"cache_key": cache_key, "error": str(cache_error)},
                )

        # Cache miss - query database
        analyzer = CampaignSuccessAnalyzer(session)
        report = await analyzer.get_campaign_duration_analysis(symbol=symbol, timeframe=timeframe)

        # Store in cache
        if redis:
            try:
                await redis.setex(
                    cache_key,
                    cache_ttl,
                    json.dumps(report.model_dump(mode="json"), default=str),
                )
                logger.debug(
                    "Campaign duration data cached",
                    extra={"cache_key": cache_key, "ttl_seconds": cache_ttl},
                )
            except Exception as cache_error:
                logger.warning(
                    "Cache storage failed",
                    extra={"cache_key": cache_key, "error": str(cache_error)},
                )

        logger.info(
            "Campaign duration analysis retrieved",
            extra={
                "symbol": symbol,
                "timeframe": timeframe,
                "total_campaigns": report.total_campaigns,
                "sequence_count": len(report.duration_by_sequence),
                "overall_avg_duration": str(report.overall_avg_duration),
            },
        )

        return report

    except Exception as e:
        logger.error(
            "Error retrieving campaign duration analysis",
            extra={"error": str(e), "symbol": symbol, "timeframe": timeframe},
        )
        raise HTTPException(
            status_code=500, detail="Failed to retrieve campaign duration analysis"
        ) from e


@router.get(
    "/quality-correlation/export",
    summary="Export quality correlation report",
    description="""
    Export quality correlation report as JSON or CSV (Story 16.5b AC #3).

    Query Parameters:
    - format: Export format ("json" or "csv")
    - symbol: Optional symbol filter (e.g., "AAPL")
    - timeframe: Optional timeframe filter (e.g., "1D")

    Returns:
    - JSON or CSV file with quality correlation metrics
    """,
)
async def export_quality_correlation_report(
    export_format: Annotated[
        str,
        Query(
            alias="format",
            description="Export format (json or csv)",
            pattern="^(json|csv)$",
            example="json",
        ),
    ] = "json",
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
    session: AsyncSession = Depends(get_db_session),
):
    """Export quality correlation report as JSON or CSV."""
    try:
        # Get report data
        analyzer = CampaignSuccessAnalyzer(session)
        report = await analyzer.get_quality_correlation_report(symbol=symbol, timeframe=timeframe)

        if export_format == "json":
            # Return JSON format
            date_str = datetime.now(UTC).strftime("%Y-%m-%d")
            filename = f"quality-correlation-{date_str}.json"

            logger.info(
                "Quality correlation report exported as JSON",
                extra={"filename": filename, "sample_size": report.sample_size},
            )

            return Response(
                content=report.model_dump_json(indent=2),
                media_type="application/json",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        else:  # export_format == "csv"
            # Convert to CSV format
            csv_buffer = io.StringIO()
            csv_buffer.write("# Quality Correlation Report\n")
            csv_buffer.write(f"# Generated: {datetime.now(UTC).isoformat()}\n")
            csv_buffer.write(f"# Sample Size: {report.sample_size}\n")
            csv_buffer.write(f"# Correlation Coefficient: {report.correlation_coefficient}\n")
            csv_buffer.write(f"# Optimal Threshold: {report.optimal_threshold}\n\n")

            # Tier performance data
            csv_buffer.write(
                "Quality Tier,Campaign Count,Win Rate (%),Avg R-Multiple,Median R-Multiple,Total R-Multiple\n"
            )
            for tier_perf in report.performance_by_tier:
                # Sanitize tier name to prevent CSV injection
                safe_tier = _sanitize_csv_value(tier_perf.tier)
                csv_buffer.write(
                    f"{safe_tier},{tier_perf.campaign_count},"
                    f"{tier_perf.win_rate},{tier_perf.avg_r_multiple},"
                    f"{tier_perf.median_r_multiple},{tier_perf.total_r_multiple}\n"
                )

            date_str = datetime.now(UTC).strftime("%Y-%m-%d")
            filename = f"quality-correlation-{date_str}.csv"

            logger.info(
                "Quality correlation report exported as CSV",
                extra={"filename": filename, "sample_size": report.sample_size},
            )

            return Response(
                content=csv_buffer.getvalue(),
                media_type="text/csv",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

    except Exception as e:
        logger.error(
            "Error exporting quality correlation report",
            extra={"error": str(e), "export_format": export_format, "symbol": symbol, "timeframe": timeframe},
        )
        raise HTTPException(
            status_code=500, detail="Failed to export quality correlation report"
        ) from e


@router.get(
    "/campaign-duration/export",
    summary="Export campaign duration report",
    description="""
    Export campaign duration report as JSON or CSV (Story 16.5b AC #3).

    Query Parameters:
    - format: Export format ("json" or "csv")
    - symbol: Optional symbol filter (e.g., "AAPL")
    - timeframe: Optional timeframe filter (e.g., "1D")

    Returns:
    - JSON or CSV file with campaign duration metrics
    """,
)
async def export_campaign_duration_report(
    export_format: Annotated[
        str,
        Query(
            alias="format",
            description="Export format (json or csv)",
            pattern="^(json|csv)$",
            example="json",
        ),
    ] = "json",
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
    session: AsyncSession = Depends(get_db_session),
):
    """Export campaign duration report as JSON or CSV."""
    try:
        # Get report data
        analyzer = CampaignSuccessAnalyzer(session)
        report = await analyzer.get_campaign_duration_analysis(symbol=symbol, timeframe=timeframe)

        if export_format == "json":
            # Return JSON format
            date_str = datetime.now(UTC).strftime("%Y-%m-%d")
            filename = f"campaign-duration-{date_str}.json"

            logger.info(
                "Campaign duration report exported as JSON",
                extra={"filename": filename, "total_campaigns": report.total_campaigns},
            )

            return Response(
                content=report.model_dump_json(indent=2),
                media_type="application/json",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        else:  # export_format == "csv"
            # Convert to CSV format
            csv_buffer = io.StringIO()
            csv_buffer.write("# Campaign Duration Report\n")
            csv_buffer.write(f"# Generated: {datetime.now(UTC).isoformat()}\n")
            csv_buffer.write(f"# Total Campaigns: {report.total_campaigns}\n")
            csv_buffer.write(f"# Overall Average Duration: {report.overall_avg_duration} days\n")
            csv_buffer.write(
                f"# Overall Median Duration: {report.overall_median_duration} days\n\n"
            )

            # Duration by sequence data
            csv_buffer.write(
                "Pattern Sequence,Campaign Count,Avg Duration (days),Median Duration (days),"
                "Min Duration (days),Max Duration (days)\n"
            )
            for duration_metrics in report.duration_by_sequence:
                # Sanitize sequence name to prevent CSV injection
                safe_sequence = _sanitize_csv_value(duration_metrics.sequence)
                csv_buffer.write(
                    f"{safe_sequence},{duration_metrics.campaign_count},"
                    f"{duration_metrics.avg_duration_days},{duration_metrics.median_duration_days},"
                    f"{duration_metrics.min_duration_days},{duration_metrics.max_duration_days}\n"
                )

            date_str = datetime.now(UTC).strftime("%Y-%m-%d")
            filename = f"campaign-duration-{date_str}.csv"

            logger.info(
                "Campaign duration report exported as CSV",
                extra={"filename": filename, "total_campaigns": report.total_campaigns},
            )

            return Response(
                content=csv_buffer.getvalue(),
                media_type="text/csv",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

    except Exception as e:
        logger.error(
            "Error exporting campaign duration report",
            extra={"error": str(e), "export_format": export_format, "symbol": symbol, "timeframe": timeframe},
        )
        raise HTTPException(
            status_code=500, detail="Failed to export campaign duration report"
        ) from e
