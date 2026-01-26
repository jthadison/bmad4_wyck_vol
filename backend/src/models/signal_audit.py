"""
Signal Audit Trail Models (Story 19.11)

Purpose:
--------
Provides Pydantic models for comprehensive signal lifecycle tracking and audit trail.
Tracks signals from generation through execution and closure with full history.

Data Models:
------------
- SignalLifecycleState: Enum of valid lifecycle states
- ValidationStageResult: Individual validation stage result
- ValidationResults: Complete 5-stage validation chain results
- TradeOutcome: P&L and metrics when position closes
- SignalAuditLogEntry: Single state transition record
- SignalAuditLog: Complete audit trail for a signal
- SignalHistoryQuery: Query filters for signal history
- SignalHistoryResponse: Paginated signal history response

Features:
---------
- Complete lifecycle tracking: generated → pending → approved → executed → closed
- Validation results persistence: All 5 stages with input/output data
- Trade outcome linking: Entry/exit prices, P&L, R-multiple
- Queryable history: Date range, symbol, pattern type, status filters
- Pagination support: For large result sets

Integration:
------------
- Story 19.9: Signal approval queue
- Story 10.8: Existing audit log system
- Story 12.8: Paper trading service for outcomes

Author: Story 19.11
"""

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class SignalLifecycleState(str, Enum):
    """
    Valid lifecycle states for signals.

    State Transitions:
    ------------------
    generated → pending → approved → executed → closed
                      ↓
                  rejected
                  expired
                  cancelled

    States:
    -------
    - GENERATED: Pattern detected, signal created
    - PENDING: In approval queue awaiting user action
    - APPROVED: User approved, ready for execution
    - REJECTED: User rejected signal
    - EXPIRED: Approval timeout exceeded
    - EXECUTED: Position opened in paper trading
    - CLOSED: Position closed with outcome
    - CANCELLED: System cancelled (duplicate, error, etc.)
    """

    GENERATED = "generated"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    EXECUTED = "executed"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class ValidationStageResult(BaseModel):
    """
    Result from a single validation stage.

    Contains input data, output data, pass/fail status, and timestamp
    for one stage of the 5-stage validation pipeline.

    Fields:
    -------
    - stage: Stage name (Volume, Phase, Level, Risk, Strategy)
    - passed: Whether stage passed validation
    - input_data: Input parameters to validator
    - output_data: Output from validator
    - timestamp: When validation executed
    """

    stage: str = Field(..., description="Validation stage name")
    passed: bool = Field(..., description="Whether stage passed")
    input_data: dict[str, Any] = Field(..., description="Input to validator")
    output_data: dict[str, Any] = Field(..., description="Output from validator")
    timestamp: datetime = Field(..., description="Validation execution time (UTC)")

    @field_validator("timestamp", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime | str) -> datetime:
        """Enforce UTC timezone."""
        if isinstance(v, str):
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


class ValidationResults(BaseModel):
    """
    Complete validation chain results for a signal.

    Contains results from all 5 validation stages plus overall status
    and rejection details if applicable.

    Fields:
    -------
    - volume_validation: Wayne's volume analysis result
    - phase_validation: Philip's phase classification result
    - level_validation: Sam's level mapping result
    - risk_validation: Rachel's risk management result
    - strategy_validation: William's strategy validation result
    - overall_passed: True if all stages passed
    - rejection_stage: Which stage failed (if any)
    - rejection_reason: Why validation failed (if any)

    Example:
    --------
    >>> results = ValidationResults(
    ...     volume_validation=ValidationStageResult(...),
    ...     phase_validation=ValidationStageResult(...),
    ...     level_validation=ValidationStageResult(...),
    ...     risk_validation=ValidationStageResult(...),
    ...     strategy_validation=ValidationStageResult(...),
    ...     overall_passed=True,
    ...     rejection_stage=None,
    ...     rejection_reason=None
    ... )
    """

    volume_validation: ValidationStageResult = Field(..., description="Wayne (Volume) result")
    phase_validation: ValidationStageResult = Field(..., description="Philip (Phase) result")
    level_validation: ValidationStageResult = Field(..., description="Sam (Level) result")
    risk_validation: ValidationStageResult = Field(..., description="Rachel (Risk) result")
    strategy_validation: ValidationStageResult = Field(..., description="William (Strategy) result")
    overall_passed: bool = Field(..., description="All stages passed")
    rejection_stage: str | None = Field(None, description="Stage that failed (if any)")
    rejection_reason: str | None = Field(None, description="Why failed (if any)")

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


