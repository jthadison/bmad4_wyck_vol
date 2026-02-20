"""
Journal Repository - Async CRUD for Trade Journal Entries

Provides data access methods for the JournalEntryModel with user isolation,
pagination, and filtering.

Author: Feature P2-8 (Trade Journal)
"""

from datetime import datetime
from uuid import UUID, uuid4

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.journal import JournalEntryModel

logger = structlog.get_logger(__name__)


class JournalRepository:
    """Repository for journal entry CRUD operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        user_id: UUID,
        symbol: str,
        entry_type: str,
        notes: str | None,
        campaign_id: UUID | None,
        signal_id: UUID | None,
        emotional_state: str | None,
        wyckoff_checklist: dict | None,
    ) -> JournalEntryModel:
        """Create a new journal entry."""
        entry = JournalEntryModel(
            id=uuid4(),
            user_id=user_id,
            symbol=symbol.upper(),
            entry_type=entry_type,
            notes=notes,
            campaign_id=campaign_id,
            signal_id=signal_id,
            emotional_state=emotional_state,
            wyckoff_checklist=wyckoff_checklist
            or {
                "phase_confirmed": False,
                "volume_confirmed": False,
                "creek_identified": False,
                "pattern_confirmed": False,
            },
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(entry)
        await self.db.flush()
        await self.db.refresh(entry)
        logger.info("journal_entry_created", entry_id=str(entry.id), user_id=str(user_id))
        return entry

    async def get_by_id(self, entry_id: UUID, user_id: UUID) -> JournalEntryModel | None:
        """Fetch a single journal entry by ID, enforcing user isolation."""
        result = await self.db.execute(
            select(JournalEntryModel).where(
                and_(
                    JournalEntryModel.id == entry_id,
                    JournalEntryModel.user_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_entries(
        self,
        user_id: UUID,
        symbol: str | None = None,
        entry_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[JournalEntryModel], int]:
        """
        List journal entries with optional filtering and pagination.

        Returns (entries, total_count).
        """
        filters = [JournalEntryModel.user_id == user_id]

        if symbol:
            filters.append(JournalEntryModel.symbol == symbol.upper())

        if entry_type:
            filters.append(JournalEntryModel.entry_type == entry_type)

        # Count total
        from sqlalchemy import func

        count_result = await self.db.execute(
            select(func.count()).select_from(JournalEntryModel).where(and_(*filters))
        )
        total_count = count_result.scalar_one()

        # Fetch page
        result = await self.db.execute(
            select(JournalEntryModel)
            .where(and_(*filters))
            .order_by(JournalEntryModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        entries = list(result.scalars().all())

        return entries, total_count

    async def list_by_campaign(self, campaign_id: UUID, user_id: UUID) -> list[JournalEntryModel]:
        """Fetch all journal entries linked to a campaign."""
        result = await self.db.execute(
            select(JournalEntryModel)
            .where(
                and_(
                    JournalEntryModel.campaign_id == campaign_id,
                    JournalEntryModel.user_id == user_id,
                )
            )
            .order_by(JournalEntryModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(
        self,
        entry: JournalEntryModel,
        symbol: str | None = None,
        entry_type: str | None = None,
        notes: str | None = None,
        emotional_state: str | None = None,
        wyckoff_checklist: dict | None = None,
    ) -> JournalEntryModel:
        """Update fields on an existing journal entry."""
        if symbol is not None:
            entry.symbol = symbol.upper()
        if entry_type is not None:
            entry.entry_type = entry_type
        if notes is not None:
            entry.notes = notes
        if emotional_state is not None:
            entry.emotional_state = emotional_state
        if wyckoff_checklist is not None:
            entry.wyckoff_checklist = wyckoff_checklist
        entry.updated_at = datetime.utcnow()

        await self.db.flush()
        await self.db.refresh(entry)
        logger.info("journal_entry_updated", entry_id=str(entry.id))
        return entry

    async def delete(self, entry: JournalEntryModel) -> None:
        """Delete a journal entry."""
        await self.db.delete(entry)
        await self.db.flush()
        logger.info("journal_entry_deleted", entry_id=str(entry.id))
