"""
Campaign Lifecycle API Routes (Story 9.1)

Purpose:
--------
Provides REST API endpoints for campaign lifecycle management and
multi-phase position tracking.

Endpoints (AC: 10):
-------------------
GET /api/v1/campaign-lifecycle - List campaigns with filters
GET /api/v1/campaign-lifecycle/{campaign_id} - Get campaign with positions

Response Models:
----------------
- Campaign: Complete campaign with all positions
- PaginatedCampaignsResponse: List with pagination metadata

Integration:
------------
- Story 9.1: Core campaign lifecycle API
- Uses CampaignService for business logic
- Returns domain models (Campaign, CampaignPosition)

Author: Story 9.1
"""

from typing import Literal, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.campaign_management.service import CampaignService
from src.models.campaign_lifecycle import Campaign, CampaignStatus
from src.repositories.campaign_lifecycle_repository import CampaignLifecycleRepository

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/campaign-lifecycle", tags=["campaign-lifecycle"])


class PaginationMetadata(BaseModel):
    """Pagination metadata for list responses."""

    returned_count: int = Field(..., description="Number of items in this response")
    total_count: int = Field(..., description="Total matching items (for pagination)")
    limit: int = Field(..., description="Limit parameter used")
    offset: int = Field(..., description="Offset parameter used")
    has_more: bool = Field(..., description="True if more items available")


class PaginatedCampaignsResponse(BaseModel):
    """Paginated list of campaigns with metadata."""

    data: list[Campaign] = Field(..., description="Campaign list")
    pagination: PaginationMetadata = Field(..., description="Pagination info")


# Dependency injection for CampaignService
# TODO: Replace with proper FastAPI dependency injection when database is ready
async def get_campaign_service() -> CampaignService:
    """
    Dependency: Get CampaignService instance.

    This is a placeholder. In production, inject AsyncSession and create
    repository + service with proper lifecycle management.
    """
    # Placeholder implementation
    # In production:
    # from src.database import get_async_session
    # session = await get_async_session()
    # repository = CampaignLifecycleRepository(session)
    # return CampaignService(repository)

    logger.warning("get_campaign_service_placeholder", message="Using placeholder service")
    # Return mock service (will use placeholder repository methods)
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_session = AsyncSession()  # type: ignore
    repository = CampaignLifecycleRepository(mock_session)
    return CampaignService(repository)


