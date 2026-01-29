"""
Circuit Breaker Models (Story 19.21)

Pydantic models for circuit breaker API responses.

Author: Story 19.21
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, auto-execution active
    OPEN = "open"  # Triggered, auto-execution paused


class CircuitBreakerStatusResponse(BaseModel):
    """
    API response for circuit breaker status.

    GET /api/v1/settings/circuit-breaker
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "state": "open",
                "consecutive_losses": 3,
                "threshold": 3,
                "triggered_at": "2026-01-23T14:30:00Z",
                "resets_at": "2026-01-24T05:00:00Z",
                "can_reset": True,
            }
        }
    )

    state: CircuitBreakerState = Field(
        description="Current circuit breaker state (closed = normal, open = paused)"
    )
    consecutive_losses: int = Field(ge=0, description="Current consecutive loss count")
    threshold: int = Field(ge=1, le=10, description="Configured threshold for triggering breaker")
    triggered_at: datetime | None = Field(
        default=None, description="Timestamp when breaker was triggered (if open)"
    )
    resets_at: datetime | None = Field(
        default=None, description="Timestamp of next automatic reset at midnight ET (if open)"
    )
    can_reset: bool = Field(default=True, description="Whether user can manually reset the breaker")


class CircuitBreakerResetResponse(BaseModel):
    """
    API response after circuit breaker reset.

    POST /api/v1/settings/circuit-breaker/reset
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "state": "closed",
                "consecutive_losses": 0,
                "reset_at": "2026-01-23T15:00:00Z",
                "message": "Circuit breaker reset successfully",
            }
        }
    )

    state: CircuitBreakerState = Field(
        default=CircuitBreakerState.CLOSED, description="State after reset (should be closed)"
    )
    consecutive_losses: int = Field(
        default=0, description="Consecutive losses after reset (should be 0)"
    )
    reset_at: datetime = Field(description="Timestamp of reset")
    message: str = Field(default="Circuit breaker reset successfully", description="Status message")
