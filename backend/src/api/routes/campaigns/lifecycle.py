"""
Campaign lifecycle endpoints.

Provides campaign listing and lifecycle management operations.
Story 11.4 (Campaign Tracker)
"""

from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user_id
from src.database import get_db
from src.models.campaign_tracker import (
    CampaignResponse,
    ExitPlanDisplay,
    PreliminaryEvent,
    TradingRangeLevels,
)
from src.repositories.campaign_repository import CampaignRepository
from src.services.campaign_tracker_service import build_campaign_response

logger = structlog.get_logger()

router = APIRouter()


@router.get("", response_model=dict)
async def get_campaigns_list(
    status_filter: Optional[str] = Query(
        None, description="Filter by status: ACTIVE, MARKUP, COMPLETED, INVALIDATED", alias="status"
    ),
    symbol: Optional[str] = Query(None, description="Filter by trading symbol"),
    limit: int = Query(50, ge=1, le=100, description="Number of campaigns to return"),
    offset: int = Query(0, ge=0, description="Number of campaigns to skip"),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> dict:
    """
    Get list of campaigns with optional filtering (Story 11.4 AC: 8, Task 1).

    Returns campaigns filtered by status and/or symbol, with complete data
    for campaign tracker visualization including progression, health status,
    entries with P&L, and exit plans.

    **Authentication Required:** Bearer token

    Query Parameters:
    -----------------
    - status: Filter by ACTIVE, MARKUP, COMPLETED, INVALIDATED (optional)
    - symbol: Filter by trading symbol (optional)
    - limit: Number of campaigns to return (1-100, default 50)
    - offset: Number of campaigns to skip for pagination (default 0)

    Response Format:
    ----------------
    {
        "data": [CampaignResponse, ...],
        "pagination": {
            "returned_count": 3,
            "total_count": 10,
            "limit": 50,
            "offset": 0,
            "has_more": true
        }
    }

    Returns:
    --------
    200 OK: List of campaigns with pagination
    400 Bad Request: Invalid filter parameters
    401 Unauthorized: Missing or invalid authentication token
    500 Internal Server Error: Database error
    """
    try:
        # Validate status filter
        valid_statuses = ["ACTIVE", "MARKUP", "COMPLETED", "INVALIDATED"]
        if status_filter and status_filter not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
            )

        repo = CampaignRepository(db)

        # Fetch campaigns with user isolation, pagination, and eager loading (SEC-001, CODE-002, CODE-003, PERF-001)
        campaigns, total_count = await repo.get_campaigns(
            user_id=user_id,
            status=status_filter,
            symbol=symbol,
            limit=limit,
            offset=offset,
        )

        # Build response for each campaign
        campaign_responses: list[CampaignResponse] = []

        for campaign in campaigns:
            # TODO Story 11.4 Task 13: Query preliminary events from patterns table
            # For now, use empty list
            preliminary_events: list[PreliminaryEvent] = []

            # TODO: Fetch trading range levels from trading_ranges table
            # For now, use mock data
            trading_range_levels = TradingRangeLevels(
                creek_level=Decimal("145.00"),
                ice_level=Decimal("160.00"),
                jump_target=Decimal("175.00"),
            )

            # TODO: Fetch exit rules from exit_rules table
            # For now, use default exit plan
            exit_plan = ExitPlanDisplay(
                target_1=Decimal("160.00"),
                target_2=Decimal("168.50"),
                target_3=Decimal("175.00"),
                current_stop=Decimal("150.00"),
                partial_exit_percentages={"T1": 50, "T2": 30, "T3": 20},
            )

            # TODO: Fetch current market prices for P&L calculation
            # For now, use empty dict (will use position.current_price)
            current_prices: dict[UUID, Decimal] = {}

            response = build_campaign_response(
                campaign=campaign,
                trading_range_levels=trading_range_levels,
                exit_plan=exit_plan,
                preliminary_events=preliminary_events,
                current_prices=current_prices,
            )
            campaign_responses.append(response)

        logger.info(
            "campaigns_list_retrieved",
            count=len(campaign_responses),
            total_count=total_count,
            user_id=str(user_id),
            status_filter=status_filter,
            symbol_filter=symbol,
            limit=limit,
            offset=offset,
        )

        # Build pagination response (CODE-003)
        has_more = (offset + len(campaign_responses)) < total_count

        return {
            "data": [c.serialize_model() for c in campaign_responses],
            "pagination": {
                "returned_count": len(campaign_responses),
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": has_more,
            },
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            "failed_to_get_campaigns_list",
            status_filter=status_filter,
            symbol=symbol,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve campaigns. Please try again later.",
        ) from e
