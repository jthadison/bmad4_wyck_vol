"""
Audit Trail Repository (Task #2).

Provides async database operations for the audit_trail table:
- insert: Create new audit trail entries
- query: Retrieve entries with filtering and pagination
"""

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.audit_trail import AuditTrailCreate, AuditTrailEntry, AuditTrailQuery
from src.orm.audit_trail import AuditTrailORM

logger = structlog.get_logger()


class AuditTrailRepository:
    """Repository for audit trail database operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(self, entry: AuditTrailCreate) -> AuditTrailEntry:
        """
        Insert a new audit trail entry.

        Args:
            entry: Audit trail data to persist.

        Returns:
            The created audit trail entry with generated ID and timestamp.
        """
        orm_obj = AuditTrailORM(
            event_type=entry.event_type,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            actor=entry.actor,
            action=entry.action,
            correlation_id=entry.correlation_id,
            audit_metadata=entry.metadata,
        )
        self._session.add(orm_obj)
        await self._session.flush()

        logger.info(
            "audit_trail_entry_created",
            audit_id=str(orm_obj.id),
            event_type=entry.event_type,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            actor=entry.actor,
        )

        return AuditTrailEntry(
            id=orm_obj.id,
            event_type=orm_obj.event_type,
            entity_type=orm_obj.entity_type,
            entity_id=orm_obj.entity_id,
            actor=orm_obj.actor,
            action=orm_obj.action,
            correlation_id=orm_obj.correlation_id,
            metadata=orm_obj.audit_metadata,
            created_at=orm_obj.created_at,
        )

    async def query(self, params: AuditTrailQuery) -> tuple[list[AuditTrailEntry], int]:
        """
        Query audit trail with filtering and pagination.

        Args:
            params: Query filters and pagination parameters.

        Returns:
            Tuple of (entries, total_count).
        """
        base_query = select(AuditTrailORM)
        count_query = select(func.count()).select_from(AuditTrailORM)

        # Apply filters
        if params.event_type:
            base_query = base_query.where(AuditTrailORM.event_type == params.event_type)
            count_query = count_query.where(AuditTrailORM.event_type == params.event_type)

        if params.entity_type:
            base_query = base_query.where(AuditTrailORM.entity_type == params.entity_type)
            count_query = count_query.where(AuditTrailORM.entity_type == params.entity_type)

        if params.entity_id:
            base_query = base_query.where(AuditTrailORM.entity_id == params.entity_id)
            count_query = count_query.where(AuditTrailORM.entity_id == params.entity_id)

        if params.actor:
            base_query = base_query.where(AuditTrailORM.actor == params.actor)
            count_query = count_query.where(AuditTrailORM.actor == params.actor)

        if params.correlation_id:
            base_query = base_query.where(AuditTrailORM.correlation_id == params.correlation_id)
            count_query = count_query.where(
                AuditTrailORM.correlation_id == params.correlation_id
            )

        if params.start_date:
            base_query = base_query.where(AuditTrailORM.created_at >= params.start_date)
            count_query = count_query.where(AuditTrailORM.created_at >= params.start_date)

        if params.end_date:
            base_query = base_query.where(AuditTrailORM.created_at <= params.end_date)
            count_query = count_query.where(AuditTrailORM.created_at <= params.end_date)

        # Order by most recent first
        base_query = base_query.order_by(AuditTrailORM.created_at.desc())

        # Pagination
        base_query = base_query.offset(params.offset).limit(params.limit)

        # Execute
        result = await self._session.execute(base_query)
        count_result = await self._session.execute(count_query)

        rows = result.scalars().all()
        total_count = count_result.scalar() or 0

        entries = [
            AuditTrailEntry(
                id=row.id,
                event_type=row.event_type,
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                actor=row.actor,
                action=row.action,
                correlation_id=row.correlation_id,
                metadata=row.audit_metadata,
                created_at=row.created_at,
            )
            for row in rows
        ]

        return entries, total_count
