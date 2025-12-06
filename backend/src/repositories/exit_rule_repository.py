"""
Exit Rule Repository - Database Operations for Exit Management (Story 9.5)

Purpose:
--------
Provides repository layer for exit rule and exit order data access with CRUD
operations for managing campaign exit strategies, partial exits, and invalidation.

Key Methods:
------------
1. get_exit_rule: Fetch exit rule for campaign
2. create_exit_rule: Create new exit rule for campaign
3. update_exit_rule: Update exit rule with new percentages or targets
4. delete_exit_rule: Delete exit rule when campaign completed
5. create_exit_order: Persist triggered exit order
6. get_exit_orders_for_campaign: Fetch all exit orders for campaign

Database Schema:
----------------
Exit Rules Table:
- id (UUID, PK)
- campaign_id (UUID, FK to campaigns, UNIQUE)
- target_1_level, target_2_level, target_3_level (NUMERIC(18,8))
- t1_exit_pct, t2_exit_pct, t3_exit_pct (NUMERIC(5,2))
- trail_to_breakeven_on_t1, trail_to_t1_on_t2 (BOOLEAN)
- spring_low, ice_level, creek_level, utad_high, jump_target (NUMERIC(18,8))
- created_at, updated_at (TIMESTAMPTZ)

Exit Orders Table:
- id (UUID, PK)
- campaign_id (UUID, FK to campaigns)
- position_id (UUID, FK to positions)
- order_type (VARCHAR: PARTIAL_EXIT, STOP_LOSS, INVALIDATION)
- exit_level (NUMERIC(18,8))
- shares (INT)
- reason (TEXT)
- triggered_at (TIMESTAMPTZ)
- executed (BOOLEAN)
- created_at (TIMESTAMPTZ)

Integration:
------------
- Story 9.5: Core repository methods for exit management
- SQLAlchemy 2.0+ async patterns
- Efficient queries with indexes

Author: Story 9.5
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.campaign import ExitRule
from src.models.exit import ExitOrder
from src.repositories.models import ExitOrderModel, ExitRuleModel

logger = structlog.get_logger(__name__)


class ExitRuleNotFoundError(Exception):
    """Raised when exit rule is not found."""

    pass


class ExitRuleRepository:
    """
    Repository for exit rule and exit order database operations.

    Provides async methods for creating, reading, updating, and deleting
    exit rules and exit orders.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Parameters:
        -----------
        session : AsyncSession
            SQLAlchemy async session
        """
        self.session = session

    async def get_exit_rule(self, campaign_id: UUID) -> ExitRule | None:
        """
        Fetch exit rule for campaign (AC 10).

        Parameters:
        -----------
        campaign_id : UUID
            Campaign identifier

        Returns:
        --------
        ExitRule | None
            Exit rule or None if not found

        Example:
        --------
        >>> exit_rule = await repo.get_exit_rule(campaign_id)
        >>> if exit_rule:
        ...     print(f"T1: {exit_rule.target_1_level}")
        """
        stmt = select(ExitRuleModel).where(ExitRuleModel.campaign_id == campaign_id)
        result = await self.session.execute(stmt)
        exit_rule_model = result.scalar_one_or_none()

        if not exit_rule_model:
            logger.info("get_exit_rule.not_found", campaign_id=str(campaign_id))
            return None

        # Convert SQLAlchemy model to Pydantic model
        exit_rule = ExitRule(
            id=exit_rule_model.id,
            campaign_id=exit_rule_model.campaign_id,
            target_1_level=exit_rule_model.target_1_level,
            target_2_level=exit_rule_model.target_2_level,
            target_3_level=exit_rule_model.target_3_level,
            t1_exit_pct=exit_rule_model.t1_exit_pct,
            t2_exit_pct=exit_rule_model.t2_exit_pct,
            t3_exit_pct=exit_rule_model.t3_exit_pct,
            trail_to_breakeven_on_t1=exit_rule_model.trail_to_breakeven_on_t1,
            trail_to_t1_on_t2=exit_rule_model.trail_to_t1_on_t2,
            spring_low=exit_rule_model.spring_low,
            ice_level=exit_rule_model.ice_level,
            creek_level=exit_rule_model.creek_level,
            utad_high=exit_rule_model.utad_high,
            jump_target=exit_rule_model.jump_target,
            created_at=exit_rule_model.created_at,
            updated_at=exit_rule_model.updated_at,
        )

        logger.info("get_exit_rule.found", campaign_id=str(campaign_id))
        return exit_rule

    async def create_exit_rule(self, exit_rule: ExitRule) -> ExitRule:
        """
        Create new exit rule for campaign (AC 10).

        Parameters:
        -----------
        exit_rule : ExitRule
            Exit rule to create

        Returns:
        --------
        ExitRule
            Created exit rule with id

        Raises:
        -------
        IntegrityError
            If campaign_id already has exit rule (UNIQUE constraint)

        Example:
        --------
        >>> exit_rule = ExitRule(campaign_id=uuid4(), ...)
        >>> created = await repo.create_exit_rule(exit_rule)
        >>> print(f"Created exit rule {created.id}")
        """
        exit_rule_model = ExitRuleModel(
            id=exit_rule.id,
            campaign_id=exit_rule.campaign_id,
            target_1_level=exit_rule.target_1_level,
            target_2_level=exit_rule.target_2_level,
            target_3_level=exit_rule.target_3_level,
            t1_exit_pct=exit_rule.t1_exit_pct,
            t2_exit_pct=exit_rule.t2_exit_pct,
            t3_exit_pct=exit_rule.t3_exit_pct,
            trail_to_breakeven_on_t1=exit_rule.trail_to_breakeven_on_t1,
            trail_to_t1_on_t2=exit_rule.trail_to_t1_on_t2,
            spring_low=exit_rule.spring_low,
            ice_level=exit_rule.ice_level,
            creek_level=exit_rule.creek_level,
            utad_high=exit_rule.utad_high,
            jump_target=exit_rule.jump_target,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        self.session.add(exit_rule_model)
        await self.session.flush()

        logger.info(
            "create_exit_rule.success",
            campaign_id=str(exit_rule.campaign_id),
            exit_rule_id=str(exit_rule_model.id),
        )

        return exit_rule

    async def update_exit_rule(self, campaign_id: UUID, updates: dict[str, Any]) -> ExitRule:
        """
        Update exit rule with new values (AC 10).

        Parameters:
        -----------
        campaign_id : UUID
            Campaign identifier
        updates : dict[str, Any]
            Fields to update (e.g., {"t1_exit_pct": 40, "t2_exit_pct": 35})

        Returns:
        --------
        ExitRule
            Updated exit rule

        Raises:
        -------
        ExitRuleNotFoundError
            If exit rule not found for campaign

        Example:
        --------
        >>> updated = await repo.update_exit_rule(
        ...     campaign_id=uuid4(),
        ...     updates={"t1_exit_pct": Decimal("40.00"), "t2_exit_pct": Decimal("35.00")}
        ... )
        """
        # Add updated_at timestamp
        updates["updated_at"] = datetime.now(UTC)

        stmt = (
            update(ExitRuleModel)
            .where(ExitRuleModel.campaign_id == campaign_id)
            .values(**updates)
            .returning(ExitRuleModel)
        )

        result = await self.session.execute(stmt)
        updated_model = result.scalar_one_or_none()

        if not updated_model:
            raise ExitRuleNotFoundError(f"Exit rule not found for campaign {campaign_id}")

        await self.session.flush()

        logger.info(
            "update_exit_rule.success",
            campaign_id=str(campaign_id),
            updates=updates,
        )

        # Fetch and return updated exit rule
        return await self.get_exit_rule(campaign_id)  # type: ignore

    async def delete_exit_rule(self, campaign_id: UUID) -> bool:
        """
        Delete exit rule for campaign.

        Parameters:
        -----------
        campaign_id : UUID
            Campaign identifier

        Returns:
        --------
        bool
            True if deleted, False if not found

        Example:
        --------
        >>> deleted = await repo.delete_exit_rule(campaign_id)
        >>> if deleted:
        ...     print("Exit rule deleted")
        """
        stmt = delete(ExitRuleModel).where(ExitRuleModel.campaign_id == campaign_id)
        result = await self.session.execute(stmt)
        await self.session.flush()

        deleted = result.rowcount > 0  # type: ignore[attr-defined]

        if deleted:
            logger.info("delete_exit_rule.success", campaign_id=str(campaign_id))
        else:
            logger.warning("delete_exit_rule.not_found", campaign_id=str(campaign_id))

        return deleted

    async def create_exit_order(self, exit_order: ExitOrder) -> ExitOrder:
        """
        Create new exit order for position.

        Parameters:
        -----------
        exit_order : ExitOrder
            Exit order to create

        Returns:
        --------
        ExitOrder
            Created exit order with id

        Example:
        --------
        >>> exit_order = ExitOrder(
        ...     campaign_id=uuid4(),
        ...     position_id=uuid4(),
        ...     order_type="PARTIAL_EXIT",
        ...     exit_level=Decimal("160.00"),
        ...     shares=50,
        ...     reason="T1 target hit",
        ...     triggered_at=datetime.now(UTC)
        ... )
        >>> created = await repo.create_exit_order(exit_order)
        """
        exit_order_model = ExitOrderModel(
            id=exit_order.id,
            campaign_id=exit_order.campaign_id,
            position_id=exit_order.position_id,
            order_type=exit_order.order_type,
            exit_level=exit_order.exit_level,
            shares=exit_order.shares,
            reason=exit_order.reason,
            triggered_at=exit_order.triggered_at,
            executed=exit_order.executed,
            created_at=datetime.now(UTC),
        )

        self.session.add(exit_order_model)
        await self.session.flush()

        logger.info(
            "create_exit_order.success",
            campaign_id=str(exit_order.campaign_id),
            position_id=str(exit_order.position_id),
            order_type=exit_order.order_type,
            shares=exit_order.shares,
        )

        return exit_order

    async def get_exit_orders_for_campaign(
        self, campaign_id: UUID, limit: int = 100
    ) -> list[ExitOrder]:
        """
        Fetch all exit orders for campaign.

        Parameters:
        -----------
        campaign_id : UUID
            Campaign identifier
        limit : int
            Maximum number of orders to return (default 100)

        Returns:
        --------
        list[ExitOrder]
            List of exit orders ordered by triggered_at DESC

        Example:
        --------
        >>> exit_orders = await repo.get_exit_orders_for_campaign(campaign_id)
        >>> for order in exit_orders:
        ...     print(f"{order.order_type}: {order.shares} shares @ {order.exit_level}")
        """
        stmt = (
            select(ExitOrderModel)
            .where(ExitOrderModel.campaign_id == campaign_id)
            .order_by(ExitOrderModel.triggered_at.desc())
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        exit_order_models = result.scalars().all()

        exit_orders = [
            ExitOrder(
                id=model.id,
                campaign_id=model.campaign_id,
                position_id=model.position_id,
                order_type=model.order_type,
                exit_level=model.exit_level,
                shares=model.shares,
                reason=model.reason,
                triggered_at=model.triggered_at,
                executed=model.executed,
                created_at=model.created_at,
            )
            for model in exit_order_models
        ]

        logger.info(
            "get_exit_orders_for_campaign.success",
            campaign_id=str(campaign_id),
            orders_count=len(exit_orders),
        )

        return exit_orders
