"""
Paper Session Repository (Story 23.8a)

Repository for archiving and retrieving paper trading sessions.
"""

from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.paper_trading import PaperAccount, PaperTrade
from src.repositories.paper_trading_orm import PaperTradingSessionDB

logger = structlog.get_logger(__name__)


class PaperSessionRepository:
    """Repository for paper trading session archive operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def archive_session(
        self,
        account: PaperAccount,
        trades: list[PaperTrade],
        metrics: dict,
    ) -> UUID:
        """Archive a paper trading session. Returns session ID."""
        now = datetime.now(UTC)

        session_db = PaperTradingSessionDB(
            account_snapshot=account.model_dump(mode="json"),
            trades_snapshot=[t.model_dump(mode="json") for t in trades],
            final_metrics=metrics,
            session_start=account.paper_trading_start_date or account.created_at,
            session_end=now,
            archived_at=now,
        )

        self.session.add(session_db)
        await self.session.commit()
        await self.session.refresh(session_db)

        logger.info(
            "paper_session_archived",
            session_id=str(session_db.id),
            total_trades=len(trades),
        )

        return session_db.id

    async def get_session(self, session_id: UUID) -> dict | None:
        """Retrieve an archived session by ID."""
        stmt = select(PaperTradingSessionDB).where(PaperTradingSessionDB.id == session_id)
        result = await self.session.execute(stmt)
        session_db = result.scalars().first()

        if not session_db:
            return None

        return self._to_dict(session_db)

    async def list_sessions(self, limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
        """List archived sessions with pagination. Returns (sessions, total_count)."""
        count_stmt = select(func.count()).select_from(PaperTradingSessionDB)
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        stmt = (
            select(PaperTradingSessionDB)
            .order_by(PaperTradingSessionDB.archived_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        sessions_db = result.scalars().all()

        return [self._to_dict(s) for s in sessions_db], total

    def _to_dict(self, session_db: PaperTradingSessionDB) -> dict:
        """Convert ORM model to dict."""
        return {
            "id": str(session_db.id),
            "account_snapshot": session_db.account_snapshot,
            "trades_snapshot": session_db.trades_snapshot,
            "final_metrics": session_db.final_metrics,
            "session_start": session_db.session_start.isoformat(),
            "session_end": session_db.session_end.isoformat(),
            "archived_at": session_db.archived_at.isoformat(),
        }
