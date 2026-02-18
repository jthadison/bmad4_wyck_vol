"""
Signal Approval Queue Models (Story 19.9)

Purpose:
--------
Pydantic models for the signal approval queue system that enables
manual approval workflow for trading signals.

Data Models:
------------
- QueueEntryStatus: Enum for queue entry status
- SignalQueueEntry: Complete queue entry with signal snapshot
- SignalQueueSubmission: Request model for submitting signals
- SignalApprovalRequest: Request model for approving signals
- SignalRejectionRequest: Request model for rejecting signals
- PendingSignalsResponse: Response model for listing pending signals
- SignalApprovalResult: Response model for approval/rejection result

Configuration:
--------------
- SIGNAL_APPROVAL_TIMEOUT_MINUTES: Default 5 minutes
- SIGNAL_QUEUE_MAX_SIZE: Maximum pending signals per user (default 50)

Author: Story 19.9
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class QueueEntryStatus(str, Enum):
    """Status values for signal queue entries."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class SignalQueueEntry(BaseModel):
    """
    Complete queue entry with signal data.

    Represents a signal awaiting user approval in the queue.

    Fields:
    -------
    - id: Unique queue entry identifier
    - signal_id: Reference to the original signal
    - user_id: Owner of this queue entry
    - status: Current status (pending, approved, rejected, expired)
    - submitted_at: When signal was added to queue
    - expires_at: When signal will expire if not actioned
    - approved_at: When signal was approved (if applicable)
    - approved_by: Who approved the signal (if applicable)
    - rejection_reason: Why signal was rejected (if applicable)
    - signal_snapshot: Cached signal data at submission time
    """

    id: UUID = Field(default_factory=uuid4, description="Unique queue entry ID")
    signal_id: UUID = Field(..., description="Reference to original signal")
    user_id: UUID = Field(..., description="Owner of this queue entry")
    status: QueueEntryStatus = Field(
        default=QueueEntryStatus.PENDING, description="Current queue status"
    )
    submitted_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="When signal was queued"
    )
    expires_at: datetime = Field(..., description="When signal expires")
    approved_at: datetime | None = Field(None, description="When signal was approved")
    approved_by: UUID | None = Field(None, description="Who approved the signal")
    rejection_reason: str | None = Field(None, description="Rejection reason if rejected")
    signal_snapshot: dict[str, Any] = Field(
        default_factory=dict, description="Signal data at submission time"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Record creation time"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Last update time"
    )

    @field_validator("expires_at", mode="before")
    @classmethod
    def ensure_utc_expires(cls, v: datetime | str) -> datetime:
        """Ensure expires_at is timezone-aware UTC."""
        if isinstance(v, str):
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    @property
    def time_remaining_seconds(self) -> int:
        """Calculate seconds remaining until expiration."""
        now = datetime.now(UTC)
        if self.expires_at <= now:
            return 0
        return int((self.expires_at - now).total_seconds())

    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return datetime.now(UTC) >= self.expires_at

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat(),
            UUID: str,
            Decimal: str,
        }
    }


class PendingSignalView(BaseModel):
    """
    Enriched view of a pending signal for API responses.

    Combines queue entry data with signal details for display.
    """

    queue_id: UUID = Field(..., description="Queue entry ID")
    signal_id: UUID = Field(..., description="Signal ID")
    symbol: str = Field(..., description="Trading symbol")
    pattern_type: str = Field(..., description="Wyckoff pattern type")
    confidence_score: float = Field(..., description="Signal confidence score")
    confidence_grade: str = Field(..., description="Confidence grade (A+, A, B+, etc.)")
    entry_price: Decimal = Field(..., description="Entry price")
    stop_loss: Decimal = Field(..., description="Stop loss price")
    target_price: Decimal = Field(..., description="Primary target price")
    risk_percent: float = Field(
        default=0.0, description="Risk as percentage of account (Story 23.10 AC2)"
    )
    wyckoff_phase: str = Field(default="", description="Wyckoff phase (A-E) (Story 23.10 AC2)")
    asset_class: str = Field(
        default="", description="Asset class (Stock, Forex, Index) (Story 23.10 AC2)"
    )
    submitted_at: datetime = Field(..., description="When signal was queued")
    expires_at: datetime = Field(..., description="When signal expires")
    time_remaining_seconds: int = Field(..., description="Seconds until expiration")

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat(),
            UUID: str,
            Decimal: str,
        }
    }


class SignalQueueSubmission(BaseModel):
    """
    Request model for submitting a signal to the approval queue.

    The signal_id must reference a valid, approved signal.
    """

    signal_id: UUID = Field(..., description="Signal to submit for approval")
    timeout_minutes: int = Field(
        default=5, ge=1, le=60, description="Minutes until expiration (1-60)"
    )


class SignalApprovalRequest(BaseModel):
    """
    Request model for approving a queued signal.

    Empty body - approval is a simple action.
    """

    pass


class SignalRejectionRequest(BaseModel):
    """
    Request model for rejecting a queued signal.

    Requires a reason for audit trail.
    """

    reason: str = Field(..., min_length=3, max_length=500, description="Reason for rejection")


class PendingSignalsResponse(BaseModel):
    """
    Response model for listing pending signals.

    Includes enriched signal views with time remaining.
    """

    signals: list[PendingSignalView] = Field(
        default_factory=list, description="List of pending signals"
    )
    total_count: int = Field(..., description="Total number of pending signals")


class SignalApprovalResult(BaseModel):
    """
    Response model for approval/rejection result.

    Includes execution details if approved.
    """

    status: QueueEntryStatus = Field(..., description="New queue entry status")
    approved_at: datetime | None = Field(None, description="When approved")
    rejection_reason: str | None = Field(None, description="Rejection reason if rejected")
    execution: dict[str, Any] | None = Field(
        None, description="Execution details if approved and executed"
    )
    message: str = Field(..., description="Human-readable result message")


class SignalApprovalConfig(BaseModel):
    """
    Configuration for signal approval queue.

    Can be loaded from environment or user settings.
    """

    timeout_minutes: int = Field(
        default=5, ge=1, le=60, description="Default signal expiration timeout"
    )
    max_queue_size: int = Field(
        default=50, ge=1, le=200, description="Maximum pending signals per user"
    )
    expiration_check_interval_seconds: int = Field(
        default=30, ge=5, le=300, description="How often to check for expired signals"
    )

    # Confidence grade thresholds
    grade_a_plus_threshold: int = Field(
        default=90, ge=0, le=100, description="Minimum score for A+ grade"
    )
    grade_a_threshold: int = Field(
        default=85, ge=0, le=100, description="Minimum score for A grade"
    )
    grade_b_plus_threshold: int = Field(
        default=80, ge=0, le=100, description="Minimum score for B+ grade"
    )
    grade_b_threshold: int = Field(
        default=75, ge=0, le=100, description="Minimum score for B grade"
    )

    def get_default_expiry(self) -> datetime:
        """Get default expiration datetime based on timeout."""
        return datetime.now(UTC) + timedelta(minutes=self.timeout_minutes)

    def get_confidence_grade(self, score: float) -> str:
        """
        Get confidence grade for a given score.

        Args:
            score: Confidence score (0-100)

        Returns:
            Grade string (A+, A, B+, B, or C)
        """
        if score >= self.grade_a_plus_threshold:
            return "A+"
        elif score >= self.grade_a_threshold:
            return "A"
        elif score >= self.grade_b_plus_threshold:
            return "B+"
        elif score >= self.grade_b_threshold:
            return "B"
        else:
            return "C"
