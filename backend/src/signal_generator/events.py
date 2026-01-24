"""
Signal validation events for real-time signal processing.

Story 19.5: Signal Validation Pipeline Integration

This module defines events emitted during signal validation,
enabling downstream processing, audit trails, and monitoring.
"""

from __future__ import annotations

__all__ = [
    "SignalValidatedEvent",
    "SignalRejectedEvent",
    "ValidationAuditEntry",
]

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from src.models.validation import ValidationStage


class SignalValidatedEvent(BaseModel):
    """
    Event emitted when a detected pattern passes all validation stages.

    This event indicates a high-quality signal ready for trading.
    Contains all validation metadata for audit and analysis.

    Attributes:
        event_id: Unique identifier for this event
        timestamp: When validation completed (UTC)
        signal_id: Identifier for the generated signal
        pattern_id: Identifier for the pattern that was validated
        symbol: Trading symbol (e.g., "AAPL", "SPY")
        pattern_type: Type of Wyckoff pattern
        confidence: Final confidence score after validation
        validation_metadata: Detailed results from each validation stage
        audit_trail: List of validation audit entries
    """

    event_id: UUID = Field(default_factory=uuid4, description="Unique event identifier")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When validation completed (UTC)",
    )
    signal_id: UUID = Field(..., description="Generated signal identifier")
    pattern_id: UUID = Field(..., description="Pattern that was validated")
    symbol: str = Field(..., min_length=1, description="Trading symbol")
    pattern_type: str = Field(..., description="Type of Wyckoff pattern")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Final confidence score")
    validation_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed results from each validation stage",
    )
    audit_trail: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Validation audit entries",
    )

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        },
    )


class SignalRejectedEvent(BaseModel):
    """
    Event emitted when a detected pattern fails validation.

    Contains detailed rejection information for analysis and debugging.

    Attributes:
        event_id: Unique identifier for this event
        timestamp: When rejection occurred (UTC)
        pattern_id: Identifier for the rejected pattern
        symbol: Trading symbol (e.g., "AAPL", "SPY")
        pattern_type: Type of Wyckoff pattern
        rejection_stage: Validation stage where pattern failed
        rejection_reason: Human-readable explanation of why pattern was rejected
        rejection_details: Additional technical details about the failure
        audit_trail: List of validation audit entries up to rejection
    """

    event_id: UUID = Field(default_factory=uuid4, description="Unique event identifier")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When rejection occurred (UTC)",
    )
    pattern_id: UUID = Field(..., description="Rejected pattern identifier")
    symbol: str = Field(..., min_length=1, description="Trading symbol")
    pattern_type: str = Field(..., description="Type of Wyckoff pattern")
    rejection_stage: ValidationStage = Field(..., description="Stage where validation failed")
    rejection_reason: str = Field(..., description="Human-readable rejection explanation")
    rejection_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Technical details about the failure",
    )
    audit_trail: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Validation audit entries up to rejection",
    )

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        },
    )


class ValidationAuditEntry(BaseModel):
    """
    Audit entry for a single validation stage execution.

    Used to track validation decisions for compliance and debugging.

    Attributes:
        signal_id: Identifier for the signal being validated
        timestamp: When this stage was executed (UTC)
        stage: Validation stage name
        passed: Whether this stage passed validation
        reason: Explanation if stage failed or has warnings
        input_data: Pattern data at this stage
        output_data: Validation result details
    """

    signal_id: UUID = Field(..., description="Signal identifier")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Stage execution timestamp (UTC)",
    )
    stage: ValidationStage = Field(..., description="Validation stage")
    passed: bool = Field(..., description="Whether stage passed")
    reason: str | None = Field(None, description="Failure/warning explanation")
    input_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Pattern data at this stage",
    )
    output_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Validation result details",
    )

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        },
    )
