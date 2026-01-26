"""
Signal Audit Repository (Story 19.11)

Repository for signal audit trail database operations.
Handles creating audit log entries and querying signal history.

Author: Story 19.11
"""

from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.signal_audit import (
    PaginationMetadata,
    SignalAuditLogEntry,
    SignalHistoryItem,
    SignalHistoryQuery,
    SignalHistoryResponse,
    TradeOutcome,
    ValidationResults,
)
from src.orm.models import Signal, SignalAuditLogORM

logger = structlog.get_logger(__name__)


class SignalAuditRepository:
    """
    Repository for signal audit trail operations.

    Provides operations for:
    - Creating audit log entries
    - Querying signal history with filters
    - Retrieving audit trail for specific signals
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: Async SQLAlchemy session
        """
        self.session = session

    async def create_audit_entry(self, entry: SignalAuditLogEntry) -> SignalAuditLogEntry:
        """
        Create a new audit log entry.

        Args:
            entry: SignalAuditLogEntry to create

        Returns:
            Created SignalAuditLogEntry with populated ID
        """
        orm_entry = SignalAuditLogORM(
            id=entry.id,
            signal_id=entry.signal_id,
            user_id=entry.user_id,
            previous_state=entry.previous_state,
            new_state=entry.new_state,
            transition_reason=entry.transition_reason,
            transition_metadata=entry.metadata,
            created_at=entry.created_at,
        )

        self.session.add(orm_entry)
        await self.session.commit()
        await self.session.refresh(orm_entry)

        logger.info(
            "audit_entry_created",
            entry_id=str(orm_entry.id),
            signal_id=str(entry.signal_id),
            state_transition=f"{entry.previous_state} -> {entry.new_state}",
        )

        return self._audit_entry_to_model(orm_entry)

    async def get_signal_audit_trail(self, signal_id: UUID) -> list[SignalAuditLogEntry]:
        """
        Get complete audit trail for a signal.

        Args:
            signal_id: Signal UUID

        Returns:
            List of audit entries in chronological order
        """
        stmt = (
            select(SignalAuditLogORM)
            .where(SignalAuditLogORM.signal_id == signal_id)
            .order_by(SignalAuditLogORM.created_at.asc())
        )
        result = await self.session.execute(stmt)
        orm_entries = result.scalars().all()

        logger.debug(
            "audit_trail_retrieved", signal_id=str(signal_id), entry_count=len(orm_entries)
        )

        return [self._audit_entry_to_model(e) for e in orm_entries]

    async def get_audit_trails_for_signals(
        self, signal_ids: list[UUID]
    ) -> dict[UUID, list[SignalAuditLogEntry]]:
        """
        Get audit trails for multiple signals in a single query (batch loading).

        Args:
            signal_ids: List of signal UUIDs

        Returns:
            Dictionary mapping signal_id to list of audit entries
        """
        if not signal_ids:
            return {}

        stmt = (
            select(SignalAuditLogORM)
            .where(SignalAuditLogORM.signal_id.in_(signal_ids))
            .order_by(SignalAuditLogORM.signal_id, SignalAuditLogORM.created_at.asc())
        )
        result = await self.session.execute(stmt)
        orm_entries = result.scalars().all()

        # Group entries by signal_id
        trails_by_signal: dict[UUID, list[SignalAuditLogEntry]] = {}
        for orm_entry in orm_entries:
            signal_id = orm_entry.signal_id
            if signal_id not in trails_by_signal:
                trails_by_signal[signal_id] = []
            trails_by_signal[signal_id].append(self._audit_entry_to_model(orm_entry))

        logger.debug(
            "audit_trails_batch_retrieved",
            signal_count=len(signal_ids),
            entry_count=len(orm_entries),
        )

        return trails_by_signal

    async def query_signal_history(self, query: SignalHistoryQuery) -> SignalHistoryResponse:
        """
        Query signal history with filters and pagination.

        Args:
            query: SignalHistoryQuery with filters

        Returns:
            SignalHistoryResponse with signals and pagination metadata
        """
        # Build base query
        stmt = select(Signal)

        # Apply filters
        filters = []

        if query.start_date:
            filters.append(Signal.created_at >= query.start_date)

        if query.end_date:
            filters.append(Signal.created_at <= query.end_date)

        if query.symbol:
            filters.append(Signal.symbol == query.symbol)

        if query.pattern_type:
            # Pattern type might be in signal_type or pattern relationship
            filters.append(Signal.signal_type == query.pattern_type)

        if query.status:
            filters.append(Signal.lifecycle_state == query.status)

        if filters:
            stmt = stmt.where(and_(*filters))

        # Count total matching items
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total_items = total_result.scalar() or 0

        # Calculate pagination
        total_pages = (total_items + query.page_size - 1) // query.page_size
        offset = (query.page - 1) * query.page_size

        # Apply ordering and pagination
        stmt = stmt.order_by(Signal.created_at.desc()).offset(offset).limit(query.page_size)

        # Execute query
        result = await self.session.execute(stmt)
        signals = result.scalars().all()

        # Batch-load audit trails for all signals (fixes N+1 query problem)
        signal_ids = [signal.id for signal in signals]
        audit_trails_map = await self.get_audit_trails_for_signals(signal_ids)

        # Build history items
        history_items = []
        for signal in signals:
            # Get audit trail from batch-loaded map
            audit_trail = audit_trails_map.get(signal.id, [])

            # Parse validation results and trade outcome
            validation_results = None
            if signal.validation_results:
                try:
                    validation_results = ValidationResults(**signal.validation_results)
                except Exception as e:
                    logger.warning(
                        "failed_to_parse_validation_results",
                        signal_id=str(signal.id),
                        error=str(e),
                    )

            trade_outcome = None
            if signal.trade_outcome:
                try:
                    trade_outcome = TradeOutcome(**signal.trade_outcome)
                except Exception as e:
                    logger.warning(
                        "failed_to_parse_trade_outcome",
                        signal_id=str(signal.id),
                        error=str(e),
                    )

            history_item = SignalHistoryItem(
                signal_id=signal.id,
                symbol=signal.symbol,
                pattern_type=signal.signal_type,
                confidence_score=float(signal.confidence_score),
                lifecycle_state=signal.lifecycle_state,
                created_at=signal.created_at,
                validation_results=validation_results,
                trade_outcome=trade_outcome,
                audit_trail=audit_trail,
            )
            history_items.append(history_item)

        # Build pagination metadata
        pagination = PaginationMetadata(
            page=query.page,
            page_size=query.page_size,
            total_items=total_items,
            total_pages=total_pages,
        )

        logger.info(
            "signal_history_queried",
            page=query.page,
            page_size=query.page_size,
            total_items=total_items,
            filters={
                "start_date": query.start_date.isoformat() if query.start_date else None,
                "end_date": query.end_date.isoformat() if query.end_date else None,
                "symbol": query.symbol,
                "pattern_type": query.pattern_type,
                "status": query.status,
            },
        )

        return SignalHistoryResponse(signals=history_items, pagination=pagination)

    async def update_signal_lifecycle_state(self, signal_id: UUID, new_state: str) -> None:
        """
        Update signal lifecycle state.

        Args:
            signal_id: Signal UUID
            new_state: New lifecycle state
        """
        from sqlalchemy import update as sql_update

        stmt = (
            sql_update(Signal)
            .where(Signal.id == signal_id)
            .values(lifecycle_state=new_state, updated_at=datetime.now(UTC))
        )

        await self.session.execute(stmt)
        await self.session.commit()

        logger.info(
            "signal_lifecycle_state_updated",
            signal_id=str(signal_id),
            new_state=new_state,
        )

    async def update_signal_validation_results(
        self, signal_id: UUID, validation_results: dict
    ) -> None:
        """
        Update signal validation results.

        Args:
            signal_id: Signal UUID
            validation_results: Validation results dictionary
        """
        from sqlalchemy import update as sql_update

        stmt = (
            sql_update(Signal)
            .where(Signal.id == signal_id)
            .values(validation_results=validation_results, updated_at=datetime.now(UTC))
        )

        await self.session.execute(stmt)
        await self.session.commit()

        logger.info(
            "signal_validation_results_updated",
            signal_id=str(signal_id),
        )

    async def update_signal_trade_outcome(self, signal_id: UUID, trade_outcome: dict) -> None:
        """
        Update signal trade outcome.

        Args:
            signal_id: Signal UUID
            trade_outcome: Trade outcome dictionary
        """
        from sqlalchemy import update as sql_update

        stmt = (
            sql_update(Signal)
            .where(Signal.id == signal_id)
            .values(trade_outcome=trade_outcome, updated_at=datetime.now(UTC))
        )

        await self.session.execute(stmt)
        await self.session.commit()

        logger.info(
            "signal_trade_outcome_updated",
            signal_id=str(signal_id),
        )

    def _audit_entry_to_model(self, orm_entry: SignalAuditLogORM) -> SignalAuditLogEntry:
        """
        Convert ORM audit entry to Pydantic model.

        Args:
            orm_entry: SignalAuditLogORM instance

        Returns:
            SignalAuditLogEntry model
        """
        return SignalAuditLogEntry(
            id=orm_entry.id,
            signal_id=orm_entry.signal_id,
            user_id=orm_entry.user_id,
            previous_state=orm_entry.previous_state,
            new_state=orm_entry.new_state,
            transition_reason=orm_entry.transition_reason,
            metadata=orm_entry.transition_metadata,
            created_at=orm_entry.created_at,
        )
