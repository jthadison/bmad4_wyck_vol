"""
Auto-Execution Models

Pydantic models for automatic signal execution engine.
Story 19.16: Auto-Execution Engine
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AutoExecutionBypassReason(str, Enum):
    """Reasons why a signal was routed to manual approval queue."""

    DISABLED = "Auto-execution disabled"
    KILL_SWITCH = "Kill switch active"
    NO_CONSENT = "Consent not given"
    CONFIDENCE_TOO_LOW = "confidence_too_low"
    PATTERN_NOT_ENABLED = "pattern_not_enabled"
    SYMBOL_NOT_IN_WHITELIST = "symbol_not_in_whitelist"
    SYMBOL_BLACKLISTED = "symbol_blacklisted"
    DAILY_TRADE_LIMIT = "daily_trade_limit_reached"
    DAILY_RISK_LIMIT = "daily_risk_limit_exceeded"


class CheckResult(BaseModel):
    """Result of a single rule check in the auto-execution chain."""

    model_config = ConfigDict(from_attributes=True)

    passed: bool = Field(..., description="Whether the check passed")
    reason: Optional[str] = Field(None, description="Reason for failure if not passed")


class AutoExecutionResult(BaseModel):
    """
    Result of auto-execution evaluation.

    Indicates whether a signal should be auto-executed or routed to manual queue.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "auto_execute": True,
                "reason": None,
                "route_to_queue": False,
                "bypass_reason": None,
            }
        },
    )

    auto_execute: bool = Field(..., description="Whether signal should be auto-executed")
    reason: Optional[str] = Field(None, description="Human-readable reason (for bypass cases)")
    route_to_queue: bool = Field(
        default=False, description="Whether to route to manual approval queue"
    )
    bypass_reason: Optional[AutoExecutionBypassReason] = Field(
        None, description="Categorized bypass reason for metrics"
    )


class ExecutionResult(BaseModel):
    """
    Result of signal auto-execution.

    Contains position details and execution metadata.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "success": True,
                "position_id": "550e8400-e29b-41d4-a716-446655440000",
                "entry_price": "150.25",
                "executed_at": "2026-01-26T10:30:00Z",
                "error": None,
            }
        },
    )

    success: bool = Field(..., description="Whether execution succeeded")
    position_id: Optional[UUID] = Field(None, description="Paper position ID if opened")
    entry_price: Optional[Decimal] = Field(None, description="Actual entry price")
    executed_at: Optional[datetime] = Field(None, description="Execution timestamp")
    error: Optional[str] = Field(None, description="Error message if failed")


class AutoExecutionAuditEntry(BaseModel):
    """
    Audit log entry for auto-execution events.

    Tracks all auto-execution decisions for compliance and debugging.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Audit entry ID")
    user_id: UUID = Field(..., description="User who owns the signal")
    signal_id: UUID = Field(..., description="Signal that was evaluated")
    symbol: str = Field(..., description="Trading symbol")
    pattern_type: str = Field(..., description="Pattern type")
    confidence_score: int = Field(..., description="Signal confidence score")
    auto_executed: bool = Field(..., description="Whether signal was auto-executed")
    bypass_reason: Optional[str] = Field(None, description="Reason if not auto-executed")
    position_id: Optional[UUID] = Field(None, description="Position ID if executed")
    risk_percentage: Decimal = Field(..., description="Risk percentage for this trade")
    trades_today_before: int = Field(..., description="Trades today before this signal")
    risk_today_before: Decimal = Field(..., description="Risk today before this signal")
    timestamp: datetime = Field(..., description="Evaluation timestamp")


class DailyCountersSnapshot(BaseModel):
    """
    Snapshot of daily auto-execution counters for a user.

    Used for tracking and displaying current limits status.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "trades_today": 3,
                "risk_today": "2.5",
                "date": "2026-01-26",
            }
        },
    )

    trades_today: int = Field(default=0, description="Number of auto-executed trades today")
    risk_today: Decimal = Field(
        default=Decimal("0.0"), description="Total risk deployed today as percentage"
    )
    date: str = Field(..., description="Date for these counters (YYYY-MM-DD)")
