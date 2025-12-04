"""
Allocation Repository - Database Operations for BMAD Allocation Plans (Story 9.2)

Purpose:
--------
Provides async repository layer for AllocationPlan database persistence.
Implements audit trail storage for campaign allocation decisions.

Key Methods:
------------
1. save_allocation_plan: Persist allocation plan to database
2. get_allocation_plans_by_campaign: Fetch all allocations for a campaign (audit trail)
3. get_allocation_plan_by_id: Fetch single allocation plan by ID

Database Schema:
----------------
allocation_plans table:
- id (UUID, PK)
- campaign_id (UUID, FK to campaigns, CASCADE)
- signal_id (UUID, FK to signals, RESTRICT)
- pattern_type (VARCHAR(10): SPRING, SOS, LPS)
- bmad_allocation_pct (NUMERIC(5,4))
- target_risk_pct (NUMERIC(5,2))
- actual_risk_pct (NUMERIC(5,2))
- position_size_shares (NUMERIC(18,8))
- allocation_used (NUMERIC(5,2))
- remaining_budget (NUMERIC(5,2))
- is_rebalanced (BOOLEAN)
- rebalance_reason (TEXT, nullable)
- approved (BOOLEAN)
- rejection_reason (TEXT, nullable)
- timestamp (TIMESTAMPTZ)

Integration:
------------
- Story 9.2: Core repository for BMAD allocation audit trail
- Story 9.1: References Campaign model
- Story 8.8: References TradeSignal model
- SQLAlchemy 2.0+ async patterns

Author: Story 9.2
"""

from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.allocation import AllocationPlan

logger = structlog.get_logger(__name__)


class AllocationRepositoryError(Exception):
    """Base exception for allocation repository errors."""

    pass


class AllocationNotFoundError(AllocationRepositoryError):
    """Raised when allocation plan not found in database."""

    pass


