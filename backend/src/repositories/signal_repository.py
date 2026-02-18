"""
Signal Repository - TradeSignal Persistence (Story 8.10)

Purpose:
--------
Repository for persisting and querying TradeSignal objects.

Features:
---------
- Save approved signals to PostgreSQL
- Query signals by symbol, date range, status
- Update signal status (FILLED, STOPPED, TARGET_HIT, etc.)
- In-memory cache for fast lookups

Integration:
------------
- Story 8.8: TradeSignal model
- Story 8.10: MasterOrchestrator persistence

Author: Story 8.10
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.signal import TradeSignal
from src.orm.models import Signal as TradeSignalModel


class SignalRepository:
    """
    Repository for TradeSignal persistence.

    Provides methods to save and query trade signals.
    When a db_session is provided, signals are persisted to PostgreSQL.
    Falls back to in-memory storage when no session is available.
    """

    def __init__(self, db_session: AsyncSession | None = None):
        """
        Initialize repository with database session.

        Args:
            db_session: SQLAlchemy async session (optional for backwards compat)
        """
        self.db_session = db_session
        self.logger = structlog.get_logger(__name__)
        # In-memory cache (also serves as fallback when no DB session)
        self._signals: dict[UUID, TradeSignal] = {}

    def _signal_to_model(self, signal: TradeSignal) -> TradeSignalModel:
        """Convert a Pydantic TradeSignal to an ORM model for insertion."""
        # Serialize the validation chain for the approval_chain JSONB column
        approval_chain: dict[str, Any] = {}
        if signal.validation_chain:
            approval_chain = signal.validation_chain.model_dump(mode="json")

        # Safely convert campaign_id to UUID (may be a human-readable string like "AAPL-2024-03-13-C")
        campaign_uuid = None
        if signal.campaign_id:
            try:
                campaign_uuid = UUID(signal.campaign_id)
            except ValueError:
                # campaign_id is a human-readable string, not a UUID — store as None in FK column
                campaign_uuid = None

        return TradeSignalModel(
            id=signal.id,
            signal_type=signal.direction,
            pattern_type=signal.pattern_type,
            phase=signal.phase,
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            generated_at=signal.timestamp,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            target_1=signal.target_levels.primary_target,
            target_2=(
                signal.target_levels.secondary_targets[0]
                if signal.target_levels.secondary_targets
                else signal.target_levels.primary_target
            ),
            position_size=signal.position_size,
            risk_amount=signal.risk_amount,
            r_multiple=signal.r_multiple,
            confidence_score=signal.confidence_score,
            campaign_id=campaign_uuid,
            status=signal.status,
            approval_chain=approval_chain,
            validation_results=None,
            lifecycle_state=signal.status.lower() if signal.status else "generated",
            created_at=signal.created_at or datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    async def save_signal(self, signal: TradeSignal) -> TradeSignal:
        """
        Persist a TradeSignal to the database.

        Args:
            signal: TradeSignal to save

        Returns:
            Saved TradeSignal with populated ID
        """
        self.logger.info(
            "save_signal",
            signal_id=str(signal.id),
            symbol=signal.symbol,
            pattern_type=signal.pattern_type,
        )

        # Always cache in memory for fast lookups
        self._signals[signal.id] = signal

        # Persist to PostgreSQL if session is available
        if self.db_session is not None:
            try:
                model = self._signal_to_model(signal)
                self.db_session.add(model)
                await self.db_session.commit()
                self.logger.info(
                    "signal_persisted",
                    signal_id=str(signal.id),
                    symbol=signal.symbol,
                )
            except Exception as e:
                await self.db_session.rollback()
                self.logger.error(
                    "signal_persist_failed",
                    signal_id=str(signal.id),
                    error=str(e),
                )
                raise

        return signal

    async def get_signal_by_id(self, signal_id: UUID) -> TradeSignal | None:
        """
        Retrieve signal by ID.

        Args:
            signal_id: Signal UUID

        Returns:
            TradeSignal if found, None otherwise
        """
        # Check in-memory cache first
        cached = self._signals.get(signal_id)
        if cached is not None:
            return cached

        # Fall back to database
        if self.db_session is not None:
            stmt = select(TradeSignalModel).where(TradeSignalModel.id == signal_id)
            result = await self.db_session.execute(stmt)
            model = result.scalar_one_or_none()
            if model is not None:
                return self._model_to_signal(model)

        return None

    async def get_signals_by_symbol(
        self,
        symbol: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        status: str | None = None,
        limit: int = 500,
    ) -> list[TradeSignal]:
        """
        Query signals by symbol with optional filters.

        Args:
            symbol: Trading symbol
            start_date: Filter by timestamp >= start_date
            end_date: Filter by timestamp <= end_date
            status: Filter by signal status
            limit: Maximum number of signals to return (default 500)

        Returns:
            List of matching TradeSignals
        """
        # Try database first if available
        if self.db_session is not None:
            conditions = [TradeSignalModel.symbol == symbol]
            if start_date:
                conditions.append(TradeSignalModel.generated_at >= start_date)
            if end_date:
                conditions.append(TradeSignalModel.generated_at <= end_date)
            if status:
                conditions.append(TradeSignalModel.status == status)

            stmt = (
                select(TradeSignalModel)
                .where(and_(*conditions))
                .order_by(TradeSignalModel.generated_at.desc())
                .limit(limit)
            )
            result = await self.db_session.execute(stmt)
            models = result.scalars().all()
            return [self._model_to_signal(m) for m in models]

        # Fall back to in-memory
        signals = [s for s in self._signals.values() if s.symbol == symbol]
        if start_date:
            signals = [s for s in signals if s.timestamp >= start_date]
        if end_date:
            signals = [s for s in signals if s.timestamp <= end_date]
        if status:
            signals = [s for s in signals if s.status == status]
        return signals[:limit]

    async def update_signal_status(
        self,
        signal_id: UUID,
        new_status: str,
    ) -> TradeSignal | None:
        """
        Update signal status (e.g., PENDING -> FILLED).

        Args:
            signal_id: Signal UUID
            new_status: New status value

        Returns:
            Updated TradeSignal if found, None otherwise
        """
        # Update in database if available
        if self.db_session is not None:
            stmt = select(TradeSignalModel).where(TradeSignalModel.id == signal_id)
            result = await self.db_session.execute(stmt)
            model = result.scalar_one_or_none()
            if model is not None:
                model.status = new_status
                model.updated_at = datetime.now(UTC)
                await self.db_session.commit()
                # Update cache
                updated = self._model_to_signal(model)
                self._signals[signal_id] = updated
                return updated
            return None

        # Fall back to in-memory
        signal = self._signals.get(signal_id)
        if signal:
            updated_data = signal.model_dump()
            updated_data["status"] = new_status
            updated_signal = TradeSignal(**updated_data)
            self._signals[signal_id] = updated_signal
            return updated_signal
        return None

    async def get_all_signals(
        self,
        limit: int = 100,
        status: str | None = None,
        since: datetime | None = None,
    ) -> list[TradeSignal]:
        """
        Get all signals with optional SQL-level filters.

        Args:
            limit: Maximum number of signals to return
            status: Filter by signal status (applied at SQL level)
            since: Filter by generated_at >= since (applied at SQL level)

        Returns:
            List of TradeSignals
        """
        if self.db_session is not None:
            conditions = []
            if status:
                conditions.append(TradeSignalModel.status == status)
            if since:
                conditions.append(TradeSignalModel.generated_at >= since)

            stmt = select(TradeSignalModel)
            if conditions:
                stmt = stmt.where(and_(*conditions))
            stmt = stmt.order_by(TradeSignalModel.created_at.desc()).limit(limit)

            result = await self.db_session.execute(stmt)
            models = result.scalars().all()
            return [self._model_to_signal(m) for m in models]

        # In-memory fallback
        signals = list(self._signals.values())
        if status:
            signals = [s for s in signals if s.status == status]
        if since:
            signals = [s for s in signals if s.timestamp >= since]
        return signals[:limit]

    async def count_signals(
        self,
        status: str | None = None,
        since: datetime | None = None,
    ) -> int:
        """
        Count signals matching filters via SELECT COUNT(*).

        Args:
            status: Filter by signal status
            since: Filter by generated_at >= since

        Returns:
            Total count of matching signals
        """
        if self.db_session is not None:
            conditions = []
            if status:
                conditions.append(TradeSignalModel.status == status)
            if since:
                conditions.append(TradeSignalModel.generated_at >= since)

            stmt = select(func.count()).select_from(TradeSignalModel)
            if conditions:
                stmt = stmt.where(and_(*conditions))

            result = await self.db_session.execute(stmt)
            return result.scalar_one()

        # In-memory fallback
        signals = list(self._signals.values())
        if status:
            signals = [s for s in signals if s.status == status]
        if since:
            signals = [s for s in signals if s.timestamp >= since]
        return len(signals)

    async def count_signals_by_symbol(
        self,
        symbol: str,
        status: str | None = None,
        since: datetime | None = None,
    ) -> int:
        """
        Count signals for a specific symbol via SELECT COUNT(*).

        Args:
            symbol: Trading symbol
            status: Filter by signal status
            since: Filter by generated_at >= since

        Returns:
            Total count of matching signals
        """
        if self.db_session is not None:
            conditions = [TradeSignalModel.symbol == symbol]
            if status:
                conditions.append(TradeSignalModel.status == status)
            if since:
                conditions.append(TradeSignalModel.generated_at >= since)

            stmt = select(func.count()).select_from(TradeSignalModel).where(and_(*conditions))

            result = await self.db_session.execute(stmt)
            return result.scalar_one()

        # In-memory fallback
        signals = [s for s in self._signals.values() if s.symbol == symbol]
        if status:
            signals = [s for s in signals if s.status == status]
        if since:
            signals = [s for s in signals if s.timestamp >= since]
        return len(signals)

    @staticmethod
    def _model_to_signal(model: TradeSignalModel) -> TradeSignal:
        """
        Convert an ORM model row back to a Pydantic TradeSignal.

        This is a lightweight conversion that reconstructs the minimal
        TradeSignal from the database columns. Some nested structures
        (validation_chain, confidence_components) are reconstructed from
        the stored approval_chain/validation_results JSON.
        """
        from decimal import Decimal

        from src.models.signal import ConfidenceComponents, TargetLevels
        from src.models.validation import ValidationChain

        # Reconstruct validation chain from stored JSON (approval_chain is canonical)
        chain_data = model.approval_chain or {}
        try:
            validation_chain = ValidationChain(**chain_data)
        except Exception:
            from uuid import uuid4

            # Fallback: create a minimal validation chain
            validation_chain = ValidationChain(
                pattern_id=model.pattern_id or uuid4(),
                validation_results=[],
                overall_status="PASS",
            )

        # Reconstruct confidence components from validation chain metadata if available
        confidence = model.confidence_score or 80
        volume_conf = confidence
        phase_conf = confidence
        pattern_conf = confidence

        # Try to extract per-stage confidence from stored validation results metadata
        for vr in chain_data.get("validation_results", []):
            meta = vr.get("metadata") or {}
            stage = vr.get("stage", "")
            if stage == "Volume" and "confidence" in meta:
                volume_conf = meta["confidence"]
            elif stage == "Phase" and "confidence" in meta:
                phase_conf = meta["confidence"]
            elif stage in ("Levels", "Strategy") and "confidence" in meta:
                pattern_conf = meta["confidence"]

        # Components not individually persisted; using overall score as approximation
        # when per-stage confidence metadata is not available in the validation chain.
        components = ConfidenceComponents(
            pattern_confidence=pattern_conf,
            phase_confidence=phase_conf,
            volume_confidence=volume_conf,
            overall_confidence=confidence,
        )

        target_1 = model.target_1 or model.entry_price
        target_2 = model.target_2

        secondary_targets = []
        if target_2 and target_2 != target_1:
            secondary_targets = [target_2]

        target_levels = TargetLevels(
            primary_target=target_1,
            secondary_targets=secondary_targets,
        )

        # Use stored pattern_type; fall back to deriving from signal_type
        if model.pattern_type:
            pattern_type = model.pattern_type
        else:
            signal_type = model.signal_type or "LONG"
            # Pre-migration fallback: LONG signals without stored pattern_type default
            # to SPRING. LPS/SOS signals created before this migration will be
            # misclassified. Acceptable for v0.1.0.
            pattern_type = "UTAD" if signal_type == "SHORT" else "SPRING"

        # Use stored phase; fall back to "C"
        phase = model.phase or "C"

        return TradeSignal(
            id=model.id,
            symbol=model.symbol,
            pattern_type=pattern_type,
            phase=phase,
            timeframe=model.timeframe or "1d",
            entry_price=model.entry_price,
            stop_loss=model.stop_loss,
            target_levels=target_levels,
            position_size=model.position_size or Decimal("100"),
            risk_amount=model.risk_amount or Decimal("0"),
            r_multiple=model.r_multiple or Decimal("2.0"),
            confidence_score=confidence,
            confidence_components=components,
            validation_chain=validation_chain,
            campaign_id=str(model.campaign_id) if model.campaign_id else None,
            status=model.status or "PENDING",
            timestamp=model.generated_at,
            created_at=model.created_at,
            notional_value=model.entry_price * (model.position_size or Decimal("100")),
        )