class TradeOutcome(BaseModel):
    """
    Trade outcome when position closes.

    Linked to signals when position closes via paper trading service.
    Contains entry/exit data, P&L calculations, and exit reason.

    Fields:
    -------
    - position_id: ID from paper trading service
    - entry_price: Actual entry price filled
    - entry_time: When position opened
    - exit_price: Actual exit price filled (None if open)
    - exit_time: When position closed (None if open)
    - shares: Number of shares/lots traded
    - pnl_dollars: Profit/loss in dollars (None if open)
    - pnl_percentage: Profit/loss percentage (None if open)
    - r_multiple: Risk multiples achieved (None if open)
    - exit_reason: Why position closed (target, stop_loss, manual, etc.)

    Example:
    --------
    >>> outcome = TradeOutcome(
    ...     position_id=UUID("..."),
    ...     entry_price=Decimal("150.25"),
    ...     entry_time=datetime.now(UTC),
    ...     exit_price=Decimal("152.10"),
    ...     exit_time=datetime.now(UTC),
    ...     shares=100,
    ...     pnl_dollars=Decimal("185.00"),
    ...     pnl_percentage=1.23,
    ...     r_multiple=2.47,
    ...     exit_reason="target_hit"
    ... )
    """

    position_id: UUID = Field(..., description="Position ID from paper trading")
    entry_price: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Actual entry price"
    )
    entry_time: datetime = Field(..., description="Position open time (UTC)")
    exit_price: Decimal | None = Field(
        None, decimal_places=8, max_digits=18, description="Actual exit price"
    )
    exit_time: datetime | None = Field(None, description="Position close time (UTC)")
    shares: int = Field(..., ge=1, description="Number of shares/lots")
    pnl_dollars: Decimal | None = Field(None, description="Profit/loss in dollars")
    pnl_percentage: float | None = Field(None, description="Profit/loss percentage")
    r_multiple: float | None = Field(None, description="Risk multiples achieved")
    exit_reason: str | None = Field(
        None, description="Exit reason (target_hit, stop_loss, manual, etc.)"
    )

    @field_validator("entry_time", "exit_time", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime | str | None) -> datetime | None:
        """Enforce UTC timezone."""
        if v is None:
            return None
        if isinstance(v, str):
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    model_config = {"json_encoders": {Decimal: str, datetime: lambda v: v.isoformat()}}


class SignalAuditLogEntry(BaseModel):
    """
    Single state transition in signal audit trail.

    Records one state change with timestamp, user (if applicable),
    transition reason, and metadata.

    Fields:
    -------
    - id: Unique entry ID
    - signal_id: Signal being tracked
    - user_id: User who triggered transition (None for system)
    - previous_state: State before transition (None for initial)
    - new_state: State after transition
    - transition_reason: Why transition occurred
    - metadata: Additional context data
    - created_at: When transition occurred

    Example:
    --------
    >>> entry = SignalAuditLogEntry(
    ...     signal_id=UUID("..."),
    ...     user_id=UUID("..."),
    ...     previous_state="pending",
    ...     new_state="approved",
    ...     transition_reason="User approved signal",
    ...     metadata={"approval_method": "web_ui"}
    ... )
    """

    id: UUID = Field(default_factory=uuid4, description="Unique entry ID")
    signal_id: UUID = Field(..., description="Signal being tracked")
    user_id: UUID | None = Field(None, description="User who triggered (None for system)")
    previous_state: str | None = Field(None, description="State before transition")
    new_state: str = Field(..., description="State after transition")
    transition_reason: str | None = Field(None, description="Why transition occurred")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional context")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Transition timestamp (UTC)"
    )

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime | str) -> datetime:
        """Enforce UTC timezone."""
        if isinstance(v, str):
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


