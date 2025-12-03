"""
Rejection Repository - RejectedSignal Logging (Story 8.10)

Purpose:
--------
Repository for logging and querying RejectedSignal objects with detailed
validation failure reasons.

Features:
---------
- Log rejected signals with full validation chain
- Query rejections by symbol, stage, date range
- Analytics: Top rejection reasons, rejection rates by stage

Integration:
------------
- Story 8.8: RejectedSignal model
- Story 8.10: MasterOrchestrator rejection logging

Author: Story 8.10
"""

from collections import defaultdict
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog

from src.models.signal import RejectedSignal


class RejectionRepository:
    """
    Repository for RejectedSignal logging and analytics.

    Provides methods to log and analyze rejected trade signals.
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
        self._rejections: dict[UUID, RejectedSignal] = {}

    async def log_rejection(self, rejection: RejectedSignal) -> RejectedSignal:
        """
        Log a RejectedSignal to the database.

        Args:
            rejection: RejectedSignal to log

        Returns:
            Logged RejectedSignal with populated ID
        """
        self.logger.info(
            "log_rejection",
            rejection_id=str(rejection.id),
            symbol=rejection.symbol,
            pattern_type=rejection.pattern_type,
            rejection_stage=rejection.rejection_stage,
            rejection_reason=rejection.rejection_reason,
        )

        # Stub implementation - store in memory
        self._rejections[rejection.id] = rejection

        # In real implementation, would save to database:
        # db_rejection = RejectedSignalModel(**rejection.model_dump())
        # self.db_session.add(db_rejection)
        # await self.db_session.commit()

        return rejection

    async def get_rejection_by_id(self, rejection_id: UUID) -> RejectedSignal | None:
        """
        Retrieve rejection by ID.

        Args:
            rejection_id: Rejection UUID

        Returns:
            RejectedSignal if found, None otherwise
        """
        return self._rejections.get(rejection_id)

    async def get_rejections_by_symbol(
        self,
        symbol: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        stage: str | None = None,
    ) -> list[RejectedSignal]:
        """
        Query rejections by symbol with optional filters.

        Args:
            symbol: Trading symbol
            start_date: Filter by timestamp >= start_date
            end_date: Filter by timestamp <= end_date
            stage: Filter by rejection_stage

        Returns:
            List of matching RejectedSignals
        """
        rejections = [r for r in self._rejections.values() if r.symbol == symbol]

        if start_date:
            rejections = [r for r in rejections if r.timestamp >= start_date]
        if end_date:
            rejections = [r for r in rejections if r.timestamp <= end_date]
        if stage:
            rejections = [r for r in rejections if r.rejection_stage == stage]

        return rejections

    async def get_rejections_by_stage(self, stage: str, limit: int = 50) -> list[RejectedSignal]:
        """
        Get recent rejections for a specific validation stage.

        Args:
            stage: Validation stage name (e.g., "Volume", "Risk")
            limit: Maximum number of rejections to return

        Returns:
            List of RejectedSignals from that stage
        """
        rejections = [r for r in self._rejections.values() if r.rejection_stage == stage]
        # Sort by timestamp descending (most recent first)
        rejections.sort(key=lambda r: r.timestamp, reverse=True)
        return rejections[:limit]

    async def get_top_rejection_reasons(self, limit: int = 10) -> list[tuple[str, int]]:
        """
        Get top rejection reasons by count (analytics).

        Args:
            limit: Number of top reasons to return

        Returns:
            List of (reason, count) tuples sorted by count descending
        """
        reason_counts: dict[str, int] = defaultdict(int)

        for rejection in self._rejections.values():
            reason_counts[rejection.rejection_reason] += 1

        # Sort by count descending
        sorted_reasons = sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_reasons[:limit]

    async def get_rejection_rate_by_stage(self) -> dict[str, int]:
        """
        Get rejection counts grouped by validation stage (analytics).

        Returns:
            Dict mapping stage name to rejection count
        """
        stage_counts: dict[str, int] = defaultdict(int)

        for rejection in self._rejections.values():
            stage_counts[rejection.rejection_stage] += 1

        return dict(stage_counts)

    async def get_all_rejections(self, limit: int = 100) -> list[RejectedSignal]:
        """
        Get all rejections (for testing/debugging).

        Args:
            limit: Maximum number of rejections to return

        Returns:
            List of RejectedSignals
        """
        rejections = list(self._rejections.values())
        rejections.sort(key=lambda r: r.timestamp, reverse=True)
        return rejections[:limit]
