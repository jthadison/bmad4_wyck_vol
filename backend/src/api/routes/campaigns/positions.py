"""
Campaign position tracking endpoints.

Provides position tracking with aggregated totals and exit rule management.
Story 9.4 (Position Tracking), Story 9.5 (Exit Rules)
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.campaign import CampaignPositions, ExitRule
from src.repositories.campaign_repository import CampaignNotFoundError, CampaignRepository
from src.repositories.exit_rule_repository import ExitRuleRepository

logger = structlog.get_logger()

router = APIRouter()


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
        Complete position list with aggregated metrics

    Raises:
    -------
    HTTPException
        404 Not Found if campaign doesn't exist
        503 Service Unavailable if database error
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
        Current exit rule configuration

    Raises:
    -------
    HTTPException
        404 Not Found if campaign doesn't have exit rule configured
        503 Service Unavailable if database error
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