class SignalAuditLog(BaseModel):
    """
    Complete audit trail for a signal.

    Contains the signal ID and all state transition entries
    in chronological order.

    Fields:
    -------
    - signal_id: Signal being tracked
    - audit_entries: List of all state transitions (chronological)

    Example:
    --------
    >>> audit_log = SignalAuditLog(
    ...     signal_id=UUID("..."),
    ...     audit_entries=[entry1, entry2, entry3]
    ... )
    """

    signal_id: UUID = Field(..., description="Signal being tracked")
    audit_entries: list[SignalAuditLogEntry] = Field(
        default_factory=list, description="State transitions (chronological)"
    )

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


class SignalHistoryQuery(BaseModel):
    """
    Query filters for signal history endpoint.

    Supports filtering by date range, symbol, pattern type,
    and lifecycle status with pagination.

    Fields:
    -------
    - start_date: Filter start (inclusive)
    - end_date: Filter end (inclusive)
    - symbol: Filter by symbol (exact match)
    - pattern_type: Filter by pattern (SPRING, SOS, etc.)
    - status: Filter by lifecycle state
    - page: Page number (1-indexed)
    - page_size: Items per page

    Example:
    --------
    >>> query = SignalHistoryQuery(
    ...     start_date=datetime(2026, 1, 15, tzinfo=UTC),
    ...     end_date=datetime(2026, 1, 20, tzinfo=UTC),
    ...     symbol="AAPL",
    ...     pattern_type="SPRING",
    ...     status="executed",
    ...     page=1,
    ...     page_size=50
    ... )
    """

    start_date: datetime | None = Field(None, description="Filter start (inclusive)")
    end_date: datetime | None = Field(None, description="Filter end (inclusive)")
    symbol: str | None = Field(None, max_length=20, description="Filter by symbol")
    pattern_type: str | None = Field(None, description="Filter by pattern type")
    status: str | None = Field(None, description="Filter by lifecycle state")
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=50, ge=1, le=200, description="Items per page")

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime | str | None) -> datetime | None:
        """Enforce UTC timezone."""
        if v is None:
            return None
        if isinstance(v, str):
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


class PaginationMetadata(BaseModel):
    """Pagination metadata for responses."""

    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_items: int = Field(..., description="Total matching items")
    total_pages: int = Field(..., description="Total pages")


class SignalHistoryItem(BaseModel):
    """Single signal in history response."""

    signal_id: UUID = Field(..., description="Signal ID")
    symbol: str = Field(..., description="Trading symbol")
    pattern_type: str = Field(..., description="Pattern type")
    confidence_score: float = Field(..., description="Confidence score")
    lifecycle_state: str = Field(..., description="Current lifecycle state")
    created_at: datetime = Field(..., description="Creation timestamp")
    validation_results: ValidationResults | None = Field(None, description="Validation results")
    trade_outcome: TradeOutcome | None = Field(None, description="Trade outcome if closed")
    audit_trail: list[SignalAuditLogEntry] = Field(..., description="State transition history")

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime | str) -> datetime:
        """Enforce UTC timezone."""
        if isinstance(v, str):
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


class SignalHistoryResponse(BaseModel):
    """
    Paginated signal history response.

    Contains list of signals matching query filters plus
    pagination metadata.

    Fields:
    -------
    - signals: List of matching signals
    - pagination: Pagination metadata

    Example:
    --------
    >>> response = SignalHistoryResponse(
    ...     signals=[signal1, signal2, ...],
    ...     pagination=PaginationMetadata(
    ...         page=1, page_size=50, total_items=156, total_pages=4
    ...     )
    ... )
    """

    signals: list[SignalHistoryItem] = Field(..., description="Matching signals")
    pagination: PaginationMetadata = Field(..., description="Pagination info")

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}