class AllocationRepository:
    """
    Repository for allocation plan database operations.

    Provides async methods for persisting and querying AllocationPlan
    records for audit trail and campaign analysis.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Parameters
        ----------
        session : AsyncSession
            SQLAlchemy async session for database operations
        """
        self.session = session
        self.logger = logger.bind(component="AllocationRepository")

    async def save_allocation_plan(self, allocation_plan: AllocationPlan) -> AllocationPlan:
        """
        Persist allocation plan to database.

        Creates audit trail record for campaign allocation decision (approved or rejected).

        Parameters
        ----------
        allocation_plan : AllocationPlan
            Allocation plan to persist

        Returns
        -------
        AllocationPlan
            The persisted allocation plan (same as input)

        Raises
        ------
        AllocationRepositoryError
            If database insert fails

        Examples
        --------
        >>> plan = AllocationPlan(...)
        >>> saved_plan = await repo.save_allocation_plan(plan)
        >>> assert saved_plan.id == plan.id
        """
        try:
            # Insert allocation plan using raw SQL
            # (ORM model mapping would be in database migration)
            insert_sql = text(
                """
                INSERT INTO allocation_plans (
                    id, campaign_id, signal_id, pattern_type,
                    bmad_allocation_pct, target_risk_pct, actual_risk_pct,
                    position_size_shares, allocation_used, remaining_budget,
                    is_rebalanced, rebalance_reason, approved, rejection_reason,
                    timestamp
                ) VALUES (
                    :id, :campaign_id, :signal_id, :pattern_type,
                    :bmad_allocation_pct, :target_risk_pct, :actual_risk_pct,
                    :position_size_shares, :allocation_used, :remaining_budget,
                    :is_rebalanced, :rebalance_reason, :approved, :rejection_reason,
                    :timestamp
                )
                """
            )

            await self.session.execute(
                insert_sql,
                {
                    "id": allocation_plan.id,
                    "campaign_id": allocation_plan.campaign_id,
                    "signal_id": allocation_plan.signal_id,
                    "pattern_type": allocation_plan.pattern_type,
                    "bmad_allocation_pct": allocation_plan.bmad_allocation_pct,
                    "target_risk_pct": allocation_plan.target_risk_pct,
                    "actual_risk_pct": allocation_plan.actual_risk_pct,
                    "position_size_shares": allocation_plan.position_size_shares,
                    "allocation_used": allocation_plan.allocation_used,
                    "remaining_budget": allocation_plan.remaining_budget,
                    "is_rebalanced": allocation_plan.is_rebalanced,
                    "rebalance_reason": allocation_plan.rebalance_reason,
                    "approved": allocation_plan.approved,
                    "rejection_reason": allocation_plan.rejection_reason,
                    "timestamp": allocation_plan.timestamp,
                },
            )
            await self.session.commit()

            self.logger.info(
                "allocation_plan_saved",
                allocation_id=str(allocation_plan.id),
                campaign_id=str(allocation_plan.campaign_id),
                pattern_type=allocation_plan.pattern_type,
                approved=allocation_plan.approved,
            )

            return allocation_plan

        except Exception as e:
            await self.session.rollback()
            self.logger.error(
                "allocation_plan_save_failed",
                allocation_id=str(allocation_plan.id),
                error=str(e),
            )
            raise AllocationRepositoryError(f"Failed to save allocation plan: {e}") from e

    async def get_allocation_plans_by_campaign(self, campaign_id: UUID) -> list[AllocationPlan]:
        """
        Get all allocation plans for a campaign (audit trail).

        Returns allocation plans ordered by timestamp (chronological order)
        to show the sequence of allocation decisions.

        Parameters
        ----------
        campaign_id : UUID
            Campaign identifier

        Returns
        -------
        list[AllocationPlan]
            List of allocation plans ordered by timestamp (earliest first)

        Examples
        --------
        >>> plans = await repo.get_allocation_plans_by_campaign(campaign_id)
        >>> assert len(plans) == 3  # Spring, SOS, LPS
        >>> assert plans[0].pattern_type == "SPRING"
        >>> assert plans[1].pattern_type == "SOS"
        """
        try:
            query_sql = text(
                """
                SELECT
                    id, campaign_id, signal_id, pattern_type,
                    bmad_allocation_pct, target_risk_pct, actual_risk_pct,
                    position_size_shares, allocation_used, remaining_budget,
                    is_rebalanced, rebalance_reason, approved, rejection_reason,
                    timestamp
                FROM allocation_plans
                WHERE campaign_id = :campaign_id
                ORDER BY timestamp ASC
                """
            )

            result = await self.session.execute(query_sql, {"campaign_id": campaign_id})
            rows = result.fetchall()

            allocation_plans = []
            for row in rows:
                plan = AllocationPlan(
                    id=row[0],
                    campaign_id=row[1],
                    signal_id=row[2],
                    pattern_type=row[3],
                    bmad_allocation_pct=row[4],
                    target_risk_pct=row[5],
                    actual_risk_pct=row[6],
                    position_size_shares=row[7],
                    allocation_used=row[8],
                    remaining_budget=row[9],
                    is_rebalanced=row[10],
                    rebalance_reason=row[11],
                    approved=row[12],
                    rejection_reason=row[13],
                    timestamp=row[14],
                )
                allocation_plans.append(plan)

            self.logger.info(
                "allocation_plans_fetched",
                campaign_id=str(campaign_id),
                count=len(allocation_plans),
            )

            return allocation_plans

        except Exception as e:
            self.logger.error(
                "allocation_plans_fetch_failed",
                campaign_id=str(campaign_id),
                error=str(e),
            )
            raise AllocationRepositoryError(
                f"Failed to fetch allocation plans for campaign {campaign_id}: {e}"
            ) from e

    async def get_allocation_plan_by_id(self, allocation_id: UUID) -> Optional[AllocationPlan]:
        """
        Get single allocation plan by ID.

        Parameters
        ----------
        allocation_id : UUID
            Allocation plan identifier

        Returns
        -------
        Optional[AllocationPlan]
            Allocation plan if found, None otherwise

        Raises
        ------
        AllocationRepositoryError
            If database query fails
        """
        try:
            query_sql = text(
                """
                SELECT
                    id, campaign_id, signal_id, pattern_type,
                    bmad_allocation_pct, target_risk_pct, actual_risk_pct,
                    position_size_shares, allocation_used, remaining_budget,
                    is_rebalanced, rebalance_reason, approved, rejection_reason,
                    timestamp
                FROM allocation_plans
                WHERE id = :allocation_id
                """
            )

            result = await self.session.execute(query_sql, {"allocation_id": allocation_id})
            row = result.fetchone()

            if row is None:
                return None

            plan = AllocationPlan(
                id=row[0],
                campaign_id=row[1],
                signal_id=row[2],
                pattern_type=row[3],
                bmad_allocation_pct=row[4],
                target_risk_pct=row[5],
                actual_risk_pct=row[6],
                position_size_shares=row[7],
                allocation_used=row[8],
                remaining_budget=row[9],
                is_rebalanced=row[10],
                rebalance_reason=row[11],
                approved=row[12],
                rejection_reason=row[13],
                timestamp=row[14],
            )

            return plan

        except Exception as e:
            self.logger.error(
                "allocation_plan_fetch_failed",
                allocation_id=str(allocation_id),
                error=str(e),
            )
            raise AllocationRepositoryError(
                f"Failed to fetch allocation plan {allocation_id}: {e}"
            ) from e
