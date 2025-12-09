"""
Audit Log Models (Story 10.8)

Purpose:
--------
Pydantic models for trade audit log - searchable history of all pattern detections
(both executed signals and rejected patterns). Provides complete transparency into
the pattern detection system's decision-making process.

Data Models:
------------
- ValidationChainStep: Individual validation step with Wyckoff rule reference
- AuditLogEntry: Complete audit log entry with pattern/signal data
- AuditLogQueryParams: Query parameters for filtering/sorting/pagination
- AuditLogResponse: Paginated response with audit log entries

Features:
---------
- Wyckoff Educational Layer: Each validation step includes Wyckoff rule reference
- Complete audit trail: All pattern detections (executed and rejected)
- Filtering: Date range, symbol, pattern type, status, confidence
- Full-text search: Across symbol, pattern type, phase, status, rejection reason
- Sorting: By timestamp, symbol, pattern type, confidence, status
- Pagination: Efficient handling of large result sets

Integration:
------------
- Story 10.5: Signal status values
- Story 10.6: Pagination patterns
- Story 10.7: Rejection detail view integration
- GET /api/v1/audit-log endpoint

Author: Story 10.8
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class ValidationChainStep(BaseModel):
    """
    Individual validation step in pattern detection process.

    Each step represents a single validation rule with pass/fail status,
    explanation, and REQUIRED Wyckoff rule reference for educational layer.

    Fields:
    -------
    - step_name: Name of validation step (e.g., "Volume Validation")
    - passed: Whether validation passed (True) or failed (False)
    - reason: Explanation of why it passed/failed
    - timestamp: When validation was performed (UTC)
    - wyckoff_rule_reference: Wyckoff methodology principle (REQUIRED FOR MVP)

    Wyckoff Rule References:
    ------------------------
    Every validation step MUST map to a Wyckoff principle:
    - "Law #1: Supply & Demand" - Volume analysis, buying/selling pressure
    - "Law #2: Cause & Effect" - Campaign risk allocation, position sizing
    - "Law #3: Effort vs Result" - Spread analysis, volume-price relationships
    - "Phase Progression" - Phase identification, pattern-phase compatibility
    - "Test Principle" - Test confirmation (3-15 bars), support/resistance testing
    - "Wyckoff Schematics" - Price structure validation against schematics

    This transforms the audit log from a technical checklist into an educational tool.

    Example:
    --------
    >>> step = ValidationChainStep(
    ...     step_name="Volume Validation",
    ...     passed=True,
    ...     reason="Volume 0.65x < 0.7x threshold",
    ...     timestamp=datetime.now(UTC),
    ...     wyckoff_rule_reference="Law #1: Supply & Demand"
    ... )
    """

    step_name: str = Field(
        ..., max_length=100, description="Name of validation step", examples=["Volume Validation"]
    )
    passed: bool = Field(..., description="Whether validation passed")
    reason: str = Field(
        ...,
        max_length=500,
        description="Explanation of pass/fail",
        examples=["Volume 0.65x < 0.7x threshold"],
    )
    timestamp: datetime = Field(..., description="When validation was performed (UTC)")
    wyckoff_rule_reference: str = Field(
        ...,
        max_length=50,
        description="Wyckoff methodology principle (REQUIRED FOR MVP)",
        examples=["Law #1: Supply & Demand"],
    )

    @field_validator("timestamp", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime | str) -> datetime:
        """Enforce UTC timezone on timestamps."""
        if isinstance(v, str):
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    @field_validator("wyckoff_rule_reference")
    @classmethod
    def validate_wyckoff_rule(cls, v: str) -> str:
        """Validate that Wyckoff rule reference is one of the allowed values."""
        allowed_rules = [
            "Law #1: Supply & Demand",
            "Law #2: Cause & Effect",
            "Law #3: Effort vs Result",
            "Phase Progression",
            "Test Principle",
            "Wyckoff Schematics",
        ]
        if v not in allowed_rules:
            raise ValueError(f"wyckoff_rule_reference must be one of {allowed_rules}, got: {v}")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "step_name": "Volume Validation",
                    "passed": True,
                    "reason": "Volume 0.65x < 0.7x threshold",
                    "timestamp": "2024-03-15T14:30:00Z",
                    "wyckoff_rule_reference": "Law #1: Supply & Demand",
                }
            ]
        }
    }


class AuditLogEntry(BaseModel):
    """
    Complete audit log entry for a pattern detection.

    Aggregates data from pattern detection (Spring, SOS, etc.) and signal generation
    to provide a complete audit trail. Includes both executed signals and rejected
    patterns for full transparency.

    Core Fields (AC: 1):
    --------------------
    - id: Unique identifier (pattern_id or signal_id)
    - timestamp: Pattern detection timestamp (UTC)
    - symbol: Ticker symbol
    - pattern_type: SPRING, UTAD, SOS, LPS, SC, AR, ST
    - phase: Wyckoff phase (A, B, C, D, E)
    - confidence_score: Overall confidence (70-95)
    - status: PENDING, APPROVED, REJECTED, FILLED, STOPPED, TARGET_HIT, EXPIRED
    - rejection_reason: Why pattern rejected (None if approved/executed)

    References:
    -----------
    - signal_id: Signal UUID (None if pattern rejected before signal generation)
    - pattern_id: Pattern UUID

    Validation Details (AC: 4):
    ----------------------------
    - validation_chain: List of ValidationChainStep with Wyckoff rule references

    Pattern Metrics:
    ----------------
    - entry_price, target_price, stop_loss: Price levels
    - r_multiple: Risk/reward ratio
    - volume_ratio: Volume relative to average
    - spread_ratio: Spread relative to average

    Status Logic:
    -------------
    - If rejection_reason IS NOT NULL → Status = REJECTED
    - If signal_id IS NOT NULL → Status = from Signal.status
    - Otherwise → Status = PENDING

    Example:
    --------
    >>> entry = AuditLogEntry(
    ...     id="550e8400-e29b-41d4-a716-446655440000",
    ...     timestamp=datetime.now(UTC),
    ...     symbol="AAPL",
    ...     pattern_type="SPRING",
    ...     phase="C",
    ...     confidence_score=85,
    ...     status="FILLED",
    ...     rejection_reason=None,
    ...     signal_id="660e8400-e29b-41d4-a716-446655440001",
    ...     pattern_id="550e8400-e29b-41d4-a716-446655440000",
    ...     validation_chain=[...],
    ...     entry_price=Decimal("150.00"),
    ...     target_price=Decimal("156.00"),
    ...     stop_loss=Decimal("148.00"),
    ...     r_multiple=Decimal("3.0"),
    ...     volume_ratio=Decimal("0.65"),
    ...     spread_ratio=Decimal("0.85")
    ... )
    """

    # Core identification (AC: 1)
    id: str = Field(..., description="Unique identifier (pattern_id or signal_id)")
    timestamp: datetime = Field(..., description="Pattern detection timestamp (UTC)")
    symbol: str = Field(..., max_length=20, description="Ticker symbol", examples=["AAPL"])
    pattern_type: Literal["SPRING", "UTAD", "SOS", "LPS", "SC", "AR", "ST"] = Field(
        ..., description="Pattern type"
    )
    phase: Literal["A", "B", "C", "D", "E"] = Field(..., description="Wyckoff phase")
    confidence_score: int = Field(..., ge=70, le=95, description="Confidence score (70-95)")
    status: Literal[
        "PENDING", "APPROVED", "REJECTED", "FILLED", "STOPPED", "TARGET_HIT", "EXPIRED"
    ] = Field(..., description="Current status")
    rejection_reason: Optional[str] = Field(
        None, max_length=500, description="Why pattern rejected (if applicable)"
    )

    # References
    signal_id: Optional[str] = Field(None, description="Signal UUID (None if rejected)")
    pattern_id: str = Field(..., description="Pattern UUID")

    # Validation details (AC: 4 - for row expansion)
    validation_chain: list[ValidationChainStep] = Field(
        ..., description="Complete validation chain with Wyckoff rules"
    )

    # Pattern details (for expansion)
    entry_price: Optional[Decimal] = Field(
        None, decimal_places=8, max_digits=18, description="Entry price"
    )
    target_price: Optional[Decimal] = Field(
        None, decimal_places=8, max_digits=18, description="Target price"
    )
    stop_loss: Optional[Decimal] = Field(
        None, decimal_places=8, max_digits=18, description="Stop loss price"
    )
    r_multiple: Optional[Decimal] = Field(
        None, decimal_places=2, max_digits=10, description="Risk/reward ratio"
    )
    volume_ratio: Decimal = Field(
        ..., decimal_places=4, max_digits=10, description="Volume relative to average"
    )
    spread_ratio: Decimal = Field(
        ..., decimal_places=4, max_digits=10, description="Spread relative to average"
    )

    @field_validator("timestamp", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime | str) -> datetime:
        """Enforce UTC timezone on timestamps."""
        if isinstance(v, str):
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    model_config = {
        "json_encoders": {Decimal: str, datetime: lambda v: v.isoformat()},
        "json_schema_extra": {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "timestamp": "2024-03-15T14:30:00Z",
                    "symbol": "AAPL",
                    "pattern_type": "SPRING",
                    "phase": "C",
                    "confidence_score": 85,
                    "status": "FILLED",
                    "rejection_reason": None,
                    "signal_id": "660e8400-e29b-41d4-a716-446655440001",
                    "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
                    "validation_chain": [],
                    "entry_price": "150.00",
                    "target_price": "156.00",
                    "stop_loss": "148.00",
                    "r_multiple": "3.0",
                    "volume_ratio": "0.65",
                    "spread_ratio": "0.85",
                }
            ]
        },
    }


class AuditLogQueryParams(BaseModel):
    """
    Query parameters for audit log endpoint (AC: 9).

    Supports filtering, sorting, full-text search, and pagination.

    Filtering (AC: 2):
    ------------------
    - start_date, end_date: Date range filter
    - symbols: List of symbols to filter
    - pattern_types: List of pattern types to filter
    - statuses: List of statuses to filter
    - min_confidence, max_confidence: Confidence range filter

    Search (AC: 7):
    ---------------
    - search_text: Full-text search across symbol, pattern_type, phase, status, rejection_reason

    Sorting (AC: 3):
    ----------------
    - order_by: Column to sort by (timestamp|symbol|pattern_type|confidence|status)
    - order_direction: Sort direction (asc|desc)

    Pagination (AC: 6):
    -------------------
    - limit: Results per page (default 50, max 200)
    - offset: Starting position (default 0)

    Example:
    --------
    >>> params = AuditLogQueryParams(
    ...     start_date=datetime(2024, 3, 1, tzinfo=UTC),
    ...     end_date=datetime(2024, 3, 31, tzinfo=UTC),
    ...     symbols=["AAPL", "TSLA"],
    ...     pattern_types=["SPRING", "SOS"],
    ...     statuses=["FILLED", "TARGET_HIT"],
    ...     min_confidence=80,
    ...     max_confidence=95,
    ...     search_text="Creek",
    ...     order_by="timestamp",
    ...     order_direction="desc",
    ...     limit=50,
    ...     offset=0
    ... )
    """

    # Filtering (AC: 2)
    start_date: Optional[datetime] = Field(None, description="Filter after this date (UTC)")
    end_date: Optional[datetime] = Field(None, description="Filter before this date (UTC)")
    symbols: Optional[list[str]] = Field(None, description="Filter by symbol(s)")
    pattern_types: Optional[list[str]] = Field(None, description="Filter by pattern type(s)")
    statuses: Optional[list[str]] = Field(None, description="Filter by status(es)")
    min_confidence: Optional[int] = Field(
        None, ge=0, le=100, description="Minimum confidence score"
    )
    max_confidence: Optional[int] = Field(
        None, ge=0, le=100, description="Maximum confidence score"
    )

    # Search (AC: 7)
    search_text: Optional[str] = Field(
        None, max_length=200, description="Full-text search across fields"
    )

    # Sorting (AC: 3)
    order_by: str = Field(
        default="timestamp",
        description="Column to sort by",
        examples=["timestamp", "symbol", "pattern_type", "confidence", "status"],
    )
    order_direction: Literal["asc", "desc"] = Field(default="desc", description="Sort direction")

    # Pagination (AC: 6)
    limit: int = Field(default=50, ge=1, le=200, description="Results per page (max 200)")
    offset: int = Field(default=0, ge=0, description="Starting position")

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime | str | None) -> datetime | None:
        """Enforce UTC timezone on date filters."""
        if v is None:
            return None

        if isinstance(v, str):
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

        if isinstance(v, datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=UTC)
            return v.astimezone(UTC)

        return v

    @field_validator("order_by")
    @classmethod
    def validate_order_by(cls, v: str) -> str:
        """Validate order_by is one of allowed columns."""
        allowed_columns = ["timestamp", "symbol", "pattern_type", "confidence", "status"]
        if v not in allowed_columns:
            raise ValueError(f"order_by must be one of {allowed_columns}, got: {v}")
        return v


class AuditLogResponse(BaseModel):
    """
    Paginated response for audit log endpoint (AC: 9).

    Contains audit log entries and pagination metadata.

    Fields:
    -------
    - data: List of AuditLogEntry objects
    - total_count: Total number of results (for pagination UI)
    - limit: Results per page
    - offset: Starting position

    Example:
    --------
    >>> response = AuditLogResponse(
    ...     data=[entry1, entry2, ...],
    ...     total_count=247,
    ...     limit=50,
    ...     offset=0
    ... )
    """

    data: list[AuditLogEntry] = Field(..., description="Audit log entries")
    total_count: int = Field(..., ge=0, description="Total number of results")
    limit: int = Field(..., ge=1, le=200, description="Results per page")
    offset: int = Field(..., ge=0, description="Starting position")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "data": [],
                    "total_count": 247,
                    "limit": 50,
                    "offset": 0,
                }
            ]
        }
    }
