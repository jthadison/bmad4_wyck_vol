"""
Signal Audit Service (Story 19.11)

Business logic for signal audit trail and lifecycle management.
Handles state transitions, audit logging, and history queries.

Author: Story 19.11
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import structlog

from src.models.signal_audit import (
    SignalAuditLogEntry,
    SignalHistoryQuery,
    SignalHistoryResponse,
    SignalLifecycleState,
    TradeOutcome,
    ValidationResults,
)
from src.repositories.signal_audit_repository import SignalAuditRepository

logger = structlog.get_logger(__name__)


class SignalAuditService:
    """
    Service for managing signal audit trail and lifecycle.

    Provides high-level operations for:
    - Recording signal lifecycle transitions
    - Storing validation results
    - Linking trade outcomes
    - Querying signal history
    """

    def __init__(self, repository: SignalAuditRepository):
        """
        Initialize signal audit service.

        Args:
            repository: Repository for audit operations
        """
        self.repository = repository

    async def record_state_transition(
        self,
        signal_id: UUID,
        new_state: SignalLifecycleState,
        previous_state: SignalLifecycleState | None = None,
        user_id: UUID | None = None,
        transition_reason: str | None = None,
        metadata: dict | None = None,
    ) -> SignalAuditLogEntry:
        """
        Record a signal lifecycle state transition.

        Creates an audit log entry and updates the signal's current state.

        Args:
            signal_id: Signal UUID
            new_state: New lifecycle state
            previous_state: Previous lifecycle state (None for initial)
            user_id: User who triggered transition (None for system)
            transition_reason: Why transition occurred
            metadata: Additional context data

        Returns:
            Created SignalAuditLogEntry
        """
        # Create audit entry
        entry = SignalAuditLogEntry(
            id=uuid4(),
            signal_id=signal_id,
            user_id=user_id,
            previous_state=previous_state.value if previous_state else None,
            new_state=new_state.value,
            transition_reason=transition_reason,
            metadata=metadata or {},
            created_at=datetime.now(UTC),
        )

        # Save audit entry
        created_entry = await self.repository.create_audit_entry(entry)

        # Update signal's lifecycle state
        await self.repository.update_signal_lifecycle_state(signal_id, new_state.value)

        logger.info(
            "signal_state_transition_recorded",
            signal_id=str(signal_id),
            transition=f"{previous_state.value if previous_state else None} -> {new_state.value}",
            user_id=str(user_id) if user_id else "system",
        )

        return created_entry

    async def record_signal_generated(
        self,
        signal_id: UUID,
        pattern_type: str,
        confidence_score: float,
        metadata: dict | None = None,
    ) -> SignalAuditLogEntry:
        """
        Record signal generation (initial state).

        Convenience method for the most common state transition.

        Args:
            signal_id: Signal UUID
            pattern_type: Pattern type (SPRING, SOS, etc.)
            confidence_score: Signal confidence score
            metadata: Additional context

        Returns:
            Created SignalAuditLogEntry
        """
        transition_reason = (
            f"{pattern_type} pattern detected with {confidence_score:.1f}% confidence"
        )

        return await self.record_state_transition(
            signal_id=signal_id,
            new_state=SignalLifecycleState.GENERATED,
            previous_state=None,
            user_id=None,  # System-generated
            transition_reason=transition_reason,
            metadata=metadata or {"pattern_type": pattern_type, "confidence": confidence_score},
        )

    async def record_signal_pending(
        self,
        signal_id: UUID,
        metadata: dict | None = None,
    ) -> SignalAuditLogEntry:
        """
        Record signal moved to pending approval queue.

        Args:
            signal_id: Signal UUID
            metadata: Additional context

        Returns:
            Created SignalAuditLogEntry
        """
        return await self.record_state_transition(
            signal_id=signal_id,
            new_state=SignalLifecycleState.PENDING,
            previous_state=SignalLifecycleState.GENERATED,
            user_id=None,
            transition_reason="Signal added to approval queue",
            metadata=metadata,
        )

    async def record_signal_approved(
        self,
        signal_id: UUID,
        user_id: UUID,
        metadata: dict | None = None,
    ) -> SignalAuditLogEntry:
        """
        Record signal approval by user.

        Args:
            signal_id: Signal UUID
            user_id: User who approved
            metadata: Additional context

        Returns:
            Created SignalAuditLogEntry
        """
        return await self.record_state_transition(
            signal_id=signal_id,
            new_state=SignalLifecycleState.APPROVED,
            previous_state=SignalLifecycleState.PENDING,
            user_id=user_id,
            transition_reason="User approved signal",
            metadata=metadata,
        )

    async def record_signal_rejected(
        self,
        signal_id: UUID,
        user_id: UUID,
        rejection_reason: str,
        metadata: dict | None = None,
    ) -> SignalAuditLogEntry:
        """
        Record signal rejection by user.

        Args:
            signal_id: Signal UUID
            user_id: User who rejected
            rejection_reason: Why signal was rejected
            metadata: Additional context

        Returns:
            Created SignalAuditLogEntry
        """
        return await self.record_state_transition(
            signal_id=signal_id,
            new_state=SignalLifecycleState.REJECTED,
            previous_state=SignalLifecycleState.PENDING,
            user_id=user_id,
            transition_reason=rejection_reason,
            metadata=metadata,
        )

    async def record_signal_expired(
        self,
        signal_id: UUID,
        metadata: dict | None = None,
    ) -> SignalAuditLogEntry:
        """
        Record signal expiration (timeout).

        Args:
            signal_id: Signal UUID
            metadata: Additional context

        Returns:
            Created SignalAuditLogEntry
        """
        return await self.record_state_transition(
            signal_id=signal_id,
            new_state=SignalLifecycleState.EXPIRED,
            previous_state=SignalLifecycleState.PENDING,
            user_id=None,
            transition_reason="Signal approval timeout exceeded",
            metadata=metadata,
        )

    async def record_signal_executed(
        self,
        signal_id: UUID,
        position_id: UUID,
        entry_price: float,
        metadata: dict | None = None,
    ) -> SignalAuditLogEntry:
        """
        Record signal execution (position opened).

        Args:
            signal_id: Signal UUID
            position_id: Paper trading position ID
            entry_price: Actual entry price filled
            metadata: Additional context

        Returns:
            Created SignalAuditLogEntry
        """
        execution_metadata = metadata or {}
        execution_metadata.update({"position_id": str(position_id), "entry_price": entry_price})

        return await self.record_state_transition(
            signal_id=signal_id,
            new_state=SignalLifecycleState.EXECUTED,
            previous_state=SignalLifecycleState.APPROVED,
            user_id=None,
            transition_reason=f"Position opened at ${entry_price:.2f}",
            metadata=execution_metadata,
        )

    async def record_signal_closed(
        self,
        signal_id: UUID,
        trade_outcome: TradeOutcome,
        metadata: dict | None = None,
    ) -> SignalAuditLogEntry:
        """
        Record signal closure (position closed).

        Updates signal with trade outcome data.

        Args:
            signal_id: Signal UUID
            trade_outcome: Complete trade outcome with P&L
            metadata: Additional context

        Returns:
            Created SignalAuditLogEntry
        """
        # Update trade outcome in signal table
        # Serialize to JSON-compatible dict
        trade_outcome_dict = trade_outcome.model_dump(mode="json")
        await self.repository.update_signal_trade_outcome(signal_id, trade_outcome_dict)

        # Build transition reason
        if trade_outcome.exit_reason:
            reason = f"Position closed: {trade_outcome.exit_reason}"
        else:
            reason = "Position closed"

        if trade_outcome.pnl_dollars:
            sign = "+" if trade_outcome.pnl_dollars > 0 else ""
            reason += f" ({sign}${trade_outcome.pnl_dollars:.2f})"

        return await self.record_state_transition(
            signal_id=signal_id,
            new_state=SignalLifecycleState.CLOSED,
            previous_state=SignalLifecycleState.EXECUTED,
            user_id=None,
            transition_reason=reason,
            metadata=metadata,
        )

    async def record_signal_cancelled(
        self,
        signal_id: UUID,
        cancellation_reason: str,
        metadata: dict | None = None,
    ) -> SignalAuditLogEntry:
        """
        Record signal cancellation (system cancelled).

        Args:
            signal_id: Signal UUID
            cancellation_reason: Why signal was cancelled
            metadata: Additional context

        Returns:
            Created SignalAuditLogEntry
        """
        return await self.record_state_transition(
            signal_id=signal_id,
            new_state=SignalLifecycleState.CANCELLED,
            previous_state=None,  # Can be cancelled from any state
            user_id=None,
            transition_reason=cancellation_reason,
            metadata=metadata,
        )

    async def store_validation_results(
        self,
        signal_id: UUID,
        validation_results: ValidationResults,
    ) -> None:
        """
        Store validation chain results for a signal.

        Args:
            signal_id: Signal UUID
            validation_results: Complete validation results
        """
        # Serialize to JSON-compatible dict
        validation_dict = validation_results.model_dump(mode="json")
        await self.repository.update_signal_validation_results(signal_id, validation_dict)

        logger.info(
            "validation_results_stored",
            signal_id=str(signal_id),
            overall_passed=validation_results.overall_passed,
            rejection_stage=validation_results.rejection_stage,
        )

    async def get_signal_audit_trail(self, signal_id: UUID) -> list[SignalAuditLogEntry]:
        """
        Get complete audit trail for a signal.

        Args:
            signal_id: Signal UUID

        Returns:
            List of audit entries in chronological order
        """
        return await self.repository.get_signal_audit_trail(signal_id)

    async def query_signal_history(self, query: SignalHistoryQuery) -> SignalHistoryResponse:
        """
        Query signal history with filters and pagination.

        Args:
            query: Query filters and pagination parameters

        Returns:
            SignalHistoryResponse with signals and pagination metadata
        """
        return await self.repository.query_signal_history(query)
