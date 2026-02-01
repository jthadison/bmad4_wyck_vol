"""
Campaign risk tracking endpoints.

Provides risk reports with BMAD allocation breakdown and allocation audit trails.
Story 7.4 (AC 1, 4), Story 9.2 (Allocation Audit Trail)
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.allocation import AllocationPlan
from src.models.campaign import CampaignRisk
from src.models.portfolio import Position
from src.repositories.allocation_repository import AllocationRepository
from src.risk_management.campaign_tracker import build_campaign_risk_report

logger = structlog.get_logger()

router = APIRouter()


# Mock function for fetching open positions
# TODO: Replace with actual repository call when position repository is implemented
async def get_open_positions() -> list[Position]:
    """
    Fetch all open positions from the database.

    This is a placeholder function. In production, this should call the
    position repository to fetch all positions with status="OPEN".

    Returns:
    --------
    list[Position]
        List of open Position objects

    Raises:
    -------
    HTTPException
        503 Service Unavailable if database is down
    """
    # PLACEHOLDER: Return empty list for now
    # In production, replace with:
    # from src.repositories.position_repository import PositionRepository
    # repo = PositionRepository()
    # return await repo.get_open_positions()

    logger.debug("get_open_positions_called", note="Using placeholder implementation")
    return []


@router.get("/{campaign_id}/risk", response_model=CampaignRisk)
async def get_campaign_risk(campaign_id: UUID) -> CampaignRisk:
    """
    Get comprehensive campaign risk report with BMAD allocation breakdown.

    AC 1: Returns total_risk, available_capacity, position_count, entry_breakdown
    AC 4: Entry breakdown includes BMAD allocation percentages for each pattern type

    BMAD Allocation (Authentic Wyckoff 3-Entry Model):
    ---------------------------------------------------
    - Spring: 40% (2.00% max) - Maximum accumulation opportunity (HIGHEST)
    - SOS: 35% (1.75% max) - Primary confirmation entry
    - LPS: 25% (1.25% max) - Secondary entry (optional)
    - Note: ST (Secondary Test) is confirmation event, not entry pattern

    Parameters:
    -----------
    campaign_id : UUID
        Campaign identifier

    Returns:
    --------
    CampaignRisk
        Comprehensive campaign risk report including:
        - total_risk: Sum of all position risks in campaign (≤ 5.0%)
        - available_capacity: Remaining capacity before 5% limit
        - position_count: Number of open positions
        - entry_breakdown: Details for each position (pattern type, risk %, allocation %)

    Raises:
    -------
    HTTPException
        404 Not Found if campaign doesn't exist
        503 Service Unavailable if database is unavailable
    """
    try:
        # Fetch all open positions
        # TODO: Replace with campaign-specific query when repository is implemented
        open_positions = await get_open_positions()

        # Build comprehensive campaign risk report
        campaign_risk = build_campaign_risk_report(campaign_id, open_positions)

        logger.info(
            "campaign_risk_retrieved",
            campaign_id=str(campaign_id),
            total_risk=str(campaign_risk.total_risk),
            available_capacity=str(campaign_risk.available_capacity),
            position_count=campaign_risk.position_count,
        )

        return campaign_risk

    except ValueError as e:
        # Campaign not found or validation error
        logger.error(
            "campaign_risk_error",
            campaign_id=str(campaign_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign not found: {campaign_id}",
        ) from e

    except Exception as e:
        # Database or other system error
        logger.error(
            "campaign_risk_system_error",
            campaign_id=str(campaign_id),
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable. Please try again later.",
        ) from e


@router.get("/{campaign_id}/allocations", response_model=list[AllocationPlan])
async def get_campaign_allocations(
    campaign_id: UUID, db_session: AsyncSession = Depends(get_db)
) -> list[AllocationPlan]:
    """
    Get allocation audit trail for campaign (Story 9.2, AC: 8).

    Returns chronological list of all allocation decisions for a campaign,
    including approved and rejected allocations with BMAD percentages,
    rebalancing reasons, and confidence thresholds.

    Use Cases:
    ----------
    - Audit trail: Review all allocation decisions for compliance
    - Debugging: Understand why allocations were approved/rejected
    - Analytics: Track rebalancing patterns and confidence scores
    - Risk review: Verify 5% campaign budget enforcement

    Parameters:
    -----------
    campaign_id : UUID
        Campaign identifier
    db_session : AsyncSession
        Database session (injected)

    Returns:
    --------
    list[AllocationPlan]
        Chronological list of allocation plans (oldest first)

    Raises:
    -------
    HTTPException
        404 Not Found if campaign doesn't exist
        503 Service Unavailable if database error
    """
    try:
        # Create repository with db session
        allocation_repository = AllocationRepository(db_session)

        # Fetch all allocation plans for campaign
        allocations = await allocation_repository.get_allocation_plans_by_campaign(campaign_id)

        if not allocations:
            # Return empty list if no allocations found (campaign might not have any yet)
            logger.info(
                "no_allocations_found",
                campaign_id=str(campaign_id),
            )
            return []

        logger.info(
            "campaign_allocations_retrieved",
            campaign_id=str(campaign_id),
            allocation_count=len(allocations),
            approved_count=sum(1 for a in allocations if a.approved),
            rejected_count=sum(1 for a in allocations if not a.approved),
        )

        return allocations

    except Exception as e:
        # Database or other system error
        logger.error(
            "campaign_allocations_error",
            campaign_id=str(campaign_id),
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable. Please try again later.",
        ) from e