@router.get("", response_model=PaginatedCampaignsResponse)
async def list_campaigns(
    symbol: Optional[str] = Query(None, description="Filter by symbol (e.g., AAPL)"),
    status: Optional[Literal["ACTIVE", "MARKUP", "COMPLETED", "INVALIDATED"]] = Query(
        None, description="Filter by campaign status"
    ),
    limit: int = Query(50, ge=1, le=100, description="Pagination limit"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    service: CampaignService = Depends(get_campaign_service),
) -> PaginatedCampaignsResponse:
    """
    List campaigns with optional filters (AC: 10).

    Returns paginated list of campaigns ordered by start_date DESC (most recent first).
    Each campaign includes all positions loaded.

    Query Parameters:
    -----------------
    - symbol: Filter by ticker symbol (optional)
    - status: Filter by lifecycle status (ACTIVE, MARKUP, COMPLETED, INVALIDATED)
    - limit: Max results to return (1-100, default 50)
    - offset: Number of results to skip (default 0)

    Returns:
    --------
    PaginatedCampaignsResponse
        {
            "data": [Campaign, ...],
            "pagination": {
                "returned_count": 10,
                "total_count": 45,
                "limit": 50,
                "offset": 0,
                "has_more": false
            }
        }

    Raises:
    -------
    HTTPException
        500 Internal Server Error if database query fails

    Example:
    --------
    GET /api/v1/campaign-lifecycle?symbol=AAPL&status=ACTIVE&limit=20

    Response:
    ```json
    {
      "data": [
        {
          "id": "uuid",
          "campaign_id": "AAPL-2024-10-15",
          "symbol": "AAPL",
          "status": "ACTIVE",
          "total_allocation": "3.5",
          "positions": [...]
        }
      ],
      "pagination": {
        "returned_count": 1,
        "total_count": 1,
        "limit": 20,
        "offset": 0,
        "has_more": false
      }
    }
    ```
    """
    try:
        # Convert status string to enum if provided
        status_enum = CampaignStatus(status) if status else None

        # Fetch campaigns from service
        if symbol:
            campaigns = await service.campaign_repository.get_campaigns_by_symbol(
                symbol, status=status_enum, limit=limit, offset=offset
            )
        else:
            # For now, if no symbol filter, return empty list
            # TODO: Implement get_all_campaigns with filters
            logger.warning(
                "list_campaigns_no_symbol_filter",
                message="Symbol filter required for now (repository not fully implemented)",
            )
            campaigns = []

        # Calculate pagination metadata
        returned_count = len(campaigns)
        total_count = returned_count  # Simplified - real impl would count total matching
        has_more = returned_count == limit  # Simplified heuristic

        pagination = PaginationMetadata(
            returned_count=returned_count,
            total_count=total_count,
            limit=limit,
            offset=offset,
            has_more=has_more,
        )

        logger.info(
            "campaigns_listed",
            symbol=symbol,
            status=status,
            returned_count=returned_count,
        )

        return PaginatedCampaignsResponse(data=campaigns, pagination=pagination)

    except Exception as e:
        logger.error(
            "list_campaigns_failed",
            symbol=symbol,
            status=status,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list campaigns. Please try again later.",
        ) from e


@router.get("/{campaign_id}", response_model=Campaign)
async def get_campaign(
    campaign_id: UUID,
    service: CampaignService = Depends(get_campaign_service),
) -> Campaign:
    """
    Get campaign by ID with all positions loaded (AC: 10).

    Fetches complete campaign state including all positions (Spring, SOS, LPS)
    with real-time P&L tracking.

    Path Parameters:
    ----------------
    - campaign_id: Campaign UUID (primary key)

    Returns:
    --------
    Campaign
        Complete campaign with all positions

    Raises:
    -------
    HTTPException
        404 Not Found if campaign doesn't exist
        500 Internal Server Error if database query fails

    Example:
    --------
    GET /api/v1/campaign-lifecycle/550e8400-e29b-41d4-a716-446655440000

    Response:
    ```json
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "campaign_id": "AAPL-2024-10-15",
      "symbol": "AAPL",
      "timeframe": "1d",
      "trading_range_id": "uuid",
      "status": "MARKUP",
      "phase": "D",
      "positions": [
        {
          "position_id": "uuid",
          "signal_id": "uuid",
          "pattern_type": "SPRING",
          "entry_price": "150.25",
          "shares": "100",
          "current_pnl": "250.00",
          "status": "OPEN"
        },
        {
          "position_id": "uuid",
          "signal_id": "uuid",
          "pattern_type": "SOS",
          "entry_price": "152.50",
          "shares": "50",
          "current_pnl": "75.00",
          "status": "OPEN"
        }
      ],
      "total_allocation": "3.5",
      "total_risk": "450.00",
      "total_pnl": "325.00",
      "start_date": "2024-10-15T10:30:00Z"
    }
    ```
    """
    try:
        # Fetch campaign by ID
        campaign = await service.campaign_repository.get_campaign_by_id(campaign_id)

        if campaign is None:
            logger.warning("campaign_not_found", campaign_id=str(campaign_id))
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign not found: {campaign_id}",
            )

        logger.info(
            "campaign_retrieved",
            campaign_id=campaign.campaign_id,
            position_count=len(campaign.positions),
        )

        return campaign

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_campaign_failed",
            campaign_id=str(campaign_id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve campaign. Please try again later.",
        ) from e
