"""
Signal Approval Service (Story 19.9)

Business logic for signal approval queue operations.

Author: Story 19.9
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog

from src.models.signal import TradeSignal
from src.models.signal_approval import (
    PendingSignalView,
    QueueEntryStatus,
    SignalApprovalConfig,
    SignalApprovalResult,
    SignalQueueEntry,
)
from src.repositories.signal_approval_repository import SignalApprovalRepository

logger = structlog.get_logger(__name__)


class SignalApprovalService:
    """
    Service for managing signal approval queue operations.

    Handles submission, approval, rejection, and expiration of signals.
    Integrates with paper trading service for approved signal execution.
    """

    def __init__(
        self,
        repository: SignalApprovalRepository,
        config: SignalApprovalConfig | None = None,
        paper_trading_service: Any = None,
        websocket_manager: Any = None,
    ):
        """
        Initialize signal approval service.

        Args:
            repository: Repository for queue operations
            config: Optional configuration (uses defaults if not provided)
            paper_trading_service: Optional paper trading service for execution
            websocket_manager: Optional WebSocket ConnectionManager for real-time events (Story 23.10)
        """
        self.repository = repository
        self.config = config or SignalApprovalConfig()
        self.paper_trading_service = paper_trading_service
        self.websocket_manager = websocket_manager

    async def submit_signal(
        self,
        signal: TradeSignal,
        user_id: UUID,
        timeout_minutes: int | None = None,
    ) -> SignalQueueEntry:
        """
        Submit a signal to the approval queue.

        Handles queue size limits by expiring oldest signal if full.

        Args:
            signal: TradeSignal to submit
            user_id: User submitting the signal
            timeout_minutes: Optional custom timeout (uses config default if not provided)

        Returns:
            Created SignalQueueEntry
        """
        timeout = timeout_minutes or self.config.timeout_minutes
        expires_at = datetime.now(UTC) + timedelta(minutes=timeout)

        # Check queue size limit
        current_count = await self.repository.count_pending_by_user(user_id)

        if current_count >= self.config.max_queue_size:
            # Expire oldest signal to make room
            oldest = await self.repository.get_oldest_pending_by_user(user_id)
            if oldest:
                await self.repository.update_status(oldest.id, QueueEntryStatus.EXPIRED)
                logger.warning(
                    "signal_queue_overflow",
                    user_id=str(user_id),
                    expired_queue_id=str(oldest.id),
                    reason="queue_full",
                )

        # Create signal snapshot for point-in-time preservation
        signal_snapshot = self._create_signal_snapshot(signal)

        entry = SignalQueueEntry(
            signal_id=signal.id,
            user_id=user_id,
            status=QueueEntryStatus.PENDING,
            expires_at=expires_at,
            signal_snapshot=signal_snapshot,
        )

        created_entry = await self.repository.create(entry)

        logger.info(
            "signal_submitted_to_queue",
            queue_id=str(created_entry.id),
            signal_id=str(signal.id),
            user_id=str(user_id),
            expires_at=expires_at.isoformat(),
        )

        # Emit WebSocket event for real-time UI update (Story 23.10)
        if self.websocket_manager:
            try:
                view = self._entry_to_view(created_entry)
                await self.websocket_manager.emit_signal_queue_added(view.model_dump(mode="json"))
            except Exception as e:
                logger.warning("websocket_emit_queue_added_failed", error=str(e))

        return created_entry

    async def approve_signal(self, queue_id: UUID, user_id: UUID) -> SignalApprovalResult:
        """
        Approve a pending signal for execution.

        Triggers paper trading execution if service is available.

        Args:
            queue_id: Queue entry UUID
            user_id: User approving the signal

        Returns:
            SignalApprovalResult with execution details
        """
        # Get entry and validate ownership
        entry = await self.repository.get_by_id(queue_id)
        if not entry:
            return SignalApprovalResult(
                status=QueueEntryStatus.PENDING,
                message="Signal not found",
            )

        if entry.user_id != user_id:
            return SignalApprovalResult(
                status=QueueEntryStatus.PENDING,
                message="Not authorized to approve this signal",
            )

        if entry.status != QueueEntryStatus.PENDING:
            return SignalApprovalResult(
                status=entry.status,
                message=f"Signal already processed: {entry.status.value}",
            )

        if entry.is_expired:
            # Auto-expire if time has passed
            await self.repository.update_status(queue_id, QueueEntryStatus.EXPIRED)
            if self.websocket_manager:
                try:
                    await self.websocket_manager.emit_signal_queue_expired(queue_id=str(queue_id))
                except Exception as e:
                    logger.warning("websocket_emit_expired_failed", error=str(e))
            return SignalApprovalResult(
                status=QueueEntryStatus.EXPIRED,
                message="Signal has expired",
            )

        # Update status to approved
        updated_entry = await self.repository.update_status(
            queue_id, QueueEntryStatus.APPROVED, approved_by=user_id
        )

        if not updated_entry:
            return SignalApprovalResult(
                status=QueueEntryStatus.PENDING,
                message="Signal already processed by another request",
            )

        # Execute via paper trading if available
        execution_result = None
        if self.paper_trading_service:
            try:
                execution_result = await self._execute_signal(entry.signal_snapshot, user_id)
            except Exception as e:
                logger.error(
                    "signal_execution_failed",
                    queue_id=str(queue_id),
                    error=str(e),
                    exc_info=True,
                )
                execution_result = {"error": str(e)}

        logger.info(
            "signal_approved",
            queue_id=str(queue_id),
            signal_id=str(entry.signal_id),
            user_id=str(user_id),
        )

        # Emit WebSocket event for real-time UI update (Story 23.10)
        if self.websocket_manager:
            try:
                await self.websocket_manager.emit_signal_queue_approved(
                    queue_id=str(queue_id),
                    signal_id=str(entry.signal_id),
                )
            except Exception as e:
                logger.warning("websocket_emit_approved_failed", error=str(e))

        return SignalApprovalResult(
            status=QueueEntryStatus.APPROVED,
            approved_at=updated_entry.approved_at,
            execution=execution_result,
            message="Signal approved and executed",
        )

    async def reject_signal(
        self, queue_id: UUID, user_id: UUID, reason: str
    ) -> SignalApprovalResult:
        """
        Reject a pending signal.

        Args:
            queue_id: Queue entry UUID
            user_id: User rejecting the signal
            reason: Reason for rejection

        Returns:
            SignalApprovalResult with rejection details
        """
        # Get entry and validate ownership
        entry = await self.repository.get_by_id(queue_id)
        if not entry:
            return SignalApprovalResult(
                status=QueueEntryStatus.PENDING,
                message="Signal not found",
            )

        if entry.user_id != user_id:
            return SignalApprovalResult(
                status=QueueEntryStatus.PENDING,
                message="Not authorized to reject this signal",
            )

        if entry.status != QueueEntryStatus.PENDING:
            return SignalApprovalResult(
                status=entry.status,
                message=f"Signal already processed: {entry.status.value}",
            )

        # Update status to rejected
        updated_entry = await self.repository.update_status(
            queue_id, QueueEntryStatus.REJECTED, rejection_reason=reason
        )

        if not updated_entry:
            return SignalApprovalResult(
                status=QueueEntryStatus.PENDING,
                message="Signal already processed by another request",
            )

        logger.info(
            "signal_rejected",
            queue_id=str(queue_id),
            signal_id=str(entry.signal_id),
            user_id=str(user_id),
            reason=reason,
        )

        # Emit WebSocket event for real-time UI update (Story 23.10)
        if self.websocket_manager:
            try:
                await self.websocket_manager.emit_signal_queue_rejected(
                    queue_id=str(queue_id),
                    signal_id=str(entry.signal_id),
                    reason=reason,
                )
            except Exception as e:
                logger.warning("websocket_emit_rejected_failed", error=str(e))

        return SignalApprovalResult(
            status=QueueEntryStatus.REJECTED,
            rejection_reason=reason,
            message="Signal rejected",
        )

    async def get_pending_signals(self, user_id: UUID) -> list[PendingSignalView]:
        """
        Get all pending signals for a user.

        Returns enriched views with calculated time remaining.

        Args:
            user_id: User UUID

        Returns:
            List of PendingSignalView objects
        """
        # Batch expire stale entries first to avoid N+1 updates in the loop
        await self.repository.expire_stale_entries()

        # Now fetch only non-expired pending entries
        entries = await self.repository.get_pending_by_user(user_id)

        views = [self._entry_to_view(entry) for entry in entries]
        return views

    async def expire_stale_signals(self) -> int:
        """
        Mark all expired pending signals as expired.

        Called by background task at regular intervals.
        Emits WebSocket events for each expired signal for real-time UI updates.

        Returns:
            Number of signals expired
        """
        # Fetch stale entries before bulk expiration to get IDs for WS events
        stale_entries = await self.repository.get_stale_pending_entries()

        expired_count = await self.repository.expire_stale_entries()

        if expired_count > 0:
            logger.info("stale_signals_expired", count=expired_count)

            if self.websocket_manager:
                for stale_entry in stale_entries:
                    try:
                        await self.websocket_manager.emit_signal_queue_expired(
                            queue_id=str(stale_entry.id)
                        )
                    except Exception as e:
                        logger.warning(
                            "websocket_emit_expired_failed",
                            queue_id=str(stale_entry.id),
                            error=str(e),
                        )

        return expired_count

    def _create_signal_snapshot(self, signal: TradeSignal) -> dict[str, Any]:
        """
        Create a snapshot of signal data at submission time.

        Args:
            signal: TradeSignal to snapshot

        Returns:
            Dictionary with essential signal fields
        """
        return {
            "id": str(signal.id),
            "symbol": signal.symbol,
            "pattern_type": signal.pattern_type,
            "phase": signal.phase,
            "timeframe": signal.timeframe,
            "asset_class": signal.asset_class,
            "entry_price": str(signal.entry_price),
            "stop_loss": str(signal.stop_loss),
            "target_price": str(signal.target_levels.primary_target),
            "position_size": str(signal.position_size),
            "position_size_unit": signal.position_size_unit,
            "risk_amount": str(signal.risk_amount),
            "r_multiple": str(signal.r_multiple),
            "confidence_score": signal.confidence_score,
            "timestamp": signal.timestamp.isoformat(),
        }

    def _entry_to_view(self, entry: SignalQueueEntry) -> PendingSignalView:
        """
        Convert queue entry to pending signal view.

        Args:
            entry: SignalQueueEntry to convert

        Returns:
            PendingSignalView with enriched data
        """
        snapshot = entry.signal_snapshot

        # Calculate confidence grade from score using config thresholds
        score = snapshot.get("confidence_score", 0)
        grade = self.config.get_confidence_grade(score)

        # Extract dollar risk amount from snapshot
        risk_amount = 0.0
        try:
            raw = snapshot.get("risk_amount")
            if raw:
                risk_amount = float(raw)
        except (ValueError, TypeError, ArithmeticError):
            pass

        return PendingSignalView(
            queue_id=entry.id,
            signal_id=entry.signal_id,
            symbol=snapshot.get("symbol", ""),
            pattern_type=snapshot.get("pattern_type", ""),
            confidence_score=float(score),
            confidence_grade=grade,
            entry_price=Decimal(snapshot.get("entry_price", "0")),
            stop_loss=Decimal(snapshot.get("stop_loss", "0")),
            target_price=Decimal(snapshot.get("target_price", "0")),
            risk_amount=risk_amount,
            wyckoff_phase=snapshot.get("phase", ""),
            asset_class=snapshot.get("asset_class", ""),
            submitted_at=entry.submitted_at,
            expires_at=entry.expires_at,
            time_remaining_seconds=entry.time_remaining_seconds,
        )

    async def _execute_signal(
        self, signal_snapshot: dict[str, Any], user_id: UUID
    ) -> dict[str, Any]:
        """
        Execute approved signal via paper trading service.

        Args:
            signal_snapshot: Signal data from queue entry
            user_id: User who approved the signal

        Returns:
            Execution result with position details
        """
        if not self.paper_trading_service:
            return {"message": "Paper trading service not available"}

        # Get current market price (would come from market data service)
        # For now, use entry price as execution price
        entry_price = Decimal(signal_snapshot.get("entry_price", "0"))

        # The paper trading service expects a TradeSignal
        # In a full implementation, we'd reconstruct it from snapshot
        # For now, return a placeholder execution result
        return {
            "position_id": None,
            "entry_price": str(entry_price),
            "shares": signal_snapshot.get("position_size"),
            "executed_at": datetime.now(UTC).isoformat(),
            "message": "Execution placeholder - integrate with paper trading service",
        }
