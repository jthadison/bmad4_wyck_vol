"""
Signal Approval Repository (Story 19.9)

Repository for signal approval queue database operations.

Author: Story 19.9
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.signal_approval import QueueEntryStatus, SignalQueueEntry
from src.orm.models import SignalApprovalQueueORM

logger = structlog.get_logger(__name__)


class SignalApprovalRepository:
    """
    Repository for signal approval queue operations.

    Provides CRUD and query operations for the signal_approval_queue table.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: Async SQLAlchemy session
        """
        self.session = session

    async def create(self, entry: SignalQueueEntry) -> SignalQueueEntry:
        """
        Create a new queue entry.

        Args:
            entry: SignalQueueEntry to create

        Returns:
            Created SignalQueueEntry with populated ID
        """
        orm_entry = SignalApprovalQueueORM(
            id=entry.id,
            signal_id=entry.signal_id,
            user_id=entry.user_id,
            status=entry.status.value,
            submitted_at=entry.submitted_at,
            expires_at=entry.expires_at,
            approved_at=entry.approved_at,
            approved_by=entry.approved_by,
            rejection_reason=entry.rejection_reason,
            signal_snapshot=entry.signal_snapshot,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        )

        self.session.add(orm_entry)
        await self.session.commit()
        await self.session.refresh(orm_entry)

        logger.info(
            "signal_queue_entry_created",
            queue_id=str(orm_entry.id),
            signal_id=str(entry.signal_id),
            user_id=str(entry.user_id),
            expires_at=entry.expires_at.isoformat(),
        )

        return self._to_model(orm_entry)

    async def get_by_id(self, queue_id: UUID) -> SignalQueueEntry | None:
        """
        Get queue entry by ID.

        Args:
            queue_id: Queue entry UUID

        Returns:
            SignalQueueEntry if found, None otherwise
        """
        stmt = select(SignalApprovalQueueORM).where(SignalApprovalQueueORM.id == queue_id)
        result = await self.session.execute(stmt)
        orm_entry = result.scalars().first()

        if not orm_entry:
            logger.debug("signal_queue_entry_not_found", queue_id=str(queue_id))
            return None

        return self._to_model(orm_entry)

    async def get_pending_by_user(self, user_id: UUID, limit: int = 50) -> list[SignalQueueEntry]:
        """
        Get all pending queue entries for a user.

        Args:
            user_id: User UUID
            limit: Maximum entries to return

        Returns:
            List of pending SignalQueueEntry objects
        """
        stmt = (
            select(SignalApprovalQueueORM)
            .where(
                SignalApprovalQueueORM.user_id == user_id,
                SignalApprovalQueueORM.status == QueueEntryStatus.PENDING.value,
            )
            .order_by(SignalApprovalQueueORM.submitted_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        orm_entries = result.scalars().all()

        return [self._to_model(e) for e in orm_entries]

    async def count_pending_by_user(self, user_id: UUID) -> int:
        """
        Count pending queue entries for a user.

        Args:
            user_id: User UUID

        Returns:
            Number of pending entries
        """
        from sqlalchemy import func

        stmt = select(func.count(SignalApprovalQueueORM.id)).where(
            SignalApprovalQueueORM.user_id == user_id,
            SignalApprovalQueueORM.status == QueueEntryStatus.PENDING.value,
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_oldest_pending_by_user(self, user_id: UUID) -> SignalQueueEntry | None:
        """
        Get the oldest pending entry for a user (for queue overflow handling).

        Args:
            user_id: User UUID

        Returns:
            Oldest pending SignalQueueEntry or None
        """
        stmt = (
            select(SignalApprovalQueueORM)
            .where(
                SignalApprovalQueueORM.user_id == user_id,
                SignalApprovalQueueORM.status == QueueEntryStatus.PENDING.value,
            )
            .order_by(SignalApprovalQueueORM.submitted_at.asc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        orm_entry = result.scalars().first()

        return self._to_model(orm_entry) if orm_entry else None

    async def update_status(
        self,
        queue_id: UUID,
        new_status: QueueEntryStatus,
        approved_by: UUID | None = None,
        rejection_reason: str | None = None,
    ) -> SignalQueueEntry | None:
        """
        Update queue entry status.

        Handles optimistic locking to prevent race conditions.

        Args:
            queue_id: Queue entry UUID
            new_status: New status value
            approved_by: UUID of approver (for approved status)
            rejection_reason: Reason for rejection (for rejected status)

        Returns:
            Updated SignalQueueEntry or None if not found/already processed
        """
        now = datetime.now(UTC)

        update_values: dict[str, Any] = {
            "status": new_status.value,
            "updated_at": now,
        }

        if new_status == QueueEntryStatus.APPROVED:
            update_values["approved_at"] = now
            update_values["approved_by"] = approved_by
        elif new_status == QueueEntryStatus.REJECTED:
            update_values["rejection_reason"] = rejection_reason

        # Only update if currently pending (prevents race conditions)
        stmt = (
            update(SignalApprovalQueueORM)
            .where(
                SignalApprovalQueueORM.id == queue_id,
                SignalApprovalQueueORM.status == QueueEntryStatus.PENDING.value,
            )
            .values(**update_values)
            .returning(SignalApprovalQueueORM)
        )

        result = await self.session.execute(stmt)
        await self.session.commit()
        orm_entry = result.scalars().first()

        if not orm_entry:
            logger.warning(
                "signal_queue_update_failed",
                queue_id=str(queue_id),
                reason="not_found_or_already_processed",
            )
            return None

        logger.info(
            "signal_queue_status_updated",
            queue_id=str(queue_id),
            new_status=new_status.value,
        )

        return self._to_model(orm_entry)

    async def expire_stale_entries(self) -> int:
        """
        Mark all expired pending entries as expired.

        Returns:
            Number of entries expired
        """
        now = datetime.now(UTC)

        stmt = (
            update(SignalApprovalQueueORM)
            .where(
                SignalApprovalQueueORM.status == QueueEntryStatus.PENDING.value,
                SignalApprovalQueueORM.expires_at <= now,
            )
            .values(
                status=QueueEntryStatus.EXPIRED.value,
                updated_at=now,
            )
        )

        result = await self.session.execute(stmt)
        await self.session.commit()

        expired_count = result.rowcount if result.rowcount else 0  # type: ignore[attr-defined]
        if expired_count > 0:
            logger.info("signal_queue_entries_expired", count=expired_count)

        return expired_count

    async def get_by_signal_id(self, signal_id: UUID, user_id: UUID) -> SignalQueueEntry | None:
        """
        Get queue entry by signal ID for a user.

        Args:
            signal_id: Signal UUID
            user_id: User UUID

        Returns:
            SignalQueueEntry if found, None otherwise
        """
        stmt = (
            select(SignalApprovalQueueORM)
            .where(
                SignalApprovalQueueORM.signal_id == signal_id,
                SignalApprovalQueueORM.user_id == user_id,
            )
            .order_by(SignalApprovalQueueORM.submitted_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        orm_entry = result.scalars().first()

        return self._to_model(orm_entry) if orm_entry else None

    def _to_model(self, orm_entry: SignalApprovalQueueORM) -> SignalQueueEntry:
        """
        Convert ORM model to Pydantic model.

        Args:
            orm_entry: SQLAlchemy ORM model

        Returns:
            SignalQueueEntry Pydantic model
        """
        return SignalQueueEntry(
            id=orm_entry.id,
            signal_id=orm_entry.signal_id,
            user_id=orm_entry.user_id,
            status=QueueEntryStatus(orm_entry.status),
            submitted_at=orm_entry.submitted_at,
            expires_at=orm_entry.expires_at,
            approved_at=orm_entry.approved_at,
            approved_by=orm_entry.approved_by,
            rejection_reason=orm_entry.rejection_reason,
            signal_snapshot=orm_entry.signal_snapshot,
            created_at=orm_entry.created_at,
            updated_at=orm_entry.updated_at,
        )
