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
POST /api/v1/campaigns/{campaign_id}/exit-rules - Create/update exit rule configuration (Story 9.5)
GET /api/v1/campaigns/{campaign_id}/exit-rules - Retrieve exit rule configuration (Story 9.5)
GET /api/v1/campaigns/{campaign_id}/performance - Returns campaign performance metrics (Story 9.6)
GET /api/v1/campaigns/{campaign_id}/pnl-curve - Returns P&L curve visualization data (Story 9.6)
GET /api/v1/campaigns/performance - Returns aggregated performance across all campaigns (Story 9.6)

BMAD Allocation (Story 9.2, FR23):
-----------------------------------
- Spring: 40% of 5% campaign budget (2.00% max) - HIGHEST allocation
- SOS: 30% of 5% campaign budget (1.50% max) - Primary confirmation entry
- LPS: 30% of 5% campaign budget (1.50% max) - Secondary entry
- Rebalancing: Adjusts percentages when earlier entries skipped
- 75% Confidence: Required for 100% LPS sole entry allocation

Author: Story 7.4 (AC 1, 4), Story 9.2 (Allocation Audit Trail), Story 9.4 (Position Tracking), Story 9.5 (Exit Rules)
"""

from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user_id
from src.database import get_db
from src.models.allocation import AllocationPlan
from src.models.campaign import (
    AggregatedMetrics,
    CampaignMetrics,
    CampaignPositions,
    CampaignRisk,
    ExitRule,
    MetricsFilter,
    PnLCurve,
)
from src.models.portfolio import Position
from src.repositories.allocation_repository import AllocationRepository
from src.repositories.campaign_repository import CampaignNotFoundError, CampaignRepository
from src.repositories.exit_rule_repository import ExitRuleRepository
from src.risk_management.campaign_tracker import build_campaign_risk_report
from src.services.campaign_performance_calculator import (
    calculate_campaign_performance,
    generate_pnl_curve,
    get_aggregated_performance,
)

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


@router.post("/{campaign_id}/exit-rules", response_model=ExitRule, status_code=status.HTTP_200_OK)
async def create_or_update_exit_rules(
    campaign_id: UUID, exit_rule: ExitRule, db_session: AsyncSession = Depends(get_db)
) -> ExitRule:
    """
    Create or update exit rule configuration for campaign (Story 9.5, AC 10).

    Creates a new exit rule or updates existing exit rule for the campaign with
    configurable partial exit percentages, trailing stop settings, and target levels.

    Validation:
    -----------
    - Exit percentages must sum to 100% (enforced by ExitRule model validator)
    - Each percentage must be 0-100%
    - Target levels must be positive Decimals with 8 decimal places
    - Campaign must exist (404 if not found)

    Request Body:
    -------------
    ExitRule with:
    - t1_exit_pct: Percentage to exit at T1 (default 50%)
    - t2_exit_pct: Percentage to exit at T2 (default 30%)
    - t3_exit_pct: Percentage to exit at T3 (default 20%)
    - trail_to_breakeven_on_t1: Move stop to entry price when T1 hit (default True)
    - trail_to_t1_on_t2: Move stop to T1 level when T2 hit (default True)
    - target_1_level: T1 target price (Ice for pre-breakout, Jump for post-breakout)
    - target_2_level: T2 target price (Jump)
    - target_3_level: T3 target price (Jump × 1.5)
    - spring_low, ice_level, creek_level, utad_high, jump_target: Invalidation levels

    Parameters:
    -----------
    campaign_id : UUID
        Campaign identifier
    exit_rule : ExitRule
        Exit rule configuration (from request body)
    db_session : AsyncSession
        Database session (injected)

    Returns:
    --------
    ExitRule
        Created or updated exit rule with all configuration

    Raises:
    -------
    HTTPException
        400 Bad Request if validation fails (percentages don't sum to 100%)
        404 Not Found if campaign doesn't exist
        503 Service Unavailable if database error

    Example Request:
    ----------------
    ```json
    {
      "campaign_id": "550e8400-e29b-41d4-a716-446655440000",
      "target_1_level": "160.00",
      "target_2_level": "175.00",
      "target_3_level": "187.50",
      "t1_exit_pct": "40.00",
      "t2_exit_pct": "35.00",
      "t3_exit_pct": "25.00",
      "trail_to_breakeven_on_t1": true,
      "trail_to_t1_on_t2": true,
      "spring_low": "145.00",
      "ice_level": "160.00",
      "creek_level": "145.00",
      "jump_target": "175.00"
    }
    ```

    Example Response:
    -----------------
    ```json
    {
      "id": "a1b2c3d4...",
      "campaign_id": "550e8400...",
      "target_1_level": "160.00",
      "target_2_level": "175.00",
      "target_3_level": "187.50",
      "t1_exit_pct": "40.00",
      "t2_exit_pct": "35.00",
      "t3_exit_pct": "25.00",
      "trail_to_breakeven_on_t1": true,
      "trail_to_t1_on_t2": true,
      "spring_low": "145.00",
      "ice_level": "160.00",
      "creek_level": "145.00",
      "utad_high": null,
      "jump_target": "175.00",
      "created_at": "2024-10-15T10:30:00Z",
      "updated_at": "2024-10-15T10:30:00Z"
    }
    ```
    """
    try:
        # Ensure campaign_id in exit_rule matches path parameter
        exit_rule.campaign_id = campaign_id

        # Create repository with db session
        exit_rule_repository = ExitRuleRepository(db_session)

        # Check if exit rule already exists
        existing_rule = await exit_rule_repository.get_exit_rule(campaign_id)

        if existing_rule:
            # Update existing exit rule
            updates = {
                "target_1_level": exit_rule.target_1_level,
                "target_2_level": exit_rule.target_2_level,
                "target_3_level": exit_rule.target_3_level,
                "t1_exit_pct": exit_rule.t1_exit_pct,
                "t2_exit_pct": exit_rule.t2_exit_pct,
                "t3_exit_pct": exit_rule.t3_exit_pct,
                "trail_to_breakeven_on_t1": exit_rule.trail_to_breakeven_on_t1,
                "trail_to_t1_on_t2": exit_rule.trail_to_t1_on_t2,
                "spring_low": exit_rule.spring_low,
                "ice_level": exit_rule.ice_level,
                "creek_level": exit_rule.creek_level,
                "utad_high": exit_rule.utad_high,
                "jump_target": exit_rule.jump_target,
            }

            updated_rule = await exit_rule_repository.update_exit_rule(campaign_id, updates)

            logger.info(
                "exit_rule_updated",
                campaign_id=str(campaign_id),
                exit_rule_id=str(updated_rule.id),
                t1_pct=str(updated_rule.t1_exit_pct),
                t2_pct=str(updated_rule.t2_exit_pct),
                t3_pct=str(updated_rule.t3_exit_pct),
            )

            return updated_rule
        else:
            # Create new exit rule
            created_rule = await exit_rule_repository.create_exit_rule(exit_rule)

            logger.info(
                "exit_rule_created",
                campaign_id=str(campaign_id),
                exit_rule_id=str(created_rule.id),
                t1_pct=str(created_rule.t1_exit_pct),
                t2_pct=str(created_rule.t2_exit_pct),
                t3_pct=str(created_rule.t3_exit_pct),
            )

            return created_rule

    except ValueError as e:
        # Validation error (percentages don't sum to 100%, negative values, etc.)
        logger.error(
            "exit_rule_validation_error",
            campaign_id=str(campaign_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        ) from e

    except Exception as e:
        # Database or other system error
        logger.error(
            "exit_rule_create_update_error",
            campaign_id=str(campaign_id),
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable. Please try again later.",
        ) from e


@router.get("/{campaign_id}/exit-rules", response_model=ExitRule)
async def get_exit_rules(campaign_id: UUID, db_session: AsyncSession = Depends(get_db)) -> ExitRule:
    """
    Retrieve exit rule configuration for campaign (Story 9.5, AC 10).

    Returns the current exit rule configuration including partial exit percentages,
    target levels, trailing stop settings, and invalidation levels.

    Parameters:
    -----------
    campaign_id : UUID
        Campaign identifier
    db_session : AsyncSession
        Database session (injected)

    Returns:
    --------
    ExitRule
        Current exit rule configuration with:
        - id: Exit rule UUID
        - campaign_id: Campaign UUID
        - target_1_level, target_2_level, target_3_level: Target prices (NUMERIC 18,8)
        - t1_exit_pct, t2_exit_pct, t3_exit_pct: Partial exit percentages
        - trail_to_breakeven_on_t1, trail_to_t1_on_t2: Trailing stop config
        - spring_low, ice_level, creek_level, utad_high, jump_target: Invalidation levels
        - created_at, updated_at: Timestamps

    Raises:
    -------
    HTTPException
        404 Not Found if campaign doesn't have exit rule configured
        503 Service Unavailable if database error

    Example Response:
    -----------------
    ```json
    {
      "id": "a1b2c3d4...",
      "campaign_id": "550e8400...",
      "target_1_level": "160.00",
      "target_2_level": "175.00",
      "target_3_level": "187.50",
      "t1_exit_pct": "50.00",
      "t2_exit_pct": "30.00",
      "t3_exit_pct": "20.00",
      "trail_to_breakeven_on_t1": true,
      "trail_to_t1_on_t2": true,
      "spring_low": "145.00",
      "ice_level": "160.00",
      "creek_level": "145.00",
      "utad_high": null,
      "jump_target": "175.00",
      "created_at": "2024-10-15T10:30:00Z",
      "updated_at": "2024-10-15T10:30:00Z"
    }
    ```
    """
    try:
        # Create repository with db session
        exit_rule_repository = ExitRuleRepository(db_session)

        # Fetch exit rule for campaign
        exit_rule = await exit_rule_repository.get_exit_rule(campaign_id)

        if not exit_rule:
            logger.warning(
                "exit_rule_not_found",
                campaign_id=str(campaign_id),
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Exit rule not found for campaign: {campaign_id}",
            )

        logger.info(
            "exit_rule_retrieved",
            campaign_id=str(campaign_id),
            exit_rule_id=str(exit_rule.id),
            t1_pct=str(exit_rule.t1_exit_pct),
            t2_pct=str(exit_rule.t2_exit_pct),
            t3_pct=str(exit_rule.t3_exit_pct),
        )

        return exit_rule

    except HTTPException:
        # Re-raise HTTP exceptions (404 from above)
        raise

    except Exception as e:
        # Database or other system error
        logger.error(
            "exit_rule_retrieval_error",
            campaign_id=str(campaign_id),
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable. Please try again later.",
        ) from e


# ==================================================================================
# Campaign Performance Tracking Endpoints (Story 9.6)
# ==================================================================================


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
        Comprehensive performance metrics:
        - campaign_id, symbol
        - total_return_pct, total_r_achieved, duration_days, max_drawdown
        - total_positions, winning_positions, losing_positions, win_rate
        - average_entry_price, average_exit_price
        - expected_jump_target, actual_high_reached, target_achievement_pct
        - phase_c_avg_r, phase_d_avg_r, phase_c_positions, phase_d_positions
        - position_details: List[PositionMetrics] with individual performance

    Raises:
    -------
    HTTPException
        404 Not Found if campaign doesn't exist
        422 Unprocessable Entity if campaign not completed (status != COMPLETED)
        503 Service Unavailable if database error

    Example Response:
    -----------------
    ```json
    {
      "campaign_id": "550e8400-e29b-41d4-a716-446655440000",
      "symbol": "AAPL",
      "total_return_pct": "15.50",
      "total_r_achieved": "8.2",
      "duration_days": 45,
      "max_drawdown": "5.25",
      "total_positions": 3,
      "winning_positions": 2,
      "losing_positions": 1,
      "win_rate": "66.67",
      "average_entry_price": "150.00",
      "average_exit_price": "173.25",
      "expected_jump_target": "175.00",
      "actual_high_reached": "178.50",
      "target_achievement_pct": "114.00",
      "expected_r": "10.0",
      "actual_r_achieved": "8.2",
      "phase_c_avg_r": "3.5",
      "phase_d_avg_r": "2.1",
      "phase_c_positions": 2,
      "phase_d_positions": 1,
      "phase_c_win_rate": "100.00",
      "phase_d_win_rate": "100.00",
      "position_details": [
        {
          "position_id": "abc123...",
          "pattern_type": "SPRING",
          "individual_r": "2.5",
          "entry_price": "100.00",
          "exit_price": "105.00",
          "shares": "50",
          "realized_pnl": "250.00",
          "win_loss_status": "WIN",
          "duration_bars": 120,
          "entry_date": "2024-10-15T10:00:00Z",
          "exit_date": "2024-10-20T15:00:00Z",
          "entry_phase": "Phase C"
        }
      ],
      "calculation_timestamp": "2024-12-06T10:00:00Z",
      "completed_at": "2024-11-01T16:30:00Z"
    }
    ```
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
        - "daily": One data point per day (recommended for campaigns > 30 days)
        - "hourly": One data point per hour (for detailed analysis)
    db_session : AsyncSession
        Database session (injected)

    Returns:
    --------
    PnLCurve
        P&L curve visualization data:
        - campaign_id: Campaign UUID
        - data_points: List[PnLPoint] chronologically ordered
          - timestamp: Point in time (UTC)
          - cumulative_pnl: Cumulative P&L at this point
          - cumulative_return_pct: Cumulative return percentage
          - drawdown_pct: Drawdown percentage at this point
        - max_drawdown_point: PnLPoint where maximum drawdown occurred

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
      "data_points": [
        {
          "timestamp": "2024-10-15T00:00:00Z",
          "cumulative_pnl": "0.00",
          "cumulative_return_pct": "0.00",
          "drawdown_pct": "0.00"
        },
        {
          "timestamp": "2024-10-16T00:00:00Z",
          "cumulative_pnl": "500.00",
          "cumulative_return_pct": "5.00",
          "drawdown_pct": "0.00"
        },
        {
          "timestamp": "2024-10-17T00:00:00Z",
          "cumulative_pnl": "300.00",
          "cumulative_return_pct": "3.00",
          "drawdown_pct": "-2.00"
        }
      ],
      "max_drawdown_point": {
        "timestamp": "2024-10-17T00:00:00Z",
        "cumulative_pnl": "300.00",
        "cumulative_return_pct": "3.00",
        "drawdown_pct": "-2.00"
      }
    }
    ```
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

    Query Parameters:
    -----------------
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
        Aggregated performance statistics:
        - total_campaigns_completed: Number of completed campaigns
        - overall_win_rate: Percentage of winning campaigns
        - average_campaign_return_pct: Average return across all campaigns
        - average_r_achieved_per_campaign: Average R-multiple per campaign
        - best_campaign: Campaign with highest return (campaign_id, return_pct)
        - worst_campaign: Campaign with lowest return (campaign_id, return_pct)
        - median_duration_days: Median campaign duration
        - average_max_drawdown: Average maximum drawdown
        - calculation_timestamp: When aggregation was calculated
        - filter_criteria: Filters applied

    Raises:
    -------
    HTTPException
        503 Service Unavailable if database error

    Example Response:
    -----------------
    ```json
    {
      "total_campaigns_completed": 25,
      "overall_win_rate": "72.00",
      "average_campaign_return_pct": "12.50",
      "average_r_achieved_per_campaign": "6.8",
      "best_campaign": {
        "campaign_id": "550e8400-e29b-41d4-a716-446655440000",
        "return_pct": "35.50"
      },
      "worst_campaign": {
        "campaign_id": "abc12345-e29b-41d4-a716-446655440000",
        "return_pct": "-5.25"
      },
      "median_duration_days": 38,
      "average_max_drawdown": "6.75",
      "calculation_timestamp": "2024-12-06T10:00:00Z",
      "filter_criteria": {
        "symbol": "AAPL",
        "timeframe": "1h",
        "start_date": "2024-01-01T00:00:00Z",
        "end_date": "2024-12-31T23:59:59Z"
      }
    }
    ```
    """
    try:
        from datetime import datetime
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
            from datetime import UTC

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


# ==================================================================================
# Campaign Tracker Endpoints (Story 11.4)
# ==================================================================================


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

    Example:
    --------
    GET /api/v1/campaigns?status=ACTIVE&symbol=AAPL&limit=20&offset=0
    Authorization: Bearer <token>

    Returns:
    --------
    200 OK: List of campaigns with pagination
    400 Bad Request: Invalid filter parameters
    401 Unauthorized: Missing or invalid authentication token
    500 Internal Server Error: Database error
    """
    from decimal import Decimal

    from src.models.campaign_tracker import (
        CampaignResponse,
        ExitPlanDisplay,
        PreliminaryEvent,
        TradingRangeLevels,
    )
    from src.services.campaign_tracker_service import build_campaign_response

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
