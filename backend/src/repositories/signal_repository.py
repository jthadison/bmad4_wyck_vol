"""
Signal Repository - TradeSignal Persistence (Story 8.10)

Purpose:
--------
Repository for persisting and querying TradeSignal objects.

Features:
---------
- Save approved signals
- Query signals by symbol, date range, status
- Update signal status (FILLED, STOPPED, TARGET_HIT, etc.)

Integration:
------------
- Story 8.8: TradeSignal model
- Story 8.10: MasterOrchestrator persistence

Author: Story 8.10
"""

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog

from src.models.signal import TradeSignal


class SignalRepository:
    """
    Repository for TradeSignal persistence.

    Provides methods to save and query trade signals.
    """

    def __init__(self, db_session: Any = None):
        """
        Initialize repository with database session.

        Args:
            db_session: SQLAlchemy async session (optional, stub for now)
        """
        self.db_session = db_session
        self.logger = structlog.get_logger(__name__)
        # In-memory storage for stub implementation
        self._signals: dict[UUID, TradeSignal] = {}

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

        # Stub implementation - store in memory
        self._signals[signal.id] = signal

        # In real implementation, would save to database:
        # db_signal = TradeSignalModel(**signal.model_dump())
        # self.db_session.add(db_signal)
        # await self.db_session.commit()
        # await self.db_session.refresh(db_signal)

        return signal

    async def get_signal_by_id(self, signal_id: UUID) -> TradeSignal | None:
        """
        Retrieve signal by ID.

        Args:
            signal_id: Signal UUID

        Returns:
            TradeSignal if found, None otherwise
        """
        return self._signals.get(signal_id)

    async def get_signals_by_symbol(
        self,
        symbol: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        status: str | None = None,
    ) -> list[TradeSignal]:
        """
        Query signals by symbol with optional filters.

        Args:
            symbol: Trading symbol
            start_date: Filter by timestamp >= start_date
            end_date: Filter by timestamp <= end_date
            status: Filter by signal status

        Returns:
            List of matching TradeSignals
        """
        signals = [s for s in self._signals.values() if s.symbol == symbol]

        if start_date:
            signals = [s for s in signals if s.timestamp >= start_date]
        if end_date:
            signals = [s for s in signals if s.timestamp <= end_date]
        if status:
            signals = [s for s in signals if s.status == status]

        return signals

    async def update_signal_status(
        self,
        signal_id: UUID,
        new_status: str,
    ) -> TradeSignal | None:
        """
        Update signal status (e.g., PENDING → FILLED).

        Args:
            signal_id: Signal UUID
            new_status: New status value

        Returns:
            Updated TradeSignal if found, None otherwise
        """
        signal = self._signals.get(signal_id)
        if signal:
            # Create updated signal with new status
            updated_data = signal.model_dump()
            updated_data["status"] = new_status
            updated_signal = TradeSignal(**updated_data)
            self._signals[signal_id] = updated_signal
            return updated_signal

        return None

    async def get_all_signals(self, limit: int = 100) -> list[TradeSignal]:
        """
        Get all signals (for testing/debugging).

        Args:
            limit: Maximum number of signals to return

        Returns:
            List of TradeSignals
        """
        return list(self._signals.values())[:limit]
