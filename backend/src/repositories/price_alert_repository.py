"""
Price Alert Repository.

Async database operations for user price alerts.
Supports CRUD and active-alert queries.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import structlog
from sqlalchemy import and_, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.price_alert import (
    AlertDirection,
    AlertType,
    PriceAlert,
    PriceAlertCreate,
    PriceAlertUpdate,
    WyckoffLevelType,
)
from src.orm.models import PriceAlertORM

logger = structlog.get_logger(__name__)


class PriceAlertRepository:
    """Repository for price alert database operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, user_id: UUID, data: PriceAlertCreate) -> PriceAlert:
        """
        Create a new price alert for the user.

        Args:
            user_id: Authenticated user UUID
            data: Alert creation payload

        Returns:
            Created PriceAlert model
        """
        orm = PriceAlertORM(
            id=uuid4(),
            user_id=user_id,
            symbol=data.symbol.upper(),
            alert_type=data.alert_type.value,
            price_level=data.price_level,
            direction=data.direction.value if data.direction else None,
            wyckoff_level_type=data.wyckoff_level_type.value if data.wyckoff_level_type else None,
            is_active=True,
            notes=data.notes,
            created_at=datetime.now(UTC),
            triggered_at=None,
        )

        self.session.add(orm)
        await self.session.commit()
        await self.session.refresh(orm)

        logger.info(
            "price_alert_created",
            user_id=str(user_id),
            symbol=data.symbol.upper(),
            alert_type=data.alert_type.value,
        )

        return self._to_model(orm)

    async def list_for_user(
        self,
        user_id: UUID,
        active_only: bool = False,
    ) -> list[PriceAlert]:
        """
        List price alerts for the user.

        Args:
            user_id: Authenticated user UUID
            active_only: If True, only return active alerts

        Returns:
            List of PriceAlert models ordered by created_at desc
        """
        stmt = select(PriceAlertORM).where(PriceAlertORM.user_id == user_id)

        if active_only:
            stmt = stmt.where(PriceAlertORM.is_active.is_(True))

        stmt = stmt.order_by(PriceAlertORM.created_at.desc())

        result = await self.session.execute(stmt)
        rows = result.scalars().all()

        return [self._to_model(r) for r in rows]

    async def get(self, alert_id: UUID, user_id: UUID) -> PriceAlert | None:
        """
        Get a single price alert by ID, scoped to the user.

        Args:
            alert_id: Alert UUID
            user_id: Authenticated user UUID

        Returns:
            PriceAlert if found and owned by user, None otherwise
        """
        stmt = select(PriceAlertORM).where(
            and_(
                PriceAlertORM.id == alert_id,
                PriceAlertORM.user_id == user_id,
            )
        )

        result = await self.session.execute(stmt)
        orm = result.scalar_one_or_none()

        return self._to_model(orm) if orm else None

    async def update(
        self,
        alert_id: UUID,
        user_id: UUID,
        data: PriceAlertUpdate,
    ) -> PriceAlert | None:
        """
        Update a price alert owned by the user.

        Args:
            alert_id: Alert UUID
            user_id: Authenticated user UUID
            data: Partial update payload

        Returns:
            Updated PriceAlert if found, None otherwise
        """
        values: dict = {}

        if data.price_level is not None:
            values["price_level"] = data.price_level
        if data.direction is not None:
            values["direction"] = data.direction.value
        if data.wyckoff_level_type is not None:
            values["wyckoff_level_type"] = data.wyckoff_level_type.value
        if data.is_active is not None:
            values["is_active"] = data.is_active
        if data.notes is not None:
            values["notes"] = data.notes

        if not values:
            return await self.get(alert_id, user_id)

        stmt = (
            update(PriceAlertORM)
            .where(
                and_(
                    PriceAlertORM.id == alert_id,
                    PriceAlertORM.user_id == user_id,
                )
            )
            .values(**values)
        )

        result = await self.session.execute(stmt)
        await self.session.commit()

        if result.rowcount == 0:  # type: ignore[attr-defined]
            logger.warning(
                "price_alert_not_found_for_update",
                alert_id=str(alert_id),
                user_id=str(user_id),
            )
            return None

        logger.info(
            "price_alert_updated",
            alert_id=str(alert_id),
            user_id=str(user_id),
            fields=list(values.keys()),
        )

        return await self.get(alert_id, user_id)

    async def delete(self, alert_id: UUID, user_id: UUID) -> bool:
        """
        Delete a price alert owned by the user.

        Args:
            alert_id: Alert UUID
            user_id: Authenticated user UUID

        Returns:
            True if deleted, False if not found
        """
        stmt = delete(PriceAlertORM).where(
            and_(
                PriceAlertORM.id == alert_id,
                PriceAlertORM.user_id == user_id,
            )
        )

        result = await self.session.execute(stmt)
        await self.session.commit()

        deleted = result.rowcount > 0 if hasattr(result, "rowcount") else False  # type: ignore[attr-defined]

        if deleted:
            logger.info(
                "price_alert_deleted",
                alert_id=str(alert_id),
                user_id=str(user_id),
            )
        else:
            logger.warning(
                "price_alert_not_found_for_delete",
                alert_id=str(alert_id),
                user_id=str(user_id),
            )

        return deleted

    def _to_model(self, orm: PriceAlertORM) -> PriceAlert:
        """Convert ORM row to Pydantic model."""
        return PriceAlert(
            id=orm.id,
            user_id=orm.user_id,
            symbol=orm.symbol,
            alert_type=AlertType(orm.alert_type),
            price_level=orm.price_level,
            direction=AlertDirection(orm.direction) if orm.direction else None,
            wyckoff_level_type=WyckoffLevelType(orm.wyckoff_level_type)
            if orm.wyckoff_level_type
            else None,
            is_active=orm.is_active,
            notes=orm.notes,
            created_at=orm.created_at,
            triggered_at=orm.triggered_at,
        )
