"""
Campaign performance tracking endpoints.

Provides performance metrics, P&L curves, and aggregated statistics.
Story 9.6 (Performance Tracking)
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.campaign import (
    AggregatedMetrics,
    CampaignMetrics,
    MetricsFilter,
    PnLCurve,
)
from src.repositories.campaign_repository import CampaignNotFoundError, CampaignRepository
from src.services.campaign_performance_calculator import (
    calculate_campaign_performance,
    generate_pnl_curve,
    get_aggregated_performance,
)

logger = structlog.get_logger()

router = APIRouter()


@router.get("/{campaign_id}/performance", response_model=CampaignMetrics)
async def get_campaign_performance(
    campaign_id: UUID, db_session: AsyncSession = Depends(get_db)
) -> CampaignMetrics:
    """
    Get comprehensive performance metrics for completed campaign (Story 9.6, AC 10).

    Returns detailed performance analytics including:
    - Campaign-level metrics: total return %, total R achieved, win rate, max drawdown
    - Position-level details: individual R-multiple, entry/exit prices, win/loss status
    - Phase-specific metrics: Phase C (Spring/LPS) vs Phase D (SOS) performance comparison
    - Target achievement: actual vs expected Jump target comparison

    Requirements:
    -------------
    - Campaign must have status = COMPLETED
    - Returns 422 Unprocessable Entity if campaign not yet completed
    - All financial data uses Decimal precision (NUMERIC 18,8)
    - All timestamps are UTC timezone-aware

    Parameters:
    -----------
    campaign_id : UUID
        Campaign identifier
    db_session : AsyncSession
        Database session (injected)

    Returns:
    --------
    CampaignMetrics
        Comprehensive performance metrics

    Raises:
    -------
    HTTPException
        404 Not Found if campaign doesn't exist
        422 Unprocessable Entity if campaign not completed (status != COMPLETED)
        503 Service Unavailable if database error
    """
    try:
        # Create repository with db session
        campaign_repository = CampaignRepository(db_session)

        # Fetch campaign to verify it exists and is completed
        campaign = await campaign_repository.get_campaign_by_id(campaign_id)

        if not campaign:
            logger.error(
                "campaign_not_found_for_performance",
                campaign_id=str(campaign_id),
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign not found: {campaign_id}",
            )

        # Verify campaign is completed
        if campaign.status != "COMPLETED":
            logger.warning(
                "campaign_not_completed",
                campaign_id=str(campaign_id),
                current_status=campaign.status,
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Campaign performance can only be calculated for completed campaigns. Current status: {campaign.status}",
            )

        # Check if metrics already cached in database
        cached_metrics = await campaign_repository.get_campaign_metrics(campaign_id)

        if cached_metrics:
            logger.info(
                "campaign_metrics_retrieved_from_cache",
                campaign_id=str(campaign_id),
                total_return_pct=str(cached_metrics.total_return_pct),
                total_r_achieved=str(cached_metrics.total_r_achieved),
                win_rate=str(cached_metrics.win_rate),
            )
            return cached_metrics

        # Calculate fresh metrics
        # Fetch all positions for campaign
        campaign_positions = await campaign_repository.get_campaign_positions(
            campaign_id=campaign_id, include_closed=True
        )

        # Calculate performance metrics
        metrics = calculate_campaign_performance(
            campaign_id=campaign_id,
            symbol=campaign.symbol,
            positions=campaign_positions.positions,
            started_at=campaign.created_at,
            completed_at=campaign.updated_at,
            initial_capital=campaign.initial_capital,
            jump_target=campaign.jump_target,
            actual_high_reached=campaign.actual_high_reached,
        )

        # Persist metrics to database for future retrieval
        await campaign_repository.save_campaign_metrics(metrics)

        logger.info(
            "campaign_performance_calculated",
            campaign_id=str(campaign_id),
            total_return_pct=str(metrics.total_return_pct),
            total_r_achieved=str(metrics.total_r_achieved),
            win_rate=str(metrics.win_rate),
            max_drawdown=str(metrics.max_drawdown),
            phase_c_positions=metrics.phase_c_positions,
            phase_d_positions=metrics.phase_d_positions,
        )

        return metrics

    except HTTPException:
        # Re-raise HTTP exceptions (404, 422)
        raise

    except CampaignNotFoundError as e:
        logger.error(
            "campaign_not_found",
            campaign_id=str(campaign_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign not found: {campaign_id}",
        ) from e

    except Exception as e:
        # Database or calculation error
        logger.error(
            "campaign_performance_error",
            campaign_id=str(campaign_id),
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable. Please try again later.",
        ) from e


@router.get("/{campaign_id}/pnl-curve", response_model=PnLCurve)
async def get_campaign_pnl_curve(
    campaign_id: UUID,
    granularity: str = Query(default="daily", description="Resampling granularity: daily | hourly"),
    db_session: AsyncSession = Depends(get_db),
) -> PnLCurve:
    """
    Get P&L curve visualization data for campaign (Story 9.6, AC 9).

    Returns time-series data of cumulative P&L and drawdown for rendering
    equity curves and performance charts in the frontend.

    Use Cases:
    ----------
    - Render equity curve chart showing campaign P&L over time
    - Overlay drawdown visualization to show risk exposure
    - Identify max drawdown point for highlighting in UI
    - Analyze campaign performance trajectory

    Parameters:
    -----------
    campaign_id : UUID
        Campaign identifier
    granularity : str, default="daily"
        Resampling granularity for data points (daily | hourly)
    db_session : AsyncSession
        Database session (injected)

    Returns:
    --------
    PnLCurve
        P&L curve visualization data

    Raises:
    -------
    HTTPException
        404 Not Found if campaign doesn't exist
        503 Service Unavailable if database error
    """
    try:
        # Create repository with db session
        campaign_repository = CampaignRepository(db_session)

        # Verify campaign exists
        campaign = await campaign_repository.get_campaign_by_id(campaign_id)

        if not campaign:
            logger.error(
                "campaign_not_found_for_pnl_curve",
                campaign_id=str(campaign_id),
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign not found: {campaign_id}",
            )

        # Fetch all positions (including closed) for P&L curve
        campaign_positions = await campaign_repository.get_campaign_positions(
            campaign_id=campaign_id, include_closed=True
        )

        # Generate P&L curve data
        pnl_curve = generate_pnl_curve(
            campaign_id=campaign_id,
            positions=campaign_positions.positions,
            initial_capital=campaign.initial_capital,
        )

        # TODO: Implement resampling based on granularity parameter
        # For now, returning raw data points (one per position exit)
        if granularity not in ["daily", "hourly"]:
            logger.warning(
                "invalid_granularity_parameter",
                campaign_id=str(campaign_id),
                granularity=granularity,
            )

        logger.info(
            "pnl_curve_generated",
            campaign_id=str(campaign_id),
            data_points_count=len(pnl_curve.data_points),
            granularity=granularity,
        )

        return pnl_curve

    except HTTPException:
        # Re-raise HTTP exceptions (404)
        raise

    except CampaignNotFoundError as e:
        logger.error(
            "campaign_not_found",
            campaign_id=str(campaign_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign not found: {campaign_id}",
        ) from e

    except Exception as e:
        # Database or calculation error
        logger.error(
            "pnl_curve_generation_error",
            campaign_id=str(campaign_id),
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable. Please try again later.",
        ) from e


@router.get("/performance", response_model=AggregatedMetrics)
async def get_aggregated_campaign_performance(
    symbol: str | None = Query(None, description="Filter by trading symbol"),
    timeframe: str | None = Query(None, description="Filter by timeframe"),
    start_date: str | None = Query(
        None, description="Filter campaigns completed after this date (ISO 8601)"
    ),
    end_date: str | None = Query(
        None, description="Filter campaigns completed before this date (ISO 8601)"
    ),
    min_return: float | None = Query(
        None, description="Filter campaigns with return >= min_return"
    ),
    min_r: float | None = Query(None, description="Filter campaigns with total R >= min_r"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(default=0, ge=0, description="Skip first N results"),
    db_session: AsyncSession = Depends(get_db),
) -> AggregatedMetrics:
    """
    Get aggregated performance statistics across all completed campaigns (Story 9.6, AC 6, 10).

    Returns system-wide performance analytics aggregated from all completed campaigns,
    with optional filtering by symbol, timeframe, and date range.

    Use Cases:
    ----------
    - Dashboard overview: Display overall win rate, average return, average R-multiple
    - Performance comparison: Compare different symbols or timeframes
    - Historical analysis: Track performance trends over time
    - Best/worst campaigns: Identify top performers and underperformers

    Parameters:
    -----------
    symbol : str, optional
        Filter by trading symbol (e.g., "AAPL", "MSFT")
    timeframe : str, optional
        Filter by timeframe (e.g., "1h", "4h", "1d")
    start_date : str, optional
        Filter campaigns completed after this date (ISO 8601 format)
    end_date : str, optional
        Filter campaigns completed before this date (ISO 8601 format)
    min_return : float, optional
        Filter campaigns with total_return_pct >= min_return
    min_r : float, optional
        Filter campaigns with total_r_achieved >= min_r
    limit : int, default=100
        Maximum number of campaigns to include (pagination)
    offset : int, default=0
        Skip first N campaigns (pagination)
    db_session : AsyncSession
        Database session (injected)

    Returns:
    --------
    AggregatedMetrics
        Aggregated performance statistics

    Raises:
    -------
    HTTPException
        503 Service Unavailable if database error
    """
    try:
        from datetime import UTC, datetime
        from decimal import Decimal

        # Build filters
        filters = MetricsFilter(
            symbol=symbol,
            timeframe=timeframe,
            start_date=datetime.fromisoformat(start_date) if start_date else None,
            end_date=datetime.fromisoformat(end_date) if end_date else None,
            min_return=Decimal(str(min_return)) if min_return is not None else None,
            min_r_achieved=Decimal(str(min_r)) if min_r is not None else None,
            limit=limit,
            offset=offset,
        )

        # Create repository with db session
        campaign_repository = CampaignRepository(db_session)

        # Fetch historical campaign metrics with filters
        historical_metrics = await campaign_repository.get_historical_metrics(filters)

        if not historical_metrics:
            # Return empty aggregation if no campaigns match filters
            logger.info(
                "no_campaigns_for_aggregation",
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
            )

            # Return zero-value aggregation
            return AggregatedMetrics(
                total_campaigns_completed=0,
                overall_win_rate=Decimal("0.00"),
                average_campaign_return_pct=Decimal("0.00"),
                average_r_achieved_per_campaign=Decimal("0.0000"),
                best_campaign=None,
                worst_campaign=None,
                median_duration_days=None,
                average_max_drawdown=Decimal("0.00"),
                calculation_timestamp=datetime.now(UTC),
                filter_criteria={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "start_date": start_date,
                    "end_date": end_date,
                    "min_return": str(min_return) if min_return is not None else None,
                    "min_r": str(min_r) if min_r is not None else None,
                },
            )

        # Calculate aggregated performance from historical metrics
        aggregated = get_aggregated_performance(
            campaigns_metrics=historical_metrics, filters=filters
        )

        logger.info(
            "aggregated_performance_calculated",
            total_campaigns=aggregated.total_campaigns_completed,
            overall_win_rate=str(aggregated.overall_win_rate),
            average_return=str(aggregated.average_campaign_return_pct),
            average_r=str(aggregated.average_r_achieved_per_campaign),
            symbol_filter=symbol,
            timeframe_filter=timeframe,
        )

        return aggregated

    except ValueError as e:
        # Invalid date format or Decimal conversion
        logger.error(
            "aggregated_performance_validation_error",
            error=str(e),
            start_date=start_date,
            end_date=end_date,
            min_return=min_return,
            min_r=min_r,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parameter format: {str(e)}",
        ) from e

    except Exception as e:
        # Database or calculation error
        logger.error(
            "aggregated_performance_error",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable. Please try again later.",
        ) from e
