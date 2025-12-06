"""
Campaign API Routes - Campaign Risk Tracking Endpoints

Purpose:
--------
Provides REST API endpoints for campaign risk tracking and BMAD allocation monitoring.

Endpoints:
----------
GET /api/v1/campaigns/{campaign_id}/risk - Returns campaign risk report with BMAD breakdown
GET /api/v1/campaigns/{campaign_id}/allocations - Returns allocation audit trail (Story 9.2)
GET /api/v1/campaigns/{campaign_id}/positions - Returns all positions with aggregated totals (Story 9.4)

BMAD Allocation (Story 9.2, FR23):
-----------------------------------
- Spring: 40% of 5% campaign budget (2.00% max) - HIGHEST allocation
- SOS: 30% of 5% campaign budget (1.50% max) - Primary confirmation entry
- LPS: 30% of 5% campaign budget (1.50% max) - Secondary entry
- Rebalancing: Adjusts percentages when earlier entries skipped
- 75% Confidence: Required for 100% LPS sole entry allocation

Author: Story 7.4 (AC 1, 4), Story 9.2 (Allocation Audit Trail), Story 9.4 (Position Tracking)
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.allocation import AllocationPlan
from src.models.campaign import CampaignPositions, CampaignRisk
from src.models.portfolio import Position
from src.repositories.allocation_repository import AllocationRepository
from src.repositories.campaign_repository import CampaignNotFoundError, CampaignRepository
from src.risk_management.campaign_tracker import build_campaign_risk_report

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])


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
    # from backend.src.repositories.position_repository import PositionRepository
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

    Example Response:
    -----------------
    ```json
    {
      "campaign_id": "550e8400-e29b-41d4-a716-446655440000",
      "total_risk": "5.0",
      "available_capacity": "0.0",
      "position_count": 3,
      "entry_breakdown": {
        "AAPL": {
          "pattern_type": "SPRING",
          "position_risk_pct": "2.0",
          "allocation_percentage": "40.0",
          "symbol": "AAPL",
          "status": "OPEN"
        },
        "MSFT": {
          "pattern_type": "SOS",
          "position_risk_pct": "1.75",
          "allocation_percentage": "35.0",
          "symbol": "MSFT",
          "status": "OPEN"
        },
        "GOOGL": {
          "pattern_type": "LPS",
          "position_risk_pct": "1.25",
          "allocation_percentage": "25.0",
          "symbol": "GOOGL",
          "status": "OPEN"
        }
      }
    }
    ```
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
        Chronological list of allocation plans (oldest first):
        - id: Allocation plan UUID
        - campaign_id: Campaign UUID
        - signal_id: Signal UUID
        - pattern_type: SPRING | SOS | LPS
        - bmad_allocation_pct: 0.40 (40%), 0.30 (30%), or rebalanced value
        - target_risk_pct: Target risk percentage
        - actual_risk_pct: Actual risk percentage
        - position_size_shares: Position size in shares
        - allocation_used: Cumulative allocation used (≤ 5.0%)
        - remaining_budget: Remaining budget after this allocation
        - is_rebalanced: True if rebalancing applied
        - rebalance_reason: Explanation if rebalanced
        - approved: True if approved, False if rejected
        - rejection_reason: Explanation if rejected
        - timestamp: When allocation was created

    Raises:
    -------
    HTTPException
        404 Not Found if campaign doesn't exist
        503 Service Unavailable if database error

    Example Response:
    -----------------
    ```json
    [
      {
        "id": "a1b2c3d4...",
        "campaign_id": "550e8400...",
        "signal_id": "abc123...",
        "pattern_type": "SPRING",
        "bmad_allocation_pct": "0.4000",
        "target_risk_pct": "2.00",
        "actual_risk_pct": "0.50",
        "position_size_shares": "166",
        "allocation_used": "0.50",
        "remaining_budget": "4.50",
        "is_rebalanced": false,
        "rebalance_reason": null,
        "approved": true,
        "rejection_reason": null,
        "timestamp": "2024-10-15T10:30:00Z"
      },
      {
        "id": "e5f6g7h8...",
        "campaign_id": "550e8400...",
        "signal_id": "def456...",
        "pattern_type": "SOS",
        "bmad_allocation_pct": "0.3000",
        "target_risk_pct": "1.50",
        "actual_risk_pct": "1.00",
        "position_size_shares": "333",
        "allocation_used": "1.50",
        "remaining_budget": "3.50",
        "is_rebalanced": false,
        "rebalance_reason": null,
        "approved": true,
        "rejection_reason": null,
        "timestamp": "2024-10-15T11:00:00Z"
      }
    ]
    ```
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


@router.get("/{campaign_id}/positions", response_model=CampaignPositions)
async def get_campaign_positions(
    campaign_id: UUID,
    include_closed: bool = Query(default=True, description="Include closed positions in results"),
    db_session: AsyncSession = Depends(get_db),
) -> CampaignPositions:
    """
    Get all positions for campaign with aggregated totals (Story 9.4, AC 10).

    Returns comprehensive position list with campaign-level aggregations:
    - Total shares across all open positions
    - Weighted average entry price (open positions only)
    - Total risk exposure (open positions only)
    - Total P&L (unrealized + realized)

    Query Performance:
    ------------------
    - Uses indexes on campaign_id and status for efficient retrieval
    - Target: < 100ms for 100+ positions (AC 9)

    Parameters:
    -----------
    campaign_id : UUID
        Campaign identifier
    include_closed : bool, default=True
        Whether to include closed positions in results (AC 6)
    db_session : AsyncSession
        Database session (injected)

    Returns:
    --------
    CampaignPositions
        Complete position list with aggregated metrics:
        - campaign_id: Campaign UUID
        - positions: List of all positions (OPEN and/or CLOSED)
        - total_shares: Sum of shares across open positions
        - weighted_avg_entry: (sum(entry_price × shares) / sum(shares)) for open positions
        - total_risk: sum((entry_price - stop_loss) × shares) for open positions
        - total_pnl: sum(current_pnl) for open + sum(realized_pnl) for closed
        - open_positions_count: Number of currently open positions
        - closed_positions_count: Number of closed positions

    Raises:
    -------
    HTTPException
        404 Not Found if campaign doesn't exist
        503 Service Unavailable if database error

    Example Response:
    -----------------
    ```json
    {
      "campaign_id": "550e8400-e29b-41d4-a716-446655440000",
      "positions": [
        {
          "id": "a1b2c3d4...",
          "campaign_id": "550e8400...",
          "signal_id": "abc123...",
          "symbol": "AAPL",
          "timeframe": "1h",
          "pattern_type": "SPRING",
          "entry_date": "2024-10-15T10:30:00Z",
          "entry_price": "150.00",
          "shares": "100",
          "stop_loss": "148.00",
          "current_price": "152.00",
          "current_pnl": "200.00",
          "status": "OPEN",
          "closed_date": null,
          "exit_price": null,
          "realized_pnl": null
        },
        {
          "id": "e5f6g7h8...",
          "campaign_id": "550e8400...",
          "signal_id": "def456...",
          "symbol": "AAPL",
          "timeframe": "1h",
          "pattern_type": "SOS",
          "entry_date": "2024-10-15T11:00:00Z",
          "entry_price": "152.00",
          "shares": "75",
          "stop_loss": "148.00",
          "current_price": "155.00",
          "current_pnl": "225.00",
          "status": "OPEN",
          "closed_date": null,
          "exit_price": null,
          "realized_pnl": null
        },
        {
          "id": "i9j0k1l2...",
          "campaign_id": "550e8400...",
          "signal_id": "ghi789...",
          "symbol": "AAPL",
          "timeframe": "1h",
          "pattern_type": "SPRING",
          "entry_date": "2024-10-14T10:00:00Z",
          "entry_price": "145.00",
          "shares": "100",
          "stop_loss": "143.00",
          "current_price": null,
          "current_pnl": null,
          "status": "CLOSED",
          "closed_date": "2024-10-15T09:00:00Z",
          "exit_price": "158.00",
          "realized_pnl": "1300.00"
        }
      ],
      "total_shares": "175",
      "weighted_avg_entry": "150.857142857143",
      "total_risk": "350.00",
      "total_pnl": "1725.00",
      "open_positions_count": 2,
      "closed_positions_count": 1
    }
    ```
    """
    try:
        # Create repository with db session
        campaign_repository = CampaignRepository(db_session)

        # Fetch all positions for campaign with aggregations
        campaign_positions = await campaign_repository.get_campaign_positions(
            campaign_id=campaign_id, include_closed=include_closed
        )

        logger.info(
            "campaign_positions_retrieved",
            campaign_id=str(campaign_id),
            total_positions=len(campaign_positions.positions),
            open_count=campaign_positions.open_positions_count,
            closed_count=campaign_positions.closed_positions_count,
            total_pnl=str(campaign_positions.total_pnl),
            include_closed=include_closed,
        )

        return campaign_positions

    except CampaignNotFoundError as e:
        # Campaign not found
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
        # Database or other system error
        logger.error(
            "campaign_positions_error",
            campaign_id=str(campaign_id),
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable. Please try again later.",
        ) from e
